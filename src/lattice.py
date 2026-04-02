"""
lattice.py — Triply V3 TPMS + Voronoi lattice generation
Hybrid pipeline:
  - MeshLib mcOffsetMesh → perfect uniform wall thickness
  - manifold3d → boolean operations
  - scikit-image marching cubes → TPMS mesh generation
  - scipy.spatial.Voronoi + cKDTree → Voronoi strut network
"""

import numpy as np
import logging
_log = logging.getLogger('triplyam')

# ── TPMS functions ─────────────────────────────────────────────────────────────

def _gyroid(x, y, z, L):
    t = 2*np.pi/L
    return np.sin(t*x)*np.cos(t*y)+np.sin(t*y)*np.cos(t*z)+np.sin(t*z)*np.cos(t*x)

def _schwarz_p(x, y, z, L):
    t = 2*np.pi/L
    return np.cos(t*x)+np.cos(t*y)+np.cos(t*z)

def _schwarz_d(x, y, z, L):
    t = 2*np.pi/L
    return (np.sin(t*x)*np.sin(t*y)*np.sin(t*z)
           +np.sin(t*x)*np.cos(t*y)*np.cos(t*z)
           +np.cos(t*x)*np.sin(t*y)*np.cos(t*z)
           +np.cos(t*x)*np.cos(t*y)*np.sin(t*z))

def _schoen_iwp(x, y, z, L):
    t = 2*np.pi/L
    return (2*(np.cos(t*x)*np.cos(t*y)+np.cos(t*y)*np.cos(t*z)+np.cos(t*z)*np.cos(t*x))
           -(np.cos(2*t*x)+np.cos(2*t*y)+np.cos(2*t*z)))

LATTICE_FNS = {
    "Gyroid":      _gyroid,
    "Schwarz P":   _schwarz_p,
    "Schwarz D":   _schwarz_d,
    "Schoen I-WP": _schoen_iwp,
}
TPMS_NAMES    = list(LATTICE_FNS.keys())
VORONOI_NAMES = ["Voronoi"]
LATTICE_NAMES = TPMS_NAMES + VORONOI_NAMES


# ── Mesh conversion helpers ────────────────────────────────────────────────────

def _to_mr(verts, faces):
    """numpy → MeshLib mesh via temp STL."""
    import meshlib.mrmeshpy as mr
    import tempfile, os
    from triply_io.exporter import export_stl
    with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as t:
        tp = t.name
    export_stl(tp, verts.astype(np.float32), faces.astype(np.int32))
    mesh = mr.loadMesh(tp)
    os.unlink(tp)
    return mesh

def _from_mr(mesh_mr):
    """MeshLib mesh → numpy directly."""
    import meshlib.mrmeshpy as mr
    nv = mesh_mr.topology.numValidVerts()
    nf = mesh_mr.topology.numValidFaces()
    verts = np.array([[mesh_mr.points[mr.VertId(i)].x,
                       mesh_mr.points[mr.VertId(i)].y,
                       mesh_mr.points[mr.VertId(i)].z]
                      for i in range(nv)], dtype=np.float32)
    faces = np.array([[mesh_mr.topology.getTriVerts(mr.FaceId(i))[j].get()
                       for j in range(3)]
                      for i in range(nf)], dtype=np.int32)
    return verts, faces

def _to_manifold(verts, faces):
    """numpy → manifold3d Manifold."""
    from manifold3d import Manifold, Mesh
    m = Mesh(vert_properties=verts.astype(np.float32),
             tri_verts=faces.astype(np.uint32))
    return Manifold(m)

def _from_manifold(mfd):
    """manifold3d Manifold → numpy."""
    r = mfd.to_mesh()
    return (np.array(r.vert_properties, dtype=np.float32),
            np.array(r.tri_verts, dtype=np.int32))

