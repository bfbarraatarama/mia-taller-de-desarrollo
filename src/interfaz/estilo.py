"""Estética Windows Vista compartida por toda la interfaz: fuentes, hoja de estilo e íconos de estado."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap, QPolygonF, QRadialGradient

FAMILIAS = ["Segoe UI", "Open Sans", "Noto Sans", "Cantarell", "sans-serif"]
AZUL_INSTRUCCION = "#003399"
ESCALA_TEXTO = 1.25  # multiplica todos los tamaños de letra


def fuente(pt: float, peso: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont()
    f.setFamilies(FAMILIAS)
    f.setPointSizeF(pt * ESCALA_TEXTO)
    f.setWeight(peso)
    return f


def degrade(x1, y1, x2, y2, *paradas) -> QLinearGradient:
    g = QLinearGradient(x1, y1, x2, y2)
    for pos, color in paradas:
        g.setColorAt(pos, QColor(color))
    return g


# ---------------------------------------------------------------------------
# Hoja de estilo
# ---------------------------------------------------------------------------

def _flechas(dir_tmp: Path) -> dict[str, str]:
    """Genera las flechas de combos y spinboxes (las hojas de estilo de Qt no las dibujan solas)."""
    rutas = {}
    for nombre, puntos in {"abajo": [(0, 0), (8, 0), (4, 4)], "arriba": [(0, 4), (8, 4), (4, 0)]}.items():
        pm = QPixmap(9, 5)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#3e3e3e"))
        p.drawPolygon(QPolygonF([QPointF(x + 0.5, y + 0.5) for x, y in puntos]))
        p.end()
        ruta = dir_tmp / f"flecha_{nombre}.png"
        pm.save(str(ruta))
        rutas[nombre] = ruta.as_posix()
    return rutas


def hoja_estilo(flechas: dict[str, str]) -> str:
    boton = "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f2f2f2, stop:0.49 #ebebeb, stop:0.5 #dddddd, stop:1 #cfcfcf)"
    boton_hover = "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #eaf6fd, stop:0.49 #d9f0fc, stop:0.5 #bee6fd, stop:1 #a7d9f5)"
    boton_press = "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #e5f4fc, stop:0.49 #c4e5f6, stop:0.5 #98d1ef, stop:1 #68b3db)"
    return f"""
    QWidget {{ color: #1b1b1b; }}
    QWidget#cuerpo {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffffff, stop:0.7 #ffffff, stop:1 #eef3f8); }}
    QLabel#instruccion {{ color: {AZUL_INSTRUCCION}; }}
    QLabel#secundario {{ color: #5a6b7d; }}
    QGroupBox {{
        border: 1px solid #d5dfe5; border-radius: 4px; margin-top: 11px; padding: 12px 9px 9px 9px;
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffffff, stop:1 #f6f9fc);
    }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 9px; padding: 0 4px; color: #1e3287; }}

    QPushButton {{
        border: 1px solid #707070; border-radius: 3px; padding: 4px 16px; min-height: 17px; background: {boton};
    }}
    QPushButton:hover {{ border-color: #3c7fb1; background: {boton_hover}; }}
    QPushButton:pressed {{ border-color: #2c628b; background: {boton_press}; }}
    QPushButton:focus {{ outline: none; }}
    QPushButton:disabled {{ border-color: #adb2b5; color: #838383; background: #f4f4f4; }}

    QComboBox {{
        border: 1px solid #707070; border-radius: 3px; padding: 3px 22px 3px 6px; min-height: 17px; background: {boton};
    }}
    QComboBox:hover {{ border-color: #3c7fb1; background: {boton_hover}; }}
    QComboBox:on {{ border-color: #2c628b; background: {boton_press}; }}
    QComboBox:disabled {{ border-color: #adb2b5; color: #838383; background: #f4f4f4; }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QComboBox::down-arrow {{ image: url({flechas['abajo']}); }}
    QComboBox QAbstractItemView {{
        border: 1px solid #979797; background: white; selection-background-color: #3399ff; selection-color: white;
        outline: none;
    }}

    QLineEdit, QSpinBox, QDoubleSpinBox {{
        border: 1px solid #abadb3; border-left-color: #e2e3ea; border-right-color: #dbdfe6; border-bottom-color: #e3e9ef;
        border-radius: 2px; padding: 3px 4px; background: white; selection-background-color: #3399ff;
    }}
    QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: #5794bf; border-top-color: #3d7bad; }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: #3d7bad; border-top-color: #3d7bad; }}
    QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{ background: #f4f4f4; color: #838383; }}
    QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::down-button {{
        width: 16px; border-left: 1px solid #d0d7e0;
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f7f7f7, stop:1 #e3e3e3);
    }}
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background: {boton_hover}; }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url({flechas['arriba']}); }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url({flechas['abajo']}); }}

    QListWidget, QTableWidget {{
        border: 1px solid #d5dfe5; border-radius: 2px; background: white; outline: none; gridline-color: #eef1f4;
    }}
    QListWidget::item {{ padding: 4px 3px; border: 1px solid transparent; border-radius: 3px; }}
    QListWidget::item:hover, QTableWidget::item:hover {{
        border: 1px solid #b8d6fb; background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #fafbfd, stop:1 #ebf3fd);
    }}
    QListWidget::item:selected, QTableWidget::item:selected {{
        border: 1px solid #7da2ce; color: black;
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #dcebfc, stop:1 #c1dbfc);
    }}
    QHeaderView::section {{
        border: none; border-right: 1px solid #e2e7ed; border-bottom: 1px solid #d5dfe5; padding: 4px 6px;
        color: #4c607a; background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffffff, stop:1 #f1f5fb);
    }}

    QToolTip {{
        border: 1px solid #767676; color: #4c4c4c; padding: 4px;
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffffff, stop:1 #e4e5f0);
    }}
    QStatusBar {{
        color: #2b3c55; border-top: 1px solid #c5d2df;
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f8fbfe, stop:1 #dde7f1);
    }}
    QStatusBar::item {{ border: none; }}
    QRadioButton, QCheckBox {{ spacing: 6px; }}
    QProgressBar {{
        border: 1px solid #b2b2b2; border-radius: 2px; background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #e6e6e6, stop:0.5 #f4f4f4, stop:1 #e0e0e0);
    }}
    QProgressBar::chunk {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #c9f7b8, stop:0.45 #37d317, stop:0.5 #2bc40d,
        stop:1 #5edc3d);
    }}
    """



# ---------------------------------------------------------------------------
# Íconos de estado
# ---------------------------------------------------------------------------

def icono_pendiente(tam: int = 18) -> QIcon:
    """Círculo gris hueco: etapa todavía no iniciada."""
    pm = QPixmap(tam, tam)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor("#a9b4bf"), 1.5))
    p.setBrush(QColor("#f3f5f7"))
    p.drawEllipse(QRectF(2, 2, tam - 4, tam - 4))
    p.end()
    return QIcon(pm)


def icono_estado(ok: bool | None, tam: int = 18) -> QIcon:
    """Círculo brillante verde con tilde, rojo con cruz o azul con 'i'."""
    pm = QPixmap(tam, tam)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = QRectF(1, 1, tam - 2, tam - 2)
    claro, oscuro = {True: ("#8ee86a", "#24910b"), False: ("#ff8d80", "#c4111b"), None: ("#9fd3ff", "#1b62b8")}[ok]
    rad = QRadialGradient(r.center().x(), r.top() + 3, tam)
    rad.setColorAt(0, QColor(claro))
    rad.setColorAt(1, QColor(oscuro))
    p.setPen(QPen(QColor(oscuro).darker(130), 1))
    p.setBrush(rad)
    p.drawEllipse(r)
    p.setPen(QPen(QColor("white"), tam / 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    k = tam / 18
    if ok is True:
        p.drawPolyline(QPolygonF([QPointF(5 * k, 9.5 * k), QPointF(8 * k, 12.5 * k), QPointF(13 * k, 6 * k)]))
    elif ok is False:
        p.drawLine(QPointF(6 * k, 6 * k), QPointF(12 * k, 12 * k))
        p.drawLine(QPointF(12 * k, 6 * k), QPointF(6 * k, 12 * k))
    else:
        p.drawLine(QPointF(9 * k, 8.5 * k), QPointF(9 * k, 13 * k))
        p.drawPoint(QPointF(9 * k, 5.5 * k))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(degrade(0, 1, 0, tam / 2, (0, "#b0ffffff"), (1, "#00ffffff")))
    p.drawEllipse(QRectF(r.left() + 2.5 * k, r.top() + 0.5, r.width() - 5 * k, r.height() * 0.5))
    p.end()
    return QIcon(pm)

