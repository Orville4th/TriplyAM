import os
path = "/home/orvilleiv/Desktop/Triply Development/Triply/src/main.py"
with open(path) as f: c = f.read()

# ==========================================================================
# 1. Fix menu shortcuts (Ctrl+I = import, Ctrl+O = open project)
# ==========================================================================
old_menu = '''        fm = mb.addMenu("File")
        self._act(fm,"Import STL / 3MF / STEP…","Ctrl+O",self._import_files)
        fm.addSeparator()
        self._act(fm,"Save Project (.triply3d)","Ctrl+S",self._save_project)
        self._act(fm,"Open Project (.triply3d)","Ctrl+Shift+O",self._open_project)
        fm.addSeparator()
        self._act(fm,"Quit","Ctrl+Q",self.close)
        em = mb.addMenu("Edit")
        self._act(em,"Copy","Ctrl+C",self._copy_sel)
        self._act(em,"Paste","Ctrl+V",self._paste)
        self._act(em,"Duplicate","Ctrl+D",self._duplicate)
        self._act(em,"Select All","Ctrl+A",self._select_all)
        sm = mb.addMenu("Settings")
        self._act(sm,"Mouse Controls…","",self._dlg_mouse)
        self._act(sm,"About Triply…","",self._dlg_about)'''

new_menu = '''        fm = mb.addMenu("File")
        self._act(fm,"Import STL / 3MF / STEP…","Ctrl+I",self._import_files)
        fm.addSeparator()
        self._act(fm,"Open Project (.triply3d)","Ctrl+O",self._open_project)
        self._act(fm,"Save Project (.triply3d)","Ctrl+S",self._save_project)
        fm.addSeparator()
        self._act(fm,"Export Selected…","Ctrl+E",self._export_sel)
        self._act(fm,"Export All Parts…","Ctrl+Shift+E",self._export_all)
        fm.addSeparator()
        self._act(fm,"Quit","Ctrl+Q",self.close)
        em = mb.addMenu("Edit")
        self._act(em,"Undo","Ctrl+Z",self._undo)
        self._act(em,"Redo","Ctrl+Y",self._redo)
        self._act(em,"Redo","Ctrl+Shift+Z",self._redo)
        em.addSeparator()
        self._act(em,"Copy","Ctrl+C",self._copy_sel)
        self._act(em,"Paste","Ctrl+V",self._paste)
        self._act(em,"Duplicate","Ctrl+D",self._duplicate)
        self._act(em,"Select All","Ctrl+A",self._select_all)
        self._act(em,"Rename…","Ctrl+R",self._rename_sel)
        sm = mb.addMenu("Settings")
        self._act(sm,"Mouse Controls…","",self._dlg_mouse)
        self._act(sm,"About Triply…","",self._dlg_about)'''

if old_menu in c:
    c = c.replace(old_menu, new_menu); print("✓ Fixed menu shortcuts")
else:
    print("✗ Menu pattern not found")

# ==========================================================================
# 2. Add undo/redo stack init to __init__
# ==========================================================================
old_init = "        self._last_import_dir = self._cfg.get(\"last_import_dir\", os.path.expanduser(\"~\"))"
new_init = """        self._last_import_dir = self._cfg.get("last_import_dir", os.path.expanduser("~"))
        # Undo/redo stacks — store snapshots of parts state
        self._undo_stack = []   # list of state dicts
        self._redo_stack = []
        self._wireframe  = False
        self._show_grid  = True
        self._ortho_mode = False"""

if old_init in c:
    c = c.replace(old_init, new_init); print("✓ Added undo/redo stack init")
else:
    print("✗ Init anchor not found")

# ==========================================================================
# 3. Replace keyPressEvent with full shortcut handler
# ==========================================================================
old_key = """    def keyPressEvent(self, event):
        if event.key()==Qt.Key.Key_A and event.modifiers()==Qt.KeyboardModifier.ControlModifier:
            self._select_all()
        else:
            super().keyPressEvent(event)"""

