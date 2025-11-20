# exporter_litematic.py
"""
Export a voxel grid to a Litematica .litematic file using litemapy.

Expected input:
    block_ids_3d: numpy array of shape (W, H, D)
                  entries are either None or 'minecraft:block_name' strings.

We create a single Region at origin (0,0,0) with size (W,H,D),
leave unspecified cells as air, and save as a valid .litematic.
"""

import os
import numpy as np
from litemapy import Region, BlockState


def export_litematic(block_ids_3d, path, name="scan2schem", author="scan2schem", description="Generated from mesh"):
    """
    Write a .litematic file.

    Args:
        block_ids_3d: np.ndarray, shape (W, H, D), dtype=object
                      values: None or 'minecraft:block_name'
        path: output file path (will be created, dirs too)
        name: schematic name (shown in Litematica UI)
        author: author string
        description: description string

    Returns:
        (abs_path, file_size_bytes)
    """
    # Normalize path and ensure parent directory exists
    path = os.path.abspath(os.path.expanduser(path))
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if not isinstance(block_ids_3d, np.ndarray):
        block_ids_3d = np.asarray(block_ids_3d, dtype=object)

    W, H, D = block_ids_3d.shape

    # Create one Region at origin with full size
    # Region(origin_x, origin_y, origin_z, width, height, length)
    region = Region(0, 0, 0, W, H, D)

    # Fill blocks: leave None as air (default), set everything else
    # Coordinate order matches how you built block_grid: (x, y, z)
    for x in range(W):
        for y in range(H):
            for z in range(D):
                bid = block_ids_3d[x, y, z]
                if bid is None:
                    continue  # remains air
                # bid should be like 'minecraft:white_concrete'
                region.setblock(x, y, z, BlockState(str(bid)))

    # Turn region into a schematic and save
    schematic = region.as_schematic(
        name=name,
        author=author,
        description=description
    )

    schematic.save(path)
    size = os.path.getsize(path)
    return path, size
