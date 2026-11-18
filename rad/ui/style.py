"""Tema Torqis (B · Minimal premium): fundos grafite quase pretos e o azul do ponteiro do símbolo.

Azul (BLUE → CYAN, #3D7BFF → #6FA8FF) = marca e interface (botões, separadores, escalas), em gradiente.
Vermelho, âmbar e verde ficam reservados para avaria / aviso / OK — como no painel do carro.
"""
import os

NIGHT = "#08090C"      # fundo principal
NIGHT_2 = "#0C0E12"    # fundo das zonas laterais
PANEL = "#13151B"      # cartões
PANEL_2 = "#1B1E26"    # cartões elevados / hover
LINE = "#2A2E38"       # contornos
LINE_SOFT = "#1E2129"
BLUE = "#3D7BFF"       # iluminação da escala
CYAN = "#6FA8FF"       # azul claro da marca (brilho, foco, selecção)
VIOLET = "#8B6CFF"
BLUE_SOFT = "#22324F"
RED = "#FF3B4E"        # ponteiro
TEXT = "#F2F4F8"
MUTED = "#8A92A6"
SOFT = "#BCC2CF"       # texto corrido secundário que tem de se ler bem (ex.: explicação de uma avaria)
DIM = "#4A4E57"
OK = "#2EE59D"
WARN = "#FFB547"
BAD = RED

ACCENT = BLUE          # compatibilidade

DISPLAY_FONT = '"Bahnschrift", "DIN Alternate", "Roboto Condensed", "Segoe UI"'
BODY_FONT = '"Segoe UI", "Inter", "Helvetica Neue", Arial'

GRAD_PRIMARY = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3D7BFF, stop:1 #6FA8FF)"
GRAD_PRIMARY_HOVER = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5A92FF, stop:1 #8FBCFF)"
GRAD_CARD = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(27, 30, 38, 0.92), stop:1 rgba(17, 19, 24, 0.92))"

# setas do QSpinBox (o Qt não desenha triângulos com bordas CSS); caminho com / para o QSS
_ASSET = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets").replace("\\", "/")

