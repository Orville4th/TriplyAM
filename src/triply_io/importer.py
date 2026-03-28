"""
importer.py — Triply file import
Supports: STL, 3MF, STEP/STP
Returns: (vertices, faces, name) numpy arrays
"""

import os
import numpy as np


def import_file(path):
    """
    Import a 3D file and return (vertices, faces, display_name).
    vertices: (N,3) float32 — flat triangle soup
    faces:    (M,3) int32  — indices into vertices
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == '.stl':
        return _import_stl(path)
    elif ext == '.3mf':
        return _import_3mf(path)
    elif ext in ('.step', '.stp'):
        return _import_step(path)
    else:
        raise ValueError(f"Unsupported format: {ext}")


def _import_stl(path):
    from stl import mesh as stl_mesh
    loaded     = stl_mesh.Mesh.from_file(path)
    verts_raw  = loaded.vectors.reshape(-1, 3).astype(np.float32)
    faces      = np.arange(len(verts_raw), dtype=np.int32).reshape(-1, 3)
    # Centre at origin
    verts_raw -= verts_raw.min(axis=0)
    return verts_raw, faces, os.path.basename(path)


def _import_3mf(path):
    """
    Parse a 3MF file (ZIP with model/3dmodel.model XML inside).
    Falls back to STL-style flat triangle soup.
    """
    import zipfile
    import xml.etree.ElementTree as ET

    try:
        with zipfile.ZipFile(path, 'r') as zf:
            model_files = [n for n in zf.namelist() if n.endswith('.model')]
            if not model_files:
                raise ValueError("No .model file found inside 3MF archive")
            xml_data = zf.read(model_files[0])

        root = ET.fromstring(xml_data)
        ns   = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}

        all_verts = []
        all_faces = []
        offset    = 0

        for mesh_el in root.findall('.//m:mesh', ns):
            verts_el  = mesh_el.find('m:vertices', ns)
            triangles = mesh_el.find('m:triangles', ns)
            if verts_el is None or triangles is None:
                continue
            verts = np.array([
                [float(v.get('x',0)), float(v.get('y',0)), float(v.get('z',0))]
                for v in verts_el.findall('m:vertex', ns)
            ], dtype=np.float32)
            faces = np.array([
                [int(t.get('v1',0)), int(t.get('v2',0)), int(t.get('v3',0))]
                for t in triangles.findall('m:triangle', ns)
            ], dtype=np.int32)
            all_verts.append(verts)
            all_faces.append(faces + offset)
            offset += len(verts)

        if not all_verts:
            raise ValueError("No mesh geometry found in 3MF")

        v = np.vstack(all_verts)
        f = np.vstack(all_faces)
        v -= v.min(axis=0)
        return v, f, os.path.basename(path)

    except Exception as e:
        raise ValueError(f"3MF import failed: {e}")


def _import_step(path):
    """
    Import STEP via cadquery. Tessellates entire solid at once for
    consistent normals and watertight mesh.
    """
    try:
        import cadquery as cq
        from mesh_repair import weld_vertices, remove_degenerate
        result = cq.importers.importStep(path)
        bb  = result.val().BoundingBox()
        span = max(bb.xmax-bb.xmin, bb.ymax-bb.ymin, bb.zmax-bb.zmin)
        # Fine tolerance for smooth appearance — 0.05% of span, min 0.002mm
        tol = max(span * 0.0005, 0.002)
        ang = 0.05  # angular deflection — smaller = smoother curves

        # Tessellate entire solid at once (not face by face)
        mesh = result.val().tessellate(tol, ang)
        verts = np.array([[p.x, p.y, p.z] for p in mesh[0]], dtype=np.float32)
        faces = np.array(mesh[1], dtype=np.int32)

        if len(verts) == 0:
            raise ValueError("STEP file produced no geometry")

        # Weld shared vertices for consistent normals
        verts, faces = weld_vertices(verts, faces, tol=0.001)
        faces = remove_degenerate(verts, faces)
        verts -= verts.min(axis=0)
        return verts, faces, os.path.basename(path)

    except ImportError:
        raise ImportError(
            "STEP import requires cadquery.\n"
            "Install with: pip install cadquery\n"
            "This may take a few minutes."
        )