def _manifold_intersect(a, b):
    """
    Intersection of two Manifolds — compatible across manifold3d versions.
    Tries instance method (newer), class method, then ^ operator fallback
    (^ is intersection in manifold3d, not XOR).
    """
    try:
        from manifold3d import OpType
        return a.boolean(b, OpType.Intersect)
    except AttributeError:
        pass
    try:
        from manifold3d import Manifold, OpType
        return Manifold.boolean(a, b, OpType.Intersect)
    except (AttributeError, TypeError):
        pass
    return a ^ b


# ── TPMS mesh builder ──────────────────────────────────────────────────────────

def _build_tpms_mesh(mins, maxs, cell_size, infill_pct,
                     lattice_type, voxel_size, smooth_iterations=0):
    from skimage.measure import marching_cubes
    from mesh_repair import weld_vertices, remove_degenerate

    fn = LATTICE_FNS.get(lattice_type, _gyroid)

    infill = float(np.clip(infill_pct, 1.0, 99.0)) / 100.0

    pad = cell_size
    origin = mins - pad
    extent = (maxs - mins) + 2*pad

    nx = max(4, int(np.ceil(extent[0]/voxel_size)))
    ny = max(4, int(np.ceil(extent[1]/voxel_size)))
    nz = max(4, int(np.ceil(extent[2]/voxel_size)))

    xs = origin[0] + np.arange(nx)*voxel_size
    ys = origin[1] + np.arange(ny)*voxel_size
    zs = origin[2] + np.arange(nz)*voxel_size
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
    field = fn(X, Y, Z, cell_size)

    # Percentile-based isovalue: solid = field > iso_level.
    # np.percentile(field, 100-infill%) gives the exact iso so that
    # infill% of voxels are above it — works correctly for all surface
    # types (Gyroid, Schwarz P/D, Schoen I-WP) without any per-type logic.
    iso_level = float(np.percentile(field, (1.0 - infill) * 100.0))

    # sdf < 0 = solid (field > iso), sdf > 0 = void
    sdf = (iso_level - field).astype(np.float32)

    # Seal boundaries as void so marching cubes sees open space at bbox edges
    sdf[0,:,:]=sdf[-1,:,:]=sdf[:,0,:]=sdf[:,-1,:]=sdf[:,:,0]=sdf[:,:,-1]=1.0

    if sdf.min() >= 0:
        raise ValueError(
            f"Infill {infill_pct:.0f}% is too low — no lattice walls visible. "
            f"Try increasing infill above 5%."
        )
    if sdf.max() <= 0:
        raise ValueError(
            f"Infill {infill_pct:.0f}% is too high — model would be solid. "
            f"Try reducing infill below 95%."
        )

    lv, lf, _, _ = marching_cubes(sdf, level=0.0,
                                   spacing=(voxel_size, voxel_size, voxel_size))
    lv[:,0]+=origin[0]; lv[:,1]+=origin[1]; lv[:,2]+=origin[2]
    lv, lf = weld_vertices(lv.astype(np.float32), lf.astype(np.int32))
    lf = remove_degenerate(lv, lf)

    if smooth_iterations > 0:
        import pyvista as pv
        faces_pv = np.hstack([np.full((len(lf),1),3), lf]).astype(np.int32)
        mesh = pv.PolyData(lv, faces_pv)
        mesh = mesh.smooth(n_iter=int(smooth_iterations*20),
                           relaxation_factor=0.1, feature_angle=30.0)
        lv = np.array(mesh.points, dtype=np.float32)
        lf = mesh.faces.reshape(-1,4)[:,1:].astype(np.int32)

    return lv, lf


# ── Voronoi lattice builder ────────────────────────────────────────────────────

