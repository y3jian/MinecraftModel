# verify_schem.py
import sys, os
import nbtlib

path = sys.argv[1] if len(sys.argv) > 1 else "data/examples/helloKitty.schem"
path = os.path.abspath(path)
print("CHECKING:", path)

schem = nbtlib.load(path)
if "Schematic" not in schem:
    raise SystemExit("Not a Sponge v2 schematic (missing root 'Schematic').")

root = schem["Schematic"]
W, H, L = int(root["Width"]), int(root["Height"]), int(root["Length"])
ver = int(root["Version"])
dver = int(root["DataVersion"])
palette = root["Palette"]
blockdata = root["BlockData"]

print(f"Version: {ver}  DataVersion: {dver}")
print(f"Dimensions: {W} x {H} x {L}  (volume: {W*H*L})")
print(f"Palette size: {len(palette)}  Keys: sample =", list(palette.keys())[:5])
print(f"BlockData length (bytes): {len(blockdata)}")

# Convert BlockData (ByteArray) back to int16 palette indices
import numpy as np
bd = np.frombuffer(blockdata, dtype=np.int8).astype(np.int16)  # WE v2 stores 16-bit per index, but our writer used int16->bytes
# If your writer used int16.view(int8), the length in bytes should be 2*(W*H*L)
# Confirm expected size:
expected_bytes = 2 * W * H * L
print("Expected BlockData bytes:", expected_bytes)
if len(blockdata) != expected_bytes:
    print("!! Mismatch: BlockData size does not equal 2*W*H*L. Your exporter may be wrong.")

# Reconstruct int16 values correctly
bd16 = np.frombuffer(blockdata, dtype=np.int16, count=W*H*L)

# Validate indices are within palette range
max_idx = int(bd16.max()) if bd16.size else -1
min_idx = int(bd16.min()) if bd16.size else -1
print(f"Palette index range in BlockData: [{min_idx}, {max_idx}] (PaletteMax={len(palette)})")
if max_idx >= len(palette) or min_idx < 0:
    print("!! ERROR: BlockData contains indices outside the Palette. This will fail to load.")

# Check for 'air' presence and count non-air blocks
air_key = None
for k,v in palette.items():
    if k.endswith(":air"):
        air_key = k
        air_id = int(v)
        break

if air_key is None:
    print("!! WARNING: 'minecraft:air' is NOT in your palette.")
    # Count nonzero indices as “filled”, but note 0 might be the first real block if air is missing
    approx_filled = int(np.count_nonzero(bd16))
    print(f"Approx. filled voxels (nonzero indices): {approx_filled} / {W*H*L}")
else:
    filled = int(np.count_nonzero(bd16 != air_id))
    print(f"'air' palette id: {air_id}  |  Filled voxels: {filled} / {W*H*L}")

print("OK ✓ if: Version=2, sizes match, indices within [0, PaletteMax-1], and air exists (preferably id 0).")
