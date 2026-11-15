"""Visores de instantáneas verificadas; no consultan archivos ni proveedores."""
from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QPlainTextEdit, QPushButton, QTabWidget,
                               QTextBrowser, QVBoxLayout)

from .presentacion import minuta_html, transcripcion_html


class LecturaSegura(QTextBrowser):
    """No resuelve recursos ni navega, incluso si cambia el contenido del visor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)

    def loadResource(self, tipo, url):
        return None


class DialogoResultado(QDialog):
    def __init__(self, titulo: str, contenido: str, *, minuta: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.resize(850, 640)
        lay = QVBoxLayout(self)
        self.pestanas = QTabWidget(self)
        self.lectura = LecturaSegura(self.pestanas)
        html = minuta_html(contenido) if minuta else transcripcion_html(contenido)
        # Sin color incrustado: QTextBrowser utiliza la paleta efectiva al dibujar.
        self.lectura.setHtml(f'<html><body>{html}</body></html>')
        self.original = QPlainTextEdit(self.pestanas)
        self.original.setReadOnly(True)
        self.original.setPlainText(contenido)
        self.pestanas.addTab(self.lectura, 'Lectura')
        self.pestanas.addTab(self.original, 'Original (Markdown)' if minuta else 'Original (JSON)')
        lay.addWidget(self.pestanas, 1)
        cerrar = QPushButton('Cerrar', self)
        cerrar.clicked.connect(self.accept)
        lay.addWidget(cerrar)
