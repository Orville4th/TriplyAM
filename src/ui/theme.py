"""
theme.py — Triply color system
Primary accent : #8B0000 (dark red)
Neutral base   : #848482 (warm grey)
All UI is monochromatic grey — no blue anywhere.
"""

ACCENT   = "#8B0000"
NEUTRAL  = "#848482"
BG       = "#1c1c1c"
SURFACE  = "#252525"
SURFACE2 = "#2e2e2e"
BORDER   = "#3a3a3a"
TEXT_PRI = "#e8e8e8"
TEXT_SEC = "#a0a0a0"
TEXT_DIM = "#666666"

def accent_hover(amt=25):
    h = ACCENT.lstrip('#')
    r,g,b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
    return f"#{min(255,r+amt):02x}{min(255,g+amt):02x}{min(255,b+amt):02x}"

def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2],16)/255.0 for i in (0,2,4))

ACCENT_RGB  = hex_to_rgb(ACCENT)
NEUTRAL_RGB = hex_to_rgb(NEUTRAL)

APP_STYLESHEET = f"""
QMainWindow, QWidget, QDialog {{
    background-color: {BG};
    color: {TEXT_PRI};
    font-family: 'Inter', 'Segoe UI', 'DejaVu Sans', system-ui, sans-serif;
    font-size: 13px;
}}
QMenuBar {{
    background: {BG};
    color: {TEXT_SEC};
    border-bottom: 1px solid {BORDER};
    padding: 2px 0;
}}
QMenuBar::item {{ padding: 4px 10px; border-radius: 4px; }}
QMenuBar::item:selected {{ background: {SURFACE2}; color: {TEXT_PRI}; }}
QMenu {{
    background: {SURFACE};
    color: {TEXT_PRI};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{ padding: 6px 20px; border-radius: 4px; }}
QMenu::item:selected {{ background: {ACCENT}; color: #ffffff; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}
QTabWidget::pane {{ border: none; background: {SURFACE}; }}
QTabBar::tab {{
    background: {BG};
    color: {TEXT_DIM};
    padding: 7px 12px;
    border: none;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.03em;
}}
QTabBar::tab:selected {{
    color: {TEXT_PRI};
    border-bottom: 2px solid {ACCENT};
    background: {SURFACE};
}}
QTabBar::tab:hover:!selected {{ color: {TEXT_SEC}; }}
QPushButton {{
    background: {SURFACE2};
    color: {TEXT_SEC};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton:hover:!disabled {{
    background: #363636;
    color: {TEXT_PRI};
    border-color: #505050;
}}
QPushButton:pressed {{ background: #404040; }}
QPushButton#btn_primary {{
    background: {ACCENT};
    color: #ffffff;
    border: none;
    font-size: 13px;
    padding: 8px 16px;
}}
QPushButton#btn_primary:hover:!disabled {{ background: {accent_hover()}; }}
QPushButton#btn_danger {{
    background: #3a1010;
    color: #f87171;
    border: 1px solid #5a2020;
}}
QPushButton#btn_danger:hover:!disabled {{ background: #4a1818; }}
QPushButton:disabled {{ color: {TEXT_DIM}; background: {SURFACE}; border-color: {BORDER}; }}
QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {SURFACE2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 8px;
    color: {TEXT_PRI};
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QTextEdit:focus {{ border-color: {ACCENT}; }}
QComboBox, QDoubleSpinBox, QSpinBox {{
    background: {SURFACE2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 8px;
    color: {TEXT_PRI};
    min-height: 24px;
}}
QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox::down-arrow {{ width: 10px; height: 10px; }}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button {{
    background: {SURFACE};
    border: none;
    width: 18px;
}}
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover,
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background: {BORDER};
}}
QListWidget, QTreeWidget {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {TEXT_PRI};
    outline: none;
}}
QListWidget::item, QTreeWidget::item {{
    padding: 5px 8px;
    border-radius: 4px;
}}
QListWidget::item:selected, QTreeWidget::item:selected {{
    background: {ACCENT};
    color: #ffffff;
}}
QListWidget::item:hover:!selected, QTreeWidget::item:hover:!selected {{
    background: {SURFACE2};
}}
QTreeWidget::branch {{ background: {SURFACE}; }}
QLabel {{ color: {TEXT_SEC}; background: transparent; }}
QLabel#section_label {{
    color: {ACCENT};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 6px 0 2px 0;
}}
QLabel#value_label {{
    color: {NEUTRAL};
    font-size: 11px;
}}
QCheckBox {{ color: {TEXT_SEC}; spacing: 6px; }}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background: {SURFACE2};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QCheckBox::indicator:hover {{ border-color: {NEUTRAL}; }}
QSlider::groove:horizontal {{
    background: {SURFACE2};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {NEUTRAL};
    width: 14px; height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{ background: {TEXT_PRI}; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::groove:vertical {{
    background: {SURFACE2};
    width: 4px;
    border-radius: 2px;
}}
QSlider::handle:vertical {{
    background: {NEUTRAL};
    width: 14px; height: 14px;
    margin: 0 -5px;
    border-radius: 7px;
}}
QSlider::handle:vertical:hover {{ background: {TEXT_PRI}; }}
QSlider::add-page:vertical {{ background: {ACCENT}; border-radius: 2px; }}
QScrollBar:vertical {{
    background: {BG};
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {NEUTRAL}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {BG};
    height: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 3px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{ background: {NEUTRAL}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    color: {TEXT_DIM};
    font-size: 11px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    color: {TEXT_DIM};
}}
QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
QStatusBar {{
    background: #141414;
    color: {TEXT_DIM};
    font-size: 11px;
    border-top: 1px solid {BORDER};
}}
QProgressBar {{
    background: {SURFACE2};
    border: 1px solid {BORDER};
    border-radius: 4px;
    text-align: center;
    color: {TEXT_PRI};
    height: 16px;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 3px;
}}
QToolTip {{
    background: {SURFACE2};
    color: {TEXT_PRI};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}}
#sidebar {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
#ad_banner {{
    background: #141414;
    border-top: 1px solid {BORDER};
}}
#props_panel {{
    background: {SURFACE};
    border-top: 1px solid {BORDER};
}}
"""