def _cylinder_mesh(p0, p1, radius, segments=8):
    """Capped cylinder between two 3D points. Low segments for fast boolean union."""
    p0 = np.array(p0, dtype=np.float64)
    p1 = np.array(p1, dtype=np.float64)
    axis = p1 - p0
    length = np.linalg.norm(axis)
    if length < 1e-6:
        return np.zeros((0,3), dtype=np.float32), np.zeros((0,3), dtype=np.int32)
    axis /= length

    perp = np.array([1.0, 0.0, 0.0])
    if abs(np.dot(axis, perp)) > 0.9:
        perp = np.array([0.0, 1.0, 0.0])
    u = np.cross(axis, perp); u /= np.linalg.norm(u)
    v = np.cross(axis, u)

    angles = np.linspace(0, 2*np.pi, segments, endpoint=False)
    ring0 = p0 + radius*(np.outer(np.cos(angles), u)+np.outer(np.sin(angles), v))
    ring1 = p1 + radius*(np.outer(np.cos(angles), u)+np.outer(np.sin(angles), v))

    verts = np.vstack([ring0, ring1, p0[None,:], p1[None,:]]).astype(np.float32)
    c0, c1 = segments*2, segments*2+1

    faces = []
    for i in range(segments):
        j = (i+1) % segments
        faces += [[i, j, segments+j], [i, segments+j, segments+i]]
        faces += [[c0, j, i], [c1, segments+i, segments+j]]

    return verts, np.array(faces, dtype=np.int32)


