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


@pytest.mark.parametrize('oscuro', [False, True])
def test_paleta_y_controles_de_panel(app, tmp_path, destino_controlado, oscuro):
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtGui import QPalette
    from shiboken6 import Shiboken
    from src.interfaz.estilo import aplicar_estilo, PALETAS

    pal, hoja, font = app.palette(), app.styleSheet(), app.font()
    panel = None
    try:
        # Reproducir el inicio real: configurar el estilo antes de crear widgets.
        app.setStyleSheet('')
        aplicar_estilo(app, oscuro=oscuro)
        panel = interfaz.PanelProcesamiento(lambda: tmp_path)
        panel.resize(650, 850)
        panel.show()
        panel.lbl.setText('La reunión está completada. Los resultados corresponden a la configuración guardada.')
        app.processEvents()
        roles = QPalette.ColorRole
        assert app.palette().color(roles.Window).name() == PALETAS[oscuro]['ventana']
        assert panel.cb_modelo.palette().color(roles.Text).name() == PALETAS[oscuro]['texto']
        assert panel.cb_modelo.palette().color(roles.ButtonText).name() == PALETAS[oscuro]['texto']
        assert panel.ed_resultados.palette().color(roles.Text).name() == PALETAS[oscuro]['texto']
        assert panel.secciones['resumen'].isChecked()
        assert panel.lbl.wordWrap()
        assert panel.lbl.height() >= max(panel.lbl.fontMetrics().height(), panel.lbl.heightForWidth(panel.lbl.width()))
        assert panel.lbl.geometry().bottom() < panel.btn_abrir_reunion.geometry().top()
        assert panel.btn_procesar.geometry().top() < panel.btn_minuta.geometry().top()
        assert panel.lbl.width() > panel.btn_abrir_reunion.width()
    finally:
        if panel is not None:
            panel.reloj.stop()
            panel.close()
            panel.deleteLater()
            QCoreApplication.sendPostedEvents(panel, QEvent.Type.DeferredDelete)
            assert not Shiboken.isValid(panel)
        app.setStyleSheet('')
        app.setPalette(pal)
        app.setFont(font)
        app.setStyleSheet(hoja)


def test_visor_de_resultado_consulta_instantanea_verificada(panel, tmp_path, modelos_falsos, monkeypatch):
    s = solicitud(tmp_path)
    procesar_reunion(s)
    panel._restaurar_reunion(consultar_reunion(s.salida, incluir_fuentes=True))
    vistos = []
    def inspeccionar(ventana):
        assert ventana.original.isReadOnly()
        assert ventana.lectura.isReadOnly()
        assert not ventana.lectura.openLinks() and not ventana.lectura.openExternalLinks()
        vistos.append((ventana.original.toPlainText(), ventana.lectura.toPlainText()))
        return 0
    monkeypatch.setattr(interfaz.DialogoResultado, 'exec', inspeccionar)
    previo = instantanea(s.salida, ['workflow.json', 'transcription.json', 'minutes.md'])
    panel._ver(interfaz.TRANSCRIPCION)
    panel._ver(interfaz.MINUTA)
    assert len(vistos) == 2 and not panel.errores_prueba
    assert vistos[0][0] == (s.salida / 'transcription.json').read_text(encoding='utf-8')
    assert 'Transcripción de la reunión' in vistos[0][1]
    assert vistos[1][0] == (s.salida / 'minutes.md').read_text(encoding='utf-8')
    assert 'Minuta de reunión' in vistos[1][1]
    assert instantanea(s.salida, previo) == previo
    (s.salida / 'asr.json').write_text('{}', encoding='utf-8')
    panel._ver(interfaz.MINUTA)
    assert len(vistos) == 2 and panel.errores_prueba


