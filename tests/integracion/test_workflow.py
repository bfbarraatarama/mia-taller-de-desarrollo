"""Fronteras E2E del workflow con modelos falsos, pero contratos y archivos reales."""
from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path

import pytest

from src.asociacion.etiquetado import Decision, ModeloFichas
from src.diarizacion.resultados import escribir_par
from src.ingesta.audio import sha256, verificar_wav
from src.minutas.generacion import ConfiguracionMinutas
from src.pipeline import (SolicitudReunion, preparar_reunion, procesar_reunion, continuar_reunion,
                          consultar_reunion, reetiquetar_reunion)
from src.pipeline import ejecucion


def archivo_wav(ruta: Path, muestras: int = 32000):
    with wave.open(str(ruta), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b'\x01\x00' * muestras)
    return ruta


def solicitud(tmp_path, *, modo='omitir', secciones=('resumen',)):
    fuentes = [archivo_wav(tmp_path / 'a.wav'), archivo_wav(tmp_path / 'b.wav')]
    return SolicitudReunion(fuentes=tuple(fuentes), salida=tmp_path / 'reunion', identificacion=modo,
                            minutas=ConfiguracionMinutas(secciones=secciones))


@pytest.fixture
def modelos_falsos(monkeypatch):
    conteo = {'src.diarizacion.diarizar': 0, 'src.stt': 0, 'src.minutas': 0}

    def ejecutar(modulo, argumentos, *, emisor):
        conteo[modulo] += 1
        directorio = Path(argumentos[argumentos.index('--salida') + 1]) if '--salida' in argumentos else Path(argumentos[0]).parent
        audio = directorio / 'audio.wav'
        if modulo == 'src.diarizacion.diarizar':
            segmentos = [{'start': .4, 'end': 3.5, 'speaker': 'SPEAKER_00'}]
            escribir_par(directorio, {'segments': segmentos}, {
                'run_id': 'falso', 'segmentos': 1, 'hablantes': 1,
                'audio': {'sha256': sha256(audio), 'duracion_s': verificar_wav(audio)/16000}})
        elif modulo == 'src.stt':
            (directorio / 'asr.json').write_text(json.dumps({'language': 'es', 'segments': [
                {'start': .5, 'end': 3.2, 'text': 'Revisamos el tema', 'words': [
                    {'start': .5, 'end': 1.2, 'word': 'Revisamos'},
                    {'start': 1.3, 'end': 1.7, 'word': 'el'},
                    {'start': 2.6, 'end': 3.2, 'word': 'tema'}]}]}), encoding='utf-8')
        elif modulo == 'src.minutas':
            cfg = argumentos[argumentos.index('--secciones') + 1].split(',')
            respuesta = {'resumen': 'Se revisó el tema.', 'temas': [], 'decisiones': [],
                         'problemas': [], 'acciones': []}
            contenido = {k: respuesta[k] for k in cfg}
            texto = json.dumps(contenido, ensure_ascii=False) + '\n'
            (directorio / 'minutes.json').write_text(texto, encoding='utf-8')
            (directorio / 'minutes.md').write_text('Minuta\n', encoding='utf-8')
            (directorio / 'ejecucion_minutas.json').write_text(json.dumps({
                'secciones': cfg, 'sha256_entrada': sha256(directorio / 'transcription.json'),
                'sha256_minuta_json': sha256(directorio / 'minutes.json')}), encoding='utf-8')
        else:
            raise AssertionError(modulo)
    monkeypatch.setattr(ejecucion, '_trabajador', ejecutar)
    return conteo


