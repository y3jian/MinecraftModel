# scan2schem.py
# Convert a 3D mesh (OBJ/PLY/GLB) to a Minecraft structure by voxelizing and mapping to blocks,
# then export as .litematic file to be used with Litematica.

import sys, os
import argparse
import numpy as np
import trimesh


from colour_mapper import BlockPalette
from litemapy import Region, BlockState
from exporter_litematic import export_litematic

sys.path.insert(0, os.path.dirname(__file__))

def voxelize_mesh(mesh_path: str, target_height: int, min_component: int):
    """
    Load mesh, normalize size, voxelize (solid), prune tiny components.
    Returns:
        block_coords: (N, 3) int voxel coordinates (x,y,z)
        block_colors: (N, 3) RGB
        grid_shape:   (W, H, D)
    """
    mesh = trimesh.load(mesh_path, force='mesh')
    print("Using vertex colors:", hasattr(mesh.visual, "vertex_colors") and mesh.visual.vertex_colors is not None)

    # Clean up mesh
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
    colors = None

    # 1) Vertex colors
    if mesh.visual.kind == "vertex" and getattr(mesh.visual, "vertex_colors", None) is not None:
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

    # 2) Texture sampling (UVs + baseColorTexture)
    if colors is None and mesh.visual.kind == "texture":
        has_uv = getattr(mesh.visual, "uv", None) is not None
        has_tex = getattr(mesh.visual, "material", None) is not None and \
                  getattr(mesh.visual.material, "baseColorTexture", None) is not None
        if has_uv and has_tex:
            # nearest vertex for each voxel
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
                uv = mesh.visual.uv[nn_idx]  # (N,2), in [0,1]
                tex_img = mesh.visual.material.baseColorTexture
                tex = np.array(tex_img.convert("RGB"), dtype=np.uint8)
                h_tex, w_tex, _ = tex.shape

                # clamp uv to [0,1], flip v for image coordinates
                u = np.clip(uv[:, 0], 0.0, 1.0)
                v = np.clip(uv[:, 1], 0.0, 1.0)
                x_pix = (u * (w_tex - 1)).astype(int)
                y_pix = ((1.0 - v) * (h_tex - 1)).astype(int)

                colors = tex[y_pix, x_pix, :].astype(np.float32)

    # 3) Fallback if everything else failed
    if colors is None:
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
    ap.add_argument("--out", default="data/examples/scan.litematic",
                help="Output .litematic file for Litematica")
    args = ap.parse_args()

    out_abs = os.path.abspath(os.path.expanduser(args.out))
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)

    print("CWD:", os.getcwd())
    print("Input mesh:", os.path.abspath(args.mesh))
    print("Palette:", os.path.abspath(args.palette))
    print("Output:", out_abs)

    # Voxelize and color
    coords_i, colors, grid_shape = voxelize_mesh(args.mesh, args.height, args.min_component)
    W, H, D = grid_shape
    print(f"Grid: {W} x {H} x {D} | occupied voxels: {len(coords_i)}")

    # Color → block IDs
    block_grid = build_block_grid(coords_i, colors, grid_shape, args.palette)

    # Export as .litematic
    name = os.path.splitext(os.path.basename(args.out))[0]
    out_path, out_size = export_litematic(
        block_grid,
        out_abs,
        name,
        "scan2schem",
        "test",
    )

    print(f"Saved .litematic: {out_path}  (bytes: {out_size})")
    print("Tip: move this file to %APPDATA%\\.minecraft\\schematics and load it with Litematica.")


if __name__ == "__main__":
    main()
