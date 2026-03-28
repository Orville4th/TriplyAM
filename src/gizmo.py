"""
Translation gizmo patch for Triply viewport.
Adds draggable X/Y/Z axis arrows centered on the selected mesh.
Red=X, Green=Y, Blue=Z — matches axis colors.
Drag on arrow to constrain movement to that axis only.
"""
import os

vp_path = "/home/orvilleiv/Desktop/Triply Development/Triply/src/viewport.py"
with open(vp_path) as f: vp = f.read()

# ── 1. Add gizmo state to __init__ ─────────────────────────────────────────
old_init = "        self._wireframe  = False"
new_init = """        self._wireframe  = False
        # Gizmo state
        self._gizmo_active   = False   # is gizmo visible
        self._gizmo_center   = None    # np.array [x,y,z] world center of selected mesh
        self._gizmo_drag_axis= None    # 'X','Y','Z' or None
        self._gizmo_drag_start = None  # screen pos at drag start
        self._gizmo_mesh_offset_start = None  # mesh offset at drag start
        self._gizmo_size     = 40.0    # arrow length in mm"""

if old_init in vp:
    vp = vp.replace(old_init, new_init); print("✓ Gizmo state in __init__")
else:
    print("✗ __init__ anchor not found")

# ── 2. set_selected — compute gizmo center ─────────────────────────────────
old_sel = """    def set_selected(self, idx):
        self._selected = idx
        self.update()"""

new_sel = """    def set_selected(self, idx):
        self._selected = idx
        if idx >= 0 and idx in self._meshes:
            mesh = self._meshes[idx]
            v    = mesh['verts'] + mesh['offset']
            self._gizmo_center = (v.max(axis=0) + v.min(axis=0)) / 2.0
            self._gizmo_active = True
        else:
            self._gizmo_active = False
            self._gizmo_center = None
        self.update()

    def update_gizmo_center(self, idx):
        \"\"\"Refresh gizmo center after mesh moves.\"\"\"
        if idx in self._meshes:
            mesh = self._meshes[idx]
            v    = mesh['verts'] + mesh['offset']
            self._gizmo_center = (v.max(axis=0) + v.min(axis=0)) / 2.0"""

if old_sel in vp:
    vp = vp.replace(old_sel, new_sel); print("✓ set_selected with gizmo center")
else:
    print("✗ set_selected not found")

# ── 3. Draw gizmo in paintGL — after meshes, before axes ───────────────────
old_paint_end = """        glDisable(GL_CLIP_PLANE0)

        # Draw axes FIRST with depth test ON — models will occlude them naturally
        self._draw_axes()"""

new_paint_end = """        glDisable(GL_CLIP_PLANE0)

        # Draw translation gizmo over selected mesh
        if self._gizmo_active and self._gizmo_center is not None:
            glDisable(GL_DEPTH_TEST)
            self._draw_gizmo()
            glEnable(GL_DEPTH_TEST)

        # Draw axes
        self._draw_axes()"""

if old_paint_end in vp:
    vp = vp.replace(old_paint_end, new_paint_end); print("✓ Gizmo in paintGL")
else:
    print("✗ paintGL end not found")

