"""Widgets dibujados a mano: encabezado, botón de grabar (orbe), medidor de nivel y barra de transporte."""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QAbstractButton, QFrame, QWidget

from estilo import degrade, fuente


class Encabezado(QWidget):
    """Franja azul brillante con la aurora de Vista."""

    def __init__(self, titulo: str, subtitulo: str):
        super().__init__()
        self.titulo, self.subtitulo = titulo, subtitulo
        self.setFixedHeight(92)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), degrade(0, 0, 0, h, (0, "#3d78b0"), (0.5, "#1d4f84"), (0.51, "#123d6b"), (1, "#1f5d96")))

        # aurora: tres cintas curvas translúcidas
        for (y0, y1, ctrl, color, ancho) in [
            (0.95, 0.15, 0.10, QColor(120, 230, 160, 70), 26),
            (1.05, 0.35, 0.30, QColor(90, 200, 255, 80), 18),
            (0.80, 0.00, -0.1, QColor(190, 255, 220, 45), 10),
        ]:
            path = QPainterPath(QPointF(w * 0.30, h * y0))
            path.cubicTo(QPointF(w * 0.55, h * ctrl), QPointF(w * 0.75, h * 1.1), QPointF(w * 1.02, h * y1))
            g = QLinearGradient(w * 0.3, 0, w, 0)
            g.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 0))
            g.setColorAt(0.5, color)
            g.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
            p.setPen(QPen(QBrush(g), ancho, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawPath(path)

        # brillo de vidrio en la mitad superior
        p.fillRect(QRectF(0, 0, w, h * 0.5), degrade(0, 0, 0, h * 0.5, (0, "#55ffffff"), (1, "#14ffffff")))
        p.setPen(QColor(255, 255, 255, 90))
        p.drawLine(0, 0, w, 0)
        p.setPen(QColor(0, 20, 50, 160))
        p.drawLine(0, h - 1, w, h - 1)

        # ícono: micrófono sobre esfera
        orbe = QRectF(18, h / 2 - 25, 50, 50)
        rad = QRadialGradient(orbe.center().x(), orbe.bottom() - 8, 40)
        rad.setColorAt(0, QColor("#bff0ff"))
        rad.setColorAt(0.5, QColor("#3a8fd6"))
        rad.setColorAt(1, QColor("#0d3566"))
        p.setPen(QPen(QColor(255, 255, 255, 120), 1))
        p.setBrush(rad)
        p.drawEllipse(orbe)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 235))
        c = orbe.center()
        p.drawRoundedRect(QRectF(c.x() - 6, c.y() - 15, 12, 20), 6, 6)
        p.setPen(QPen(QColor(255, 255, 255, 235), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(c.x() - 10, c.y() - 7, 20, 18), 200 * 16, 140 * 16)
        p.drawLine(QPointF(c.x(), c.y() + 11), QPointF(c.x(), c.y() + 16))
        p.drawLine(QPointF(c.x() - 6, c.y() + 16), QPointF(c.x() + 6, c.y() + 16))
        brillo = QRectF(orbe.left() + 7, orbe.top() + 2, orbe.width() - 14, orbe.height() * 0.45)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(degrade(0, brillo.top(), 0, brillo.bottom(), (0, "#c8ffffff"), (1, "#10ffffff")))
        p.drawEllipse(brillo)

        # textos con sombra suave
        for texto, f, y, color in [(self.titulo, fuente(16, QFont.Weight.DemiBold), 43, "#ffffff"),
                                    (self.subtitulo, fuente(9.5), 70, "#cfe8ff")]:
            p.setFont(f)
            p.setPen(QColor(0, 0, 0, 90))
            p.drawText(QPointF(83, y + 1), texto)
            p.setPen(QColor(color))
            p.drawText(QPointF(82, y), texto)


class Orbe(QAbstractButton):
    """Botón esférico de grabar/detener, al estilo del orbe de inicio de Vista."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(74, 74)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.grabando = False

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        hover = self.underMouse() and self.isEnabled()

        # anillo exterior
        p.setPen(QPen(QColor(0, 0, 0, 200), 1))
        p.setBrush(degrade(0, r.top(), 0, r.bottom(), (0, "#8a8a8a"), (0.5, "#2a2a2a"), (1, "#050505")))
        p.drawEllipse(r)

        c = r.adjusted(5, 5, -5, -5)
        if not self.isEnabled():
            claro, medio, oscuro = "#d8d8d8", "#8c8c8c", "#3c3c3c"
        elif self.grabando:
            claro, medio, oscuro = ("#ffd0c0", "#ff3b2b", "#6a0000") if hover else ("#ffb3a0", "#e3221a", "#550000")
        else:
            claro, medio, oscuro = ("#d6fbff", "#47a8f0", "#0b2f5e") if hover else ("#b6ecff", "#2f88d3", "#082650")
        rad = QRadialGradient(c.center().x(), c.bottom() - c.height() * 0.12, c.width() * 0.78)
        rad.setColorAt(0, QColor(claro))
        rad.setColorAt(0.55, QColor(medio))
        rad.setColorAt(1, QColor(oscuro))
        p.setPen(QPen(QColor(255, 255, 255, 110), 1))
        p.setBrush(rad)
        p.drawEllipse(c)

        # símbolo
        cc, s = c.center(), c.width() * 0.22
        p.setPen(Qt.PenStyle.NoPen)
        if self.grabando:
            p.setBrush(degrade(0, cc.y() - s, 0, cc.y() + s, (0, "#ffffff"), (1, "#e2e2e2")))
            p.drawRoundedRect(QRectF(cc.x() - s, cc.y() - s, 2 * s, 2 * s), 3, 3)
        else:
            punto = QRadialGradient(cc.x() - s * 0.3, cc.y() - s * 0.3, s * 1.4)
            punto.setColorAt(0, QColor("#ff8f80" if self.isEnabled() else "#eeeeee"))
            punto.setColorAt(1, QColor("#c0100a" if self.isEnabled() else "#9a9a9a"))
            p.setPen(QPen(QColor(255, 255, 255, 200), 1.5))
            p.setBrush(punto)
            p.drawEllipse(cc, s, s)

        # reflejo superior y resplandor inferior
        brillo = QRectF(c.left() + c.width() * 0.13, c.top() + 2, c.width() * 0.74, c.height() * 0.48)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(degrade(0, brillo.top(), 0, brillo.bottom(),
                           (0, "#e6ffffff" if hover else "#c8ffffff"), (1, "#0cffffff")))
        p.drawEllipse(brillo)
        if self.isDown():
            p.setBrush(QColor(0, 0, 0, 55))
            p.drawEllipse(c)


class Medidor(QWidget):
    """Barra de nivel al estilo de la barra de progreso de Vista (verde/amarilla/roja) con destello."""

    MIN_DB = -60.0
    COLORES = {
        "verde": ("#c9f7b1", "#4ccb24", "#1e8b07", "#3fb51a"),
        "amarillo": ("#fff3a8", "#ebc61f", "#a68300", "#d9b310"),
        "rojo": ("#ffb4aa", "#e3352d", "#99100c", "#cc2620"),
    }

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(24)
        self.setMinimumWidth(200)
        self.reiniciar()

    def reiniciar(self):
        self.db = self.pico = self.MIN_DB
        self.t_pico = 0.0
        self.activo = False
        self.update()

    def poner(self, rms: float, pico: float, dt: float):
        ahora = time.monotonic()
        db = 20 * math.log10(max(rms, 1e-6))
        pk = 20 * math.log10(max(pico, 1e-6))
        self.db = max(db, self.db - 28 * dt)  # caída de 28 dB/s
        if pk >= self.pico or ahora - self.t_pico > 1.5:
            self.pico, self.t_pico = pk, ahora
        self.activo = True
        self.update()

    def _x(self, db: float, ancho: float) -> float:
        return max(0.0, min(1.0, (db - self.MIN_DB) / -self.MIN_DB)) * ancho

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        # canal
        p.setPen(QPen(QColor("#b2b2b2"), 1))
        p.setBrush(degrade(0, r.top(), 0, r.bottom(), (0, "#e9e9e9"), (0.5, "#f6f6f6"), (1, "#dadada")))
        p.drawRoundedRect(r, 3, 3)
        interior = r.adjusted(1.5, 1.5, -1.5, -1.5)

        # relleno
        ancho = self._x(self.db, interior.width())
        if ancho > 1:
            nombre = "rojo" if self.pico > -3 else "amarillo" if self.pico > -12 else "verde"
            claro, base, oscuro, borde = self.COLORES[nombre]
            barra = QRectF(interior.left(), interior.top(), ancho, interior.height())
            p.setPen(QPen(QColor(borde), 1))
            p.setBrush(degrade(0, barra.top(), 0, barra.bottom(),
                               (0, claro), (0.45, base), (0.55, oscuro), (1, base)))
            p.drawRoundedRect(barra, 2, 2)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(degrade(0, barra.top(), 0, barra.center().y(), (0, "#a0ffffff"), (1, "#20ffffff")))
            p.drawRoundedRect(QRectF(barra.left() + 1, barra.top() + 1, barra.width() - 2, barra.height() / 2 - 1), 2, 2)

            # destello que recorre la barra
            if self.activo:
                fase = (time.monotonic() % 2.2) / 2.2
                x = interior.left() + fase * (interior.width() + 120) - 60
                g = QLinearGradient(x - 60, 0, x + 60, 0)
                g.setColorAt(0, QColor(255, 255, 255, 0))
                g.setColorAt(0.5, QColor(255, 255, 255, 120))
                g.setColorAt(1, QColor(255, 255, 255, 0))
                p.save()
                p.setClipRect(barra)
                p.fillRect(barra, g)
                p.restore()

        # marcas cada 10 dB
        p.setPen(QColor(0, 0, 0, 35))
        for db in range(-50, 0, 10):
            x = interior.left() + self._x(db, interior.width())
            p.drawLine(QPointF(x, interior.bottom() - 4), QPointF(x, interior.bottom()))

        # pico retenido
        if self.pico > self.MIN_DB:
            x = interior.left() + self._x(self.pico, interior.width())
            p.setPen(QPen(QColor(30, 30, 30, 170), 2))
            p.drawLine(QPointF(x, interior.top() + 1), QPointF(x, interior.bottom() - 1))


class BarraTransporte(QFrame):
    """Barra negra brillante tipo Windows Media Player 11."""

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        h = r.height()
        p.setPen(QPen(QColor("#000000"), 1))
        p.setBrush(degrade(0, 0, 0, h, (0, "#4a4f55"), (0.48, "#1d2125"), (0.5, "#050607"), (1, "#1b2a36")))
        p.drawRoundedRect(r, 6, 6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(degrade(0, 0, 0, h * 0.5, (0, "#40ffffff"), (1, "#08ffffff")))
        p.drawRoundedRect(QRectF(r.left() + 1, r.top() + 1, r.width() - 2, h * 0.48), 5, 5)
        # resplandor celeste inferior
        rad = QRadialGradient(r.center().x(), r.bottom() + 10, r.width() * 0.45)
        rad.setColorAt(0, QColor(80, 170, 255, 70))
        rad.setColorAt(1, QColor(80, 170, 255, 0))
        p.setBrush(rad)
        p.drawRoundedRect(r, 6, 6)