new_key = """    def keyPressEvent(self, event):
        key  = event.key()
        mods = event.modifiers()
        ctrl  = mods == Qt.KeyboardModifier.ControlModifier
        shift = mods == Qt.KeyboardModifier.ShiftModifier
        ctrl_shift = mods == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        no_mod = mods == Qt.KeyboardModifier.NoModifier

        # File
        if ctrl and key == Qt.Key.Key_I:   self._import_files()
        elif ctrl and key == Qt.Key.Key_O:  self._open_project()
        elif ctrl and key == Qt.Key.Key_S:  self._save_project()
        elif ctrl and key == Qt.Key.Key_E and not shift: self._export_sel()
        elif ctrl_shift and key == Qt.Key.Key_E: self._export_all()

        # Edit
        elif ctrl and key == Qt.Key.Key_Z:  self._undo()
        elif ctrl and key == Qt.Key.Key_Y:  self._redo()
        elif ctrl_shift and key == Qt.Key.Key_Z: self._redo()
        elif ctrl and key == Qt.Key.Key_C:  self._copy_sel()
        elif ctrl and key == Qt.Key.Key_V:  self._paste()
        elif ctrl and key == Qt.Key.Key_D:  self._duplicate()
        elif ctrl and key == Qt.Key.Key_A:  self._select_all()
        elif ctrl and key == Qt.Key.Key_R:  self._rename_sel()
        elif key == Qt.Key.Key_Escape:      self._deselect_all()
        elif key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace): self._remove_sel()

        # View — snap views
        elif no_mod and key == Qt.Key.Key_F: self._snap_view(0, 0)
        elif no_mod and key == Qt.Key.Key_R: self._snap_view(0, -90)
        elif no_mod and key == Qt.Key.Key_T: self._snap_view(-90, 0)
        elif no_mod and key == Qt.Key.Key_Home: self._snap_view(25, -35)
        elif key == Qt.Key.Key_5 and no_mod: self._toggle_ortho()
        elif key == Qt.Key.Key_H and no_mod: self._toggle_bv()
        elif key == Qt.Key.Key_G and no_mod: self._toggle_grid()
        elif key == Qt.Key.Key_W and no_mod: self._toggle_wireframe()
        elif ctrl_shift and key == Qt.Key.Key_H: self._fit_view()
        elif key == Qt.Key.Key_1 and no_mod and hasattr(Qt.Key,'Key_1'): self._snap_view(0, 0)
        elif key == Qt.Key.Key_3 and no_mod: self._snap_view(0, -90)
        elif key == Qt.Key.Key_7 and no_mod: self._snap_view(-90, 0)
        elif key == Qt.Key.Key_0 and no_mod: self._snap_view(25, -35)

        # Transform
        elif no_mod and key == Qt.Key.Key_BracketLeft:  self._scale_pct_quick(-5)
        elif no_mod and key == Qt.Key.Key_BracketRight: self._scale_pct_quick(+5)
        elif ctrl and key == Qt.Key.Key_G: self._gen_lattice()
        elif ctrl and key == Qt.Key.Key_P and not shift: self._pack_all()
        elif ctrl_shift and key == Qt.Key.Key_P: self._pack_sel()

        # Rotate with X/Y/Z + arrow keys
        elif no_mod and key == Qt.Key.Key_Left:  self._rotate_arrow(-5)
        elif no_mod and key == Qt.Key.Key_Right: self._rotate_arrow(+5)
        elif no_mod and key == Qt.Key.Key_Up:    self._rotate_arrow_ud(-5)
        elif no_mod and key == Qt.Key.Key_Down:  self._rotate_arrow_ud(+5)

        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Shortcut helpers
    # ------------------------------------------------------------------
    def _snap_view(self, rx, ry):
        self.viewport._rot_x = float(rx)
        self.viewport._rot_y = float(ry)
        self.viewport.update()

    def _fit_view(self):
        self.viewport._fit_view()
        self.viewport.update()

    def _toggle_bv(self):
        self.chk_show_bv.setChecked(not self.chk_show_bv.isChecked())

    def _toggle_grid(self):
        self._show_grid = not self._show_grid
        self.viewport._show_grid = self._show_grid
        self.viewport.update()
        self.status.showMessage(f"Grid: {'on' if self._show_grid else 'off'}")

    def _toggle_wireframe(self):
        self._wireframe = not self._wireframe
        self.viewport._wireframe = self._wireframe
        self.viewport.update()
        self.status.showMessage(f"Wireframe: {'on' if self._wireframe else 'off'}")

    def _toggle_ortho(self):
        self._ortho_mode = not self._ortho_mode
        self.viewport._ortho = self._ortho_mode
        self.viewport.update()
        self.status.showMessage(f"Projection: {'orthographic' if self._ortho_mode else 'perspective'}")

    def _scale_pct_quick(self, delta_pct):
        p = self._get_sel()
        if not p: return
        factor = 1.0 + delta_pct / 100.0
        p['verts'] = p['verts'] * factor
        self.viewport.update_mesh(p['mesh_idx'], p['verts'], p['faces'])
        self.status.showMessage(f"Scaled {delta_pct:+d}%: {p['name']}")

    _rotate_axis = 'Z'  # tracks last pressed axis key
    def _rotate_arrow(self, deg):
        self._rotate(self._rotate_axis, deg)
    def _rotate_arrow_ud(self, deg):
        # Up/Down rotates around X when no axis key held
        self._rotate('X', deg)

    def _rename_sel(self):
        p = self._get_sel()
        if not p: return
        self._rename(p['id'])"""