@pytest.mark.parametrize('oscuro', [False, True])
def test_visor_muestra_contenido_inerte_y_original(app, panel, oscuro):
    from PySide6.QtCore import QCoreApplication, QEvent, QUrl
    from shiboken6 import Shiboken
    from src.interfaz.estilo import aplicar_estilo
    from src.interfaz.visores import DialogoResultado
    from .test_presentacion import datos, fila

    pal, hoja, font = app.palette(), app.styleSheet(), app.font()
    aplicar_estilo(app, oscuro=oscuro)
    ataque = '<img src="https://ejemplo.invalid/privado">'
    original = datos(fila(0, 1, ataque), fila(1, 2, 'texto siguiente.'))
    v = DialogoResultado('Transcripción', original, minuta=False, parent=panel)
    try:
        assert ataque in v.lectura.toPlainText()
        assert v.original.toPlainText() == original
        assert v.lectura.loadResource(2, QUrl('file:///tmp/no-leer')) is None
        assert v.lectura.loadResource(2, QUrl('https://ejemplo.invalid/privado')) is None
        assert not v.lectura.openLinks() and not v.lectura.openExternalLinks()
        assert v.pestanas.count() == 2
    finally:
        v.close()
        v.deleteLater()
        QCoreApplication.sendPostedEvents(v, QEvent.Type.DeferredDelete)
        assert not Shiboken.isValid(v)
        app.setPalette(pal)
        app.setStyleSheet(hoja)
        app.setFont(font)


@pytest.mark.parametrize('oscuro', [False, True])
def test_ventana_en_columnas_y_detalles_de_captura(app, tmp_path, monkeypatch, destino_controlado, oscuro):
    from PySide6.QtCore import QCoreApplication, QEvent, Qt
    from shiboken6 import Shiboken
    from src.interfaz.estilo import aplicar_estilo
    from src.interfaz.interfaz import Ventana

    # No depende de dispositivos, archivos privados ni preferencias del equipo.
    monkeypatch.setattr(Ventana, '_cargar_dispositivos', lambda *a, **k: None)
    def configurar(v):
        v.rb_auto.setChecked(True)
        v.ed_salida.setText(str(tmp_path))
    monkeypatch.setattr(Ventana, '_cargar_config', configurar)
    monkeypatch.setattr(Ventana, '_ofrecer_grabaciones_interrumpidas', lambda self: None)
    monkeypatch.setattr(Ventana, '_guardar_config', lambda self: None)
    pal, hoja, font = app.palette(), app.styleSheet(), app.font()
    aplicar_estilo(app, oscuro=oscuro)
    v = Ventana()
    try:
        v.resize(1440, 920)
        v.show()
        app.processEvents()
        assert v.divisor.orientation() == Qt.Orientation.Horizontal
        assert v.divisor.widget(0).geometry().right() < v.panel.geometry().left()
        assert v.desplazable.horizontalScrollBar().maximum() == 0
        assert v.desplazable.verticalScrollBar().maximum() == 0
        assert not v.btn_detalles.isEnabled()
        assert not v.lista.isVisible() and not v.tabla.isVisible()
        v._mostrar_reporte({'archivo': 'prueba.wav', 'duracion_total_s': 3., 'modo': 'auto',
                           'pruebas': [{'prueba': 'audio válido', 'ok': True, 'detalle': {}}], 'fuentes': {}})
        assert v.btn_detalles.isEnabled() and not v.lista.isVisible()
        v.btn_detalles.click()
        app.processEvents()
        assert v.lista.isVisible() and v.tabla.isVisible()
        assert v.lista.count() == 1 and v.tabla.columnCount() == 8
        v.btn_detalles.click()
        v.resize(660, 740)
        app.processEvents()
        assert v.divisor.orientation() == Qt.Orientation.Vertical
        assert v.desplazable.verticalScrollBar().maximum() > 0
        v.desplazable.ensureWidgetVisible(v.panel.btn_procesar)
        assert v.panel.btn_procesar.isVisible()
        v.resize(1440, 920)
        app.processEvents()
        assert v.divisor.orientation() == Qt.Orientation.Horizontal
    finally:
        v.panel.reloj.stop()
        v.reloj.stop()
        v.close()
        monkeypatch.undo()
        v.deleteLater()
        QCoreApplication.sendPostedEvents(v, QEvent.Type.DeferredDelete)
        assert not Shiboken.isValid(v)
        app.setPalette(pal)
        app.setStyleSheet(hoja)
        app.setFont(font)


