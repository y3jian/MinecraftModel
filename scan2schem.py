#!/usr/bin/env python3
# scan2schem.py
# Convert a 3D mesh (OBJ/PLY/GLB) to a Minecraft structure by voxelizing and mapping to blocks,
# then export as either .schem (Sponge v2) or .schematic (MCEdit legacy) based on the --out extension.

import os
import argparse
import numpy as np
import trimesh

from colour_mapper import BlockPalette
from exporter_schem import write_schem
from exporter_schematic import write_schematic


def voxelize_mesh(mesh_path: str, target_height: int, min_component: int):
    """
    Load mesh, normalize size, voxelize (solid), prune tiny components.
    Returns:
        block_coords: (N, 3) int voxel coordinates within [0..W-1], [0..H-1], [0..D-1]
        block_colors: (N, 3) uint8 colors per occupied voxel
        grid_shape:   (W, H, D)
    """
    mesh = trimesh.load(mesh_path, force='mesh')

    # Clean up faces/verts (API-safe)
    mesh.remove_unreferenced_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())

    # Normalize scale to target height and center on origin
    size = (mesh.bounds[1] - mesh.bounds[0]).max()
    if size <= 0:
        raise SystemExit("Mesh has zero size after loading. Check your file.")
    scale = float(target_height) / float(size)
    mesh.apply_scale(scale)
    mesh.apply_translation(-mesh.bounds.mean(axis=0))

    # Voxelize with pitch such that max extent ~ target_height
    pitch = mesh.extents.max() / float(target_height)
    vox = mesh.voxelized(pitch=pitch).fill()

    # Voxel centers (float), then integerize to a 0-based grid
    coords_f = vox.points  # (N,3) float
    if coords_f.size == 0:
        raise SystemExit("Voxelization produced no voxels. Try increasing --height or check the mesh.")
    ci = np.floor(coords_f - coords_f.min(axis=0)).astype(int)

    W = int(ci[:, 0].max() + 1)
    H = int(ci[:, 1].max() + 1)
    D = int(ci[:, 2].max() + 1)

    # Simple per-voxel color: nearest vertex color if present; otherwise mid-gray
    if mesh.visual.kind == "vertex" and getattr(mesh.visual, "vertex_colors", None) is not None:
        # Try trimesh KDTree, fall back to scipy if needed
        try:
            from trimesh.kdtree import KDTree
            kdt = KDTree(mesh.vertices)
            _, nn_idx = kdt.query(coords_f)
        except Exception:
            try:
                from scipy.spatial import cKDTree
                kdt = cKDTree(mesh.vertices)
                _, nn_idx = kdt.query(coords_f)
            except Exception:
                nn_idx = None
        if nn_idx is not None:
            vcols = mesh.visual.vertex_colors[:, :3].astype(np.float32)
            colors = vcols[nn_idx]
        else:
            colors = np.full((ci.shape[0], 3), 190, dtype=np.float32)
    else:
        colors = np.full((ci.shape[0], 3), 190, dtype=np.float32)

    # Prune tiny floating components using 6-neighborhood flood fill on the occupancy grid
    occ = -np.ones((W, H, D), dtype=np.int32)
    for i, (x, y, z) in enumerate(ci):
        occ[x, y, z] = i

    from collections import deque
    label = np.full(ci.shape[0], -1, dtype=int)
    dirs = [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]
    comp_id = 0
    for i, (x, y, z) in enumerate(ci):
        if label[i] != -1:
            continue
        q = deque([(x, y, z)])
        members = []
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
        # prune small components
        if len(members) < int(min_component):
            for m in members:
                occ[tuple(ci[m])] = -1
                label[m] = -1
        else:
            comp_id += 1

    keep = label != -1
    if not np.any(keep):
        raise SystemExit("Nothing left after pruning; try lowering --min_component.")

    return ci[keep], colors[keep].astype(np.float32), (W, H, D)


def build_block_grid(coords_i, colors, grid_shape, palette_path):
    """
    Map per-voxel colors to Minecraft block names and fill a sparse 3D grid.
    Returns:
        block_grid: np.ndarray (W,H,D) of object dtype; entries are None or 'minecraft:block_name'
    """
    W, H, D = grid_shape
    pal = BlockPalette(palette_path)

    block_grid = np.empty((W, H, D), dtype=object)
    # Only set occupied voxels; unassigned cells remain None (treated as air by exporters)
    for (x, y, z), col in zip(coords_i, colors):
        block_grid[x, y, z] = pal.nearest(col)

    return block_grid


def main():
    ap = argparse.ArgumentParser(description="Voxelize a mesh and export to Minecraft schematic.")
    ap.add_argument("--mesh", required=True, help="Path to OBJ/PLY/GLB mesh")
    ap.add_argument("--palette", default="palettes/wool_concrete.json", help="Path to block palette JSON")
    ap.add_argument("--height", type=int, default=64, help="Target model height in blocks")
    ap.add_argument("--min_component", type=int, default=50, help="Prune components smaller than this many voxels")
    ap.add_argument("--out", default="scan.schem", help="Output file (.schem for Sponge v2, .schematic for MCEdit)")
    args = ap.parse_args()

    # Resolve output path and ensure parent folder exists
    out_abs = os.path.abspath(os.path.expanduser(args.out))
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)

    print("CWD:", os.getcwd())
    print("Input mesh:", os.path.abspath(args.mesh))
    print("Palette:", os.path.abspath(args.palette))
    print("Output:", out_abs)

    # Voxelize, color, prune
    coords_i, colors, grid_shape = voxelize_mesh(args.mesh, args.height, args.min_component)
    W, H, D = grid_shape
    print(f"Grid: {W} x {H} x {D} | occupied voxels: {len(coords_i)}")

    # Map to blocks and build sparse grid
    block_grid = build_block_grid(coords_i, colors, grid_shape, args.palette)

    # Pick exporter by extension
    if out_abs.lower().endswith(".schematic"):
        out_path, out_size = write_schematic(block_grid, out_abs)
        fmt = "MCEdit .schematic"
    else:
        out_path, out_size = write_schem(block_grid, out_abs)  # Sponge v2
        fmt = "Sponge .schem"

    print(f"Saved ({fmt}): {out_path}  (bytes: {out_size})")
    print(f"Done. Tip: paste WITHOUT '-a' to ensure air is placed (or use Amulet to import into a world).")


if __name__ == "__main__":
    main()
