# exporter_litematic.py
import os
from litemapy import Schematic, Region, BlockState  # pip install litemapy

def write_litematic(block_ids_3d, path, name="scan2schem", author="you", desc="Generated from voxel grid"):
    """
    block_ids_3d: np.ndarray (W,H,D) of either None or 'minecraft:block' strings.
    path: output .litematic file path
    """
    path = os.path.abspath(os.path.expanduser(path))
    os.makedirs(os.path.dirname(path), exist_ok=True)

    W, H, D = block_ids_3d.shape

    # Create one region at the schematic origin (0,0,0) sized to the grid
    reg = Region(0, 0, 0, W, H, D)

    # Set blocks (skip None -> leaves air)
    # NOTE: Region coords are x,y,z with 0..W-1 etc., same order we used
    # Just iterate over the grid and set non-air blocks
    for x in range(W):
        for y in range(H):
            for z in range(D):
                bid = block_ids_3d[x, y, z]
                if bid:  # not None
                    reg.setblock(x, y, z, BlockState(bid))

    # Wrap region into a schematic and save
    schem = reg.as_schematic(name=name, author=author, description=desc)
    schem.save(path)  # writes a valid .litematic file
    return path, os.path.getsize(path)