@pytest.mark.parametrize('permiso', [False, True])
def test_dialogo_de_consentimiento_con_texto_literal(panel, monkeypatch, permiso):
    from PySide6.QtCore import Qt
    caja_tipo = interfaz.QMessageBox
    boton = caja_tipo.StandardButton.Yes if permiso else caja_tipo.StandardButton.No
    ataque = '<img src="https://ejemplo.invalid/recurso">'
    def resolver(caja):
        assert caja.textFormat() == Qt.TextFormat.PlainText
        assert ataque in caja.text()
        assert caja.defaultButton() is caja.button(caja_tipo.StandardButton.No)
        assert caja.escapeButton() is caja.button(caja_tipo.StandardButton.No)
        caja.button(boton).click()
        return 0
    monkeypatch.setattr(caja_tipo, 'exec', resolver)
    assert panel._autorizacion_remota(SimpleNamespace(descripcion=ataque)) is permiso



def test_tema_guardado_y_referencia_del_sistema(app, tmp_path):
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtGui import QColor, QPalette
    from src.interfaz.estilo import tema_guardado, oscuro_sistema

    c = QSettings(str(tmp_path / 'tema.ini'), QSettings.Format.IniFormat)
    assert tema_guardado(c) == 'sistema'
    for tema in ('claro', 'oscuro', 'sistema', 'invalido'):
        c.setValue('tema', tema)
        c.sync()
        assert tema_guardado(QSettings(c.fileName(), QSettings.Format.IniFormat)) == (
            'sistema' if tema == 'invalido' else tema)

    # Emular una plataforma que no informa el esquema de color. La referencia
    # de sistema no debe cambiar al aplicar manualmente otra paleta.
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor('#111111'))
    esquema = [Qt.ColorScheme.Unknown]
    props = {}
    sim = SimpleNamespace(styleHints=lambda: SimpleNamespace(colorScheme=lambda: esquema[0]),
                          property=props.get, setProperty=props.__setitem__, palette=lambda: pal)
    assert oscuro_sistema(sim) is True
    pal.setColor(QPalette.ColorRole.Window, QColor('#ffffff'))
    assert oscuro_sistema(sim) is True
    esquema[0] = Qt.ColorScheme.Light
    assert oscuro_sistema(sim) is False
    esquema[0] = Qt.ColorScheme.Unknown
    assert oscuro_sistema(sim) is False