def _build_voronoi_mesh(mins, maxs, strut_radius, n_seeds, shell_off,
                        part_manifold, progress_cb=None):
    """
    Voronoi strut lattice clipped to part_manifold.

    shell_off=False (Shell-on):  arms reach wall naturally.
    shell_off=True  (Shell-off): + boundary nodes connected with Y-junctions.

    Key fix vs 0.3.0: edges are kept when EITHER endpoint is inside the padded
    bbox, not both — this prevents valid near-boundary edges being discarded.
    """
    from scipy.spatial import Voronoi, cKDTree

    def _prog(msg):
        if progress_cb: progress_cb(msg)

    # ── Seed points ────────────────────────────────────────────────────────────
    _prog(f"Voronoi: placing {n_seeds} seed points...")
    rng = np.random.default_rng(42)
    margin = max(strut_radius * 2, 0.5)
    safe_mins = mins + margin
    safe_maxs = maxs - margin
    for dim in range(3):
        if safe_mins[dim] >= safe_maxs[dim]:
            safe_mins[dim] = mins[dim]
            safe_maxs[dim] = maxs[dim]
    seeds = rng.uniform(safe_mins, safe_maxs,
                        size=(int(n_seeds), 3)).astype(np.float64)

    # Mirror seeds to force finite ridges at boundaries
    mirrors = []
    for dim in range(3):
        lo, hi = mins[dim], maxs[dim]
        r = seeds.copy(); r[:,dim] = 2*lo - seeds[:,dim]; mirrors.append(r)
        r = seeds.copy(); r[:,dim] = 2*hi - seeds[:,dim]; mirrors.append(r)
    all_pts = np.vstack([seeds] + mirrors)

    _prog("Voronoi: computing diagram...")
    vor = Voronoi(all_pts)
    _log.debug(f"Voronoi: {len(vor.vertices)} vertices, {len(vor.ridge_vertices)} ridges, "
               f"{len(seeds)} orig seeds, {len(all_pts)} total pts")

    # ── Extract edges ──────────────────────────────────────────────────────────
    # Keep ridges where BOTH seed points are original (index < n_orig).
    # Filter by midpoint (stray struts) and by edge length (overlong/degenerate).
    # Overlong edges create crossing struts and messy junctions; too-short edges
    # create needle geometry that manifold3d struggles to boolean correctly.
    _prog("Voronoi: extracting edges...")
    n_orig = len(seeds)
    vv = vor.vertices
    raw_edges = []
    skipped_infinite = 0
    skipped_mirror = 0
    skipped_outside = 0

    # Allow midpoints up to one strut-radius outside the bbox
    mid_pad = strut_radius
    for (s0, s1), ridge_verts in zip(vor.ridge_points, vor.ridge_vertices):
        if -1 in ridge_verts:
            skipped_infinite += 1
            continue
        if s0 >= n_orig or s1 >= n_orig:
            skipped_mirror += 1
            continue
        a, b = ridge_verts[0], ridge_verts[1]
        pa, pb = vv[a], vv[b]
        mid = (pa + pb) * 0.5
        if np.any(mid < mins - mid_pad) or np.any(mid > maxs + mid_pad):
            skipped_outside += 1
            continue
        raw_edges.append((pa, pb))

    # ── Edge-length filter ─────────────────────────────────────────────────────
    # Expected avg cell spacing based on bbox volume and seed count
    bbox_vol  = float(np.prod(maxs - mins))
    avg_spacing = (bbox_vol / max(n_seeds, 1)) ** (1.0 / 3.0)
    min_len   = strut_radius * 2.0          # shorter than diameter → degenerate
    max_len   = avg_spacing * 3.5           # longer than 3.5× cell → crossing strut

    edges = []
    skipped_len = 0
    for pa, pb in raw_edges:
        length = float(np.linalg.norm(pb - pa))
        if length < min_len or length > max_len:
            skipped_len += 1
            continue
        edges.append((pa, pb))

    _log.debug(f"Voronoi edges: {len(edges)} kept, "
               f"{skipped_infinite} infinite skipped, {skipped_mirror} mirror skipped, "
               f"{skipped_outside} outside skipped, {skipped_len} length-filtered "
               f"(min={min_len:.2f} max={max_len:.2f})")

    # ── Add bounding-box edge-frame struts ────────────────────────────────────
    # Build 12 struts along every edge of the part bbox so internal Voronoi
    # struts always terminate into a solid perimeter frame — like a carbon lattice.
    corners = np.array([[mins[0], mins[1], mins[2]],
                        [maxs[0], mins[1], mins[2]],
                        [maxs[0], maxs[1], mins[2]],
                        [mins[0], maxs[1], mins[2]],
                        [mins[0], mins[1], maxs[2]],
                        [maxs[0], mins[1], maxs[2]],
                        [maxs[0], maxs[1], maxs[2]],
                        [mins[0], maxs[1], maxs[2]]])
    bbox_edges = [(0,1),(1,2),(2,3),(3,0),   # bottom face
                  (4,5),(5,6),(6,7),(7,4),   # top face
                  (0,4),(1,5),(2,6),(3,7)]   # verticals
    frame_manifolds = []
    for i0, i1 in bbox_edges:
        cv, cf = _cylinder_mesh(corners[i0], corners[i1], strut_radius, segments=16)
        if len(cf) == 0:
            continue
        try:
            m = _to_manifold(cv, cf)
            if not m.is_empty():
                frame_manifolds.append(m)
        except Exception:
            continue
    _log.debug(f"Voronoi frame: {len(frame_manifolds)}/12 edge struts built")

    if not edges:
        _log.error(f"Voronoi: no edges found. bbox={maxs-mins}, seeds={n_seeds}, "
                   f"n_orig={n_orig}, total_ridges={len(vor.ridge_vertices)}")
        raise ValueError(
            f"Voronoi produced no valid edges — try more seeds. "
            f"(bbox: {(maxs-mins).round(1)}, seeds: {n_seeds})"
        )

    _prog(f"Voronoi: {len(edges)} edges → building cylinders...")

    # ── Build and union cylinders in batches ───────────────────────────────────
    BATCH = 64
    current_union = None
    total = len(edges)
    cyl_ok = 0
    cyl_fail = 0

    for batch_start in range(0, total, BATCH):
        batch = edges[batch_start: batch_start + BATCH]
        batch_manifolds = []
        for p0, p1 in batch:
            cv, cf = _cylinder_mesh(p0, p1, strut_radius, segments=16)
            if len(cf) == 0:
                cyl_fail += 1
                continue
            try:
                m = _to_manifold(cv, cf)
                if not m.is_empty():
                    batch_manifolds.append(m)
                    cyl_ok += 1
                else:
                    cyl_fail += 1
            except Exception as e:
                _log.debug(f"Cylinder to_manifold failed: {e}")
                cyl_fail += 1
                continue

        if not batch_manifolds:
            continue

        batch_union = batch_manifolds[0]
        for m in batch_manifolds[1:]:
            try:
                batch_union = batch_union + m
            except Exception as e:
                _log.debug(f"Batch union step failed: {e}")
                continue

        if current_union is None:
            current_union = batch_union
        else:
            try:
                current_union = current_union + batch_union
            except Exception as e:
                _log.debug(f"Running union step failed: {e}")

        pct = min(69, int(batch_start / total * 70))
        _prog(f"Voronoi: unioning cylinders... {pct}%")

    _log.debug(f"Voronoi cylinders: {cyl_ok} ok, {cyl_fail} failed, "
               f"union_empty={current_union is None or current_union.is_empty()}")

    if current_union is None or current_union.is_empty():
        raise ValueError(
            "Voronoi cylinder union is empty — try increasing strut diameter or seed count."
        )

    # ── Merge bbox edge-frame into union ──────────────────────────────────────
    if frame_manifolds:
        _prog("Voronoi: merging edge frame...")
        frame_union = frame_manifolds[0]
        for m in frame_manifolds[1:]:
            try:
                frame_union = frame_union + m
            except Exception:
                continue
        try:
            current_union = current_union + frame_union
        except Exception as e:
            _log.debug(f"Frame union merge failed: {e}")

    # ── Shell-off: Y-junction boundary connections ────────────────────────────
    if shell_off:
        _prog("Voronoi: finding boundary nodes...")
        tol = strut_radius * 3.0
        # Only consider Voronoi vertices that are inside or near the bbox
        lo_loose = mins - tol
        hi_loose = maxs + tol
        boundary_nodes = []
        for pt in vv:
            # Must be within loose bbox
            if not (np.all(pt >= lo_loose) and np.all(pt <= hi_loose)):
                continue
            # Must be near at least one face
            on_face = any(
                pt[dim] <= mins[dim] + tol or pt[dim] >= maxs[dim] - tol
                for dim in range(3)
            )
            if on_face:
                boundary_nodes.append(pt)

        if len(boundary_nodes) >= 2:
            _prog(f"Voronoi: connecting {len(boundary_nodes)} boundary nodes...")
            bn = np.array(boundary_nodes)
            tree = cKDTree(bn)
            k = min(4, len(bn))
            dists, idxs = tree.query(bn, k=k)
            YJUNC_TOL = strut_radius * 1.5
            extra = []
            for i, (row_d, row_i) in enumerate(zip(dists, idxs)):
                neighbours = [(d, j) for d, j in zip(row_d, row_i)
                              if j != i and d > 1e-6]
                if not neighbours:
                    continue
                d_near = neighbours[0][0]
                to_connect = [neighbours[0][1]]
                for d, j in neighbours[1:]:
                    if d <= d_near + YJUNC_TOL:
                        to_connect.append(j)
                for j in to_connect:
                    cv, cf = _cylinder_mesh(bn[i], bn[j], strut_radius, segments=16)
                    if len(cf) == 0:
                        continue
                    try:
                        m = _to_manifold(cv, cf)
                        if not m.is_empty():
                            extra.append(m)
                    except Exception:
                        continue

            if extra:
                _prog(f"Voronoi: adding {len(extra)} boundary connections...")
                for m in extra:
                    try:
                        current_union = current_union + m
                    except Exception:
                        continue

    # ── Clip to cavity ────────────────────────────────────────────────────────
    _prog("Voronoi: clipping to part cavity...")
    try:
        clipped = _manifold_intersect(current_union, part_manifold)
    except Exception as e:
        raise ValueError(f"Voronoi clip failed: {e}")

    if clipped.is_empty():
        raise ValueError(
            "Voronoi clipped result is empty — struts may not intersect the part. "
            "Try a larger strut diameter or more seeds."
        )

    rv, rf = _from_manifold(clipped)
    return rv.astype(np.float32), rf.astype(np.int32)


