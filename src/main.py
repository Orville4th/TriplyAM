"""
Triply — AM Tools and Lattices
By Orville Wright IV. All rights reserved.
"""

import sys, os, json, copy, re
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QDoubleSpinBox, QSpinBox,
    QGroupBox, QFormLayout, QListWidget, QListWidgetItem,
    QMessageBox, QProgressDialog, QCheckBox, QTabWidget,
    QStatusBar, QDialog, QDialogButtonBox,
    QInputDialog, QMenu, QSlider, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QAbstractItemView,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QCursor, QColor, QFont

SRC = os.path.dirname(os.path.abspath(__file__))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from viewport import Viewport3D
from ui.theme import APP_STYLESHEET, ACCENT, NEUTRAL, ACCENT_RGB, NEUTRAL_RGB

CONFIG_PATH = os.path.join(SRC, '..', 'config.json')
MESH_COLOR  = (0.62, 0.62, 0.62)

PRINTERS = {
    "Large Part — No Limits (for really large parts!)": (10000,10000,10000),
    "Formlabs Form 1+ (SLA)":         (125,125,165),
    "Formlabs Form 2 (SLA)":          (145,145,175),
    "Formlabs Form 3 (SLA)":          (145,145,185),
    "Formlabs Form 3+ (SLA)":         (145,145,185),
    "Formlabs Form 3B (SLA)":         (145,145,185),
    "Formlabs Form 3B+ (SLA)":        (145,145,185),
    "Formlabs Form 3L (SLA)":         (335,200,300),
    "Formlabs Form 3BL (SLA)":        (335,200,300),
    "Formlabs Form 4 (mSLA)":         (200,125,210),
    "Formlabs Form 4B (mSLA)":        (200,125,210),
    "Formlabs Form 4L (mSLA)":        (400,250,210),
    "Formlabs Fuse 1+ (SLS)":         (165,165,300),
    "Formlabs Fuse 1+ 30W (SLS)":     (165,165,300),
    "Elegoo Saturn 4 Ultra (MSLA)":   (218,123,220),
    "Phrozen Sonic Mega 8K (MSLA)":   (330,185,400),
    "EOS P 396 (SLS)":                (340,340,600),
    "Sintratec S3 (SLS)":             (370,370,540),
    "3D Systems ProX SLS 6100 (SLS)": (381,330,460),
    "EOS M 290 (DMLS)":               (250,250,325),
    "EOS M 300-4 (DMLS)":             (300,300,400),
    "Trumpf TruPrint 3000 (DMLS)":    (300,300,400),
    "SLM Solutions SLM 500 (DMLS)":   (500,280,365),
    "Renishaw RenAM 500Q (DMLS)":     (250,250,350),
    "3D Systems DMP Flex 350 (DMLS)": (275,275,380),
    "GE Additive Concept M2 (DMLS)":  (245,245,350),
    "HP Multi-Jet Fusion 5600 (MJF)":  (380,284,380),
    "Custom":                          (200,200,200),
}

def load_config():
    try:
        with open(CONFIG_PATH) as f: return json.load(f)
    except: return {}

def save_config(cfg):
    try:
        with open(CONFIG_PATH,'w') as f: json.dump(cfg,f,indent=2)
    except: pass

def slbl(text):
    l = QLabel(text); l.setObjectName("section_label"); return l

def vlbl(text="—"):
    l = QLabel(text); l.setObjectName("value_label"); return l


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------
class ExportWorker(QThread):
    progress = pyqtSignal(str, int)  # message, percent
    finished = pyqtSignal()
    error    = pyqtSignal(str)

    def __init__(self, path, vertices, faces, quality):
        super().__init__()
        self.path=path; self.vertices=vertices
        self.faces=faces; self.quality=quality

    def run(self):
        try:
            import os
            ext=os.path.splitext(self.path)[1].lower()
            self.progress.emit("Preparing mesh...", 10)
            if ext=='.stl':
                self.progress.emit("Writing STL...", 40)
                from triply_io.exporter import export_stl
                export_stl(self.path, self.vertices, self.faces)
            elif ext=='.3mf':
                self.progress.emit("Writing 3MF...", 40)
                from triply_io.exporter import export_3mf
                export_3mf(self.path, self.vertices, self.faces)
            elif ext in ('.step','.stp'):
                self.progress.emit("Writing STEP (slow for large meshes)...", 20)
                from triply_io.exporter import export_step
                export_step(self.path, self.vertices, self.faces, self.quality)
            self.progress.emit("Done!", 100)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class LatticeWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(object, object)
    error    = pyqtSignal(str)

    def __init__(self, stl_verts, wall_t, cell_sz, latt_t,
                 ltype, res, sm_iter, sm_fac, wall_only, cancel_flag, stl_faces=None, step_path=None):
        super().__init__()
        self.stl_verts   = stl_verts
        self.stl_faces   = stl_faces
        self.step_path   = step_path
        self.wall_t      = wall_t
        self.cell_sz     = cell_sz
        self.latt_t      = latt_t
        self.ltype       = ltype
        self.res         = res
        self.sm_iter     = sm_iter
        self.sm_fac      = sm_fac
        self.wall_only   = wall_only
        self.cancel_flag = cancel_flag

    def run(self):
        try:
            from lattice import generate_lattice
            v, f = generate_lattice(
                self.stl_verts, self.wall_t, self.cell_sz, self.latt_t,
                stl_faces=self.stl_faces,
                step_path=self.step_path,
                lattice_type=self.ltype,
                resolution=self.res if self.res > 0 else None,
                smooth_iterations=self.sm_iter,
                smooth_factor=self.sm_fac,
                wall_only=self.wall_only,
                progress_cb=lambda m: self.progress.emit(m),
                cancel_flag=self.cancel_flag,
            )
            self.finished.emit(v, f)
        except InterruptedError:
            self.error.emit("__cancelled__")
        except Exception as e:
            self.error.emit(str(e))


class PackWorker(QThread):
    part_placed = pyqtSignal(str, int, float, float, float)
    finished    = pyqtSignal(object, int)
    cancelled   = pyqtSignal()

    def __init__(self, parts, bv, gap, wall_off, exact, rot_z, rot_xy, cancel_flag):
        super().__init__()
        self.parts       = parts
        self.bv          = bv
        self.gap         = gap
        self.wall_off    = wall_off
        self.exact       = exact
        self.rot_z       = rot_z
        self.rot_xy      = rot_xy
        self.cancel_flag = cancel_flag

    def run(self):
        from packer import pack_parts
        def cb(*args):
            pass  # positions applied in bulk on finish
        placements, n = pack_parts(
            self.parts, *self.bv,
            part_gap=self.gap, wall_offset=self.wall_off,
            exact=self.exact, allow_rot_z=self.rot_z, allow_rot_xy=self.rot_xy,
            progress_cb=cb, cancel_flag=self.cancel_flag,
        )
        if self.cancel_flag and self.cancel_flag[0]:
            self.cancelled.emit()
        else:
            self.finished.emit(placements, n)