if old_key in c:
    c = c.replace(old_key, new_key); print("✓ Replaced keyPressEvent")
else:
    print("✗ keyPressEvent not found")

# ==========================================================================
# 4. Add undo/redo methods + state snapshot
# ==========================================================================
old_rename = "    def _rename(self, pid):"
new_rename = """    def _push_undo(self):
        \"\"\"Snapshot current parts state onto undo stack.\"\"\"
        import copy
        state = {
            pid: {
                'verts':  p['verts'].copy(),
                'faces':  p['faces'].copy(),
                'offset': p['offset'].copy(),
                'name':   p['name'],
                'locks':  dict(p.get('locks',{})),
            }
            for pid, p in self._parts.items()
        }
        self._undo_stack.append(state)
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _undo(self):
        if not self._undo_stack:
            self.status.showMessage("Nothing to undo."); return
        # Save current to redo
        import copy
        state = {
            pid: {
                'verts':  p['verts'].copy(),
                'faces':  p['faces'].copy(),
                'offset': p['offset'].copy(),
                'name':   p['name'],
                'locks':  dict(p.get('locks',{})),
            }
            for pid, p in self._parts.items()
        }
        self._redo_stack.append(state)
        prev = self._undo_stack.pop()
        self._apply_state(prev)
        self.status.showMessage(f"Undo — {len(self._undo_stack)} step(s) remaining")

    def _redo(self):
        if not self._redo_stack:
            self.status.showMessage("Nothing to redo."); return
        self._push_undo()
        nxt = self._redo_stack.pop()
        self._apply_state(nxt)
        self.status.showMessage("Redo")

    def _apply_state(self, state):
        for pid, s in state.items():
            if pid in self._parts:
                p = self._parts[pid]
                p['verts']  = s['verts']
                p['faces']  = s['faces']
                p['offset'] = s['offset']
                p['name']   = s['name']
                p['locks']  = s['locks']
                self.viewport.update_mesh(p['mesh_idx'], p['verts'], p['faces'])
                self.viewport.set_mesh_offset(p['mesh_idx'], *p['offset'])

    def _rename(self, pid):"""

if old_rename in c:
    c = c.replace(old_rename, new_rename); print("✓ Added undo/redo methods")
else:
    print("✗ _rename anchor not found")

# ==========================================================================
# 5. Push undo before destructive operations
# ==========================================================================
# Before remove
old_rem = """    def _remove_sel(self):
        item = self.tree.currentItem()
        if not item: return
        pid = item.data(0, Qt.ItemDataRole.UserRole)
        if pid=='__lattice__' or pid not in self._parts: return"""
new_rem = """    def _remove_sel(self):
        item = self.tree.currentItem()
        if not item: return
        pid = item.data(0, Qt.ItemDataRole.UserRole)
        if pid=='__lattice__' or pid not in self._parts: return
        self._push_undo()"""

if old_rem in c:
    c = c.replace(old_rem, new_rem); print("✓ Push undo before remove")
else:
    print("✗ remove anchor not found")

# Before scale
old_sc = """    def _scale_pct(self):
        p=self._get_sel()
        if not p or p['locks'].get('type')=='xyz': return"""
new_sc = """    def _scale_pct(self):
        p=self._get_sel()
        if not p or p['locks'].get('type')=='xyz': return
        self._push_undo()"""

if old_sc in c:
    c = c.replace(old_sc, new_sc); print("✓ Push undo before scale_pct")
else:
    print("✗ scale_pct anchor not found")

# Before rotate
old_rot = """    def _rotate(self, axis, deg):
        p=self._get_sel()
        if not p: return"""
new_rot = """    def _rotate(self, axis, deg):
        p=self._get_sel()
        if not p: return
        self._push_undo()"""

if old_rot in c:
    c = c.replace(old_rot, new_rot); print("✓ Push undo before rotate")
else:
    print("✗ rotate anchor not found")

# ==========================================================================
# 6. Add undo/redo buttons to menu bar area (toolbar)
# ==========================================================================
old_build = """    def _build_menu(self):
        mb = self.menuBar()"""
new_build = """    def _build_menu(self):
        mb = self.menuBar()
        # Add undo/redo toolbar buttons via corner widget
        from PyQt6.QtWidgets import QToolBar
        from PyQt6.QtGui import QIcon
        tb = QToolBar()
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setStyleSheet(
            "QToolBar { background: #1c1c1c; border: none; spacing: 2px; padding: 2px 6px; }"
            "QToolButton { background: #2a2a2a; color: #848482; border: 1px solid #3a3a3a; "
            "border-radius: 4px; padding: 3px 10px; font-size: 13px; font-weight: 700; }"
            "QToolButton:hover { background: #363636; color: #e0e0e0; }"
            "QToolButton:pressed { background: #8B0000; color: white; }"
        )
        act_undo = tb.addAction("↩ Undo")
        act_undo.triggered.connect(self._undo)
        act_undo.setShortcut("Ctrl+Z")
        act_redo = tb.addAction("↪ Redo")
        act_redo.triggered.connect(self._redo)
        act_redo.setShortcut("Ctrl+Y")
        self.addToolBar(tb)"""

