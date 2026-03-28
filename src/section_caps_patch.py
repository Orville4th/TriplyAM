import re

vp_path = "/home/orvilleiv/Desktop/Triply Development/Triply/src/viewport.py"
with open(vp_path) as f:
    vp = f.read()

# Find the gizmo section and insert section caps before it
if '_draw_section_caps' in vp:
    print("Already patched")
else:
    # Find paintGL and add section cap call
    # Use regex to find the gizmo block
    gizmo_pattern = r'(        # Draw translation gizmo)'
    replacement = r'''        # Draw section caps when layer slider is active
        if self._layer_pct < 1.0 and self._bv_list:
            self._draw_section_caps()

        \1'''
    vp, n = re.subn(gizmo_pattern, replacement, vp)
    print(f"paintGL: {n} replacements")

    # Add methods before _draw_gizmo
    gizmo_def = '    def _draw_gizmo(self):'
    if gizmo_def in vp:
        insertion = '''    def _draw_section_caps(self):
        """Draw hatch fills on section cut plane."""
        if not self._meshes or not self._bv_list:
            return
        bz = self._bv_list[0][2]
        clip_z = bz * self._layer_pct

        pastels = [
            (1.0,0.7,0.7),(0.7,1.0,0.7),(0.7,0.7,1.0),(1.0,1.0,0.7),
            (1.0,0.7,1.0),(0.7,1.0,1.0),(1.0,0.85,0.7),(0.85,0.7,1.0),
        ]

        glDisable(GL_LIGHTING)
        glDisable(GL_CLIP_PLANE0)
        glLineWidth(1.2)

        for i, (idx, mesh) in enumerate(self._meshes.items()):
            if not mesh['visible']:
                continue
            v     = mesh['verts'] + mesh['offset']
            faces = mesh['faces']
            r, g, b = pastels[i % len(pastels)]

            z0 = v[faces[:,0], 2]
            z1 = v[faces[:,1], 2]
            z2 = v[faces[:,2], 2]
            crossing = ~((z0 >= clip_z) & (z1 >= clip_z) & (z2 >= clip_z)) & \
                       ~((z0 <  clip_z) & (z1 <  clip_z) & (z2 <  clip_z))

            if not crossing.any():
                continue

            segments = []
            for tri in faces[crossing]:
                pts = v[tri]
                segs = self._clip_tri_at_z(pts, clip_z)
                segments.extend(segs)

            if not segments:
                continue

            # Collect all intersection points for hatch bounds
            xs = [x for x1,y1,x2,y2 in segments for x in (x1,x2)]
            ys = [y for x1,y1,x2,y2 in segments for y in (y1,y2)]
            if not xs:
                continue
            xmin,xmax = min(xs),max(xs)
            ymin,ymax = min(ys),max(ys)

            # Draw hatch lines (no stencil — simpler, reliable)
            glColor3f(r * 0.75, g * 0.75, b * 0.75)
            hatch = 4.0
            diag  = max(xmax-xmin, ymax-ymin) + hatch * 4
            glBegin(GL_LINES)
            t = xmin - diag
            while t < xmax + diag:
                glVertex3f(t,        ymin - diag, clip_z + 0.2)
                glVertex3f(t + diag, ymin + diag, clip_z + 0.2)
                glVertex3f(t,        ymin + diag, clip_z + 0.2)
                glVertex3f(t + diag, ymin - diag, clip_z + 0.2)
                t += hatch
            glEnd()

            # Draw cap outline in pastel
            glColor3f(r, g, b)
            glLineWidth(2.0)
            glBegin(GL_LINES)
            for x1,y1,x2,y2 in segments:
                glVertex3f(x1, y1, clip_z + 0.3)
                glVertex3f(x2, y2, clip_z + 0.3)
            glEnd()
            glLineWidth(1.0)

        glEnable(GL_LIGHTING)
        glEnable(GL_CLIP_PLANE0)

    def _clip_tri_at_z(self, pts, z):
        """Find line segment where triangle intersects Z plane."""
        intersections = []
        for i, j in [(0,1),(1,2),(2,0)]:
            zi, zj = pts[i,2], pts[j,2]
            if (zi < z) != (zj < z):
                t = (z - zi) / (zj - zi)
                x = pts[i,0] + t*(pts[j,0]-pts[i,0])
                y = pts[i,1] + t*(pts[j,1]-pts[i,1])
                intersections.append((x,y))
        if len(intersections) == 2:
            return [(intersections[0][0], intersections[0][1],
                     intersections[1][0], intersections[1][1])]
        return []

    def _draw_gizmo(self):'''
        vp = vp.replace(gizmo_def, insertion, 1)
        print("✓ Added _draw_section_caps and _clip_tri_at_z")
    else:
        print("✗ _draw_gizmo not found")

with open(vp_path, 'w') as f:
    f.write(vp)
print("Done")