# ── 4. _draw_gizmo method ───────────────────────────────────────────────────
old_draw_axes = "    def _draw_axes(self):"
new_draw_axes = """    def _draw_gizmo(self):
        \"\"\"Draw X/Y/Z translation arrows centered on selected mesh.\"\"\"
        import numpy as np
        cx, cy, cz = self._gizmo_center
        sz = self._gizmo_size
        hl = sz * 0.22   # arrowhead length
        hw = sz * 0.08   # arrowhead base half-width

        glDisable(GL_LIGHTING)
        glLineWidth(3.0)

        axes = [
            ('X', (cx,cy,cz), (cx+sz,cy,   cz),   (1.0,0.15,0.15), self._gizmo_drag_axis=='X'),
            ('Y', (cx,cy,cz), (cx,   cy+sz, cz),   (0.15,1.0,0.15), self._gizmo_drag_axis=='Y'),
            ('Z', (cx,cy,cz), (cx,   cy,    cz+sz),(0.15,0.35,1.0), self._gizmo_drag_axis=='Z'),
        ]

        for axis, start, end, color, active in axes:
            r,g,b = color
            if active:
                r = min(1.0, r*1.0 + 0.4)
                g = min(1.0, g*1.0 + 0.4)
                b = min(1.0, b*1.0 + 0.4)
            glColor3f(r, g, b)

            # Shaft line
            glBegin(GL_LINES)
            glVertex3fv(start)
            glVertex3fv(end)
            glEnd()

            # Arrowhead cone (simplified as 4-sided pyramid)
            ex,ey,ez = end
            sx,sy,sz_ = start

            # Direction vector
            dx,dy,dz = ex-sx, ey-sy, ez-sz_
            ln = (dx*dx+dy*dy+dz*dz)**0.5
            if ln < 1e-6: continue
            dx/=ln; dy/=ln; dz/=ln

            # Two perpendicular vectors
            import numpy as _np
            d = _np.array([dx,dy,dz])
            up = _np.array([0,0,1]) if abs(dz)<0.9 else _np.array([0,1,0])
            p1 = _np.cross(d, up); p1/=_np.linalg.norm(p1)
            p2 = _np.cross(d, p1); p2/=_np.linalg.norm(p2)

            # Cone base center (step back from tip)
            bx = ex - dx*hl
            by = ey - dy*hl
            bz = ez - dz*hl

            # 4 base points
            pts = [
                (bx+p1[0]*hw, by+p1[1]*hw, bz+p1[2]*hw),
                (bx+p2[0]*hw, by+p2[1]*hw, bz+p2[2]*hw),
                (bx-p1[0]*hw, by-p1[1]*hw, bz-p1[2]*hw),
                (bx-p2[0]*hw, by-p2[1]*hw, bz-p2[2]*hw),
            ]

            glBegin(GL_TRIANGLE_FAN)
            glVertex3f(ex, ey, ez)   # tip
            for pt in pts + [pts[0]]:
                glVertex3fv(pt)
            glEnd()

            # Small sphere at center origin of gizmo
            glPointSize(10.0)
            glColor3f(0.9, 0.9, 0.9)
            glBegin(GL_POINTS)
            glVertex3f(cx, cy, cz)
            glEnd()
            glPointSize(1.0)

        glLineWidth(1.0)
        glEnable(GL_LIGHTING)

    def _gizmo_hit_test(self, screen_x, screen_y):
        \"\"\"
        Returns 'X','Y','Z' if mouse is near a gizmo arrow, else None.
        Projects each arrow endpoint to screen and checks distance.
        \"\"\"
        if not self._gizmo_active or self._gizmo_center is None:
            return None

        import numpy as np
        cx,cy,cz = self._gizmo_center
        sz = self._gizmo_size
        tips = {
            'X': np.array([cx+sz, cy,    cz   ]),
            'Y': np.array([cx,    cy+sz, cz   ]),
            'Z': np.array([cx,    cy,    cz+sz]),
        }
        center_s = self._world_to_screen(cx, cy, cz)
        if center_s is None:
            return None

        THRESHOLD = 14  # pixels

        for axis, tip in tips.items():
            tip_s = self._world_to_screen(*tip)
            if tip_s is None:
                continue
            # Check if mouse is within threshold of the shaft line segment
            ax,ay = center_s
            bx,by = tip_s
            mx,my = screen_x, screen_y
            # Point-to-segment distance
            dx,dy = bx-ax, by-ay
            ln2 = dx*dx + dy*dy
            if ln2 < 1e-6:
                continue
            t = max(0.0, min(1.0, ((mx-ax)*dx + (my-ay)*dy) / ln2))
            px = ax + t*dx - mx
            py = ay + t*dy - my
            dist = (px*px + py*py)**0.5
            if dist < THRESHOLD:
                return axis
        return None

    def _world_to_screen(self, wx, wy, wz):
        \"\"\"Project world point to screen coordinates.\"\"\"
        import numpy as np
        aspect = self._width / self._height
        pm  = _perspective(45.0, aspect, 0.1, 10000.0)

        # Build modelview from current camera state
        # Apply rotation then translation
        rx = np.radians(self._rot_x)
        ry = np.radians(self._rot_y)

        # Rotation matrices
        cx,sx = np.cos(rx),np.sin(rx)
        cy,sy = np.cos(ry),np.sin(ry)
        Rx = np.array([[1,0,0,0],[0,cx,-sx,0],[0,sx,cx,0],[0,0,0,1]],dtype=np.float32)
        Rz = np.array([[cy,-sy,0,0],[sy,cy,0,0],[0,0,1,0],[0,0,0,1]],dtype=np.float32)
        T  = np.array([[1,0,0,self._pan_x],[0,1,0,self._pan_y],[0,0,1,-self._zoom],[0,0,0,1]],dtype=np.float32)
        mv = T @ Rx @ Rz

        pt  = np.array([wx, wy, wz, 1.0], dtype=np.float32)
        clip = pm @ mv @ pt
        if abs(clip[3]) < 1e-6:
            return None
        ndc = clip[:3] / clip[3]
        if not (-1 <= ndc[0] <= 1 and -1 <= ndc[1] <= 1):
            return None
        sx = int((ndc[0]+1)/2 * self._width)
        sy = int((1-ndc[1])/2 * self._height)  # flip Y
        return (sx, sy)

    def _draw_axes(self):"""

