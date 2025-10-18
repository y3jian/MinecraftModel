import os
import argparse
import numpy as np
import trimesh

from colour_mapper import BlockPalette
from exporter_schem import write_schem
from exporter_schematic import write_schematic

print("CWD:", os.getcwd())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", required=True, help="path to OBJ/PLY/GLB")
    ap.add_argument("--palette", default="palettes/wool_concrete.json")
    ap.add_argument("--height", type=int, default=64, help="target height in blocks")
    ap.add_argument("--min_component", type=int, default=50, help="drop tiny floating parts (#voxels)")
    ap.add_argument("--out", default="scan.schem")
    args = ap.parse_args()

    mesh = trimesh.load(args.mesh, force='mesh')
    mesh.remove_unreferenced_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())

    # scale to target height & center
    size = (mesh.bounds[1] - mesh.bounds[0]).max()
    scale = args.height / size
    mesh.apply_scale(scale)
    mesh.apply_translation(-mesh.bounds.mean(axis=0))

    # voxelize (solid)
    pitch = mesh.extents.max() / args.height
    vox = mesh.voxelized(pitch=pitch).fill()
    coords = vox.points

    # per-voxel color (vertex-color fallback)
    if mesh.visual.kind == "vertex" and getattr(mesh.visual, "vertex_colors", None) is not None:
        try:
            from trimesh.kdtree import KDTree
            kdt = KDTree(mesh.vertices)
            _, idx = kdt.query(coords)
        except Exception:
            from scipy.spatial import cKDTree
            kdt = cKDTree(mesh.vertices)
            dist, idx = kdt.query(coords)
        colors = mesh.visual.vertex_colors[idx][:, :3].astype(np.float32)
    else:
        colors = np.full((coords.shape[0], 3), 190, dtype=np.float32)

    # integer grid coords starting at 0,0,0
    ci = np.floor(coords - coords.min(axis=0)).astype(int)
    W, H, D = (ci[:, 0].max() + 1, ci[:, 1].max() + 1, ci[:, 2].max() + 1)

    # occupancy for flood fill
    occ = -np.ones((W, H, D), dtype=np.int32)
    for i, (x, y, z) in enumerate(ci):
        occ[x, y, z] = i

    # prune tiny components
    from collections import deque
    label = np.full(ci.shape[0], -1, dtype=int)
    dirs = [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]
    comp_id = 0
    for i, (x, y, z) in enumerate(ci):
        if label[i] != -1:
            continue
        q, members = deque([(x, y, z)]), []
        while q:
            a, b, c = q.popleft()
            idx = occ[a, b, c]
            if idx == -1 or label[idx] != -1:
                continue
            label[idx] = comp_id
            members.append(idx)
            for dx, dy, dz in dirs:
                na, nb, nc = a + dx, b + dy, c + dz
                if 0 <= na < W and 0 <= nb < H and 0 <= nc < D and occ[na, nb, nc] != -1:
                    if label[occ[na, nb, nc]] == -1:
                        q.append((na, nb, nc))
        if len(members) < args.min_component:
            for m in members:
                occ[tuple(ci[m])] = -1
                label[m] = -1
        else:
            comp_id += 1

    keep = label != -1
    if not np.any(keep):
        raise SystemExit("Nothing left after pruning; try lowering --min_component")

    ci = ci[keep]
    colors = colors[keep]

    # map to blocks
    pal = BlockPalette(args.palette)
    block_grid = np.empty((W, H, D), dtype=object)
    for (x, y, z), col in zip(ci, colors):
        block_grid[x, y, z] = pal.nearest(col)

    out_abs = os.path.abspath(os.path.expanduser(args.out))
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)

    if out_abs.lower().endswith(".schematic"):
        out_path, out_size = write_schematic(block_grid, out_abs)
    else:
        out_path, out_size = write_schem(block_grid, out_abs)

    print(f"Saved {out_path}  (bytes: {out_size})")
if __name__ == "__main__":
    main()