def test_ingesta_y_e2e_reutilizable(tmp_path, modelos_falsos):
    s = solicitud(tmp_path)
    resultado = procesar_reunion(s)
    assert resultado['estado'] == 'completado'
    assert verificar_wav(s.salida / 'audio.wav') == 64000
    ingesta = json.loads((s.salida / 'ingesta.json').read_text())
    assert [(f['inicio_muestra'], f['fin_muestra']) for f in ingesta['fuentes']] == [(0, 32000), (32000, 64000)]
    assert len(list((s.salida / 'fuentes').iterdir())) == 2
    assert 'minutes.md' in resultado['artefactos']
    procesar_reunion(s)
    assert modelos_falsos == {'src.diarizacion.diarizar': 1, 'src.stt': 1, 'src.minutas': 1}
    assert len(list((s.salida / 'fuentes').iterdir())) == 2


def test_pausa_fichas_y_reetiquetado_sin_gpu(tmp_path, modelos_falsos):
    s = solicitud(tmp_path, modo='pausa')
    assert preparar_reunion(s)['estado'] == 'esperando_identificacion'
    assert not (s.salida / 'transcription.json').exists()
    from src.asociacion.asociacion import asociar
    fichas = ModeloFichas(asociar(s.salida))
    fichas.escribir_nombre('SPEAKER_00', 'Ana')
    assert continuar_reunion(s.salida, fichas.confirmar())['estado'] == 'completado'
    assert (s.salida / 'speakers.json').exists()
    assert reetiquetar_reunion(s.salida, {'SPEAKER_00': 'Beatriz'})['estado'] == 'completado'
    datos = json.loads((s.salida / 'transcription.json').read_text())
    assert {i['name'] for i in datos['segments']} == {'Beatriz'}
    assert modelos_falsos == {'src.diarizacion.diarizar': 1, 'src.stt': 1, 'src.minutas': 2}


def test_error_y_reanudacion_selectiva(tmp_path, monkeypatch, modelos_falsos):
    s = solicitud(tmp_path)
    original = ejecucion._trabajador
    falla = {'vez': True}

    def worker(modulo, args, *, emisor):
        if modulo == 'src.stt' and falla['vez']:
            falla['vez'] = False
            raise RuntimeError('Fallo simulado')
        return original(modulo, args, emisor=emisor)
    monkeypatch.setattr(ejecucion, '_trabajador', worker)
    with pytest.raises(RuntimeError, match='Fallo simulado'):
        procesar_reunion(s)
    estado = consultar_reunion(s.salida)
    assert estado['estado'] == 'fallido'
    assert 'diarization.json' in estado['artefactos']
    assert 'asr.json' not in estado['artefactos']
    assert procesar_reunion(s)['estado'] == 'completado'
    assert modelos_falsos['src.diarizacion.diarizar'] == 1


def test_entrada_corrupta_no_se_reutiliza(tmp_path, modelos_falsos):
    s = solicitud(tmp_path, modo='pausa')
    preparar_reunion(s)
    (s.salida / 'diarization.json').write_text('{invalido', encoding='utf-8')
    with pytest.raises(ValueError, match='checkpoint íntegro'):
        continuar_reunion(s.salida, Decision('escribir'))
    assert 'diarization.json' not in consultar_reunion(s.salida)['artefactos']


def test_remoto_no_autorizado_no_inicia_procesamiento(tmp_path, modelos_falsos):
    s = solicitud(tmp_path)
    from dataclasses import replace
    s = replace(s, minutas=ConfiguracionMinutas(modelo='nova-lite'))
    with pytest.raises(PermissionError, match='autorización'):
        procesar_reunion(s)
    assert sum(modelos_falsos.values()) == 0
    assert not (s.salida / 'audio.wav').exists()


def test_configuracion_minutas_llega_completa_al_trabajador(tmp_path, modelos_falsos, monkeypatch):
    from dataclasses import replace

    s = solicitud(tmp_path)
    s = replace(s, minutas=ConfiguracionMinutas(
        secciones=('temas', 'acciones'), temperatura=0.35, max_tokens_salida=1024,
        reintentos_formato=4, num_ctx=4096, max_caracteres_bloque=2500,
    ))
    original = ejecucion._trabajador
    recibido = {}

    def verificar(modulo, args, *, emisor):
        if modulo == 'src.minutas':
            recibido.update({k: args[args.index(k) + 1] for k in (
                '--secciones', '--temperatura', '--max-tokens-salida',
                '--reintentos-formato', '--num-ctx', '--max-caracteres-bloque')})
        return original(modulo, args, emisor=emisor)

    monkeypatch.setattr(ejecucion, '_trabajador', verificar)
    assert procesar_reunion(s)['estado'] == 'completado'
    assert recibido == {'--secciones': 'temas,acciones', '--temperatura': '0.35',
                       '--max-tokens-salida': '1024', '--reintentos-formato': '4',
                       '--num-ctx': '4096', '--max-caracteres-bloque': '2500'}