if old_draw_axes in vp:
    vp = vp.replace(old_draw_axes, new_draw_axes); print("✓ Added _draw_gizmo and helpers")
else:
    print("✗ _draw_axes anchor not found")

# ── 5. Mouse events — gizmo drag ───────────────────────────────────────────
old_mouse_press = """    def mousePressEvent(self, event):
        self._last_pos  = event.position().toPoint()
        self._mouse_btn = event.button()
        self._drag_dist = 0
        if event.button() == Qt.MouseButton.LeftButton:
            if self._hit_view_cube(event.position().toPoint()):
                return"""

new_mouse_press = """    def mousePressEvent(self, event):
        self._last_pos  = event.position().toPoint()
        self._mouse_btn = event.button()
        self._drag_dist = 0
        if event.button() == Qt.MouseButton.LeftButton:
            if self._hit_view_cube(event.position().toPoint()):
                return
            # Check gizmo hit BEFORE orbit
            pos = event.position().toPoint()
            axis = self._gizmo_hit_test(pos.x(), pos.y())
            if axis:
                self._gizmo_drag_axis        = axis
                self._gizmo_drag_start       = pos
                # Find selected mesh offset
                if self._selected in self._meshes:
                    self._gizmo_mesh_offset_start = self._meshes[self._selected]['offset'].copy()
                self._mouse_btn = None  # suppress orbit
                self.update()
                return"""

if old_mouse_press in vp:
    vp = vp.replace(old_mouse_press, new_mouse_press); print("✓ Gizmo mousePressEvent")
else:
    print("✗ mousePressEvent not found")

old_mouse_move = """    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        dx  = pos.x() - self._last_pos.x()
        dy  = pos.y() - self._last_pos.y()
        self._drag_dist += abs(dx) + abs(dy)
        if self._mouse_btn == self._orbit_btn:
            self._rot_y += dx * 0.5
            self._rot_x += dy * 0.5
        elif self._mouse_btn == self._pan_btn:
            self._pan_x += dx * 0.3
            self._pan_y -= dy * 0.3
        self._last_pos = pos
        self.update()"""

new_mouse_move = """    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        dx  = pos.x() - self._last_pos.x()
        dy  = pos.y() - self._last_pos.y()
        self._drag_dist += abs(dx) + abs(dy)

        # Gizmo drag takes priority
        if self._gizmo_drag_axis and self._gizmo_drag_start is not None:
            self._handle_gizmo_drag(pos)
            self._last_pos = pos
            return

        if self._mouse_btn == self._orbit_btn:
            self._rot_y += dx * 0.5
            self._rot_x += dy * 0.5
        elif self._mouse_btn == self._pan_btn:
            self._pan_x += dx * 0.3
            self._pan_y -= dy * 0.3
        self._last_pos = pos
        self.update()

    def _handle_gizmo_drag(self, pos):
        \"\"\"Move selected mesh along the constrained axis.\"\"\"
        import numpy as np
        if self._selected not in self._meshes: return
        if self._gizmo_mesh_offset_start is None: return

        start_pos = self._gizmo_drag_start
        dx_screen = pos.x() - start_pos.x()
        dy_screen = pos.y() - start_pos.y()

        # Convert screen delta to world delta along the drag axis
        # Project the axis direction to screen space to get sensitivity
        cx,cy,cz = self._gizmo_center
        sz = self._gizmo_size
        axis = self._gizmo_drag_axis

        if axis=='X':   world_tip = (cx+sz, cy,    cz)
        elif axis=='Y': world_tip = (cx,    cy+sz, cz)
        else:           world_tip = (cx,    cy,    cz+sz)

        c_s  = self._world_to_screen(cx,cy,cz)
        t_s  = self._world_to_screen(*world_tip)
        if c_s is None or t_s is None: return

        # Screen direction of the axis
        ax_s = np.array([t_s[0]-c_s[0], t_s[1]-c_s[1]], dtype=np.float32)
        ax_len = np.linalg.norm(ax_s)
        if ax_len < 1e-6: return
        ax_s /= ax_len

        # Project mouse delta onto axis screen direction
        mouse_d = np.array([dx_screen, dy_screen], dtype=np.float32)
        proj = np.dot(mouse_d, ax_s)

        # Scale: sz world units = ax_len screen pixels
        world_delta = proj * sz / ax_len

        # Apply to offset
        off = self._gizmo_mesh_offset_start.copy()
        if axis=='X':   off[0] += world_delta
        elif axis=='Y': off[1] += world_delta
        else:           off[2] += world_delta

        self._meshes[self._selected]['offset'] = off

        # Update gizmo center
        mesh = self._meshes[self._selected]
        v = mesh['verts'] + off
        self._gizmo_center = (v.max(axis=0) + v.min(axis=0)) / 2.0

        self.mesh_moved.emit(self._selected, float(off[0]), float(off[1]), float(off[2]))
        self.update()"""