def test_selector_de_tema_en_vivo_conserva_reunion_y_visores(app, tmp_path, monkeypatch,
                                                          destino_controlado, modelos_falsos):
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt
    from PySide6.QtGui import QPalette, QTextCursor
    from shiboken6 import Shiboken
    from src.interfaz import estilo
    from src.interfaz import interfaz as principal
    from src.interfaz.visores import DialogoResultado

    ini = str(tmp_path / 'tema.ini')
    def config(*args):
        return QSettings(ini, QSettings.Format.IniFormat)
    c = config()
    c.setValue('tema', 'claro')
    c.setValue('salida', str(tmp_path))
    c.sync()
    monkeypatch.setattr(principal, 'QSettings', config)
    monkeypatch.setattr(principal.Ventana, '_cargar_dispositivos', lambda *a, **k: None)
    monkeypatch.setattr(principal.Ventana, '_ofrecer_grabaciones_interrumpidas', lambda self: None)
    sistema = [False]
    monkeypatch.setattr(estilo, 'oscuro_sistema', lambda app: sistema[0])
    pal, hoja, font = app.palette(), app.styleSheet(), app.font()
    v = visor = reabierta = None
    def destruir(w):
        w.panel.reloj.stop()
        w.reloj.stop()
        w.close()
        w.deleteLater()
        QCoreApplication.sendPostedEvents(w, QEvent.Type.DeferredDelete)
        assert not Shiboken.isValid(w)
    try:
        estilo.aplicar_tema(app, estilo.tema_guardado(config()))
        v = principal.Ventana()
        v.resize(1440, 920)
        v.show()
        s = solicitud(tmp_path)
        procesar_reunion(s)
        v.panel._restaurar_reunion(consultar_reunion(s.salida, incluir_fuentes=True))
        previo = instantanea(s.salida, ['workflow.json', 'transcription.json', 'minutes.md'])
        fuentes = v.panel.archivos()
        original = (s.salida / 'minutes.md').read_text(encoding='utf-8')
        visor = DialogoResultado('Minuta', original, minuta=True, parent=v)
        visor.show()
        app.processEvents()
        assert v.cb_tema.currentData() == 'claro'
        roles = QPalette.ColorRole
        def comprobar(oscuro):
            c = estilo.PALETAS[oscuro]
            assert app.palette().color(roles.Window).name() == c['ventana']
            assert v.panel.cb_modelo.palette().color(roles.ButtonText).name() == c['texto']
            assert v.panel.ed_resultados.palette().color(roles.Text).name() == c['texto']
            assert v.panel.lbl.palette().color(v.panel.lbl.foregroundRole()).name() == c['secundario']
            assert visor.lectura.palette().color(roles.Text).name() == c['texto']
            # El texto hereda el color de pintura; ningún fragmento fija el
            # color del tema anterior en el documento enriquecido.
            cursor = QTextCursor(visor.lectura.document())
            while cursor.movePosition(QTextCursor.MoveOperation.NextCharacter):
                assert cursor.charFormat().foreground().style() == Qt.BrushStyle.NoBrush
            assert visor.original.palette().color(roles.Text).name() == c['texto']
            assert visor.original.toPlainText() == original
        comprobar(False)
        for tema, oscuro in (('oscuro', True), ('claro', False), ('oscuro', True), ('sistema', False)):
            v.cb_tema.setCurrentIndex(v.cb_tema.findData(tema))
            app.processEvents()
            comprobar(oscuro)
            assert estilo.tema_guardado(config()) == tema
        sistema[0] = True
        v._cambio_esquema_sistema(Qt.ColorScheme.Dark)
        app.processEvents()
        comprobar(True)
        v.cb_tema.setCurrentIndex(v.cb_tema.findData('claro'))
        v._cambio_esquema_sistema(Qt.ColorScheme.Dark)
        app.processEvents()
        comprobar(False)
        assert v.panel.archivos() == fuentes and v.panel.btn_minuta.isEnabled()
        assert instantanea(s.salida, previo) == previo
        assert tuple(modelos_falsos.values()) == (1, 1, 1)
        visor.close()
        visor.deleteLater()
        QCoreApplication.sendPostedEvents(visor, QEvent.Type.DeferredDelete)
        assert not Shiboken.isValid(visor)
        visor = None
        destruir(v)
        v = None
        estilo.aplicar_tema(app, estilo.tema_guardado(config()))
        reabierta = principal.Ventana()
        assert reabierta.cb_tema.currentData() == 'claro'
        assert app.palette().color(roles.Window).name() == estilo.PALETAS[False]['ventana']
    finally:
        if visor is not None and Shiboken.isValid(visor):
            visor.close()
            visor.deleteLater()
            QCoreApplication.sendPostedEvents(visor, QEvent.Type.DeferredDelete)
        for w in (v, reabierta):
            if w is not None and Shiboken.isValid(w):
                destruir(w)
        monkeypatch.undo()
        app.setStyleSheet('')
        app.setPalette(pal)
        app.setFont(font)
        app.setStyleSheet(hoja)


def test_aviso_consolidacion_visible_sin_invalidar_resultados(panel, tmp_path, modelos_falsos, monkeypatch):
    s = solicitud(tmp_path)
    procesar_reunion(s)
    consulta = consultar_reunion(s.salida, incluir_fuentes=True)
    consulta['consolidacion']['uniones_locales'] = 1
    consulta['consolidacion']['concatenaciones_resumen'] = 1
    monkeypatch.setattr(interfaz, 'consultar_reunion', lambda *a, **kw: consulta)
    panel._restaurar_reunion(consulta)
    assert 'uniones locales' in panel.lbl_destino_modelo.text()
    assert 'síntesis parciales' in panel.lbl_destino_modelo.text()
    assert panel.btn_minuta.isEnabled()
    consulta['consolidacion']['uniones_locales'] = 0
    consulta['consolidacion']['concatenaciones_resumen'] = 0
    panel._actualizar()
    assert 'uniones locales' not in panel.lbl_destino_modelo.text()
    assert 'síntesis parciales' not in panel.lbl_destino_modelo.text()