class StepSpin(QWidget):
    valueChanged = pyqtSignal(float)
    def __init__(self, lo, hi, val, step, suffix=" mm"):
        super().__init__()
        lay = QHBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(2)
        bd = QPushButton("▼"); bu = QPushButton("▲")
        for b in (bd,bu): b.setFixedSize(24,28); b.setStyleSheet("padding:0;font-size:10px;")
        self.spin = QDoubleSpinBox()
        self.spin.setRange(lo,hi); self.spin.setValue(val)
        self.spin.setSuffix(suffix); self.spin.setDecimals(2)
        self.spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.spin.valueChanged.connect(self.valueChanged.emit)
        bd.clicked.connect(lambda: self.spin.setValue(max(lo, self.spin.value()-step)))
        bu.clicked.connect(lambda: self.spin.setValue(min(hi, self.spin.value()+step)))
        lay.addWidget(bd); lay.addWidget(self.spin,1); lay.addWidget(bu)
    def value(self): return self.spin.value()
    def setValue(self, v): self.spin.setValue(v)
    def setEnabled(self, e): self.spin.setEnabled(e); super().setEnabled(e)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class TripLyWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Triply — AM Tools and Lattices")

        # Load settings first so scale is available
        import os, json as _json
        self._settings_path = os.path.expanduser("~/.triply_settings.json")
        try:
            with open(self._settings_path) as f: self._settings = _json.load(f)
        except: self._settings = {}

        # Apply UI scale — works on any display without hardcoding
        scale = float(self._settings.get('ui_scale', 1.0))
        if scale != 1.0:
            from PyQt6.QtGui import QFont
            font = QApplication.font()
            font.setPointSizeF(font.pointSizeF() * scale)
            QApplication.setFont(font)
        self.resize(int(1440*scale), int(900*scale))

        self._parts         = {}
        self._next_id       = 0
        self._clipboard     = None
        self._bv            = (165,165,300)
        self._n_volumes     = 1
        self._cancel_flag   = [False]
        self._lat_worker    = None
        self._pack_worker   = None
        self._cfg           = load_config()
        self._cfg.setdefault("default_printer","Formlabs Fuse 1+ (SLS)")
        self._cfg.setdefault("custom_printers",{})
        self._cfg.setdefault("mouse_orbit","Right Button")
        self._cfg.setdefault("mouse_pan","Middle Button")
        self._undo_stack = []
        self._redo_stack = []
        self._last_import_dir = self._cfg.get("last_import_dir", os.path.expanduser("~"))
        self._last_export_dir = self._cfg.get("last_export_dir", os.path.expanduser("~"))

        self.setStyleSheet(APP_STYLESHEET)
        self._build_ui()
        self._apply_mouse()
        self._update_bv()
        # Start zoomed to default build volume
        bx,by,bz = self._bv
        self.viewport.fit_to_volume(bx, by, bz)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        self._build_menu()

        central = QWidget(); self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────
        sidebar = QWidget(); sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(280); sidebar.setMaximumWidth(400)
        sb = QVBoxLayout(sidebar); sb.setContentsMargins(0,0,0,0); sb.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(False)
        tb = self.tabs.tabBar()
        tb.setExpanding(True)
        tb.setDrawBase(False)
        self.tabs.setStyleSheet(
            "QTabBar { width: 330px; }"
            "QTabBar::tab { min-width: 0px; padding: 7px 3px; font-size: 10px; font-weight: 700; letter-spacing: 0.02em; }"
        )

        self.tabs.addTab(self._tab_parts(),     "Parts")
        self.tabs.addTab(self._tab_volume(),    "Printer")
        self.tabs.addTab(self._tab_modify(),    "Modify")
        self.tabs.addTab(self._tab_transform(), "Transform")
        self.tabs.addTab(self._tab_pack(),      "Pack")
        self.tabs.addTab(self._tab_export(),    "Export")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        sb.addWidget(self.tabs)

        # ── Viewport + slicer ─────────────────────────────────────────
        vp_container = QWidget()
        vp_lay = QHBoxLayout(vp_container)
        vp_lay.setContentsMargins(0,0,0,0); vp_lay.setSpacing(0)

        self.viewport = Viewport3D()
        self.viewport.part_clicked.connect(self._on_vp_click)
        self.viewport.empty_clicked.connect(self._deselect_all)
        self.viewport.files_dropped.connect(self._on_dropped)
        self.viewport.mesh_moved.connect(self._on_mesh_moved)
        vp_lay.addWidget(self.viewport, 1)

        sp = QWidget()
        sp.setStyleSheet("background:#121212;border-left:1px solid #2a2a2a;")
        from PyQt6.QtWidgets import QSizePolicy as _QSP
        sp.setSizePolicy(_QSP.Policy.Minimum, _QSP.Policy.Expanding)
        spl = QVBoxLayout(sp); spl.setContentsMargins(6,8,6,8)

        self.layer_slider = QSlider(Qt.Orientation.Vertical)
        # Range in 0.1mm steps — updated when printer changes
        bz = self._bv[2]
        self._slider_steps = int(bz / 0.1)
        self.layer_slider.setRange(0, self._slider_steps)
        self.layer_slider.setValue(self._slider_steps)
        self.layer_slider.setSingleStep(1)
        self.layer_slider.setPageStep(10)
        self.layer_slider.valueChanged.connect(self._on_layer)

        bz_init = self._bv[2]
        self.lbl_layer = QLabel(f"{bz_init:.1f}mm")
        self.lbl_layer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_layer.setStyleSheet("color:#ccc;font-size:9px;font-weight:700;")
        spl.addWidget(self.layer_slider,1)
        vp_lay.addWidget(sp)

        # ── Right panel ───────────────────────────────────────────────
        rp_widget = QWidget(); rp_widget.setMinimumWidth(160); rp_widget.setMaximumWidth(260)
        rp_widget.setStyleSheet("background:#181818;")
        rp = QVBoxLayout(rp_widget); rp.setContentsMargins(0,0,0,0); rp.setSpacing(0)

        props = QWidget(); props.setObjectName("props_panel")
        pl = QVBoxLayout(props); pl.setContentsMargins(14,10,10,8); pl.setSpacing(4)
        pl.addWidget(slbl("PROPERTIES"))
        self.prop_name    = QLabel("—"); self.prop_name.setStyleSheet("color:#e0e0e0;font-weight:600;font-size:12px;")
        self.prop_size    = vlbl("X:—  Y:—  Z:—")
        self.prop_vol     = vlbl("Volume: —")
        self.prop_area    = vlbl("Surface: —")
        self.prop_reduce   = vlbl("Reduction: —")
        self.prop_tris     = vlbl("Triangles: —")
        self.prop_density  = vlbl("Volumetric density: —")
        note_style = "color:#555;font-size:10px;"
        for w in (self.prop_name, self.prop_size, self.prop_vol,
                  self.prop_area, self.prop_reduce):
            pl.addWidget(w)
        pl.addWidget(self.prop_tris)
        tri_note = QLabel("Keep under 2M for best performance.")
        tri_note.setWordWrap(True); tri_note.setStyleSheet(note_style)
        pl.addWidget(tri_note)
        pl.addWidget(self.prop_density)
        dens_note = QLabel("Volume of parts relative to total build volume (selected).")
        dens_note.setWordWrap(True); dens_note.setStyleSheet(note_style)
        pl.addWidget(dens_note)
        pl.addStretch()
        rp.addWidget(props, 1)

        ad = QWidget(); ad.setObjectName("ad_banner"); ad.setFixedHeight(70)
        al = QVBoxLayout(ad); al.setContentsMargins(6,4,6,4)
        a_lbl = QLabel("Advertisement\nSupports free development")
        a_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        a_lbl.setStyleSheet("color:#404040;font-size:10px;")
        al.addWidget(a_lbl)
        rp.addWidget(ad)

        root.addWidget(sidebar, 0)
        root.addWidget(vp_container, 1)
        root.addWidget(rp_widget, 0)

        self.status = QStatusBar(); self.status.setFixedHeight(24)
        self.setStatusBar(self.status)

        # Defer initial fit so viewport has real pixel dimensions
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self._initial_fit)
        self.status.showMessage(
            "Triply  |  Right-drag:orbit  Middle-drag:pan  Scroll:zoom  "
            "Left-click:select  Click empty:deselect  Ctrl+A:select all  Drop files to import"
        )

    def _on_tab_changed(self, idx):
        """Auto-select first part when switching to Modify/Transform/Pack tabs."""
        if not hasattr(self, '_parts') or not hasattr(self, '_selected'):
            return
        tab_name = self.tabs.tabText(idx)
        if tab_name in ("Modify", "Transform", "Pack"):
            if self._selected not in self._parts:
                for pid, part in self._parts.items():
                    if part.get('parent') is None:
                        self._select_part(pid)
                        break

    def _initial_fit(self):
        """Called after window is shown so viewport has correct dimensions."""
        bx,by,bz = self._bv
        self.viewport.fit_to_volume(bx,by,bz)

    def _build_menu(self):
        mb = self.menuBar()
        fm = mb.addMenu("File")
        self._act(fm,"New Scene","Ctrl+N",self._new_scene)
        self._act(fm,"Import STL / 3MF / STEP…","Ctrl+I",self._import_files)
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
        sm.addSeparator()
        self._act(sm,"UI Scale…","",self._open_ui_scale_dialog)
        sm.addSeparator()
        self._act(sm,"About Triply…","",self._dlg_about)

    def _act(self, menu, text, shortcut, slot):
        a = QAction(text, self)
        if shortcut: a.setShortcut(shortcut)
        a.triggered.connect(slot); menu.addAction(a)

    # ------------------------------------------------------------------
    # PARTS TAB
    # ------------------------------------------------------------------
    def _tab_parts(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(8,8,8,8); lay.setSpacing(6)
        lay.addWidget(slbl("PARTS TREE"))
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumHeight(260)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_ctx)
        self.tree.currentItemChanged.connect(self._on_tree_sel)
        self.tree.keyPressEvent = self._tree_key
        lay.addWidget(self.tree)
        r = QHBoxLayout(); r.setSpacing(4)
        for txt,fn in [("Import",self._import_files),("Remove",self._remove_sel),
                        ("Copy",self._copy_sel),("Paste",self._paste)]:
            b = QPushButton(txt); b.clicked.connect(fn); r.addWidget(b)
        lay.addLayout(r)
        b = QPushButton("Export Selected as STL"); b.clicked.connect(self._export_sel_stl)
        lay.addWidget(b)
        lay.addStretch(); return w

    # ------------------------------------------------------------------
    # VOLUME TAB
    # ------------------------------------------------------------------
    def _tab_volume(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(8,8,8,8); lay.setSpacing(6)
        lay.addWidget(slbl("PRINTER"))
        self.combo_printer = QComboBox()
        self._rebuild_printers()
        self.combo_printer.currentTextChanged.connect(self._on_printer)
        lay.addWidget(self.combo_printer)
        r = QHBoxLayout(); r.setSpacing(4)
        b1 = QPushButton("+ Custom"); b1.clicked.connect(self._add_custom_printer)
        self.btn_set_default = QPushButton("★ Default")
        self.btn_set_default.clicked.connect(self._set_default_printer)
        b3 = QPushButton("🗑 Delete"); b3.clicked.connect(self._delete_printer)
        b3.setObjectName("btn_danger")
        r.addWidget(b1); r.addWidget(self.btn_set_default); r.addWidget(b3)
        lay.addLayout(r)
        lay.addWidget(slbl("BUILD VOLUME (mm)"))
        form = QFormLayout(); form.setSpacing(5)
        self.spin_bvx = QDoubleSpinBox(); self.spin_bvy = QDoubleSpinBox(); self.spin_bvz = QDoubleSpinBox()
        for sp in (self.spin_bvx,self.spin_bvy,self.spin_bvz):
            sp.setRange(1,5000); sp.setDecimals(1); sp.setSuffix(" mm")
            sp.valueChanged.connect(self._update_bv)
        form.addRow("X:",self.spin_bvx); form.addRow("Y:",self.spin_bvy); form.addRow("Z:",self.spin_bvz)
        lay.addLayout(form)
        self.chk_show_bv = QCheckBox("Show build volume"); self.chk_show_bv.setChecked(True)
        self.chk_show_bv.toggled.connect(lambda v: self.viewport.set_show_build_volume(v) if hasattr(self,'viewport') else None)
        lay.addWidget(self.chk_show_bv)
        default = self._cfg.get("default_printer","Formlabs Fuse 1+ (SLS)")
        idx = self.combo_printer.findText(default)
        self.combo_printer.setCurrentIndex(idx if idx>=0 else 0)
        # Set initial gold styling
        cur = self.combo_printer.currentText()
        self._update_default_btn_style(cur)
        lay.addStretch(); return w

    def _rebuild_printers(self):
        cur = self.combo_printer.currentText() if hasattr(self,'combo_printer') else ""
        self.combo_printer.blockSignals(True); self.combo_printer.clear()
        all_p = dict(PRINTERS); all_p.update(self._cfg.get("custom_printers",{}))
        # Sort alphabetically, Custom always last
        sorted_names = sorted(
            [k for k in all_p if k != "Custom"]
        ) + ["Custom"]
        self.combo_printer.addItems(sorted_names)
        idx = self.combo_printer.findText(cur)
        if idx>=0: self.combo_printer.setCurrentIndex(idx)
        self.combo_printer.blockSignals(False)

    def _on_printer(self, name):
        all_p = dict(PRINTERS); all_p.update(self._cfg.get("custom_printers",{}))
        dims = all_p.get(name,(200,200,200))
        is_c = (name=="Custom")
        for sp in (self.spin_bvx,self.spin_bvy,self.spin_bvz): sp.setEnabled(is_c)
        self.spin_bvx.setValue(dims[0]); self.spin_bvy.setValue(dims[1]); self.spin_bvz.setValue(dims[2])
        self._update_default_btn_style(name)

    def _update_default_btn_style(self, name):
        if not hasattr(self, 'btn_set_default'): return
        is_default = (name == self._cfg.get("default_printer",""))
        if is_default:
            self.btn_set_default.setStyleSheet(
                "background:#9a7c00;color:#ffe066;border:1px solid #c8a800;"
                "border-radius:6px;padding:6px 14px;font-weight:700;"
            )
            self.btn_set_default.setText("★ Default")
        else:
            self.btn_set_default.setStyleSheet("")
            self.btn_set_default.setText("★ Default")

    def _add_custom_printer(self):
        name,ok = QInputDialog.getText(self,"Custom Printer","Name:")
        if not ok or not name.strip(): return
        x,ok = QInputDialog.getDouble(self,"Build Volume","X (mm):",200,1,5000); 
        if not ok: return
        y,ok = QInputDialog.getDouble(self,"Build Volume","Y (mm):",200,1,5000); 
        if not ok: return
        z,ok = QInputDialog.getDouble(self,"Build Volume","Z (mm):",200,1,5000); 
        if not ok: return
        self._cfg.setdefault("custom_printers",{})[name]=[x,y,z]
        save_config(self._cfg); self._rebuild_printers(); self.combo_printer.setCurrentText(name)

    def _set_default_printer(self):
        name = self.combo_printer.currentText()
        self._cfg["default_printer"] = name
        save_config(self._cfg)
        self._update_default_btn_style(name)
        self.status.showMessage(f"Default printer: {name}")

    def _delete_printer(self):
        name = self.combo_printer.currentText()
        if name == "Custom":
            QMessageBox.information(self, "Delete Printer",
                "'Custom' cannot be deleted."); return
        # Check if it's a built-in printer
        if name in PRINTERS:
            QMessageBox.information(
                self, "Delete Printer",
                f"'{name}' is a built-in printer and cannot be deleted. "
                "Only custom printers can be removed."
            )
            return
        # It's a custom printer — confirm and delete
        reply = QMessageBox.question(
            self, "Delete Printer",
            f"Delete custom printer '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            custom = self._cfg.get("custom_printers", {})
            if name in custom:
                del custom[name]
                self._cfg["custom_printers"] = custom
                # If deleted printer was default, reset to Fuse 1+
                if self._cfg.get("default_printer") == name:
                    self._cfg["default_printer"] = "Formlabs Fuse 1+ (SLS)"
                save_config(self._cfg)
                self._rebuild_printers()
                self.status.showMessage(f"Deleted: {name}")

    def _update_bv(self):
        if not hasattr(self,'viewport'): return
        x=self.spin_bvx.value(); y=self.spin_bvy.value(); z=self.spin_bvz.value()
        self._bv=(x,y,z)
        self.viewport.clear_build_volumes()
        for i in range(self._n_volumes):
            self.viewport.add_build_volume(x,y,z, i*(x+20), f"Vol {i+1}")
        self._update_density()
        # Update slider range to match new build volume height in 0.1mm steps
        if hasattr(self,'layer_slider'):
            self._slider_steps = int(z / 0.1)
            self.layer_slider.blockSignals(True)
            self.layer_slider.setRange(0, self._slider_steps)
            self.layer_slider.setValue(self._slider_steps)
            self.layer_slider.blockSignals(False)
            self.lbl_layer.setText(f"{z:.1f}mm")
            if hasattr(self,'lbl_layer_top'):
                self.lbl_layer_top.setText(f"{z:.0f}mm")
        # Fit view to new build volume size
        self.viewport.fit_to_volume(x, y, z)

    # ------------------------------------------------------------------
    # MODIFY TAB
    # ------------------------------------------------------------------
    def _tab_modify(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(8,8,8,8); lay.setSpacing(6)
        lay.addWidget(slbl("SELECTED PART"))
        self.lbl_mod = QLabel("No part selected")
        self.lbl_mod.setStyleSheet("font-size:12px;font-style:italic;color:#848482;")
        lay.addWidget(self.lbl_mod)
        lay.addWidget(slbl("LATTICE TYPE"))
        self.combo_ltype = QComboBox()
        from lattice import LATTICE_NAMES
        self.combo_ltype.addItems(LATTICE_NAMES)
        lay.addWidget(self.combo_ltype)
        lay.addWidget(slbl("PARAMETERS"))
        pf = QFormLayout(); pf.setSpacing(6)
        self.sp_wall  = StepSpin(0.0,20.0,1.5,0.1)
        self.sp_cell  = StepSpin(2.0,50.0,8.0,0.5)
        self.sp_latt  = StepSpin(0.2, 5.0,0.8,0.1)
        self.sp_res = StepSpin(0, 240, 0, 32)
        self.sp_res.spin.setSpecialValueText("Auto")
        pf.addRow("Outer wall (0=none):", self.sp_wall)
        pf.addRow("Cell size:",           self.sp_cell)
        pf.addRow("Lattice wall:",        self.sp_latt)
        pf.addRow("Resolution:",          self.sp_res)
        lay.addLayout(pf)
        self.chk_no_shell = QCheckBox("Lattice only (no outer shell)")
        self.chk_no_shell.toggled.connect(lambda v: self.sp_wall.setEnabled(not v))
        lay.addWidget(self.chk_no_shell)
        lay.addWidget(slbl("SMOOTHING"))
        sf = QFormLayout(); sf.setSpacing(5)
        self.sp_sm_i = StepSpin(0, 20, 2, 1)
        self.sp_sm_f = StepSpin(0.0, 1.0, 0.3, 0.05)
        sf.addRow("Passes:", self.sp_sm_i); sf.addRow("Factor:", self.sp_sm_f)
        lay.addLayout(sf)
        sm_note = QLabel(
            "<b>Passes</b> — number of smoothing iterations. "
            "0 = off (fastest, most faceted). 2 = recommended. "
            "Higher = rounder struts but slower and may shrink thin features.<br><br>"
            "<b>Factor</b> — blend strength per pass (0.0–1.0). "
            "0.3 = subtle rounding. 0.5 = moderate. "
            "Higher values smooth more aggressively but can distort strut thickness."
        )
        sm_note.setWordWrap(True)
        sm_note.setStyleSheet("color:#666;font-size:10px;padding:4px 0px;")
        lay.addWidget(sm_note)
        self.btn_gen = QPushButton("Generate Lattice")
        self.btn_gen.setObjectName("btn_primary"); self.btn_gen.clicked.connect(self._gen_lattice)
        lay.addWidget(self.btn_gen)
        self.lat_prog = QProgressBar(); self.lat_prog.setVisible(False)
        self.lat_prog.setRange(0,100); self.lat_prog.setValue(0)
        self.lat_prog.setTextVisible(True); self.lat_prog.setFormat("%p%")
        lay.addWidget(self.lat_prog)
        btn_cancel_lat = QPushButton("Cancel"); btn_cancel_lat.setObjectName("btn_danger")
        btn_cancel_lat.clicked.connect(lambda: self._cancel_flag.__setitem__(0,True))
        btn_cancel_lat.setVisible(False); self._btn_cancel_lat = btn_cancel_lat
        lay.addWidget(btn_cancel_lat)
        lay.addStretch(); return w

    # ------------------------------------------------------------------
    # PACK TAB
    # ------------------------------------------------------------------
    def _tab_pack(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(8,8,8,8); lay.setSpacing(6)
        lay.addWidget(slbl("INSTANCES"))
        self.pack_list = QListWidget(); self.pack_list.setMaximumHeight(120)
        lay.addWidget(self.pack_list)
        lay.addWidget(slbl("OPTIONS"))
        pf = QFormLayout(); pf.setSpacing(5)
        self.spin_spacing = QDoubleSpinBox(); self.spin_spacing.setRange(0.5,100); self.spin_spacing.setValue(2.0); self.spin_spacing.setSuffix(" mm"); self.spin_spacing.setDecimals(1)
        self.spin_wall_off = QDoubleSpinBox(); self.spin_wall_off.setRange(0,100); self.spin_wall_off.setValue(5.0); self.spin_wall_off.setSuffix(" mm"); self.spin_wall_off.setDecimals(1)
        self.spin_wall_off.setToolTip("Minimum distance from any part to the build volume wall")
        pf.addRow("Part spacing:", self.spin_spacing)
        pf.addRow("Distance to wall:", self.spin_wall_off)
        lay.addLayout(pf)

        self.chk_quick = QCheckBox("Quick pack (bounding box — faster)")
        self.chk_quick.setChecked(False); lay.addWidget(self.chk_quick)
        self.chk_rot_z  = QCheckBox("Allow Z rotation"); self.chk_rot_z.setChecked(True); lay.addWidget(self.chk_rot_z)
        self.chk_rot_xy = QCheckBox("Allow XY rotation"); self.chk_rot_xy.setChecked(False); lay.addWidget(self.chk_rot_xy)
        r = QHBoxLayout(); r.setSpacing(4)
        b1 = QPushButton("Pack Selected"); b1.clicked.connect(self._pack_sel)
        b2 = QPushButton("Pack All"); b2.setObjectName("btn_primary"); b2.clicked.connect(self._pack_all)
        r.addWidget(b1); r.addWidget(b2); lay.addLayout(r)
        self.pack_prog = QProgressBar(); self.pack_prog.setVisible(False); self.pack_prog.setRange(0,0)
        lay.addWidget(self.pack_prog)
        self.btn_cancel_pack = QPushButton("Cancel Packing"); self.btn_cancel_pack.setObjectName("btn_danger")
        self.btn_cancel_pack.setVisible(False); self.btn_cancel_pack.clicked.connect(self._cancel_pack)
        lay.addWidget(self.btn_cancel_pack)
        self.lbl_pack_status = QLabel(""); self.lbl_pack_status.setStyleSheet("color:#848482;font-size:11px;"); self.lbl_pack_status.setWordWrap(True)
        lay.addWidget(self.lbl_pack_status)
        lay.addStretch(); return w

    # ------------------------------------------------------------------
    # TRANSFORM TAB
    # ------------------------------------------------------------------
    def _tab_transform(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(8,8,8,8); lay.setSpacing(6)
        lay.addWidget(slbl("SELECTED PART"))
        self.lbl_xf = QLabel("No part selected"); self.lbl_xf.setStyleSheet("font-size:12px;font-style:italic;color:#848482;")
        lay.addWidget(self.lbl_xf)

        # XYZ Position
        pg = QGroupBox("Position (mm)"); pf = QFormLayout(pg); pf.setSpacing(5)
        self.sp_pos_x = QDoubleSpinBox(); self.sp_pos_y = QDoubleSpinBox(); self.sp_pos_z = QDoubleSpinBox()
        for sp in (self.sp_pos_x, self.sp_pos_y, self.sp_pos_z):
            sp.setRange(-9999, 9999); sp.setDecimals(2); sp.setSuffix(" mm")
        pf.addRow("X:", self.sp_pos_x)
        pf.addRow("Y:", self.sp_pos_y)
        pf.addRow("Z:", self.sp_pos_z)
        b_pos = QPushButton("Apply Position"); b_pos.clicked.connect(self._apply_position)
        pf.addRow(b_pos)
        lay.addWidget(pg)

        sg = QGroupBox("Scale"); sf = QVBoxLayout(sg)
        pr = QHBoxLayout()
        self.sp_pct = QDoubleSpinBox(); self.sp_pct.setRange(1,10000); self.sp_pct.setValue(100); self.sp_pct.setSuffix(" %")
        bp = QPushButton("Apply %"); bp.clicked.connect(self._scale_pct)
        pr.addWidget(self.sp_pct,1); pr.addWidget(bp); sf.addLayout(pr)
        mr = QHBoxLayout()
        self.sp_sx=QDoubleSpinBox(); self.sp_sy=QDoubleSpinBox(); self.sp_sz=QDoubleSpinBox()
        for sp,lbl in [(self.sp_sx,"X"),(self.sp_sy,"Y"),(self.sp_sz,"Z")]:
            sp.setRange(0.001,9999); sp.setValue(10); sp.setSuffix("mm"); sp.setDecimals(2)
            mr.addWidget(QLabel(lbl+":")); mr.addWidget(sp)
        bm = QPushButton("Apply mm"); bm.clicked.connect(self._scale_mm)
        sf.addLayout(mr); sf.addWidget(bm); lay.addWidget(sg)
        rg = QGroupBox("Rotate (5° steps)"); rf = QFormLayout(rg); rf.setSpacing(4)
        for axis in ['X','Y','Z']:
            row = QHBoxLayout()
            for deg,lbl in [(-5,"◄ −5°"),(+5,"+5° ►")]:
                b = QPushButton(lbl); b.clicked.connect(lambda _,a=axis,d=deg: self._rotate(a,d)); row.addWidget(b)
            rf.addRow(f"Rot {axis}:", row)
        lay.addWidget(rg)
        lg = QGroupBox("Lock Transform"); lf = QVBoxLayout(lg)
        self.chk_lock_xy  = QCheckBox("Lock XY rotation"); self.chk_lock_xyz = QCheckBox("Lock XYZ rotation")
        lf.addWidget(self.chk_lock_xy); lf.addWidget(self.chk_lock_xyz); lay.addWidget(lg)
        br = QPushButton("Reset Transform"); br.clicked.connect(self._reset_xf); lay.addWidget(br)
        lay.addStretch(); return w

    # ------------------------------------------------------------------
    # EXPORT TAB
    # ------------------------------------------------------------------
    def _tab_export(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(8,8,8,8); lay.setSpacing(6)
        lay.addWidget(slbl("EXPORT"))
        for txt,slot in [("Export Selected…",self._export_sel),
                          ("Export All Parts…",self._export_all),
                          ("Export Packed Scene…",self._export_packed)]:
            b = QPushButton(txt); b.clicked.connect(slot); lay.addWidget(b)
        lay.addWidget(slbl("QUALITY PRESET"))
        self.combo_quality = QComboBox()
        self.combo_quality.addItems(["Low (0.5mm)","Medium (0.1mm)","High (0.001mm)"])
        self.combo_quality.setCurrentIndex(2); lay.addWidget(self.combo_quality)
        note = QLabel("Parts with lattice applied export as a single fused mesh.")
        note.setStyleSheet("color:#555;font-size:11px;"); note.setWordWrap(True); lay.addWidget(note)
        self.exp_status = QLabel(""); self.exp_status.setVisible(False)
        self.exp_status.setStyleSheet("color:#848482;font-size:11px;"); self.exp_status.setWordWrap(True)
        lay.addWidget(self.exp_status)
        self.exp_prog = QProgressBar(); self.exp_prog.setVisible(False)
        self.exp_prog.setRange(0,100); self.exp_prog.setValue(0)
        self.exp_prog.setTextVisible(True); self.exp_prog.setFormat("%p%")
        lay.addWidget(self.exp_prog)
        lay.addStretch(); return w

    # ------------------------------------------------------------------
    # Key handling
    # ------------------------------------------------------------------
    def keyPressEvent(self, event):
        key  = event.key()
        mods = event.modifiers()
        ctrl       = mods == Qt.KeyboardModifier.ControlModifier
        ctrl_shift = mods == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        no_mod     = mods == Qt.KeyboardModifier.NoModifier

        # File
        if   ctrl and key == Qt.Key.Key_N:  self._new_scene()
        elif ctrl and key == Qt.Key.Key_I:  self._import_files()
        elif ctrl and key == Qt.Key.Key_O:  self._open_project()
        elif ctrl and key == Qt.Key.Key_S:  self._save_project()
        elif ctrl and key == Qt.Key.Key_E and not ctrl_shift: self._export_sel()
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
        # View
        elif no_mod and key == Qt.Key.Key_F: self._snap_view(0, 0)
        elif no_mod and key == Qt.Key.Key_R: self._snap_view(0, -90)
        elif no_mod and key == Qt.Key.Key_T: self._snap_view(-90, 0)
        elif no_mod and key == Qt.Key.Key_Home: self._snap_view(25, -35)
        elif no_mod and key == Qt.Key.Key_H: self._toggle_bv()
        elif no_mod and key == Qt.Key.Key_G: self._toggle_grid()
        elif no_mod and key == Qt.Key.Key_W: self._toggle_wireframe()
        elif ctrl_shift and key == Qt.Key.Key_H: self._fit_view()
        # Transform
        elif no_mod and key == Qt.Key.Key_BracketLeft:  self._scale_pct_quick(-5)
        elif no_mod and key == Qt.Key.Key_BracketRight: self._scale_pct_quick(+5)
        elif ctrl and key == Qt.Key.Key_G:  self._gen_lattice()
        elif ctrl and key == Qt.Key.Key_P and not ctrl_shift: self._pack_all()
        elif ctrl_shift and key == Qt.Key.Key_P: self._pack_sel()
        else:
            super().keyPressEvent(event)

    def _tree_key(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._remove_sel()
        else:
            QTreeWidget.keyPressEvent(self.tree, event)

    # ------------------------------------------------------------------
    # Parts
    # ------------------------------------------------------------------
    def _new_scene(self):
        if self._parts:
            reply = QMessageBox.question(
                self, "New Scene",
                "Clear all parts and start a new scene?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        # Remove all meshes from viewport
        for p in self._parts.values():
            self.viewport.remove_mesh(p['mesh_idx'])
        # Remove any clone meshes
        live = {p['mesh_idx'] for p in self._parts.values()}
        for idx in list(self.viewport._meshes.keys()):
            if idx not in live:
                self.viewport.remove_mesh(idx)
        self._parts.clear()
        self.tree.clear()
        self._n_volumes = 1
        self._update_bv()
        self._refresh_pack_list()
        self.prop_name.setText("—")
        self.prop_size.setText("X:—  Y:—  Z:—")
        self.prop_vol.setText("Volume: —")
        self.prop_area.setText("Surface: —")
        self.prop_reduce.setText("Reduction: —")
        self.prop_density.setText("Volumetric density: —")
        self.viewport.set_selected(-1)
        self.viewport.update()
        self.status.showMessage("New scene — ready to import.")

    def _import_files(self):
        paths,_ = QFileDialog.getOpenFileNames(
            self,"Import Files", self._last_import_dir,
            "3D Files (*.stl *.3mf *.step *.stp);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if paths:
            # Only accept files — validate each path is a real file
            valid = [p for p in paths if os.path.isfile(p)
                     and p.lower().endswith(('.stl','.3mf','.step','.stp'))]
            if valid:
                d = os.path.dirname(os.path.abspath(valid[0]))
                self._last_import_dir = d
                self._cfg["last_import_dir"] = d
                save_config(self._cfg)
                for p in valid:
                    self._load_file(p)

    def _on_dropped(self, paths):
        for p in paths: self._load_file(p)

    def _load_file(self, path):
        try:
            from triply_io.importer import import_file
            verts,faces,name = import_file(path)
            self._push_undo()
            self._add_part(name, path, verts, faces)
        except Exception as e:
            QMessageBox.critical(self,"Import Error",str(e))

    def _add_part(self, name, path, verts, faces, parent_id=None):
        from mesh_repair import compute_volume, compute_surface_area, compute_bbox
        # Check if part exceeds build volume and warn user
        if parent_id is None and hasattr(self,'_bv'):
            bx,by,bz=self._bv
            dx=float(verts[:,0].max()-verts[:,0].min())
            dy=float(verts[:,1].max()-verts[:,1].min())
            dz=float(verts[:,2].max()-verts[:,2].min())
            if dx>bx or dy>by or dz>bz:
                # Find smallest fitting printer
                all_p=dict(PRINTERS); all_p.update(self._cfg.get("custom_printers",{}))
                suggestions=[n for n,dims in all_p.items()
                             if dims[0]>=dx and dims[1]>=dy and dims[2]>=dz]
                msg=f"'{name}' ({dx:.0f}×{dy:.0f}×{dz:.0f}mm) is larger than the current build volume ({bx:.0f}×{by:.0f}×{bz:.0f}mm)."
                if suggestions:
                    msg+=f"\n\nSuggested printers that fit this part:\n" + "\n".join(f"  • {s}" for s in suggestions[:5])
                else:
                    msg+="\n\nNo printer in your list fits this part. Consider using 'Large Part — No Limits'."
                QMessageBox.warning(self,"Part Exceeds Build Volume",msg)
        pid = self._next_id; self._next_id += 1
        mesh_idx = self.viewport.add_mesh(verts, faces, color=MESH_COLOR)
        part = {
            'id':pid,'name':name,'path':path,'verts':verts,'faces':faces,
            'mesh_idx':mesh_idx,'offset':np.zeros(3,dtype=np.float32),
            'instances':1,'locks':{},'parent':parent_id,'children':[],
            'volume':compute_volume(verts,faces),
            'area':compute_surface_area(verts,faces),
            'bbox':compute_bbox(verts),
        }
        self._parts[pid] = part
        disp = name if len(name)<=28 else name[:26]+'…'
        item = QTreeWidgetItem([f"  {disp}"])
        item.setToolTip(0, name)
        item.setData(0, Qt.ItemDataRole.UserRole, pid)
        if parent_id is not None:
            pi = self._find_item(parent_id)
            if pi: pi.addChild(item); pi.setExpanded(True)
            else: self.tree.addTopLevelItem(item)
        else:
            self.tree.addTopLevelItem(item)
        self._refresh_pack_list()
        self._update_density()
        self.status.showMessage(f"Loaded: {name}")
        return pid
        return pid

    def _remove_sel(self):
        item = self.tree.currentItem()
        if not item: return
        pid = item.data(0, Qt.ItemDataRole.UserRole)
        if pid=='__lattice__' or pid not in self._parts: return
        self._push_undo()
        part = self._parts[pid]
        self.viewport.remove_mesh(part['mesh_idx'])
        del self._parts[pid]
        (item.parent() or self.tree.invisibleRootItem()).removeChild(item)
        self._refresh_pack_list(); self._update_density()

    def _save_settings(self):
        import os, json as _json
        try:
            with open(self._settings_path,'w') as f: _json.dump(self._settings,f,indent=2)
        except: pass

    def _open_ui_scale_dialog(self):
        """Let user set UI scale factor for their display."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton
        dlg=QDialog(self); dlg.setWindowTitle("UI Scale"); dlg.setFixedWidth(300)
        lay=QVBoxLayout(dlg)
        lay.addWidget(QLabel("Select UI scale for your display:"))
        combo=QComboBox()
        options=[("100% (default)",1.0),("110%",1.1),("125%",1.25),("150%",1.5),("175%",1.75),("200%",2.0)]
        current=float(self._settings.get('ui_scale',1.0))
        for label,val in options:
            combo.addItem(label,val)
        for i,(_,val) in enumerate(options):
            if abs(val-current)<0.01: combo.setCurrentIndex(i)
        lay.addWidget(combo)
        note=QLabel("Restart Triply to apply the new scale.")
        note.setStyleSheet("color:#888;font-size:11px;"); note.setWordWrap(True)
        lay.addWidget(note)
        btns=QHBoxLayout()
        ok=QPushButton("Apply & Restart"); cancel=QPushButton("Cancel")
        btns.addWidget(ok); btns.addWidget(cancel); lay.addLayout(btns)
        cancel.clicked.connect(dlg.reject)
        def apply():
            self._settings['ui_scale']=combo.currentData()
            self._save_settings()
            dlg.accept()
            import subprocess, sys
            subprocess.Popen([sys.executable]+sys.argv)
            QApplication.quit()
        ok.clicked.connect(apply)
        dlg.exec()

    def _cleanup_build_volumes(self):
        """Remove empty build volumes — recalculate how many are needed."""
        if not self._parts:
            self._n_volumes = 1
            self._update_bv()
            return
        bv_x = self._bv[0]
        # Find the highest volume index actually used by a part
        max_vol = 0
        for p in self._parts.values():
            ox = float(p['offset'][0])
            # Work out which volume this part is in based on X offset
            vol_idx = int(ox / (bv_x + 20)) if (bv_x + 20) > 0 else 0
            max_vol = max(max_vol, vol_idx)
        needed = max_vol + 1
        if needed < self._n_volumes:
            self._n_volumes = needed
            self._update_bv()
            self.status.showMessage(
                f"Removed empty build volume — {needed} volume(s) remaining."
            )

    def _deselect_all(self):
        """Called when user clicks empty space in viewport."""
        self.tree.clearSelection()
        self.tree.setCurrentItem(None)
        for p in self._parts.values():
            self.viewport.set_mesh_color(p['mesh_idx'], MESH_COLOR)
        self.viewport.set_selected(-1)
        self.viewport.update()
        self._update_props()

    def _select_all(self):
        for p in self._parts.values():
            if p.get('parent') is None:
                self.viewport.set_mesh_color(p['mesh_idx'], ACCENT_RGB)
        self.tree.selectAll()
        self.status.showMessage(f"Selected all {len(self._parts)} parts")
        self._update_props()

    def _copy_sel(self):
        p = self._get_sel()
        if p: self._clipboard=copy.deepcopy(p); self.status.showMessage(f"Copied: {p['name']}")

    def _paste(self):
        if not self._clipboard: self.status.showMessage("Nothing to paste."); return
        self._push_undo()
        c = copy.deepcopy(self._clipboard)
        c['verts'] = c['verts'] + 10
        base = self._clipboard['name']
        # Strip existing suffix like " (2)" to get clean base name
        import re
        base = re.sub(r' \(\d+\)$', '', os.path.splitext(base)[0])
        ext  = os.path.splitext(self._clipboard['name'])[1]
        # Find highest existing iteration
        existing = [p['name'] for p in self._parts.values()]
        n = 1
        while f"{base} ({n}){ext}" in existing:
            n += 1
        new_name = f"{base} ({n}){ext}"
        pid = self._add_part(new_name, c.get('path'), c['verts'], c['faces'])

        # Copy lattice metadata and tree label to pasted part
        if pid is not None and c.get('has_lattice') and pid in self._parts:
            self._parts[pid]['has_lattice'] = True
            self._parts[pid]['lattice_type'] = c.get('lattice_type', '')
            self._parts[pid]['volume_with_lattice'] = c.get('volume_with_lattice', 0)
            self._parts[pid]['volume_original'] = c.get('volume_original', c.get('volume', 0))
            ltype = c.get('lattice_type', 'Lattice')
            pi = self._find_item(pid)
            if pi:
                li = QTreeWidgetItem([f"    ◈ {ltype}"])
                li.setData(0, Qt.ItemDataRole.UserRole, '__lattice__')
                li.setFlags(Qt.ItemFlag.NoItemFlags)
                li.setForeground(0, QColor(ACCENT))
                f2 = li.font(0); f2.setItalic(True); f2.setPointSize(10); li.setFont(0, f2)
                pi.addChild(li); pi.setExpanded(True)

    def _duplicate(self):
        p = self._get_sel()
        if not p: return
        self._push_undo()
        self._clipboard = copy.deepcopy(p)
        # Offset slightly so duplicate doesn't sit exactly on original
        self._clipboard['verts'] = p['verts'].copy()
        self._paste()

    def _on_tree_sel(self, current, previous):
        if not current: return
        pid = current.data(0, Qt.ItemDataRole.UserRole)
        if pid=='__lattice__' or pid not in self._parts:
            if previous:
                self.tree.blockSignals(True); self.tree.setCurrentItem(previous); self.tree.blockSignals(False)
            return
        self._select_part(pid)
        self._update_props(pid)

    def _on_mesh_moved(self, mesh_idx, x, y, z):
        """Called when gizmo drag finishes — sync part offset."""
        for p in self._parts.values():
            if p['mesh_idx'] == mesh_idx:
                p['offset'] = np.array([x,y,z], dtype=np.float32)
                # Update position spinboxes
                if hasattr(self,'sp_pos_x'):
                    self.sp_pos_x.blockSignals(True); self.sp_pos_x.setValue(x); self.sp_pos_x.blockSignals(False)
                    self.sp_pos_y.blockSignals(True); self.sp_pos_y.setValue(y); self.sp_pos_y.blockSignals(False)
                    self.sp_pos_z.blockSignals(True); self.sp_pos_z.setValue(z); self.sp_pos_z.blockSignals(False)
                break

    def _on_vp_click(self, mesh_idx):
        for pid,p in self._parts.items():
            if p['mesh_idx']==mesh_idx:
                item = self._find_item(pid)
                if item: self.tree.setCurrentItem(item)
                self._select_part(pid)
                break

    def _select_part(self, pid):
        for p in self._parts.values():
            self.viewport.set_mesh_color(p['mesh_idx'],
                ACCENT_RGB if p['id']==pid else MESH_COLOR)
        part = self._parts[pid]
        self.lbl_mod.setText(f"◻  {part['name']}")
        self.lbl_xf.setText(f"◻  {part['name']}")
        v = part['verts']
        self.sp_sx.setValue(float(v[:,0].max()-v[:,0].min()))
        self.sp_sy.setValue(float(v[:,1].max()-v[:,1].min()))
        self.sp_sz.setValue(float(v[:,2].max()-v[:,2].min()))
        # Update position spinboxes from current offset
        off = part.get('offset', np.zeros(3))
        self.sp_pos_x.setValue(float(off[0]))
        self.sp_pos_y.setValue(float(off[1]))
        self.sp_pos_z.setValue(float(off[2]))
        self.viewport.set_selected(part['mesh_idx'])
        self._update_props(pid)
        self.viewport.update()

    def _get_sel(self):
        item = self.tree.currentItem()
        if not item: return None
        pid = item.data(0, Qt.ItemDataRole.UserRole)
        if pid=='__lattice__': return None
        return self._parts.get(pid)

    def _find_item(self, pid):
        def search(item):
            if item.data(0,Qt.ItemDataRole.UserRole)==pid: return item
            for i in range(item.childCount()):
                r=search(item.child(i))
                if r: return r
            return None
        for i in range(self.tree.topLevelItemCount()):
            r=search(self.tree.topLevelItem(i))
            if r: return r
        return None

    def _tree_ctx(self, pos):
        item=self.tree.currentItem(); pid=item.data(0,Qt.ItemDataRole.UserRole) if item else None
        menu=QMenu()
        menu.addAction("Import Files…",self._import_files)
        if pid and pid!='__lattice__' and pid in self._parts:
            menu.addSeparator()
            menu.addAction("Apply Lattice", lambda: (self.tabs.setCurrentIndex(2),self._gen_lattice()))
            menu.addAction("Pack Selected", self._pack_sel)
            menu.addSeparator()
            menu.addAction("Copy",self._copy_sel); menu.addAction("Paste",self._paste)
            menu.addAction("Duplicate",self._duplicate)
            menu.addSeparator()
            menu.addAction("Rename…", lambda: self._rename(pid))
            menu.addAction("Lock XY",  lambda: self._lock(pid,"xy"))
            menu.addAction("Lock XYZ", lambda: self._lock(pid,"xyz"))
            menu.addAction("Clear Lock",lambda: self._lock(pid,"none"))
            menu.addSeparator()
            menu.addAction("Delete",self._remove_sel)
        menu.exec(QCursor.pos())

    def _rename(self, pid):
        if pid not in self._parts: return
        n,ok = QInputDialog.getText(self,"Rename","Name:",text=self._parts[pid]['name'])
        if ok and n.strip():
            self._parts[pid]['name']=n
            item=self._find_item(pid)
            if item: item.setText(0,f"  {n}")

    def _lock(self, pid, t):
        if pid in self._parts:
            self._parts[pid]['locks']={'type':t}
            self.status.showMessage(f"Lock {t}: {self._parts[pid]['name']}")

    def _refresh_pack_list(self):
        self.pack_list.clear()
        for p in self._parts.values():
            if p.get('parent') is None:
                self.pack_list.addItem(f"◻  {p['name']}  ×{p.get('instances',1)}")

    # ------------------------------------------------------------------
    # Build volume
    # ------------------------------------------------------------------
    def _update_density(self):
        bx,by,bz = self._bv
        bv_vol = bx*by*bz
        if bv_vol>0:
            total = sum(p.get('volume',0) for p in self._parts.values() if p.get('parent') is None)
            self.prop_density.setText(f"Volumetric density: {total/bv_vol*100:.1f}%")
        else:
            self.prop_density.setText("Volumetric density: —")

    def _update_props(self, pid=None):
        """Update properties panel. Shows single part or aggregate of all selected."""
        selected_items = self.tree.selectedItems()
        # Filter to real parts only (not lattice labels)
        sel_pids = []
        for item in selected_items:
            p = item.data(0, Qt.ItemDataRole.UserRole)
            if p != '__lattice__' and p in self._parts:
                sel_pids.append(p)

        # Also include pid if passed and not already included
        if pid and pid in self._parts and pid not in sel_pids:
            sel_pids = [pid]

        if not sel_pids:
            # Nothing selected — show totals for all top-level parts
            top = [p for p in self._parts.values() if p.get('parent') is None]
            if not top:
                self.prop_name.setText("—")
                self.prop_size.setText("X:—  Y:—  Z:—")
                self.prop_vol.setText("Volume: —")
                self.prop_area.setText("Surface: —")
                self.prop_reduce.setText("Vol. Reduction: —")
                self.prop_tris.setText("Triangles: —")
                self._update_density(); return
            total_vol  = sum(p.get('volume',0) for p in top)
            total_area = sum(p.get('area',0) for p in top)
            total_tris = sum(len(p['faces']) for p in top)
            self.prop_name.setText(f"All parts ({len(top)})")
            self.prop_name.setToolTip("")
            self.prop_size.setText("—")
            self.prop_vol.setText(f"Total vol: {total_vol:.2f} mm³")
            self.prop_area.setText(f"Total area: {total_area:.2f} mm²")
            self.prop_reduce.setText("Vol. Reduction: —")
            self.prop_tris.setText(f"Triangles: {total_tris/1e6:.2f}M" if total_tris>=1_000_000 else
                                   f"Triangles: {total_tris/1000:.1f}K" if total_tris>=1_000 else
                                   f"Triangles: {total_tris}")
            self._update_density(); return

        if len(sel_pids) == 1:
            # Single selection — show full detail
            p  = self._parts[sel_pids[0]]
            bb = p['bbox']
            name_str = p['name'] if len(p['name'])<=22 else p['name'][:20]+'…'
            self.prop_name.setText(name_str)
            self.prop_name.setToolTip(p['name'])
            self.prop_size.setText(f"X:{bb[0]:.1f}  Y:{bb[1]:.1f}  Z:{bb[2]:.1f} mm")
            self.prop_vol.setText(f"Vol: {p['volume']:.2f} mm³")
            self.prop_area.setText(f"Area: {p['area']:.2f} mm²")
            if p.get('has_lattice') and 'volume_with_lattice' in p:
                orig = p.get('volume_original', p['volume'])
                after = p['volume_with_lattice']
                if orig > 0:
                    pct = (orig - after) / orig * 100
                    self.prop_reduce.setText(f"Vol. Reduction: {pct:.1f}%")
                else:
                    self.prop_reduce.setText("Vol. Reduction: —")
            else:
                self.prop_reduce.setText("Vol. Reduction: 0%")
            tc=len(p['faces'])
            self.prop_tris.setText(f"Triangles: {tc/1e6:.2f}M" if tc>=1_000_000 else
                                   f"Triangles: {tc/1000:.1f}K" if tc>=1_000 else
                                   f"Triangles: {tc}")
        else:
            # Multi selection — show aggregates
            parts = [self._parts[pid] for pid in sel_pids]
            total_vol  = sum(p.get('volume',0) for p in parts)
            total_area = sum(p.get('area',0) for p in parts)
            total_tris = sum(len(p['faces']) for p in parts)
            self.prop_name.setText(f"{len(parts)} parts selected")
            self.prop_name.setToolTip("")
            self.prop_size.setText("—")
            self.prop_vol.setText(f"Total vol: {total_vol:.2f} mm³")
            self.prop_area.setText(f"Total area: {total_area:.2f} mm²")
            self.prop_reduce.setText("Vol. Reduction: —")
            self.prop_tris.setText(f"Triangles: {total_tris/1e6:.2f}M" if total_tris>=1_000_000 else
                                   f"Triangles: {total_tris/1000:.1f}K" if total_tris>=1_000 else
                                   f"Triangles: {total_tris}")

        self._update_density()

    # ------------------------------------------------------------------
    # Packing
    # ------------------------------------------------------------------
    def _pack_sel(self):
        p=self._get_sel()
        if not p: QMessageBox.information(self,"Pack","Select a part first."); return
        self._do_pack([p])

    def _pack_all(self):
        top=[p for p in self._parts.values() if p.get('parent') is None]
        if not top: QMessageBox.information(self,"Pack","No parts loaded."); return
        self._do_pack(top)

    def _do_pack(self, parts):
        self._cancel_flag=[False]
        self.pack_prog.setVisible(True); self.btn_cancel_pack.setVisible(True)
        self.lbl_pack_status.setText("Packing…")

        # Reset placement tracker for fresh pack
        self._placement_tracker = {}
        # Reset ALL parts (not just the ones being packed) to origin
        # so previously packed parts don't ghost in old positions
        for p in self._parts.values():
            p['offset'] = np.zeros(3, dtype=np.float32)
            self.viewport.set_mesh_offset(p['mesh_idx'], 0, 0, 0)

        # Remove any visual clones from previous pack
        live_indices = {p['mesh_idx'] for p in self._parts.values()}
        dead = [idx for idx in list(self.viewport._meshes.keys())
                if idx not in live_indices]
        for idx in dead:
            self.viewport.remove_mesh(idx)

        # Reset to single build volume
        self._n_volumes = 1
        self._update_bv()
        self.viewport.update()

        self._pack_worker = PackWorker(
            parts, self._bv,
            self.spin_spacing.value(), self.spin_wall_off.value(),
            not self.chk_quick.isChecked(),
            self.chk_rot_z.isChecked(), self.chk_rot_xy.isChecked(),
            self._cancel_flag
        )
        self._pack_worker.part_placed.connect(self._on_placed)
        self._pack_worker.finished.connect(self._on_pack_finished)
        self._pack_worker.cancelled.connect(self._on_pack_cancelled)
        self._pack_worker.start()

    def _on_placed(self, name, vol_idx, px, py, pz):
        bv_x = self._bv[0]
        ox   = vol_idx * (bv_x + 20)

        if not hasattr(self, '_pack_index'):
            self._pack_index = {}

        count = self._pack_index.get(name, 0)
        self._pack_index[name] = count + 1


        matched = 0
        placed  = False
        for p in self._parts.values():
            if p['name'] == name:
                if matched == count:
                    v   = p['verts']
                    off = np.array([
                        ox + px - float(v[:,0].min()),
                        py      - float(v[:,1].min()),
                        pz      - float(v[:,2].min()),
                    ], dtype=np.float32)
                    p['offset'] = off
                    self.viewport.set_mesh_offset(
                        p['mesh_idx'], float(off[0]), float(off[1]), float(off[2]))
                    placed = True
                    break
                matched += 1

        if not placed:
            # Name didn't match exactly — try stripping .stl and matching base
            base = name.rsplit('.', 1)[0] if '.' in name else name
            for p in self._parts.values():
                pbase = p['name'].rsplit('.', 1)[0] if '.' in p['name'] else p['name']
                if pbase == base:
                    v   = p['verts']
                    off = np.array([
                        ox + px - float(v[:,0].min()),
                        py      - float(v[:,1].min()),
                        pz      - float(v[:,2].min()),
                    ], dtype=np.float32)
                    p['offset'] = off
                    self.viewport.set_mesh_offset(
                        p['mesh_idx'], float(off[0]), float(off[1]), float(off[2]))
                    break

        if vol_idx + 1 > self._n_volumes:
            self._n_volumes = vol_idx + 1
            self._update_bv()

    def _on_pack_done(self, placements, n_vols):
        pass  # superseded by _on_pack_finished

    def _on_pack_finished(self, placements, n_vols):
        self._pack_index = {}
        self._n_volumes = n_vols
        bv_x = self._bv[0]

        # Build id->part lookup
        id_to_part = {p['id']: p for p in self._parts.values()}

        for label, part_data, vol_idx, px, py, pz in placements:
            ox  = vol_idx * (bv_x + 20)
            pid = part_data.get('id') if isinstance(part_data, dict) else None
            part = id_to_part.get(pid, part_data) if pid else part_data
            if not isinstance(part, dict) or 'verts' not in part:
                continue
            v   = part['verts']
            off = np.array([
                ox + px - float(v[:,0].min()),
                py      - float(v[:,1].min()),
                pz      - float(v[:,2].min()),
            ], dtype=np.float32)
            part['offset'] = off
            self.viewport.set_mesh_offset(
                part['mesh_idx'], float(off[0]), float(off[1]), float(off[2]))

        # Rebuild build volumes to match actual count used
        self.viewport.clear_build_volumes()
        bx,by,bz = self._bv
        for i in range(n_vols):
            self.viewport.add_build_volume(bx,by,bz,i*(bx+20),f"Vol {i+1}")
        self.viewport.update()
        self.pack_prog.setVisible(False)
        self.btn_cancel_pack.setVisible(False)
        self.lbl_pack_status.setText(
            f"Packed {len(placements)} part(s) into {n_vols} build volume(s)."
        )

    def _on_pack_cancelled(self):
        self.pack_prog.setVisible(False); self.btn_cancel_pack.setVisible(False)
        self.lbl_pack_status.setText("Packing cancelled.")

    def _cancel_pack(self): self._cancel_flag[0]=True

    # ------------------------------------------------------------------
    # Layer slicer
    # ------------------------------------------------------------------
    def _on_layer(self, val):
        steps = getattr(self, '_slider_steps', 100)
        bz = self._bv[2]
        mm = val * 0.1
        self.lbl_layer.setText(f"{mm:.1f}mm")
        self.viewport.set_layer_clip(val / steps)

    # ------------------------------------------------------------------
    # Lattice
    # ------------------------------------------------------------------
    def _gen_lattice(self):
        p=self._get_sel()
        if not p:
            # Auto-select first part if none selected
            for pid,part in self._parts.items():
                if part.get('parent') is None:
                    self._select_part(pid)
                    p=part; break
        if not p: QMessageBox.information(self,"Lattice","Import a part first."); return
        self._cancel_flag=[False]
        self.lat_prog.setVisible(True); self.lat_prog.setValue(0); self._btn_cancel_lat.setVisible(True)
        class _NoDlg:
            def setLabelText(self,t): pass
            def close(self): pass
        self._progress=_NoDlg()
        # Pass STEP path for CAD-level shelling if available
        src_path=p.get('path','')
        step_path=src_path if src_path and src_path.lower().endswith(('.step','.stp')) else None
        self._lat_worker=LatticeWorker(
            p['verts'], self.sp_wall.value(), self.sp_cell.value(),
            self.sp_latt.value(), self.combo_ltype.currentText(),
            self.sp_res.value(), self.sp_sm_i.value(), self.sp_sm_f.value(),
            self.chk_no_shell.isChecked(), self._cancel_flag,
            stl_faces=p.get('faces'),
            step_path=step_path
        )
        self._lat_worker.progress.connect(self._on_lat_progress)
        self._lat_worker.finished.connect(lambda v,f: self._on_lat_done(p['id'],v,f))
        self._lat_worker.error.connect(self._on_lat_err)
        self._lat_worker.start()


    def _on_lat_progress(self, msg):
        if hasattr(self,'lat_status'):
            self.lat_status.setText(msg); self.lat_status.setVisible(True)
        steps={'Cleaning':10,'Grid':15,'Making part':20,'Evaluating':30,
               'Marching':50,'Welding':60,'Smooth':68,'Building manifold':72,
               'Boolean: TPMS':80,'Building hollow':85,'Clipping TPMS':88,
               'Combining':92,'pymeshfix':96,'Done':100}
        if hasattr(self,'lat_prog'):
            for k,p in steps.items():
                if k.lower() in msg.lower():
                    self.lat_prog.setValue(p); break

    def _on_lat_done(self, pid, verts, faces):
        self._progress.close()
        self.lat_prog.setVisible(False); self._btn_cancel_lat.setVisible(False)
        if hasattr(self,'lat_status'): self.lat_status.setVisible(False)
        parent=self._parts.get(pid)
        if not parent: return
        # Store original solid volume before replacing with lattice mesh
        parent['volume_original'] = parent['volume']
        # Replace parent mesh with fused result
        parent['verts']=verts; parent['faces']=faces
        self.viewport.update_mesh(parent['mesh_idx'],verts,faces)
        self.viewport.set_mesh_color(parent['mesh_idx'],MESH_COLOR)
        # Re-select so viewport click works again
        self.viewport.set_selected(parent['mesh_idx'])
        parent['has_lattice']=True
        parent['lattice_type']=self.combo_ltype.currentText()
        from mesh_repair import compute_volume, compute_surface_area, compute_bbox
        parent['volume_with_lattice']=compute_volume(verts,faces)
        parent['area']=compute_surface_area(verts,faces)
        parent['bbox']=compute_bbox(verts)
        # Non-selectable label in tree
        pi=self._find_item(pid)
        if pi:
            for i in range(pi.childCount()-1,-1,-1):
                c=pi.child(i)
                if c.data(0,Qt.ItemDataRole.UserRole)=='__lattice__': pi.removeChild(c)
            li=QTreeWidgetItem([f"    ◈ {self.combo_ltype.currentText()}"])
            li.setData(0,Qt.ItemDataRole.UserRole,'__lattice__')
            li.setFlags(Qt.ItemFlag.NoItemFlags)
            li.setForeground(0,QColor(ACCENT))
            f=li.font(0); f.setItalic(True); f.setPointSize(10); li.setFont(0,f)
            pi.addChild(li); pi.setExpanded(True)
        self._update_props(pid)
        self.status.showMessage(f"Lattice fused into: {parent['name']} — export from Export tab")

    def _on_lat_err(self, msg):
        self._progress.close()
        self.lat_prog.setVisible(False); self._btn_cancel_lat.setVisible(False)
        if msg!="__cancelled__": QMessageBox.critical(self,"Lattice Error",msg)
        else: self.status.showMessage("Cancelled.")

    # ------------------------------------------------------------------
    # Transform
    # ------------------------------------------------------------------
    def _push_undo(self):
        if not hasattr(self, '_undo_stack'):
            self._undo_stack = []; self._redo_stack = []
        state = {pid: {'verts':p['verts'].copy(),'faces':p['faces'].copy(),
                       'offset':p['offset'].copy(),'name':p['name'],
                       'locks':dict(p.get('locks',{}))}
                 for pid,p in self._parts.items()}
        self._undo_stack.append(state)
        if len(self._undo_stack)>50: self._undo_stack.pop(0)
        if hasattr(self,'_redo_stack'): self._redo_stack.clear()

    def _undo(self):
        if not hasattr(self,'_undo_stack') or not self._undo_stack:
            self.status.showMessage("Nothing to undo."); return
        if not hasattr(self,'_redo_stack'): self._redo_stack=[]
        state={pid:{'verts':p['verts'].copy(),'faces':p['faces'].copy(),
                    'offset':p['offset'].copy(),'name':p['name'],
                    'locks':dict(p.get('locks',{}))}
               for pid,p in self._parts.items()}
        self._redo_stack.append(state)
        self._apply_state(self._undo_stack.pop())
        self.status.showMessage(f"Undo — {len(self._undo_stack)} step(s) remaining")

    def _redo(self):
        if not hasattr(self,'_redo_stack') or not self._redo_stack:
            self.status.showMessage("Nothing to redo."); return
        self._push_undo()
        self._apply_state(self._redo_stack.pop())
        self.status.showMessage("Redo")

    def _apply_state(self, state):
        # Remove parts that didn't exist in the saved state
        for pid in list(self._parts.keys()):
            if pid not in state:
                self.viewport.remove_mesh(self._parts[pid]['mesh_idx'])
                del self._parts[pid]

        # Update existing parts
        for pid, s in state.items():
            if pid in self._parts:
                p = self._parts[pid]
                p['verts']  = s['verts']; p['faces'] = s['faces']
                p['offset'] = s['offset']; p['name']  = s['name']
                p['locks']  = s['locks']
                self.viewport.update_mesh(p['mesh_idx'], p['verts'], p['faces'])
                self.viewport.set_mesh_offset(p['mesh_idx'], *p['offset'])
            else:
                # Part existed in saved state but not now — re-add it
                mesh_idx = self.viewport.add_mesh(s['verts'], s['faces'],
                                                  color=(0.65,0.65,0.65))
                from mesh_repair import compute_volume, compute_surface_area, compute_bbox
                self._parts[pid] = {
                    'id': pid, 'name': s['name'], 'path': None,
                    'verts': s['verts'], 'faces': s['faces'],
                    'mesh_idx': mesh_idx, 'offset': s['offset'],
                    'instances': 1, 'locks': s['locks'],
                    'parent': None, 'children': [],
                    'volume': compute_volume(s['verts'], s['faces']),
                    'area':   compute_surface_area(s['verts'], s['faces']),
                    'bbox':   compute_bbox(s['verts']),
                }

        # Rebuild tree to match
        self.tree.clear()
        for pid, p in self._parts.items():
            item = QTreeWidgetItem([f"  {p['name']}"])
            item.setData(0, Qt.ItemDataRole.UserRole, pid)
            self.tree.addTopLevelItem(item)

        self._refresh_pack_list()
        self._update_density()
        self.viewport.update()

    def _scale_pct(self):
        p=self._get_sel()
        if not p or p['locks'].get('type')=='xyz': return
        if p.get('has_lattice'):
            r=QMessageBox.question(self,"Warning",
                "This part has a lattice applied.\n"
                "Scaling will stretch the lattice geometry.\n"
                "For best results: scale first, then generate lattice.\n\n"
                "Continue scaling?",
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
            if r!=QMessageBox.StandardButton.Yes: return
        pct=self.sp_pct.value()/100.0
        p['verts']=p['verts']*pct
        self.viewport.update_mesh(p['mesh_idx'],p['verts'],p['faces'])
        from mesh_repair import compute_volume,compute_surface_area,compute_bbox
        p['volume']=compute_volume(p['verts'],p['faces'])
        p['area']=compute_surface_area(p['verts'],p['faces'])
        p['bbox']=compute_bbox(p['verts']); self._update_props(p['id'])

    def _clamp_offset(self, p, x, y, z):
        """Clamp offset so part stays within build volume. Floor is always Z=0."""
        bx,by,bz = self._bv
        v = p['verts']
        # Part dimensions
        dx=float(v[:,0].max()-v[:,0].min())
        dy=float(v[:,1].max()-v[:,1].min())
        dz=float(v[:,2].max()-v[:,2].min())
        # If part is larger than build volume, allow free placement (no clamp)
        if dx>bx or dy>by or dz>bz:
            return float(x), float(y), float(z)
        # Clamp so part stays inside build volume
        x = float(np.clip(x, 0, bx-dx))
        y = float(np.clip(y, 0, by-dy))
        z = float(np.clip(z, 0, bz-dz))  # floor at 0
        return x, y, z

    def _apply_position(self):
        p = self._get_sel()
        if not p: return
        self._push_undo()
        x = self.sp_pos_x.value()
        y = self.sp_pos_y.value()
        z = self.sp_pos_z.value()
        x,y,z = self._clamp_offset(p, x, y, z)
        import numpy as np
        off = np.array([x, y, z], dtype=np.float32)
        p['offset'] = off
        # Update spinboxes if clamped
        self.sp_pos_x.blockSignals(True); self.sp_pos_x.setValue(x); self.sp_pos_x.blockSignals(False)
        self.sp_pos_y.blockSignals(True); self.sp_pos_y.setValue(y); self.sp_pos_y.blockSignals(False)
        self.sp_pos_z.blockSignals(True); self.sp_pos_z.setValue(z); self.sp_pos_z.blockSignals(False)
        self.viewport.set_mesh_offset(p['mesh_idx'], x, y, z)
        self.status.showMessage(f"Moved {p['name']} to ({x:.1f}, {y:.1f}, {z:.1f})")

    def _scale_mm(self):
        p=self._get_sel()
        if not p or p['locks'].get('type')=='xyz': return
        if p.get('has_lattice'):
            r=QMessageBox.question(self,"Warning",
                "This part has a lattice applied.\n"
                "Scaling will stretch the lattice geometry.\n"
                "For best results: scale first, then generate lattice.\n\n"
                "Continue scaling?",
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
            if r!=QMessageBox.StandardButton.Yes: return
        v=p['verts']
        curr=np.array([v[:,0].max()-v[:,0].min(),v[:,1].max()-v[:,1].min(),v[:,2].max()-v[:,2].min()])
        tgt=np.array([self.sp_sx.value(),self.sp_sy.value(),self.sp_sz.value()])
        scale=np.where(curr>1e-6,tgt/curr,1.0)
        p['verts']=v*scale; self.viewport.update_mesh(p['mesh_idx'],p['verts'],p['faces'])
        from mesh_repair import compute_volume,compute_surface_area,compute_bbox
        p['volume']=compute_volume(p['verts'],p['faces'])
        p['area']=compute_surface_area(p['verts'],p['faces'])
        p['bbox']=compute_bbox(p['verts']); self._update_props(p['id'])

    def _rotate(self, axis, deg):
        p=self._get_sel()
        if not p: return
        self._push_undo()
        lk=p['locks'].get('type','')
        if lk=='xyz' or (lk=='xy' and axis in ('X','Y')): return
        rad=np.radians(deg); c=np.cos(rad); s=np.sin(rad)
        if axis=='X': R=np.array([[1,0,0],[0,c,-s],[0,s,c]])
        elif axis=='Y': R=np.array([[c,0,s],[0,1,0],[-s,0,c]])
        else: R=np.array([[c,-s,0],[s,c,0],[0,0,1]])
        ctr=p['verts'].mean(axis=0)
        p['verts']=(p['verts']-ctr)@R.T+ctr
        self.viewport.update_mesh(p['mesh_idx'],p['verts'],p['faces'])

    def _reset_xf(self):
        p=self._get_sel()
        if not p or not p.get('path'): return
        try:
            from triply_io.importer import import_file
            v,f,_=import_file(p['path'])
            p['verts']=v; p['faces']=f
            self.viewport.update_mesh(p['mesh_idx'],v,f)
            self.status.showMessage(f"Reset: {p['name']}")
        except Exception as e: QMessageBox.critical(self,"Reset Error",str(e))

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _save_path(self, default_name):
        base=os.path.splitext(default_name)[0]
        path,_ = QFileDialog.getSaveFileName(
            self,"Export", os.path.join(self._last_export_dir, base,
            options=QFileDialog.Option.DontUseNativeDialog),
            "STL (*.stl);;3MF (*.3mf);;STEP (*.step)"
        )
        if not path: return None
        # Auto-add extension
        if not os.path.splitext(path)[1]:
            path += '.stl'
        d=os.path.dirname(os.path.abspath(path))
        self._last_export_dir=d; self._cfg["last_export_dir"]=d; save_config(self._cfg)
        return path

    def _run_export(self, path, verts, faces):
        if '.' not in path.split('/')[-1]: path+='.stl'
        q_map={"Low (0.5mm)":"Low","Medium (0.1mm)":"Medium","High (0.001mm)":"High"}
        quality=q_map.get(self.combo_quality.currentText(),"High")
        if hasattr(self,'exp_prog'):
            self.exp_prog.setVisible(True); self.exp_prog.setValue(0)
        if hasattr(self,'exp_status'):
            self.exp_status.setVisible(True); self.exp_status.setText("Starting export...")
        self._exp_worker=ExportWorker(path,verts,faces,quality)
        def on_prog(msg,pct):
            if hasattr(self,'exp_status'): self.exp_status.setText(msg)
            if hasattr(self,'exp_prog'): self.exp_prog.setValue(pct)
        def on_done():
            if hasattr(self,'exp_prog'): self.exp_prog.setVisible(False)
            if hasattr(self,'exp_status'): self.exp_status.setVisible(False)
            self.status.showMessage(f"Exported: {path}")
        def on_err(e):
            if hasattr(self,'exp_prog'): self.exp_prog.setVisible(False)
            if hasattr(self,'exp_status'): self.exp_status.setVisible(False)
            QMessageBox.critical(self,"Export Error",e)
        self._exp_worker.progress.connect(on_prog)
        self._exp_worker.finished.connect(on_done)
        self._exp_worker.error.connect(on_err)
        self._exp_worker.start()

    def _do_export(self, verts, faces, name):
        path=self._save_path(name)
        if not path: return
        self._run_export(path, verts, faces)

    def _export_sel(self):
        p=self._get_sel()
        if not p: QMessageBox.information(self,"Export","Select a part first."); return
        import numpy as np
        # Always use the stored verts+faces which are set by generate_lattice
        # These are already the correct scaled+latticed geometry
        v = p['verts'].copy()
        f = p['faces'].copy()
        # Apply current offset
        off = p.get('offset', np.zeros(3))
        v = v + off
        self._do_export(v, f, p['name'])

    def _export_sel_stl(self):
        p=self._get_sel()
        if not p: return
        base=os.path.splitext(p['name'])[0]
        path,_=QFileDialog.getSaveFileName(
            self,"Export STL",os.path.join(self._last_export_dir,base+".stl",
            options=QFileDialog.Option.DontUseNativeDialog),"STL (*.stl)"
        )
        if not path: return
        if not path.lower().endswith('.stl'): path+='.stl'
        d=os.path.dirname(os.path.abspath(path))
        self._last_export_dir=d; self._cfg["last_export_dir"]=d; save_config(self._cfg)
        from triply_io.exporter import export_stl
        export_stl(path,p['verts'],p['faces'])
        self.status.showMessage(f"Exported: {path}")

    def _export_all(self):
        if not self._parts: return
        folder=QFileDialog.getExistingDirectory(self,"Export Folder",self._last_export_dir,
            options=QFileDialog.Option.DontUseNativeDialog)
        if not folder: return
        self._last_export_dir=folder; self._cfg["last_export_dir"]=folder; save_config(self._cfg)
        from triply_io.exporter import export_stl
        for p in self._parts.values():
            export_stl(os.path.join(folder,p['name']+'.stl'),p['verts'],p['faces'])
        self.status.showMessage(f"Exported {len(self._parts)} parts.")

    def _export_packed(self):
        if not self._parts: return
        path=self._save_path("packed_scene.stl")
        if not path: return
        from triply_io.exporter import export_stl
        all_v,all_f,off=[],[],0
        for p in self._parts.values():
            v=p['verts']+p['offset']; all_v.append(v); all_f.append(p['faces']+off); off+=len(v)
        export_stl(path,np.vstack(all_v),np.vstack(all_f))

    # ------------------------------------------------------------------
    # Project
    # ------------------------------------------------------------------
    def _save_project(self):
        path,_=QFileDialog.getSaveFileName(self,"Save Project","project.triply3d","Triply Project (*.triply3d)",
            options=QFileDialog.Option.DontUseNativeDialog)
        if not path: return
        import zipfile, tempfile
        try:
            with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as zf:
                meta={'version':'1.0','bv':list(self._bv),
                      'printer':self.combo_printer.currentText(),
                      'parts':[{'id':p['id'],'name':p['name'],'path':p.get('path',''),
                                 'instances':p.get('instances',1),'locks':p.get('locks',{}),
                                 'parent':p.get('parent'),'offset':p['offset'].tolist()}
                                for p in self._parts.values()]}
                zf.writestr('meta.json',json.dumps(meta,indent=2))
                from triply_io.exporter import export_stl
                for p in self._parts.values():
                    with tempfile.NamedTemporaryFile(suffix='.stl',delete=False) as tmp:
                        export_stl(tmp.name,p['verts'],p['faces'])
                        zf.write(tmp.name,f"meshes/{p['id']}.stl")
                        os.unlink(tmp.name)
            self.status.showMessage(f"Saved: {path}")
        except Exception as e: QMessageBox.critical(self,"Save Error",str(e))

    def _open_project(self):
        path,_=QFileDialog.getOpenFileName(self,"Open Project","","Triply Project (*.triply3d)",
            options=QFileDialog.Option.DontUseNativeDialog)
        if not path: return
        import zipfile, tempfile
        try:
            with zipfile.ZipFile(path,'r') as zf:
                meta=json.loads(zf.read('meta.json'))
                self.viewport.clear_meshes(); self._parts.clear(); self.tree.clear()
                for pm in meta['parts']:
                    with tempfile.NamedTemporaryFile(suffix='.stl',delete=False) as tmp:
                        tmp.write(zf.read(f"meshes/{pm['id']}.stl")); tp=tmp.name
                    from triply_io.importer import import_file
                    v,f,n=import_file(tp); os.unlink(tp)
                    self._add_part(pm['name'],pm.get('path'),v,f,parent_id=pm.get('parent'))
                bv=meta.get('bv',self._bv)
                self.spin_bvx.setValue(bv[0]); self.spin_bvy.setValue(bv[1]); self.spin_bvz.setValue(bv[2])
            self.status.showMessage(f"Loaded: {path}")
        except Exception as e: QMessageBox.critical(self,"Open Error",str(e))

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    def _dlg_mouse(self):
        dlg=QDialog(self); dlg.setWindowTitle("Mouse Controls"); dlg.setMinimumWidth(280)
        lay=QVBoxLayout(dlg); form=QFormLayout()
        co=QComboBox(); cp=QComboBox()
        opts=["Left Button","Middle Button","Right Button"]
        for cb in (co,cp): cb.addItems(opts)
        co.setCurrentText(self._cfg.get("mouse_orbit","Right Button"))
        cp.setCurrentText(self._cfg.get("mouse_pan","Middle Button"))
        form.addRow("Orbit:",co); form.addRow("Pan:",cp); lay.addLayout(form)
        btns=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject); lay.addWidget(btns)
        if dlg.exec()==QDialog.DialogCode.Accepted:
            self._cfg["mouse_orbit"]=co.currentText(); self._cfg["mouse_pan"]=cp.currentText()
            save_config(self._cfg); self._apply_mouse()

    def _apply_mouse(self):
        m={"Left Button":Qt.MouseButton.LeftButton,"Middle Button":Qt.MouseButton.MiddleButton,"Right Button":Qt.MouseButton.RightButton}
        self.viewport.set_mouse_mapping(
            orbit=m.get(self._cfg.get("mouse_orbit","Right Button"),Qt.MouseButton.RightButton),
            pan=m.get(self._cfg.get("mouse_pan","Middle Button"),Qt.MouseButton.MiddleButton),
        )

    def _dlg_about(self):
        QMessageBox.about(self,"About Triply",
            "<b>Triply — AM Tools and Lattices</b><br>Version 0.2.0<br><br>"
            "Created by <b>Orville Wright IV</b><br>"
            "All rights reserved. © 2025 Orville Wright IV<br><br>"
            "Free additive manufacturing toolset for SLS, SLA, mSLA, and DMLS.<br><br>"
            "<i>Free for makers worldwide.</i>")


def main():
    # Auto HiDPI — works correctly on 1080p, 1440p, 4K, mixed setups
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app=QApplication(sys.argv)
    # AA_UseHighDpiPixmaps removed in PyQt6 — HiDPI handled automatically

    # Surface format: Compatibility profile required for legacy OpenGL
    # (glEnable(GL_LIGHTING), glLightfv, glShadeModel etc. used in viewport.py)
    from PyQt6.QtGui import QSurfaceFormat
    fmt=QSurfaceFormat()
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
    fmt.setVersion(2, 1)
    QSurfaceFormat.setDefaultFormat(fmt)

    app.setApplicationName("Triply")
    app.setApplicationDisplayName("Triply — AM Tools and Lattices")
    win=TripLyWindow(); win.show(); sys.exit(app.exec())

if __name__=="__main__":
    import traceback, os
    try:
        main()
    except Exception as e:
        log = os.path.expanduser("~/.triply-crash.log")
        with open(log, "a") as f:
            traceback.print_exc(file=f)
        raise
