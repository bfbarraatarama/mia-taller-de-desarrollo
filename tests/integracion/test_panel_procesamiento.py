"""Reapertura y decisiones en Qt, sin audio ni inferencia real."""
from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
QtWidgets = pytest.importorskip('PySide6.QtWidgets', reason='falta PySide6 (entorno de la interfaz)')

from src.asociacion.etiquetado import Decision, ModeloFichas
from src.interfaz import panel_procesamiento as interfaz
from src.minutas.generacion import ConfiguracionMinutas
from src.minutas.proveedores import resolver_destino
from src.pipeline import (consultar_identificacion, consultar_reunion, continuar_reunion,
                          preparar_reunion, procesar_reunion)
from src.pipeline.ejecucion import _exclusivo
from .test_workflow import modelos_falsos, solicitud, destino_controlado, instantanea


@pytest.fixture(scope='module')
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def panel(app, tmp_path, destino_controlado, monkeypatch):
    from PySide6.QtCore import QCoreApplication, QEvent
    from shiboken6 import Shiboken

    p = interfaz.PanelProcesamiento(lambda: tmp_path)
    errores = []
    monkeypatch.setattr(p, '_mostrar_error', lambda *args: errores.append(args))
    p.errores_prueba = errores
    try:
        yield p
    finally:
        # Restaurar los dobles mientras el objeto nativo sigue existiendo.
        monkeypatch.undo()
        p.proc = None
        p.reloj.stop()
        p.close()
        # Las pruebas no ejecutan QApplication.exec(): despachar la destrucción.
        p.deleteLater()
        QCoreApplication.sendPostedEvents(p, QEvent.Type.DeferredDelete)
        assert not Shiboken.isValid(p)


def test_reapertura_recupera_configuracion_fuentes_progreso_y_no_ejecuta(panel, tmp_path, modelos_falsos, monkeypatch):
    s = replace(solicitud(tmp_path), modelo_stt='large-v3', dispositivo_stt='cuda', dispositivo_diarizacion='cpu',
                num_speakers=2, minutas=ConfiguracionMinutas(secciones=('acciones', 'resumen'),
                num_ctx=4096, temperatura=.2, max_tokens_salida=1024))
    procesar_reunion(s)
    s.fuentes[0].unlink()
    previo = instantanea(s.salida, ['workflow.json', 'asr.json', 'minutes.json'])
    monkeypatch.setattr(panel, '_lanzar', lambda *a, **k: pytest.fail('no corresponde lanzar un proceso'))
    monkeypatch.setattr(interfaz, 'etiquetar', lambda *a, **k: pytest.fail('no corresponde abrir fichas'))
    monkeypatch.setattr(interfaz.QFileDialog, 'getExistingDirectory', lambda *a: str(s.salida))
    panel._abrir_reunion()
    assert not panel.errores_prueba
    assert panel.archivos() == [str(p.resolve()) for p in s.fuentes]
    assert 'copia conservada' in panel.lista.item(0).text()
    assert panel.cb_whisper.currentData() == 'large-v3'
    assert panel.cb_dispositivo_stt.currentData() == 'cuda'
    assert panel.cb_dispositivo.currentData() == 'cpu'
    assert panel.sp_hablantes.value() == 2
    assert panel._config_minutas() == s.minutas
    assert all(fila[1].value() == 1000 for fila in panel.filas.values())
    assert panel.btn_fichas.isEnabled() and panel.btn_minuta.isEnabled()
    assert instantanea(s.salida, previo) == previo
    assert tuple(modelos_falsos.values()) == (1, 1, 1)
    panel.cb_whisper.setCurrentIndex(panel.cb_whisper.findData('tiny'))
    assert not panel.btn_fichas.isEnabled()
    panel._nueva_reunion()
    assert panel.archivos() == [] and panel.resultados is None
    assert panel.cb_whisper.currentData() == 'medium'
    assert panel.cb_dispositivo.currentData() == panel.cb_dispositivo_stt.currentData() == 'auto'
    assert panel.sp_hablantes.value() == 0 and panel._config_minutas() == ConfiguracionMinutas()
    assert not panel.btn_minuta.isEnabled()
    panel.ultima_grabacion = s.fuentes[1]
    panel._alternar()
    assert panel.archivos() == []  # no hereda automáticamente otra reunión


