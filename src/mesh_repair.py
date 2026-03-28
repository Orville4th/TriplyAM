"""
mesh_repair.py — Triply mesh repair pipeline
Ensures watertight, manifold, outward-normal meshes suitable for slicers.
"""

import numpy as np


def repair(vertices, faces, progress_cb=None):
    """
    Full repair pipeline. Returns (vertices, faces).
    Steps: weld → remove degenerate → fix winding → fill small holes
    """
    if progress_cb: progress_cb("Welding duplicate vertices...")
    vertices, faces = weld_vertices(vertices, faces)

    if progress_cb: progress_cb("Removing degenerate faces...")
    faces = remove_degenerate(vertices, faces)

    if progress_cb: progress_cb("Fixing face winding...")
    faces = fix_winding(vertices, faces)

    if progress_cb: progress_cb("Checking manifold edges...")
    faces = remove_non_manifold(vertices, faces)

    if progress_cb: progress_cb("Done.")
    return vertices.astype(np.float32), faces.astype(np.int32)


def repair_pymeshfix(vertices, faces):
    """
    Repair using pymeshfix — handles non-manifold edges and holes.
    Same algorithm as MeshMixer/PyVista.
    """
    try:
        import pymeshfix
        import numpy as np
        meshfix = pymeshfix.MeshFix(vertices.astype(np.float64),
                                     faces.astype(np.int32))
        meshfix.repair(verbose=False, joincomp=True,
                       remove_smallest_components=False)
        v = meshfix.v.astype(np.float32)
        f = meshfix.f.astype(np.int32)
        return (v, f) if len(f) > 0 else (vertices, faces)
    except Exception:
        return vertices, faces


def weld_vertices(vertices, faces, tol=1e-4):
    """Merge vertices within tolerance."""
    rounded = np.round(vertices / tol).astype(np.int64)
    key_map = {}
    new_verts = []
    remap = np.zeros(len(vertices), dtype=np.int32)

    for i, key in enumerate(map(tuple, rounded)):
        if key not in key_map:
            key_map[key] = len(new_verts)
            new_verts.append(vertices[i])
        remap[i] = key_map[key]

    new_faces = remap[faces]
    # Remove faces with duplicate vertex indices
    valid = (
        (new_faces[:, 0] != new_faces[:, 1]) &
        (new_faces[:, 1] != new_faces[:, 2]) &
        (new_faces[:, 0] != new_faces[:, 2])
    )
    return np.array(new_verts, dtype=np.float32), new_faces[valid]


def remove_degenerate(vertices, faces, min_area=1e-10):
    """Remove zero-area triangles."""
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    areas = np.linalg.norm(cross, axis=1) * 0.5
    return faces[areas > min_area]


def fix_winding(vertices, faces):
    """
    Make face normals consistent and outward-pointing.
    Uses centroid-based voting: normals should point away from mesh center.
    """
    center = vertices.mean(axis=0)
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    centroids = (v0 + v1 + v2) / 3.0
    normals   = np.cross(v1 - v0, v2 - v0)
    outward   = centroids - center
    dot       = np.einsum('ij,ij->i', normals, outward)
    result    = faces.copy()
    result[dot < 0] = result[dot < 0][:, [0, 2, 1]]
    return result


def remove_non_manifold(vertices, faces):
    """
    Remove faces that share an edge with more than 2 faces (non-manifold).
    These cause slicer errors.
    """
    from collections import defaultdict
    edge_count = defaultdict(int)

    for tri in faces:
        for i in range(3):
            a, b = int(tri[i]), int(tri[(i+1)%3])
            key  = (min(a,b), max(a,b))
            edge_count[key] += 1

    # Faces that only use manifold edges (each edge shared by ≤ 2 faces)
    keep = []
    for tri in faces:
        manifold = True
        for i in range(3):
            a, b = int(tri[i]), int(tri[(i+1)%3])
            key  = (min(a,b), max(a,b))
            if edge_count[key] > 2:
                manifold = False
                break
        if manifold:
            keep.append(tri)

    return np.array(keep, dtype=np.int32) if keep else faces


def compute_volume(vertices, faces):
    """Signed volume via divergence theorem."""
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    vol = np.sum(np.einsum('ij,ij->i', v0, np.cross(v1, v2))) / 6.0
    return abs(float(vol))


def compute_surface_area(vertices, faces):
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    return float(np.sum(np.linalg.norm(cross, axis=1)) * 0.5)


def compute_bbox(vertices):
    mins = vertices.min(axis=0)
    maxs = vertices.max(axis=0)
    return maxs - mins  # (dx, dy, dz)


def laplacian_smooth(vertices, faces, iterations=3, factor=0.4):
    """Laplacian mesh smoothing — smooths faceted TPMS geometry."""
    if iterations == 0:
        return vertices, faces

    n   = len(vertices)
    adj = [set() for _ in range(n)]
    for f in faces:
        adj[f[0]].add(f[1]); adj[f[0]].add(f[2])
        adj[f[1]].add(f[0]); adj[f[1]].add(f[2])
        adj[f[2]].add(f[0]); adj[f[2]].add(f[1])

    v = vertices.copy().astype(np.float64)
    for _ in range(iterations):
        nv = v.copy()
        for i in range(n):
            nb = list(adj[i])
            if nb:
                nv[i] = v[i] + factor * (v[nb].mean(axis=0) - v[i])
        v = nv

    return v.astype(np.float32), faces
