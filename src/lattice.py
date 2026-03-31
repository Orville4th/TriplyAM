"""
lattice.py — Triply V3 TPMS lattice generation
Hybrid pipeline:
  - MeshLib mcOffsetMesh → perfect uniform wall thickness
  - manifold3d → TPMS boolean operations (handles strut topology correctly)
  - scikit-image marching cubes → TPMS mesh generation
"""

import numpy as np

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
    "Gyroid":     _gyroid,
    "Schwarz P":  _schwarz_p,
    "Schwarz D":  _schwarz_d,
    "Schoen I-WP": _schoen_iwp,
}
LATTICE_NAMES = list(LATTICE_FNS.keys())


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
    """MeshLib mesh → numpy directly (no STL roundtrip)."""
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


# ── TPMS mesh builder ──────────────────────────────────────────────────────────

def _build_tpms_mesh(mins, maxs, cell_size, lattice_thickness,
                     lattice_type, voxel_size, smooth_iterations=0):
    from skimage.measure import marching_cubes
    from mesh_repair import weld_vertices, remove_degenerate

    fn = LATTICE_FNS.get(lattice_type, _gyroid)
    # lattice_thickness is now a DENSITY PERCENTAGE (0-99).
    # threshold = density% / 100 * 0.9
    # 0% = thin walls (small threshold = narrow solid band near field=0)
    # 50% = medium walls
    # 99% = near-solid (threshold=0.891, almost everything is solid)
    # This is cell-size independent and directly intuitive.
    density_pct = float(lattice_thickness)  # 0-99 range from UI
    threshold = (density_pct / 100.0) * 0.9

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
    sdf = (threshold - np.abs(field)).astype(np.float32)

    # Seal boundaries
    sdf[0,:,:]=sdf[-1,:,:]=sdf[:,0,:]=sdf[:,-1,:]=sdf[:,:,0]=sdf[:,:,-1]=1.0

    lv, lf, _, _ = marching_cubes(sdf, level=0.0,
                                   spacing=(voxel_size, voxel_size, voxel_size))
    lv[:,0]+=origin[0]; lv[:,1]+=origin[1]; lv[:,2]+=origin[2]
    lv, lf = weld_vertices(lv.astype(np.float32), lf.astype(np.int32))
    lf = remove_degenerate(lv, lf)

    # Optional smoothing
    if smooth_iterations > 0:
        import pyvista as pv
        faces_pv = np.hstack([np.full((len(lf),1),3), lf]).astype(np.int32)
        mesh = pv.PolyData(lv, faces_pv)
        mesh = mesh.smooth(n_iter=int(smooth_iterations*20),
                           relaxation_factor=0.1,
                           feature_angle=30.0)
        lv = np.array(mesh.points, dtype=np.float32)
        lf = mesh.faces.reshape(-1,4)[:,1:].astype(np.int32)

    return lv, lf


# ── Main pipeline ──────────────────────────────────────────────────────────────

def generate_lattice(stl_verts, wall_thickness, cell_size, lattice_thickness,
                     stl_faces=None, step_path=None,
                     lattice_type="Gyroid", resolution=None,
                     smooth_iterations=1, smooth_factor=0.3,
                     wall_only=False, progress_cb=None, cancel_flag=None):
    """
    Generate TPMS lattice infill with uniform shell.

    Pipeline:
      1. MeshLib mcOffsetMesh → perfect uniform wall thickness
      2. manifold3d → shell boolean (part - inner)
      3. scikit-image marching cubes → TPMS strut mesh
      4. manifold3d → clip TPMS to inner cavity
      5. manifold3d → union shell + TPMS
    """
    import meshlib.mrmeshpy as mr
    from mesh_repair import weld_vertices, remove_degenerate
    from manifold3d import Manifold

    def _prog(msg):
        if progress_cb: progress_cb(msg)
    def _check():
        if cancel_flag and cancel_flag[0]: raise InterruptedError("Cancelled")

    _prog(f"Type: {lattice_type}  Cell: {cell_size}mm  Wall: {wall_thickness}mm")
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

    # ── Voxel size ─────────────────────────────────────────────────────────────
    if resolution is None or resolution == 0:
        voxel_size = float(np.clip(cell_size/8.0, 0.15, 0.4))
    else:
        voxel_size = float(np.clip(np.max(span)/resolution, 0.05, 1.0))
    _prog(f"Voxel size: {voxel_size:.3f}mm")

    # ── Step 1: MeshLib uniform shell offset ───────────────────────────────────
    wt = float(wall_thickness)
    part_mr = _to_mr(sv, sf)
    part_m = _to_manifold(sv, sf)

    if wt > 0 and not wall_only:
        _prog(f"Computing shell offset ({wt}mm)...")
        op = mr.OffsetParameters()
        op.voxelSize = min(voxel_size, 0.2)
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
        # No shell — TPMS fills entire part volume
        inner_m = part_m
        shell_m = None

    # ── Step 2: TPMS mesh ──────────────────────────────────────────────────────
    _prog(f"Generating {lattice_type} TPMS...")
    tv, tf = _build_tpms_mesh(mins, maxs, cell_size, lattice_thickness,
                               lattice_type, voxel_size, smooth_iterations)
    _prog(f"TPMS: {len(tf)} faces")
    _check()

    tpms_m = _to_manifold(tv, tf)

    # ── Step 3: Clip TPMS to inner cavity ─────────────────────────────────────
    _prog("Clipping TPMS to cavity...")
    inner_tpms_m = tpms_m ^ inner_m
    _prog(f"Inner TPMS: {inner_tpms_m.num_tri()} tris, vol={inner_tpms_m.volume():.0f}")
    _check()

    # ── Step 4: Combine shell + TPMS ──────────────────────────────────────────
    _prog("Combining shell + TPMS...")
    if shell_m is not None and not shell_m.is_empty():
        final_m = shell_m + inner_tpms_m
    else:
        final_m = inner_tpms_m
    _prog(f"Final: {final_m.num_tri()} tris, vol={final_m.volume():.0f}")
    _check()

    # ── Step 5: Extract result ─────────────────────────────────────────────────
    _prog("Extracting mesh...")
    rv, rf = _from_manifold(final_m)

    from collections import defaultdict
    ec = defaultdict(int)
    for tri in rf:
        for i in range(3):
            a,b=int(tri[i]),int(tri[(i+1)%3]); ec[(min(a,b),max(a,b))]+=1
    nm = sum(1 for x in ec.values() if x!=2)
    _prog(f"Done! {len(rv)} verts, {len(rf)} faces — {nm} non-manifold edges")
    return rv.astype(np.float32), rf.astype(np.int32)