def test_default_reunion_estable_y_no_se_sobrescriben_reuniones(tmp_path):
    from src.rutas import DIRECTORIO_RESULTADOS_PREDETERMINADO
    a = SolicitudReunion((tmp_path / 'uno.wav',))
    b = SolicitudReunion((tmp_path / 'dos.wav',))
    c = SolicitudReunion((tmp_path / 'uno.wav',))
    assert a.salida.parent == DIRECTORIO_RESULTADOS_PREDETERMINADO
    assert a.salida == c.salida
    assert a.salida != b.salida
    assert SolicitudReunion((tmp_path / 'uno.wav',), salida=tmp_path / 'explicita').salida == tmp_path / 'explicita'


def test_exclusion_por_reunion_incluso_en_el_mismo_proceso(tmp_path):
    with ejecucion._exclusivo(tmp_path / 'ejecucion'):
        with pytest.raises(RuntimeError, match='Otra ejecución'):
            with ejecucion._exclusivo(tmp_path / 'ejecucion'):
                pytest.fail('Se obtuvo un bloqueo duplicado')
    with ejecucion._exclusivo(tmp_path / 'ejecucion'):
        pass
    assert len(list((tmp_path / 'ejecucion').glob('.workflow.lock'))) == 1


def test_clave_remota_de_ollama_requiere_consentimiento(monkeypatch):
    from src.pipeline.ejecucion import _consentimiento
    monkeypatch.setenv('OLLAMA_HOST', 'http://modelo.red:11434')
    with pytest.raises(PermissionError, match='autorización'):
        _consentimiento(ConfiguracionMinutas())
    assert _consentimiento(ConfiguracionMinutas(permitir_remoto=True)) == 'ollama_externo'
    monkeypatch.setenv('OLLAMA_HOST', 'http://127.0.0.1:11434')
    assert _consentimiento(ConfiguracionMinutas()) == 'ollama_local'


def test_cambio_de_minutas_invalida_resultado_previo_durante_pausa(tmp_path, modelos_falsos):
    from dataclasses import replace
    s = solicitud(tmp_path)
    assert procesar_reunion(s)['estado'] == 'completado'
    cambio = replace(s, minutas=ConfiguracionMinutas(secciones=('acciones',)), identificacion='pausa')
    result = preparar_reunion(cambio)
    assert result['estado'] == 'esperando_identificacion'
    assert 'minutes.md' not in result['artefactos']  # sigue físicamente, pero no es vigente
    assert modelos_falsos['src.diarizacion.diarizar'] == 1
    assert modelos_falsos['src.stt'] == 1
    assert continuar_reunion(s.salida)['estado'] == 'completado'
    manifest = json.loads((s.salida / 'workflow.json').read_text())
    assert manifest['solicitud']['minutas']['secciones'] == ['acciones']


def test_continuar_con_configuracion_distinta_actualiza_verdad_persistida(tmp_path, modelos_falsos):
    s = solicitud(tmp_path, modo='pausa')
    preparar_reunion(s)
    alternativa = ConfiguracionMinutas(secciones=('temas',), temperatura=.2)
    assert continuar_reunion(s.salida, configuracion=alternativa)['estado'] == 'completado'
    estado = json.loads((s.salida / 'workflow.json').read_text())
    assert estado['solicitud']['minutas']['secciones'] == ['temas']
    assert estado['solicitud']['minutas']['temperatura'] == .2