# ── Small component removal ────────────────────────────────────────────────────

def _remove_small_components(verts, faces, min_fraction=0.01):
    """Remove disconnected fragments smaller than min_fraction of largest component."""
    if len(faces) == 0:
        return verts, faces

    from collections import defaultdict, deque
    adj = defaultdict(set)
    for tri in faces:
        a, b, c = int(tri[0]), int(tri[1]), int(tri[2])
        adj[a].update([b, c])
        adj[b].update([a, c])
        adj[c].update([a, b])

    visited = np.zeros(len(verts), dtype=bool)
    components = []

    for start in range(len(verts)):
        if visited[start] or start not in adj:
            continue
        component = set()
        queue = deque([start])
        while queue:
            v = queue.popleft()
            if visited[v]: continue
            visited[v] = True
            component.add(v)
            for nb in adj[v]:
                if not visited[nb]:
                    queue.append(nb)
        if component:
            components.append(component)

    if not components:
        return verts, faces

    sizes = [len(c) for c in components]
    max_size = max(sizes)
    threshold_size = max(int(max_size * min_fraction), 10)

    keep_verts = set()
    for comp, size in zip(components, sizes):
        if size >= threshold_size:
            keep_verts.update(comp)

    keep_faces_mask = np.array([
        int(f[0]) in keep_verts and int(f[1]) in keep_verts and int(f[2]) in keep_verts
        for f in faces
    ])
    new_faces = faces[keep_faces_mask]

    used = np.zeros(len(verts), dtype=bool)
    used[new_faces.ravel()] = True
    old_to_new = np.full(len(verts), -1, dtype=np.int32)
    new_idx = np.where(used)[0]
    old_to_new[new_idx] = np.arange(len(new_idx), dtype=np.int32)

    new_verts = verts[new_idx]
    new_faces_remapped = old_to_new[new_faces]

    return new_verts.astype(np.float32), new_faces_remapped.astype(np.int32)


