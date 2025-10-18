# test_schematic.py
import os, numpy as np
import nbtlib
from nbtlib import Compound, List
from nbtlib.tag import Short, String, ByteArray, Int

def make_test_schematic(path):
    """
    Make a 3x3x3 stone cube with an air block in the center.
    Exports as legacy MCEdit .schematic
    """
    W, H, D = 3, 3, 3

    def idx(x, y, z): return y * (W * D) + z * W + x

    total = W * H * D
    blocks = np.full(total, 1, dtype=np.uint8)   # stone = id 1
    data   = np.zeros(total, dtype=np.uint8)     # meta = 0

    # set center block to air (id 0)
    cx, cy, cz = 1, 1, 1
    blocks[idx(cx, cy, cz)] = 0

    root = Compound({
        "Width":  Short(W),
        "Height": Short(H),
        "Length": Short(D),
        "Materials": String("Alpha"),
        "Blocks": ByteArray(blocks.tolist()),
        "Data":   ByteArray(data.tolist()),
        "Entities": List[Compound]([]),
        "TileEntities": List[Compound]([]),
        "WEOffsetX": Int(0),
        "WEOffsetY": Int(0),
        "WEOffsetZ": Int(0),
    })

    file = nbtlib.File(root, root_name="Schematic")
    file.save(path)
    return path, os.path.getsize(path)

if __name__ == "__main__":
    out = os.path.abspath("air_test.schematic")
    p, size = make_test_schematic(out)
    print(f"Saved {p} ({size} bytes)")