def test_reapertura_activa_no_expone_resultados(panel, tmp_path, modelos_falsos):
    s = solicitud(tmp_path)
    procesar_reunion(s)
    with _exclusivo(s.salida):
        panel._restaurar_reunion(consultar_reunion(s.salida, incluir_fuentes=True))
        assert not panel.btn_minuta.isEnabled()
        assert not panel.btn_fichas.isEnabled() and not panel.btn_procesar.isEnabled()
    panel._restaurar_reunion(consultar_reunion(s.salida, incluir_fuentes=True))
    assert panel.btn_minuta.isEnabled() and panel.btn_procesar.isEnabled()


def test_continuacion_usa_seleccion_actual_y_consentimiento_nuevo(panel, tmp_path, modelos_falsos, monkeypatch):
    s = solicitud(tmp_path, modo='pausa')
    preparar_reunion(s)
    panel._restaurar_reunion(consultar_reunion(s.salida, incluir_fuentes=True))
    assert panel.btn_fichas.isEnabled() and not panel.btn_minuta.isEnabled()
    panel.cb_modelo.setCurrentIndex(panel.cb_modelo.findData('nova-lite'))
    panel.secciones['acciones'].setChecked(True)
    lanzados = []
    confirmaciones = []
    respuestas = iter([False, True])
    monkeypatch.setattr(interfaz, 'etiquetar', lambda *a, **k: Decision('escribir'))
    def confirmar(destino):
        confirmaciones.append(destino.huella)
        return next(respuestas)
    monkeypatch.setattr(panel, '_autorizacion_remota', confirmar)
    monkeypatch.setattr(panel, '_lanzar', lambda args, carpeta, **k: lanzados.append((args, carpeta, k)))
    panel._continuar_con_fichas()
    assert not lanzados and consultar_reunion(s.salida)['estado'] == 'esperando_identificacion'
    panel._continuar_con_fichas()
    assert not panel.errores_prueba
    assert len(confirmaciones) == 2 and len(lanzados) == 1
    args, carpeta, opciones = lanzados[0]
    assert carpeta == s.salida and '--permitir-remoto' in args
    assert args[args.index('--modelo')+1] == 'nova-lite'
    assert args[args.index('--secciones')+1] == 'resumen,acciones'
    assert args[args.index('--destino-autorizado')+1] == resolver_destino('nova-lite').huella
    assert json.loads(opciones['stdin'])['accion'] == 'escribir'
    assert not panel._config_minutas().permitir_remoto
    assert tuple(modelos_falsos.values()) == (1, 1, 0)


def test_reapertura_de_identificacion_anterior_y_cancelacion(panel, tmp_path, modelos_falsos, monkeypatch):
    s = solicitud(tmp_path, modo='pausa')
    preparar_reunion(s)
    asociacion, _, _, _ = consultar_identificacion(s.salida)
    fichas = ModeloFichas(asociacion)
    fichas.escribir_nombre('SPEAKER_00', 'Ana')
    decision = fichas.confirmar()
    continuar_reunion(s.salida, decision)
    panel._restaurar_reunion(consultar_reunion(s.salida, incluir_fuentes=True))
    def cancelar(a, p, *, anterior):
        assert anterior == decision.etiquetado
        return Decision('cancelar')
    monkeypatch.setattr(interfaz, 'etiquetar', cancelar)
    monkeypatch.setattr(panel, '_lanzar', lambda *a, **k: pytest.fail('no corresponde cancelar una reunión completada'))
    previo = instantanea(s.salida, ['workflow.json', 'speakers.json'])
    panel._continuar_con_fichas()
    assert not panel.errores_prueba and instantanea(s.salida, previo) == previo


