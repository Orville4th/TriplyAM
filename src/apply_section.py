import re

vp_path = "/home/orvilleiv/Desktop/Triply Development/Triply/src/viewport.py"
mn_path = "/home/orvilleiv/Desktop/Triply Development/Triply/src/main.py"

# ── viewport.py ────────────────────────────────────────────────────────────
with open(vp_path) as f:
    vp = f.read()

# 1. Find exact paintGL clip plane disable line and insert after it
trigger = "glDisable(GL_CLIP_PLANE0)"
if trigger in vp:
    # Find the one in paintGL (not in _draw_section_caps)
    idx = vp.find(trigger)
    # Insert section cap call right before the gizmo block
    cap_call = "\n        # Section fill on cut plane\n        if self._layer_pct < 1.0 and self._bv_list:\n            self._draw_section_caps()\n"
    # Find "# Draw translation gizmo" and insert before it
    gizmo_comment = "        # Draw translation gizmo"
    if gizmo_comment in vp:
        vp = vp.replace(gizmo_comment, cap_call + gizmo_comment, 1)
        print("✓ Inserted section cap call in paintGL")
    else:
        print("✗ gizmo comment not found, trying alternate")
        # Just insert after first glDisable(GL_CLIP_PLANE0)
        vp = vp.replace(trigger, trigger + cap_call, 1)
        print("✓ Inserted after clip plane disable")
else:
    print("✗ clip plane disable not found")

# 2. Add methods — find _draw_gizmo and insert before it
gizmo_def = "\n    def _draw_gizmo(self):"
if gizmo_def in vp:
    new_methods = '''
    def _draw_section_caps(self):
        """Fill cut faces when clip plane is active."""
        if not self._meshes or not self._bv_list:
            return
        bz = float(self._bv_list[0][2])
        clip_z = bz * self._layer_pct

        pastels = [
            (1.0,0.6,0.6),(0.6,1.0,0.6),(0.6,0.6,1.0),(1.0,1.0,0.6),
            (1.0,0.6,1.0),(0.6,1.0,1.0),(1.0,0.8,0.6),(0.8,0.6,1.0),
        ]

        glDisable(GL_LIGHTING)
        glDisable(GL_CLIP_PLANE0)
        glDepthMask(GL_FALSE)

        for i, (idx, mesh) in enumerate(self._meshes.items()):
            if not mesh['visible']:
                continue
            import numpy as _np
            v     = mesh['verts'] + mesh['offset']
            faces = mesh['faces']
            r, g, b = pastels[i % len(pastels)]

            z0 = v[faces[:,0], 2]
            z1 = v[faces[:,1], 2]
            z2 = v[faces[:,2], 2]

            # Triangles crossing the clip plane
            above = _np.stack([z0>=clip_z, z1>=clip_z, z2>=clip_z], axis=1)
            crossing = ~above.all(axis=1) & above.any(axis=1)
            if not crossing.any():
                continue

            # Collect intersection segments
            segs = []
            for tri in faces[crossing]:
                pts = v[tri]
                isect = []
                for a, b_ in [(0,1),(1,2),(2,0)]:
                    za, zb = pts[a,2], pts[b_,2]
                    if (za < clip_z) != (zb < clip_z):
                        t = (clip_z - za) / (zb - za)
                        x = pts[a,0] + t*(pts[b_,0]-pts[a,0])
                        y = pts[a,1] + t*(pts[b_,1]-pts[a,1])
                        isect.append((x, y))
                if len(isect) == 2:
                    segs.append((isect[0][0], isect[0][1],
                                 isect[1][0], isect[1][1]))

            if not segs:
                continue

            # Draw filled cap — project crossing triangles onto clip plane
            glColor3f(r*0.55, g*0.55, b*0.55)
            glBegin(GL_TRIANGLES)
            for tri in faces[crossing]:
                pts = v[tri]
                for pt in pts:
                    glVertex3f(float(pt[0]), float(pt[1]), clip_z + 0.05)
            glEnd()

            # Draw hatch lines along cut edges
            glColor3f(r*0.4, g*0.4, b*0.4)
            glLineWidth(0.8)
            glBegin(GL_LINES)
            hatch = 3.0
            for x1, y1, x2, y2 in segs:
                dx = x2-x1; dy = y2-y1
                ln = (dx*dx+dy*dy)**0.5
                if ln < 1e-6:
                    continue
                nx, ny = -dy/ln*hatch*0.5, dx/ln*hatch*0.5
                steps = max(1, int(ln/hatch))
                for k in range(steps+1):
                    t = min(1.0, k/steps)
                    mx = x1+t*dx; my = y1+t*dy
                    glVertex3f(mx-nx, my-ny, clip_z+0.15)
                    glVertex3f(mx+nx, my+ny, clip_z+0.15)
            glEnd()

            # Draw cut outline
            glColor3f(r, g, b)
            glLineWidth(1.8)
            glBegin(GL_LINES)
            for x1, y1, x2, y2 in segs:
                glVertex3f(x1, y1, clip_z+0.2)
                glVertex3f(x2, y2, clip_z+0.2)
            glEnd()
            glLineWidth(1.0)

        glDepthMask(GL_TRUE)
        glEnable(GL_LIGHTING)
        glEnable(GL_CLIP_PLANE0)

'''
    vp = vp.replace(gizmo_def, new_methods + gizmo_def, 1)
    print("✓ Added _draw_section_caps")
else:
    print("✗ _draw_gizmo not found")

with open(vp_path, 'w') as f:
    f.write(vp)

# ── main.py — request stencil buffer ──────────────────────────────────────
with open(mn_path) as f:
    mn = f.read()

old_main = "def main():\n    app=QApplication(sys.argv)"
new_main = """def main():
    from PyQt6.QtGui import QSurfaceFormat
    fmt = QSurfaceFormat()
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    QSurfaceFormat.setDefaultFormat(fmt)
    app=QApplication(sys.argv)"""

if old_main in mn:
    mn = mn.replace(old_main, new_main)
    print("✓ Added stencil buffer request")
else:
    print("✗ main() not found")

with open(mn_path, 'w') as f:
    f.write(mn)

print("\nDone")