# ── Main pipeline ──────────────────────────────────────────────────────────────

def generate_lattice(stl_verts, wall_thickness, cell_size, infill_pct,
                     stl_faces=None, step_path=None,
                     lattice_type="Gyroid", resolution=None,
                     smooth_iterations=1, smooth_factor=0.3,
                     wall_only=False, n_seeds=300, strut_diameter=2.0,
                     progress_cb=None, cancel_flag=None):
    """
    Generate TPMS or Voronoi lattice infill with uniform shell.

    infill_pct    : 1–99%  solid volume fraction (TPMS only)
    strut_diameter: mm     strut diameter (Voronoi only)
    wall_only     : no outer shell; for Voronoi also enables shell-off mode
    n_seeds       : Voronoi seed count
    """
    import meshlib.mrmeshpy as mr
    from mesh_repair import weld_vertices, remove_degenerate
    from manifold3d import Manifold

    def _prog(msg):
        if progress_cb: progress_cb(msg)
    def _check():
        if cancel_flag and cancel_flag[0]: raise InterruptedError("Cancelled")

    is_voronoi = lattice_type == "Voronoi"

    _prog(f"Type: {lattice_type}  Wall: {wall_thickness}mm")
    _check()

    # ── Prepare part mesh ──────────────────────────────────────────────────────
    _prog("Preparing mesh...")
    if stl_faces is not None:
        sv, sf = weld_vertices(stl_verts, stl_faces, tol=0.01)
    else:
        sv = stl_verts.astype(np.float32)
        sf = np.arange(len(sv), dtype=np.int32).reshape(-1,3)
        sv, sf = weld_vertices(sv, sf, tol=0.01)
    sf = remove_degenerate(sv, sf)

    mins = sv.min(axis=0).astype(np.float64)
    maxs = sv.max(axis=0).astype(np.float64)
    span = maxs - mins
    _prog(f"Part: {len(sf)} faces, span {span.round(1)}")
    _check()

    # ── Voxel size (TPMS only) ─────────────────────────────────────────────────
    if not is_voronoi:
        if resolution is None or resolution == 0:
            wall_mm_approx = max((float(infill_pct)/100.0) * min(span) * 0.3, 0.3)
            voxel_size = float(np.clip(wall_mm_approx / 3.0, 0.05, 0.5))
        else:
            voxel_size = float(np.clip(np.max(span)/resolution, 0.05, 1.0))
        _prog(f"Voxel size: {voxel_size:.3f}mm")

    # ── Step 1: MeshLib shell offset ───────────────────────────────────────────
    wt = float(wall_thickness)
    part_mr = _to_mr(sv, sf)
    part_m  = _to_manifold(sv, sf)

    if wt > 0 and not wall_only:
        _prog(f"Computing shell offset ({wt}mm)...")
        op = mr.OffsetParameters()
        op.voxelSize = min((voxel_size if not is_voronoi else 0.2), 0.2)
        inner_mr = mr.mcOffsetMesh(mr.MeshPart(part_mr), -wt, op)
        iv, ifc = _from_mr(inner_mr)
        _prog(f"Inner cavity: {len(ifc)} faces")
        _check()

        inner_m = _to_manifold(iv, ifc)
        if inner_m.is_empty():
            inner_m = _to_manifold(iv, ifc[:,[0,2,1]].astype(np.int32))

        _prog(f"Part vol={part_m.volume():.0f}, Inner vol={inner_m.volume():.0f}")
        shell_m = part_m - inner_m
        _prog(f"Shell: {shell_m.num_tri()} tris, vol={shell_m.volume():.0f}")
        _check()
    else:
        inner_m = part_m
        shell_m = None

    # ── Step 2: Generate lattice ───────────────────────────────────────────────
    if is_voronoi:
        shell_off = bool(wall_only)   # no outer shell → sealed boundary mode
        strut_radius = max(float(strut_diameter) / 2.0, 0.05)
        _prog(f"Generating Voronoi (d={strut_diameter:.2f}mm, seeds={n_seeds}, "
              f"{'shell-off' if shell_off else 'shell-on'})...")
        tv, tf = _build_voronoi_mesh(
            mins, maxs, strut_radius, int(n_seeds),
            shell_off, inner_m, progress_cb=_prog
        )
        _prog(f"Voronoi: {len(tf)} faces")
        _check()
        inner_lattice_m = _to_manifold(tv, tf)

    else:
        _prog(f"Generating {lattice_type} ({infill_pct:.0f}% infill)...")
        tv, tf = _build_tpms_mesh(mins, maxs, cell_size, infill_pct,
                                   lattice_type, voxel_size, smooth_iterations)
        _prog(f"TPMS: {len(tf)} faces")
        _check()

        tpms_m = _to_manifold(tv, tf)
        _prog("Clipping TPMS to cavity...")
        # Always clip to inner_m — the cavity after shell offset.
        # When wall_only=True, inner_m IS part_m so behaviour is identical.
        # When a shell exists, inner_m is the shrunken interior, so the lattice
        # fills only the cavity; shell_m is then unioned on top in Step 3.
        inner_lattice_m = _manifold_intersect(tpms_m, inner_m)
        _prog(f"Clipped: {inner_lattice_m.num_tri()} tris")
        _check()

    # ── Step 3: Combine shell + lattice ───────────────────────────────────────
    _prog("Combining shell + lattice...")
    if shell_m is not None and not shell_m.is_empty():
        final_m = shell_m + inner_lattice_m
    else:
        final_m = inner_lattice_m
    _prog(f"Final: {final_m.num_tri()} tris, vol={final_m.volume():.0f}")
    _check()

    # ── Step 4: Extract and clean ─────────────────────────────────────────────
    _prog("Extracting mesh...")
    rv, rf = _from_manifold(final_m)

    _prog("Removing floating geometry...")
    rv, rf = _remove_small_components(rv, rf)

    from collections import defaultdict
    ec = defaultdict(int)
    for tri in rf:
        for i in range(3):
            a,b=int(tri[i]),int(tri[(i+1)%3]); ec[(min(a,b),max(a,b))]+=1
    nm = sum(1 for x in ec.values() if x!=2)
    _prog(f"Done! {len(rv)} verts, {len(rf)} faces — {nm} non-manifold edges")
    return rv.astype(np.float32), rf.astype(np.int32)