if old_mouse_move in vp:
    vp = vp.replace(old_mouse_move, new_mouse_move); print("✓ Gizmo mouseMoveEvent + drag handler")
else:
    print("✗ mouseMoveEvent not found")

old_mouse_rel = """    def mouseReleaseEvent(self, event):
        if self._drag_dist < 5:
            pos = event.position().toPoint()
            hit = self._try_select(pos)
            if not hit:
                self.empty_clicked.emit()
        self._mouse_btn = None
        self._drag_dist = 0"""

new_mouse_rel = """    def mouseReleaseEvent(self, event):
        if self._gizmo_drag_axis:
            self._gizmo_drag_axis         = None
            self._gizmo_drag_start        = None
            self._gizmo_mesh_offset_start = None
            self.update()
            return
        if self._drag_dist < 5:
            pos = event.position().toPoint()
            hit = self._try_select(pos)
            if not hit:
                self.empty_clicked.emit()
        self._mouse_btn = None
        self._drag_dist = 0"""

if old_mouse_rel in vp:
    vp = vp.replace(old_mouse_rel, new_mouse_rel); print("✓ Gizmo mouseReleaseEvent")
else:
    print("✗ mouseReleaseEvent not found")

# ── 6. Add mesh_moved signal to class ──────────────────────────────────────
old_sig = """    part_clicked  = pyqtSignal(int)
    files_dropped = pyqtSignal(list)
    empty_clicked = pyqtSignal()"""

new_sig = """    part_clicked  = pyqtSignal(int)
    files_dropped = pyqtSignal(list)
    empty_clicked = pyqtSignal()
    mesh_moved    = pyqtSignal(int, float, float, float)  # idx, x, y, z"""

if old_sig in vp:
    vp = vp.replace(old_sig, new_sig); print("✓ Added mesh_moved signal")
else:
    print("✗ signals not found")

with open(vp_path, 'w') as f: f.write(vp)

# ── 7. Wire mesh_moved signal in main.py ───────────────────────────────────
mn_path = "/home/orvilleiv/Desktop/Triply Development/Triply/src/main.py"
with open(mn_path) as f: mn = f.read()

old_vp_signals = """        self.viewport.part_clicked.connect(self._on_vp_click)
        self.viewport.empty_clicked.connect(self._deselect_all)
        self.viewport.files_dropped.connect(self._on_dropped)"""

new_vp_signals = """        self.viewport.part_clicked.connect(self._on_vp_click)
        self.viewport.empty_clicked.connect(self._deselect_all)
        self.viewport.files_dropped.connect(self._on_dropped)
        self.viewport.mesh_moved.connect(self._on_mesh_moved)"""

if old_vp_signals in mn:
    mn = mn.replace(old_vp_signals, new_vp_signals); print("✓ Wired mesh_moved in main")
else:
    print("✗ viewport signals not found in main")

# Add _on_mesh_moved handler
old_on_vp = """    def _on_vp_click(self, mesh_idx):"""
new_on_vp = """    def _on_mesh_moved(self, mesh_idx, x, y, z):
        \"\"\"Update part offset when gizmo drags it.\"\"\"
        import numpy as np
        for p in self._parts.values():
            if p['mesh_idx'] == mesh_idx:
                p['offset'] = np.array([x, y, z], dtype=np.float32)
                break

    def _on_vp_click(self, mesh_idx):"""

if old_on_vp in mn:
    mn = mn.replace(old_on_vp, new_on_vp); print("✓ Added _on_mesh_moved")
else:
    print("✗ _on_vp_click anchor not found")

# Push undo before gizmo starts (on part selection change)
old_sel_part = """    def _select_part(self, pid):
        for p in self._parts.values():
            self.viewport.set_mesh_color(p['mesh_idx'],
                ACCENT_RGB if p['id']==pid else MESH_COLOR)"""
new_sel_part = """    def _select_part(self, pid):
        self._push_undo()   # snapshot before any gizmo dragging
        for p in self._parts.values():
            self.viewport.set_mesh_color(p['mesh_idx'],
                ACCENT_RGB if p['id']==pid else MESH_COLOR)"""

if old_sel_part in mn:
    mn = mn.replace(old_sel_part, new_sel_part); print("✓ Push undo on select")
else:
    print("✗ _select_part not found")

with open(mn_path, 'w') as f: f.write(mn)
print("\n=== Done ===")