if old_build in c:
    c = c.replace(old_build, new_build); print("✓ Added undo/redo toolbar")
else:
    print("✗ _build_menu anchor not found")

# ==========================================================================
# 7. Add wireframe support to viewport
# ==========================================================================
vp_path = "/home/orvilleiv/Desktop/Triply Development/Triply/src/viewport.py"
with open(vp_path) as f: vp = f.read()

# Add _wireframe and _ortho flags to __init__
old_vp_init = "        self._layer_pct = 1.0"
new_vp_init = """        self._layer_pct = 1.0
        self._wireframe  = False
        self._ortho      = False
        self._show_grid  = True"""

if old_vp_init in vp:
    vp = vp.replace(old_vp_init, new_vp_init); print("✓ Added viewport flags")
else:
    print("✗ viewport init anchor not found")

# Add wireframe toggle to _draw_mesh
old_dm = """    def _draw_mesh(self, mesh, selected):
        r, g, b = mesh['color']

        # Always use glColor3f — no alpha, no transparency
        if selected:
            # Brighten selected mesh slightly
            glColor3f(min(1.0, r*1.4 + 0.1),
                      min(1.0, g*1.4 + 0.1),
                      min(1.0, b*1.4 + 0.1))
        else:
            glColor3f(r, g, b)

        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_NORMAL_ARRAY)
        glVertexPointer(3, GL_FLOAT, 0, mesh['verts'])
        glNormalPointer(GL_FLOAT, 0, mesh['normals'])
        glDrawElements(GL_TRIANGLES,
                       len(mesh['faces']) * 3,
                       GL_UNSIGNED_INT,
                       mesh['faces'])
        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_NORMAL_ARRAY)"""

new_dm = """    def _draw_mesh(self, mesh, selected):
        r, g, b = mesh['color']

        if selected:
            glColor3f(min(1.0, r*1.4 + 0.1),
                      min(1.0, g*1.4 + 0.1),
                      min(1.0, b*1.4 + 0.1))
        else:
            glColor3f(r, g, b)

        if self._wireframe:
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)

        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_NORMAL_ARRAY)
        glVertexPointer(3, GL_FLOAT, 0, mesh['verts'])
        glNormalPointer(GL_FLOAT, 0, mesh['normals'])
        glDrawElements(GL_TRIANGLES,
                       len(mesh['faces']) * 3,
                       GL_UNSIGNED_INT,
                       mesh['faces'])
        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_NORMAL_ARRAY)

        if self._wireframe:
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)"""

if old_dm in vp:
    vp = vp.replace(old_dm, new_dm); print("✓ Added wireframe to _draw_mesh")
else:
    print("✗ _draw_mesh not found")

# Add ortho projection support to resizeGL
old_rgl = """    def resizeGL(self, w, h):
        self._width  = max(w, 1)
        self._height = max(h, 1)
        glViewport(0, 0, self._width, self._height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        pm = _perspective(45.0, self._width / self._height, 0.1, 10000.0)
        glLoadMatrixf(pm.T)
        glMatrixMode(GL_MODELVIEW)"""

new_rgl = """    def resizeGL(self, w, h):
        self._width  = max(w, 1)
        self._height = max(h, 1)
        self._rebuild_projection()

    def _rebuild_projection(self):
        glViewport(0, 0, self._width, self._height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = self._width / self._height
        if self._ortho:
            scale = self._zoom * 0.005
            glOrtho(-scale*aspect, scale*aspect, -scale, scale, -10000, 10000)
        else:
            pm = _perspective(45.0, aspect, 0.1, 10000.0)
            glLoadMatrixf(pm.T)
        glMatrixMode(GL_MODELVIEW)"""

if old_rgl in vp:
    vp = vp.replace(old_rgl, new_rgl); print("✓ Added ortho projection")
else:
    print("✗ resizeGL not found")

# Update paintGL to call _rebuild_projection when ortho changes
old_pgl = """    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()"""
new_pgl = """    def paintGL(self):
        self._rebuild_projection()
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()"""

if old_pgl in vp:
    vp = vp.replace(old_pgl, new_pgl); print("✓ Projection rebuilt each frame")
else:
    print("✗ paintGL not found")

with open(vp_path, 'w') as f: f.write(vp)

with open(path, 'w') as f: f.write(c)
print("\n=== Done ===")
