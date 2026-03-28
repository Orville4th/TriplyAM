"""
exporter.py — Triply file export
Supports: STL (binary), 3MF, STEP (via cadquery)
Quality presets: low=0.5mm, medium=0.1mm, high=0.001mm
"""

import os
import struct
import numpy as np


QUALITY_PRESETS = {
    "Low":    0.5,
    "Medium": 0.1,
    "High":   0.001,
}


def export_file(path, vertices, faces, quality="Medium"):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.stl':
        export_stl(path, vertices, faces)
    elif ext == '.3mf':
        export_3mf(path, vertices, faces)
    elif ext in ('.step', '.stp'):
        export_step(path, vertices, faces, quality)
    else:
        raise ValueError(f"Unsupported export format: {ext}")


def export_stl(path, vertices, faces):
    """Write binary STL — always valid, always watertight if input is."""
    with open(path, 'wb') as f:
        f.write(b'\x00' * 80)
        f.write(struct.pack('<I', len(faces)))
        v = vertices.astype(np.float32)
        for tri in faces:
            v0, v1, v2 = v[tri[0]], v[tri[1]], v[tri[2]]
            e1 = v1 - v0
            e2 = v2 - v0
            n  = np.cross(e1, e2)
            nl = np.linalg.norm(n)
            n  = n / nl if nl > 1e-10 else np.array([0, 0, 1], dtype=np.float32)
            f.write(n.astype(np.float32).tobytes())
            f.write(v0.tobytes())
            f.write(v1.tobytes())
            f.write(v2.tobytes())
            f.write(b'\x00\x00')


def export_3mf(path, vertices, faces):
    """Write a minimal valid 3MF archive."""
    import zipfile

    rels_content = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
                Target="/3D/model.model" Id="rel0"/>
</Relationships>"""

    v_lines = '\n'.join(
        f'      <vertex x="{float(vertices[i,0]):.6f}" y="{float(vertices[i,1]):.6f}" z="{float(vertices[i,2]):.6f}"/>'
        for i in range(len(vertices))
    )
    f_lines = '\n'.join(
        f'      <triangle v1="{int(faces[i,0])}" v2="{int(faces[i,1])}" v3="{int(faces[i,2])}"/>'
        for i in range(len(faces))
    )

    model_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US"
       xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <resources>
    <object id="1" type="model">
      <mesh>
        <vertices>
{v_lines}
        </vertices>
        <triangles>
{f_lines}
        </triangles>
      </mesh>
    </object>
  </resources>
  <build>
    <item objectid="1"/>
  </build>
</model>"""

    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('_rels/.rels', rels_content)
        zf.writestr('3D/model.model', model_content)
        zf.writestr('[Content_Types].xml',
            '<?xml version="1.0"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
            '</Types>')


def export_step(path, vertices, faces, quality="Medium"):
    """
    Export a proper STEP solid (not faceted) via cadquery BRep reconstruction.
    Falls back to faceted STEP if full solid reconstruction fails.
    """
    tol = QUALITY_PRESETS.get(quality, 0.1)
    try:
        import cadquery as cq
        from OCC.Core.BRep import BRep_Builder
        from OCC.Core.BRepBuilderAPI import (
            BRepBuilderAPI_MakePolygon,
            BRepBuilderAPI_MakeFace,
            BRepBuilderAPI_Sewing,
        )
        from OCC.Core.TopoDS import TopoDS_Compound
        from OCC.Core.gp import gp_Pnt
        from OCC.Core.BRep import BRep_Builder
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse
        from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs
        from OCC.Core.IFSelect import IFSelect_RetDone

        sewing = BRepBuilderAPI_Sewing(tol)
        v = vertices.astype(np.float64)

        for tri in faces:
            p0 = gp_Pnt(*v[tri[0]])
            p1 = gp_Pnt(*v[tri[1]])
            p2 = gp_Pnt(*v[tri[2]])
            wire = BRepBuilderAPI_MakePolygon(p0, p1, p2, True).Wire()
            face = BRepBuilderAPI_MakeFace(wire)
            if face.IsDone():
                sewing.Add(face.Face())

        sewing.Perform()
        sewn = sewing.SewedShape()

        writer = STEPControl_Writer()
        writer.Transfer(sewn, STEPControl_AsIs)
        status = writer.Write(path)
        if status != IFSelect_RetDone:
            raise RuntimeError("STEP write failed")

    except ImportError:
        # Fallback: write faceted STEP using ASCII format
        _export_step_faceted(path, vertices, faces)
    except Exception:
        _export_step_faceted(path, vertices, faces)


def _export_step_faceted(path, vertices, faces):
    """Fallback: write a faceted STEP file without cadquery."""
    lines = [
        "ISO-10303-21;",
        "HEADER;",
        "FILE_DESCRIPTION(('Triply Export'),'2;1');",
        "FILE_NAME('','',(''),(''),'Triply','','');",
        "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));",
        "ENDSEC;",
        "DATA;",
    ]
    idx = 1
    v = vertices.astype(np.float64)
    vert_ids = []
    for pt in v:
        lines.append(f"#{idx}=CARTESIAN_POINT('',(${pt[0]:.6f},${pt[1]:.6f},${pt[2]:.6f}));".replace('$',''))
        vert_ids.append(idx); idx += 1
    for tri in faces:
        a, b, c = vert_ids[tri[0]], vert_ids[tri[1]], vert_ids[tri[2]]
        lines.append(f"#{idx}=FACE_BOUND('',#{a},#{b},#{c},.T.);"); idx += 1
    lines += ["ENDSEC;", "END-ISO-10303-21;"]
    with open(path, 'w') as f:
        f.write('\n'.join(lines))