def test_cancelacion_de_pausa_no_consulta_consentimiento(panel, tmp_path, modelos_falsos, monkeypatch):
    s = replace(solicitud(tmp_path, modo='pausa'), minutas=ConfiguracionMinutas(modelo='nova-lite'))
    preparar_reunion(s)
    panel._restaurar_reunion(consultar_reunion(s.salida, incluir_fuentes=True))
    monkeypatch.setattr(interfaz, 'etiquetar', lambda *a, **k: Decision('cancelar'))
    monkeypatch.setattr(panel, '_autorizacion_remota', lambda *a: pytest.fail('no corresponde autorizar'))
    lanzados = []
    monkeypatch.setattr(panel, '_lanzar', lambda args, carpeta, **k: lanzados.append((args, k)))
    panel._continuar_con_fichas()
    assert not panel.errores_prueba and len(lanzados) == 1
    args, opciones = lanzados[0]
    assert '--permitir-remoto' not in args and json.loads(opciones['stdin'])['accion'] == 'cancelar'


def test_temporizadores_viejos_no_actuan_sobre_proceso_o_reunion_nuevos(panel, tmp_path, monkeypatch):
    llamadas = []
    viejo = SimpleNamespace(state=lambda: interfaz.QProcess.ProcessState.Running,
                            kill=lambda: llamadas.append('viejo'))
    nuevo = SimpleNamespace(state=lambda: interfaz.QProcess.ProcessState.Running,
                            kill=lambda: llamadas.append('nuevo'))
    panel.proc = nuevo
    panel._forzar_cancelacion(viejo)
    assert not llamadas
    panel._forzar_cancelacion(nuevo)
    assert llamadas == ['nuevo']
    panel.proc = None
    panel.resultados = tmp_path
    monkeypatch.setattr(panel, '_continuar_con_fichas', lambda: llamadas.append('fichas'))
    panel._fichas_pendientes(panel._revision-1, tmp_path)
    panel._fichas_pendientes(panel._revision, tmp_path / 'otra')
    assert llamadas == ['nuevo']
    panel._fichas_pendientes(panel._revision, tmp_path)
    assert llamadas == ['nuevo', 'fichas']


def test_decision_de_modal_no_lanza_si_cambio_la_revision(panel, tmp_path, modelos_falsos, monkeypatch):
    s = solicitud(tmp_path, modo='pausa')
    preparar_reunion(s)
    panel._restaurar_reunion(consultar_reunion(s.salida, incluir_fuentes=True))
    def confirmar(*a, **k):
        panel._revision += 1
        return Decision('escribir')
    monkeypatch.setattr(interfaz, 'etiquetar', confirmar)
    monkeypatch.setattr(panel, '_lanzar', lambda *a, **k: pytest.fail('decisión obsoleta'))
    panel._continuar_con_fichas()
    assert not panel.errores_prueba
    assert consultar_reunion(s.salida)['estado'] == 'esperando_identificacion'


def test_aviso_de_seleccion_pendiente_y_original_modificado(panel, tmp_path, modelos_falsos):
    from .test_workflow import archivo_wav
    s = solicitud(tmp_path)
    procesar_reunion(s)
    archivo_wav(s.fuentes[0], 48000)
    panel._restaurar_reunion(consultar_reunion(s.salida, incluir_fuentes=True))
    assert 'original modificado' in panel.lista.item(0).text()
    assert 'aún no se aplicó' not in panel.lbl_destino_modelo.text()
    panel.cb_modelo.setCurrentIndex(panel.cb_modelo.findData('nova-lite'))
    assert 'aún no se aplicó' in panel.lbl_destino_modelo.text()
    assert panel.btn_minuta.isEnabled() and panel.btn_fichas.isEnabled()
    panel.cb_modelo.setCurrentIndex(panel.cb_modelo.findData('qwen2.5-7b'))
    assert 'aún no se aplicó' not in panel.lbl_destino_modelo.text()
