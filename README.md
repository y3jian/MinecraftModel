## Scan2Craft 
 I wanted to honour my favourite Hello Kitty stuffed animal in my Minecraft world with a GIANT statue, but didn't want to spend hours building it. 
 Scan2Craft is a Python pipeline that converts real-life scans (GLB/OBJ/PLY) into Minecraft .litematic structures.

# How it Works
Scan2Craft takes an input 3D scan, voxelizes a mesh, samples texture colours, maps colours to a customizable block palette, and exports a Litematica schematic ready to be used in Minecraft!

# Example
![alt text](image.png)

# Installation
```bash
pip install -r requirements.txt
```

# Usage
```bash
python scan2schem.py \
  --mesh data/scans/helloKitty.glb \
  --height 48 \
  --out data/examples/helloKitty.litematic
```

# Tech
Python, NumPy, Trimesh, scikit-image, litemapy