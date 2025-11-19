import os
from litemapy import Schematic, Region, BlockState

# --- Output folder ---
out_path = os.path.abspath("data/examples/my_build.litematic")
os.makedirs(os.path.dirname(out_path), exist_ok=True)

# Create region size 5x5x5 at origin
reg = Region(0, 0, 0, 5, 5, 5)

# Fill with white concrete
for x in range(5):
    for y in range(5):
        for z in range(5):
            reg.setblock(x, y, z, BlockState("minecraft:white_concrete"))

# Wrap in a schematic and save
schem = reg.as_schematic(
    name="MyStructure",
    author="Me",
    description="Generated with Python"
)

schem.save(out_path)

print("Saved:", out_path)