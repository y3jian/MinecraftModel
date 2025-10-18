# exporter_schematic.py
import os
import numpy as np
import nbtlib
from nbtlib import Compound, List
from nbtlib.tag import Short, String, ByteArray, Int

COLOR_INDEX = {
    "white": 0, "orange": 1, "magenta": 2, "light_blue": 3,
    "yellow": 4, "lime": 5, "pink": 6, "gray": 7,
    "light_gray": 8, "cyan": 9, "purple": 10, "blue": 11,
    "brown": 12, "green": 13, "red": 14, "black": 15
}

def _name_to_legacy(block_name: str):
    if block_name is None:
        return (0, 0)  # air
    b = block_name.replace("minecraft:", "")
    if b == "air":
        return (0, 0)
    if b.endswith("_wool"):
        color = b.replace("_wool", "")
        return (35, COLOR_INDEX.get(color, 0))
    if b.endswith("_concrete"):
        color = b.replace("_concrete", "")
        return (251, COLOR_INDEX.get(color, 0))
    if b == "stone":
        return (1, 0)
    if b.endswith("_planks"):
        species = {"oak":0,"spruce":1,"birch":2,"jungle":3,"acacia":4,"dark_oak":5}
        kind = b.replace("_planks","")
        return (5, species.get(kind, 0))
    return (1, 0)  # fallback stone

def write_schematic(block_ids_3d, path):
    """
    Write legacy MCEdit .schematic
    """
    path = os.path.abspath(os.path.expanduser(path))
    os.makedirs(os.path.dirname(path), exist_ok=True)

    W, H, D = block_ids_3d.shape
    def idx(x, y, z): return y * (W * D) + z * W + x

    total = W * H * D
    blocks = np.zeros(total, dtype=np.uint8)
    data   = np.zeros(total, dtype=np.uint8)

    for x in range(W):
        for y in range(H):
            for z in range(D):
                bid, meta = _name_to_legacy(block_ids_3d[x, y, z])
                i = idx(x, y, z)
                blocks[i] = bid & 0xFF
                data[i]   = meta & 0x0F

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