QSS = f"""
* {{ font-family: {BODY_FONT}; font-size: 10.5pt; }}       /* lê-se melhor a partir do carro */
QMainWindow {{ background: {NIGHT}; }}
QWidget#root {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #15171D, stop:0.45 {NIGHT}, stop:1 #0A0B0F);
}}
QWidget {{ color: {TEXT}; background: transparent; }}
QDialog, QMessageBox {{ background: {PANEL}; }}
QMessageBox QLabel {{ color: {TEXT}; }}

QFrame#sidebar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #101217, stop:1 #08090C);
    border-right: 1px solid {LINE_SOFT};
}}
QPushButton#nav {{
    text-align: left; padding: 11px 16px; border: none; border-radius: 10px;
    background: transparent; color: {MUTED}; font-size: 10.5pt; font-weight: 600;
}}
QPushButton#nav:hover {{ background: rgba(61, 123, 255, 0.08); color: {TEXT}; }}
QPushButton#nav:checked {{
    color: white; border-left: 3px solid {CYAN};
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(111, 168, 255, 0.22), stop:1 rgba(61, 123, 255, 0.02));
}}
QPushButton#nav:disabled {{ color: #393C46; }}
QPushButton#search {{
    text-align: left; padding: 9px 12px; border-radius: 10px; color: {MUTED};
    background: rgba(255, 255, 255, 0.03); border: 1px solid {LINE_SOFT}; font-weight: 500;
}}
QPushButton#search:hover {{ border-color: {BLUE}; color: {TEXT}; }}

QFrame#card {{ background: {GRAD_CARD}; border: 1px solid {LINE}; border-radius: 14px; }}
QFrame#cardGlow {{ background: {GRAD_CARD}; border: 1px solid rgba(111, 168, 255, 0.35); border-radius: 14px; }}
QFrame#stat {{ background: {GRAD_CARD}; border: 1px solid {LINE}; border-radius: 14px; }}
QFrame#stat:hover {{ border-color: {BLUE}; }}
QFrame#banner {{
    border-radius: 12px; border: 1px solid rgba(111, 168, 255, 0.35);
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(111, 168, 255, 0.14), stop:1 rgba(61, 123, 255, 0.08));
}}

QPushButton {{
    background: {PANEL_2}; border: 1px solid {LINE}; border-radius: 9px;
    padding: 9px 16px; color: {TEXT}; font-weight: 600;
}}
QPushButton:hover {{ border-color: {BLUE}; color: white; background: #242730; }}
QPushButton:pressed {{ background: {BLUE_SOFT}; }}
QPushButton:focus {{ border-color: {BLUE}; }}
QPushButton:checked {{ border-color: {CYAN}; background: rgba(111, 168, 255, 0.16); color: white; }}
QPushButton:disabled {{ color: #464852; border-color: #21232B; background: #17191F; }}
QPushButton#primary {{ background: {GRAD_PRIMARY}; border: none; color: #0C0F14; }}
QPushButton#primary:hover {{ background: {GRAD_PRIMARY_HOVER}; }}
QPushButton#primary:pressed {{ background: #2E6AE8; }}
QPushButton#primary:disabled {{ background: #272B35; color: #5E6F99; }}
QPushButton#danger {{ background: rgba(255, 59, 78, 0.12); border: 1px solid rgba(255, 59, 78, 0.45); color: #FFC4CA; }}
QPushButton#danger:hover {{ background: rgba(255, 59, 78, 0.24); color: white; border-color: {RED}; }}
QPushButton#ghost {{ background: transparent; border: 1px solid transparent; color: {MUTED}; }}
QPushButton#ghost:hover {{ color: white; border-color: {LINE}; }}
QPushButton#module {{
    text-align: left; padding: 12px 14px; border-radius: 11px; background: {GRAD_CARD};
    border: 1px solid {LINE}; font-weight: 500;
}}
QPushButton#module:hover {{ border-color: {CYAN}; background: {PANEL_2}; }}
QPushButton#tile {{
    text-align: left; padding: 18px 20px; border-radius: 16px; background: {GRAD_CARD};
    border: 1px solid {LINE}; font-size: 10.5pt; color: {MUTED};
}}
QPushButton#tile:checked {{
    border: 1px solid {CYAN};
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #252B35, stop:1 #13151B);
}}
QPushButton#tile:hover {{
    border-color: {CYAN};
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #272B35, stop:1 #13151B);
}}

QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: rgba(8, 9, 12, 0.75); border: 1px solid {LINE}; border-radius: 8px; padding: 7px 9px;
    selection-background-color: {BLUE}; selection-color: #0C0F14;
}}
QLineEdit:hover, QSpinBox:hover, QComboBox:hover {{ border-color: #3A3F4C; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {CYAN}; }}
QLineEdit#paletteInput {{
    font-size: 13pt; padding: 12px 14px; border-radius: 12px; border: 1px solid {CYAN};
    background: rgba(8, 9, 12, 0.9);
}}
QLineEdit#plateBig {{
    font-family: {DISPLAY_FONT}; font-size: 17pt; font-weight: 700; letter-spacing: 2px; padding: 10px 14px;
    border-radius: 10px;
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {PANEL}; border: 1px solid {LINE}; selection-background-color: {BLUE}; }}
QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border; width: 22px; border: none; border-left: 1px solid {LINE}; background: transparent;
}}
QSpinBox::up-button {{ subcontrol-position: top right; border-top-right-radius: 8px; }}
QSpinBox::down-button {{ subcontrol-position: bottom right; border-bottom-right-radius: 8px; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {PANEL_2}; }}
QSpinBox::up-arrow {{ image: url("{_ASSET}/spin_up_muted.png"); width: 10px; height: 10px; }}
QSpinBox::down-arrow {{ image: url("{_ASSET}/spin_down_muted.png"); width: 10px; height: 10px; }}
QSpinBox::up-arrow:hover {{ image: url("{_ASSET}/spin_up_cyan.png"); }}
QSpinBox::down-arrow:hover {{ image: url("{_ASSET}/spin_down_cyan.png"); }}

QTabWidget::pane {{ border: 1px solid {LINE}; border-radius: 14px; top: -1px; background: rgba(15, 17, 21, 0.85); }}
QTabBar::tab {{
    background: transparent; color: {MUTED}; padding: 9px 11px; margin-right: 1px;
    border-bottom: 2px solid transparent; font-weight: 600;
}}
QTabBar::tab:hover {{ color: {TEXT}; }}
QTabBar::tab:selected {{ color: white; border-bottom: 2px solid {CYAN}; }}
QTabBar::tab:disabled {{ color: #393C46; }}

QTableWidget, QTreeWidget, QListWidget {{
    background: rgba(13, 14, 18, 0.85); alternate-background-color: rgba(24, 26, 32, 0.6);
    border: 1px solid {LINE}; border-radius: 12px; gridline-color: #21232B; outline: 0;
}}
QHeaderView {{ background: transparent; border: none; }}
QHeaderView::section {{
    background: {PANEL}; color: {MUTED}; padding: 9px 10px; border: none; border-bottom: 1px solid {LINE};
    font-weight: 600; font-size: 9.5pt;
}}
QTableWidget::item, QTreeWidget::item {{ padding: 6px 4px; border-bottom: 1px solid #1E2128; }}
QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {{
    background: rgba(111, 168, 255, 0.18); color: white;
}}
QTableWidget::item:hover, QTreeWidget::item:hover {{ background: rgba(61, 123, 255, 0.08); }}
QListWidget#palette {{ border: none; background: transparent; }}
QListWidget#palette::item {{ padding: 9px 12px; border-radius: 9px; margin: 1px 0; }}
QListWidget#palette::item:selected {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(111, 168, 255, 0.28), stop:1 rgba(61, 123, 255, 0.06));
}}

QPlainTextEdit#log {{ font-family: Consolas, "Cascadia Mono", monospace; font-size: 9pt; color: #8FB5FF; background: #08090B; border: none; }}
QDockWidget {{ color: {MUTED}; font-weight: 600; }}
QDockWidget::title {{ background: {NIGHT_2}; padding: 6px 10px; }}

QLabel#wordmark {{ font-family: "Bahnschrift Light", {DISPLAY_FONT}; font-size: 16pt; font-weight: 300; color: {TEXT}; letter-spacing: 5px; }}
QLabel#wordmarkSub {{ font-family: {DISPLAY_FONT}; font-size: 8pt; color: {CYAN}; letter-spacing: 3px; }}
QLabel#h1 {{ font-family: {DISPLAY_FONT}; font-size: 22pt; font-weight: 700; color: white; }}
QLabel#display {{ font-family: {DISPLAY_FONT}; font-size: 36pt; font-weight: 700; color: white; }}
QLabel#h2 {{ font-family: {DISPLAY_FONT}; font-size: 13pt; font-weight: 600; color: white; }}
QLabel#eyebrow {{ font-family: {DISPLAY_FONT}; font-size: 9pt; font-weight: 600; color: {CYAN}; letter-spacing: 2px; padding-top: 4px; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#value {{ font-family: {DISPLAY_FONT}; font-size: 21pt; font-weight: 700; color: white; }}
QLabel#bigValue {{ font-family: {DISPLAY_FONT}; font-size: 28pt; font-weight: 700; color: white; }}
QLabel#unit {{ color: {BLUE}; font-weight: 600; }}
QLabel#cellName {{ color: {MUTED}; font-size: 9pt; font-weight: 600; letter-spacing: 1px; }}
QLabel#kbd {{
    color: {MUTED}; font-size: 8pt; padding: 1px 6px; border: 1px solid {LINE}; border-radius: 5px;
    background: rgba(255, 255, 255, 0.03);
}}
QLabel#pill {{ border-radius: 9px; padding: 2px 10px; font-weight: 700; font-size: 9pt; }}
QLabel#toast {{
    background: rgba(24, 26, 32, 0.97); border: 1px solid {BLUE}; border-radius: 12px;
    padding: 12px 18px; color: white; font-weight: 600;
}}

QProgressBar {{ background: rgba(8, 9, 12, 0.8); border: 1px solid {LINE}; border-radius: 6px; text-align: center; height: 10px; color: {MUTED}; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3D7BFF, stop:1 {CYAN}); border-radius: 5px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: 1px solid #3D424E; background: rgba(8, 9, 12, 0.8); }}
QCheckBox::indicator:checked {{ background: {GRAD_PRIMARY}; border-color: {CYAN}; }}
QRadioButton {{ spacing: 8px; }}
QRadioButton::indicator {{ width: 14px; height: 14px; border-radius: 8px; border: 1px solid #3D424E; background: rgba(8, 9, 12, 0.8); }}
QRadioButton::indicator:hover {{ border-color: {CYAN}; }}
QRadioButton::indicator:checked {{ background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 {CYAN}, stop:0.45 {CYAN}, stop:0.55 rgba(8, 9, 12, 0.8), stop:1 rgba(8, 9, 12, 0.8)); border-color: {CYAN}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {LINE}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {BLUE_SOFT}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {LINE}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollArea {{ background: transparent; }}
QStatusBar {{ background: {NIGHT}; color: {MUTED}; border-top: 1px solid {LINE_SOFT}; }}
QStatusBar::item {{ border: none; }}
QPushButton#statusBtn {{ padding: 3px 12px; border-radius: 6px; font-weight: 500; color: {MUTED}; background: transparent; }}
QPushButton#statusBtn:checked {{ color: white; background: {PANEL_2}; }}
QToolTip {{ background: {PANEL_2}; color: white; border: 1px solid {CYAN}; padding: 4px; }}
"""


def severity_color(sev):
    return {"alta": RED, "media": WARN, "baixa": BLUE}.get(sev, MUTED)


def pill_style(color):
    """Estilo de uma etiqueta arredondada com a cor de estado (fundo translúcido)."""
    from PySide6.QtGui import QColor
    c = QColor(color)
    return (f"QLabel#pill {{ color: {color}; background: rgba({c.red()}, {c.green()}, {c.blue()}, 0.16); "
            f"border: 1px solid rgba({c.red()}, {c.green()}, {c.blue()}, 0.5); }}")
