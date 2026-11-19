"""Botón «Copiar» de los visores: lleva la minuta o la transcripción al portapapeles."""
from __future__ import annotations

import pytest
from PySide6 import QtWidgets
from PySide6.QtCore import QCoreApplication, QEvent

from src.interfaz.visores import DialogoResultado
from .test_presentacion import datos, fila

MINUTA = """# Minuta de reunión

## Resumen

Se acordó usar el foro.

## Acciones pendientes

- [01:22] Abrir un tema sobre los mapatones. — Responsable: Rafael
"""


@pytest.fixture(scope='module')
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def visor(app):
    creados = []

    def crear(*args, **kwargs):
        creados.append(DialogoResultado(*args, **kwargs))
        return creados[-1]

    yield crear
    for v in creados:
        v.close()
        v.deleteLater()
        QCoreApplication.sendPostedEvents(v, QEvent.Type.DeferredDelete)


def test_copiar_minuta_lleva_markdown_y_formato(app, visor):
    app.clipboard().clear()
    v = visor('Minuta', MINUTA, minuta=True)
    v.boton_copiar.click()
    datos_copiados = app.clipboard().mimeData()
    assert datos_copiados.text() == MINUTA
    assert datos_copiados.hasHtml()
    assert '<h2>Acciones pendientes</h2>' in datos_copiados.html()
    assert 'Responsable: Rafael' in datos_copiados.html()
    assert v.boton_copiar.text() == 'Copiado ✓'


def test_copiar_transcripcion_lleva_texto_legible_no_json(app, visor):
    app.clipboard().clear()
    original = datos(fila(0, 1, 'Propongo usar el foro.'), fila(1, 2, 'Yo lo abro.', speaker='SPEAKER_01', name='Rafael'))
    v = visor('Transcripción', original, minuta=False)
    v.boton_copiar.click()
    texto = app.clipboard().mimeData().text()
    assert 'Propongo usar el foro.' in texto and 'Rafael' in texto and 'Ana' in texto
    assert '"segments"' not in texto
    assert app.clipboard().mimeData().hasHtml()


def test_copiar_no_interpreta_html_del_contenido(app, visor):
    app.clipboard().clear()
    ataque = '<img src="https://ejemplo.invalid/privado">'
    v = visor('Minuta', MINUTA.replace('Se acordó usar el foro.', ataque), minuta=True)
    v.boton_copiar.click()
    html = app.clipboard().mimeData().html()
    assert '<img' not in html
    assert '&lt;img' in html
