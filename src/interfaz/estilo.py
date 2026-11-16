"""Estética Windows Vista compartida por toda la interfaz: fuentes, hoja de estilo e íconos de estado."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPalette, QPen, QPixmap, QPolygonF, QRadialGradient

FAMILIAS = ["Segoe UI", "Open Sans", "Noto Sans", "Cantarell", "sans-serif"]
ESCALA_TEXTO = 1.15  # multiplica todos los tamaños de letra


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

# Paletas completas para que Fusion no mezcle texto del sistema con fondos propios.
PALETAS = {
    False: {'ventana': '#f4f7fa', 'base': '#ffffff', 'alterno': '#edf2f7',
            'texto': '#182b3c', 'secundario': '#40576c', 'deshabilitado': '#586b7c',
            'boton': '#e7edf4', 'seleccion': '#175c96', 'seleccion_texto': '#ffffff',
            'borde': '#778b9e', 'acento': '#164d83', 'aviso': '#824500',
            'claro': '#ffffff', 'medio_claro': '#e4eaf1', 'medio': '#91a1af',
            'oscuro': '#5d6f80', 'sombra': '#405264'},
    True: {'ventana': '#1d2834', 'base': '#141d27', 'alterno': '#253443',
           'texto': '#edf3fa', 'secundario': '#c4d2df', 'deshabilitado': '#9eafbf',
           'boton': '#2d3e50', 'seleccion': '#87bcef', 'seleccion_texto': '#10243a',
           'borde': '#718ca5', 'acento': '#a4d0ff', 'aviso': '#ffcb84',
           'claro': '#596e82', 'medio_claro': '#465b6e', 'medio': '#34485b',
           'oscuro': '#101923', 'sombra': '#0a1119'},
}


TEMAS = (('Sistema', 'sistema'), ('Claro', 'claro'), ('Oscuro', 'oscuro'))


def tema_guardado(config) -> str:
    tema = config.value('tema', 'sistema')
    return tema if tema in ('sistema', 'claro', 'oscuro') else 'sistema'


def oscuro_sistema(app) -> bool:
    esquema = app.styleHints().colorScheme()
    # Algunas plataformas no informan el esquema. Recordar el color del sistema
    # ANTES de aplicar nuestras paletas, no deducirlo del último tema manual.
    previo = app.property('tema_sistema_oscuro')
    if esquema != Qt.ColorScheme.Unknown:
        oscuro = esquema == Qt.ColorScheme.Dark
    elif previo is not None:
        oscuro = bool(previo)
    else:
        oscuro = app.palette().color(QPalette.ColorRole.Window).lightness() < 128
    app.setProperty('tema_sistema_oscuro', oscuro)
    return oscuro


def aplicar_tema(app, tema: str) -> None:
    aplicar_estilo(app, oscuro={'sistema': None, 'claro': False, 'oscuro': True}[tema])


def aplicar_estilo(app, *, oscuro: bool | None = None) -> None:
    sistema = oscuro_sistema(app)
    if oscuro is None:
        oscuro = sistema
    # Retirar la hoja anterior antes de cambiar la paleta. No superponer
    # reglas de temas distintos sobre widgets existentes.
    app.setStyleSheet('')
    c = PALETAS[oscuro]
    if app.style().objectName().lower() != 'fusion':
        app.setStyle('Fusion')
    pal = QPalette()
    roles = {'Window': 'ventana', 'WindowText': 'texto', 'Base': 'base',
             'AlternateBase': 'alterno', 'Text': 'texto', 'Button': 'boton',
             'ButtonText': 'texto', 'Highlight': 'seleccion', 'Accent': 'seleccion',
             'HighlightedText': 'seleccion_texto',
             'ToolTipBase': 'base', 'ToolTipText': 'texto', 'PlaceholderText': 'secundario',
             'Link': 'acento', 'LinkVisited': 'acento', 'BrightText': 'texto',
             'Light': 'claro', 'Midlight': 'medio_claro', 'Mid': 'medio',
             'Dark': 'oscuro', 'Shadow': 'sombra'}
    for grupo in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive, QPalette.ColorGroup.Disabled):
        for rol, clave in roles.items():
            if grupo == QPalette.ColorGroup.Disabled and rol in (
                    'WindowText', 'Text', 'ButtonText', 'PlaceholderText'):
                clave = 'deshabilitado'
            pal.setColor(grupo, getattr(QPalette.ColorRole, rol), QColor(c[clave]))
    app.setPalette(pal)
    app.setFont(fuente(9.5))
    # Los indicadores, flechas, estados de selección y foco los dibuja Fusion
    # con esta misma paleta. Evitar subcontroles parciales de QSS.
    app.setStyleSheet(f"""
        QLabel#instruccion {{ color: {c['acento']}; }}
        QLabel#secundario {{ color: {c['secundario']}; }}
        QLabel#aviso {{ color: {c['aviso']}; }}
        QGroupBox {{ margin-top: 9px; padding: 9px 7px 7px; border: 1px solid {c['borde']}; border-radius: 5px; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; color: {c['acento']}; }}
        QSplitter::handle {{ background: {c['borde']}; }}
    """)


def tooltip_literal(texto: str) -> str:
    """Los tooltips de Qt interpretan texto enriquecido; escapar datos variables."""
    return "<qt>" + escape(texto).replace("\n", "<br>") + "</qt>" if texto else ""


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

