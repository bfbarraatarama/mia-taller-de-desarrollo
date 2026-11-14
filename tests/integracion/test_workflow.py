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
                'modelo': 'pyannote/speaker-diarization-community-1',
                'modo_dispositivo': argumentos[argumentos.index('--device') + 1],
                'dispositivo': 'cuda' if argumentos[argumentos.index('--device') + 1] == 'cuda' else 'cpu',
                'num_speakers': int(argumentos[argumentos.index('--num-speakers') + 1]) if '--num-speakers' in argumentos else None,
                'audio': {'sha256': sha256(audio), 'duracion_s': verificar_wav(audio)/16000}})
        elif modulo == 'src.stt':
            (directorio / 'asr.json').write_text(json.dumps({'language': 'es', 'segments': [
                {'start': .5, 'end': 3.2, 'text': 'Revisamos el tema', 'words': [
                    {'start': .5, 'end': 1.2, 'word': 'Revisamos'},
                    {'start': 1.3, 'end': 1.7, 'word': 'el'},
                    {'start': 2.6, 'end': 3.2, 'word': 'tema'}]}]}), encoding='utf-8')
            return json.dumps({'model': argumentos[argumentos.index('--model') + 1],
                               'device': argumentos[argumentos.index('--device') + 1] if '--device' in argumentos else 'cpu',
                               'duration': verificar_wav(audio) / 16000, 'status': 'success'})
        elif modulo == 'src.minutas':
            from src.minutas.generacion import generar_minuta
            from src.minutas.modelos import obtener_modelo
            from src.minutas.proveedores import RespuestaModelo

            def arg(nombre):
                return argumentos[argumentos.index(nombre) + 1]

            cfg = ConfiguracionMinutas(modelo=arg('--modelo'),
                permitir_remoto='--permitir-remoto' in argumentos,
                secciones=tuple(arg('--secciones').split(',')), temperatura=float(arg('--temperatura')),
                max_tokens_salida=int(arg('--max-tokens-salida')), reintentos_formato=int(arg('--reintentos-formato')),
                num_ctx=int(arg('--num-ctx')), max_caracteres_bloque=int(arg('--max-caracteres-bloque')))
            modelo = obtener_modelo(cfg.modelo)

            class ClienteFalso:
                nombre = modelo.identificador
                proveedor = modelo.proveedor

                def responder(self, instrucciones, datos, esquema):
                    respuesta = {'resumen': 'Se revisó el tema.', 'temas': [], 'decisiones': [],
                                 'problemas': [], 'acciones': []}
                    return RespuestaModelo({k: respuesta[k] for k in cfg.secciones})

            generar_minuta(directorio / 'transcription.json', directorio, configuracion=cfg,
                           cliente=ClienteFalso(), sobrescribir=True)
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


# Estados efectivos, dependencias y recuperación. Se sustituyen únicamente los
# trabajadores de inferencia; la ingesta FFmpeg y todos los artefactos son reales.

def manifiesto(carpeta):
    return json.loads((carpeta / 'workflow.json').read_text(encoding='utf-8'))


def guardar_manifiesto(carpeta, datos):
    from src.pipeline.estado import publicar
    publicar(carpeta, datos)


def instantanea(carpeta, archivos):
    return {n: (sha256(carpeta / n), (carpeta / n).stat().st_mtime_ns) for n in archivos}


@pytest.mark.parametrize('cambio,delta,conservados', [
    ('diar', (1, 0, 1), ('audio.wav', 'ingesta.json', 'asr.json')),
    ('stt', (0, 1, 1), ('audio.wav', 'ingesta.json', 'diarization.json', 'diarization.meta.json')),
    ('minutas', (0, 0, 1), ('audio.wav', 'ingesta.json', 'diarization.json', 'diarization.meta.json',
                            'asr.json', 'transcription.json', 'transcription.meta.json')),
    ('orden', (1, 1, 1), ()),
    ('audio', (1, 1, 1), ()),
    ('dispositivo_diar', (1, 0, 1), ('asr.json',)),
    ('dispositivo_stt', (0, 1, 1), ('diarization.json', 'diarization.meta.json')),
])
def test_matriz_invalidacion(tmp_path, modelos_falsos, cambio, delta, conservados):
    from dataclasses import replace
    s = solicitud(tmp_path)
    procesar_reunion(s)
    anterior = instantanea(s.salida, conservados)
    if cambio == 'diar':
        nueva = replace(s, num_speakers=2)
    elif cambio == 'stt':
        nueva = replace(s, modelo_stt='small')
    elif cambio == 'minutas':
        nueva = replace(s, minutas=ConfiguracionMinutas(secciones=('acciones',)))
    elif cambio == 'orden':
        nueva = replace(s, fuentes=tuple(reversed(s.fuentes)))
    elif cambio == 'audio':
        archivo_wav(Path(s.fuentes[0]), 32001)
        nueva = s
    elif cambio == 'dispositivo_diar':
        nueva = replace(s, dispositivo_diarizacion='cuda')
    else:
        nueva = replace(s, dispositivo_stt='cpu')
    assert procesar_reunion(nueva)['estado'] == 'completado'
    assert tuple(modelos_falsos.values()) == tuple(1 + d for d in delta)
    assert instantanea(s.salida, conservados) == anterior


_GRUPOS = {
    'preparar': ('audio.wav', 'ingesta.json'),
    'diarizar': ('diarization.json', 'diarization.meta.json'),
    'transcribir': ('asr.json',),
    'asociar': ('transcription.json', 'transcription.meta.json', 'speakers.json'),
    'minuta': ('minutes.json', 'minutes.md', 'ejecucion_minutas.json'),
}


@pytest.mark.parametrize('etapa,archivo', [(e, a) for e, grupo in _GRUPOS.items() for a in grupo])
@pytest.mark.parametrize('alteracion', ['ausencia', 'corrupcion'])
def test_corrupcion_grupo_cierra_dependencias(tmp_path, modelos_falsos, etapa, archivo, alteracion):
    s = solicitud(tmp_path, modo='pausa')
    preparar_reunion(s)
    reetiquetar_reunion(s.salida, {'SPEAKER_00': 'Ana'})
    afectadas = {
        'preparar': set(_GRUPOS), 'diarizar': {'diarizar', 'asociar', 'minuta'},
        'transcribir': {'transcribir', 'asociar', 'minuta'}, 'asociar': {'asociar', 'minuta'},
        'minuta': {'minuta'},
    }[etapa]
    conservar = set(_GRUPOS) - afectadas
    conservados = [a for e in conservar for a in _GRUPOS[e]]
    anterior = instantanea(s.salida, conservados)
    ruta = s.salida / archivo
    if alteracion == 'ausencia':
        ruta.unlink()
    else:
        ruta.write_bytes(b'{}')
    persistido = (s.salida / 'workflow.json').read_bytes()
    consulta = consultar_reunion(s.salida)
    assert consulta['estado'] == 'fallido'
    assert set(consulta['etapas_vigentes']) == conservar
    assert set(consulta['artefactos']) == set(conservados)
    assert (s.salida / 'workflow.json').read_bytes() == persistido  # consultar no reescribe
    preparar_reunion(s)
    assert reetiquetar_reunion(s.salida, {'SPEAKER_00': 'Ana'})['estado'] == 'completado'
    assert tuple(modelos_falsos.values()) == tuple(1 + int(e in afectadas) for e in ('diarizar', 'transcribir', 'minuta'))
    assert instantanea(s.salida, conservados) == anterior


@pytest.mark.parametrize('registro', [{}, [], {'clave': 'x', 'archivos': {}}, None])
def test_registro_incompleto_no_es_checkpoint(tmp_path, modelos_falsos, registro):
    s = solicitud(tmp_path)
    procesar_reunion(s)
    datos = manifiesto(s.salida)
    datos['etapas']['transcribir'] = registro
    guardar_manifiesto(s.salida, datos)
    result = consultar_reunion(s.salida)
    assert result['estado'] == 'fallido'
    assert result['etapas_vigentes'] == ['preparar', 'diarizar']
    assert procesar_reunion(s)['estado'] == 'completado'
    assert tuple(modelos_falsos.values()) == (1, 2, 2)


@pytest.mark.parametrize('datos', [[], {}, {'version': True, 'estado': 'completado', 'etapas': {}},
                                    {'version': 1, 'estado': [], 'etapas': {}}])
def test_manifiesto_global_invalido_no_se_sobrescribe(tmp_path, datos):
    s = solicitud(tmp_path)
    s.salida.mkdir()
    p = s.salida / 'workflow.json'
    p.write_text(json.dumps(datos))
    previo = p.read_bytes()
    with pytest.raises(ValueError):
        consultar_reunion(s.salida)
    with pytest.raises(ValueError):
        procesar_reunion(s)
    assert p.read_bytes() == previo


def test_grupo_incompleto_aunque_hashes_coincidan(tmp_path, modelos_falsos):
    s = solicitud(tmp_path)
    procesar_reunion(s)
    datos = manifiesto(s.salida)
    del datos['etapas']['diarizar']['archivos']['diarization.meta.json']
    guardar_manifiesto(s.salida, datos)
    assert consultar_reunion(s.salida)['etapas_vigentes'] == ['preparar', 'transcribir']
    assert procesar_reunion(s)['estado'] == 'completado'
    assert tuple(modelos_falsos.values()) == (2, 1, 2)


def test_contrato_invalido_aun_con_hash_coincidente(tmp_path, modelos_falsos):
    s = solicitud(tmp_path)
    procesar_reunion(s)
    ruta = s.salida / 'asr.json'
    ruta.write_text('{}')
    datos = manifiesto(s.salida)
    datos['etapas']['transcribir']['archivos']['asr.json'] = sha256(ruta)
    guardar_manifiesto(s.salida, datos)
    assert consultar_reunion(s.salida)['etapas_vigentes'] == ['preparar', 'diarizar']
    assert procesar_reunion(s)['estado'] == 'completado'
    assert tuple(modelos_falsos.values()) == (1, 2, 2)


def test_fuentes_movidas_y_reconstruccion_ordenada(tmp_path, modelos_falsos):
    from dataclasses import replace
    s = solicitud(tmp_path)
    # Diferencia de cantidad de muestras y contenido; el orden es comprobable.
    with wave.open(str(s.fuentes[1]), 'wb') as w:
        w.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        w.writeframes(b'\x02\x00' * 40000)
    original = procesar_reunion(s)
    digest = sha256(s.salida / 'audio.wav')
    for fuente in s.fuentes:
        Path(fuente).unlink()
    antes = instantanea(s.salida, original['artefactos'])
    assert procesar_reunion(s)['estado'] == 'completado'
    assert instantanea(s.salida, original['artefactos']) == antes
    (s.salida / 'audio.wav').unlink()
    assert procesar_reunion(s)['estado'] == 'completado'
    assert sha256(s.salida / 'audio.wav') == digest
    inversa = replace(s, fuentes=tuple(reversed(s.fuentes)))
    assert procesar_reunion(inversa)['estado'] == 'completado'
    ingesta = json.loads((s.salida / 'ingesta.json').read_text())
    assert [e['nombre_original'] for e in ingesta['fuentes']] == ['b.wav', 'a.wav']
    assert [e['fin_muestra'] for e in ingesta['fuentes']] == [40000, 72000]
    assert ingesta['fuentes'][0]['ruta_original'] == str(s.fuentes[1])
    with wave.open(str(s.salida / 'audio.wav'), 'rb') as w:
        assert w.readframes(40000) == b'\x02\x00' * 40000
        assert w.readframes(32000) == b'\x01\x00' * 32000


def test_copia_corrupta_no_sustituye_original_perdido(tmp_path, modelos_falsos):
    s = solicitud(tmp_path)
    procesar_reunion(s)
    ingesta = json.loads((s.salida / 'ingesta.json').read_text())
    Path(s.fuentes[0]).unlink()
    (s.salida / ingesta['fuentes'][0]['fuente']).write_bytes(b'corrupto')
    with pytest.raises(ValueError, match='sin copia verificable'):
        procesar_reunion(s)
    assert tuple(modelos_falsos.values()) == (1, 1, 1)


def test_colision_de_nombres_no_destruye_copias(tmp_path, modelos_falsos):
    from dataclasses import replace
    s = solicitud(tmp_path)
    (tmp_path / 'otra').mkdir()
    otra = archivo_wav(tmp_path / 'otra' / 'a.wav', 48000)
    procesar_reunion(s)
    previo = json.loads((s.salida / 'ingesta.json').read_text())
    copia = s.salida / previo['fuentes'][0]['fuente']
    digest = sha256(copia)
    Path(s.fuentes[0]).unlink()
    nueva = replace(s, fuentes=(otra, s.fuentes[0]))
    assert procesar_reunion(nueva)['estado'] == 'completado'
    assert sha256(copia) == digest
    vigente = json.loads((s.salida / 'ingesta.json').read_text())
    assert [f['muestras'] for f in vigente['fuentes']] == [48000, 32000]


def test_legacy_legible_y_reutiliza_sin_inferencias_gpu(tmp_path, modelos_falsos):
    from dataclasses import asdict
    from src.pipeline.estado import huella
    from src.rutas import PROMPT_EXTRACCION_MINUTAS, PROMPT_CONSOLIDACION_MINUTAS, DEFINICIONES_SECCIONES_MINUTAS
    s = solicitud(tmp_path)
    procesar_reunion(s)
    datos = manifiesto(s.salida)
    datos.pop('tiempos')
    datos.pop('fuentes_conservadas')
    datos['inicio_s'] = 123456.0
    ingesta = json.loads((s.salida / 'ingesta.json').read_text())
    for f in ingesta['fuentes']:
        f.pop('ruta_original')
    p = s.salida / 'ingesta.json'
    p.write_text(json.dumps(ingesta))
    datos['etapas']['preparar']['archivos']['ingesta.json'] = sha256(p)
    datos['etapas']['preparar']['metadata']['duracion_s'] = .27  # campo ambiguo antiguo
    for registro in datos['etapas'].values():
        registro['metadata'].pop('tiempo_procesamiento_s', None)
    datos['etapas']['transcribir']['metadata'].pop('sha256_audio')
    datos['etapas']['minuta']['clave'] = huella(sha256(s.salida / 'transcription.json'), asdict(s.minutas),
        [(p.name, sha256(p)) for p in (PROMPT_EXTRACCION_MINUTAS, PROMPT_CONSOLIDACION_MINUTAS,
                                       DEFINICIONES_SECCIONES_MINUTAS)], ejecucion._paquetes('ollama', 'boto3', 'pydantic'))
    guardar_manifiesto(s.salida, datos)
    consulta = consultar_reunion(s.salida)
    assert consulta['estado'] == 'completado'
    assert consulta['duracion_audio_s'] == 4.0
    assert consulta['tiempos'] is None
    for fuente in s.fuentes:
        Path(fuente).unlink()
    assert procesar_reunion(s)['estado'] == 'completado'
    assert tuple(modelos_falsos.values()) == (1, 1, 2)  # nuevo identificador de destino


def test_tiempos_separados_y_espera_con_reloj_controlado(tmp_path, modelos_falsos, monkeypatch):
    from src.pipeline import temporalidad
    reloj = [100.0]
    monkeypatch.setattr(temporalidad, 'monotonic', lambda: reloj[0])
    monkeypatch.setattr(ejecucion, 'monotonic', lambda: reloj[0])
    worker = ejecucion._trabajador
    ingestar = ejecucion.ingestar
    asociar = ejecucion.asociar

    def modelo(modulo, args, *, emisor):
        reloj[0] += {'src.diarizacion.diarizar': 20, 'src.stt': 18, 'src.minutas': 19}[modulo]
        return worker(modulo, args, emisor=emisor)

    def ingesta(*args, **kwargs):
        reloj[0] += 2
        return ingestar(*args, **kwargs)

    def asociacion(*args, **kwargs):
        reloj[0] += 1
        return asociar(*args, **kwargs)

    monkeypatch.setattr(ejecucion, '_trabajador', modelo)
    monkeypatch.setattr(ejecucion, 'ingestar', ingesta)
    monkeypatch.setattr(ejecucion, 'asociar', asociacion)
    s = solicitud(tmp_path, modo='pausa')
    eventos = []
    pausa = preparar_reunion(s, emisor=eventos.append)
    assert pausa['tiempos']['latencia_activa_s'] == 41
    assert pausa['tiempos']['espera_identificacion_s'] is None
    assert not pausa['tiempos']['medicion_cerrada']
    assert not any(e.get('etapa') == 'asociar' and e.get('estado') == 'ok' for e in eventos)
    reloj[0] += 60
    final = continuar_reunion(s.salida, emisor=eventos.append)
    assert final['tiempos']['latencia_activa_s'] == 61
    assert final['tiempos']['espera_identificacion_s'] == 60
    assert final['tiempos']['medicion_cerrada']
    assert final['duracion_audio_s'] == 4
    assert manifiesto(s.salida)['etapas']['preparar']['metadata']['duracion_s'] == 4
    assert manifiesto(s.salida)['etapas']['preparar']['metadata']['tiempo_procesamiento_s'] == 2
    assert eventos[-1]['estado'] == final['estado'] == 'completado'
    assert eventos[-1]['latencia_s'] == 61
    from dataclasses import replace
    nuevo = procesar_reunion(replace(s, identificacion='omitir'))
    assert nuevo['tiempos']['latencia_activa_s'] == 0
    assert nuevo['tiempos']['espera_identificacion_s'] == 0
    assert all(e == {'estado': 'reutilizada', 'tiempo_s': 0.0} for e in nuevo['tiempos']['etapas'].values())


def test_espera_no_comparable_entre_arranques(tmp_path, modelos_falsos, monkeypatch):
    from src.pipeline import temporalidad
    s = solicitud(tmp_path, modo='pausa')
    preparar_reunion(s)
    monkeypatch.setattr(temporalidad, 'DOMINIO_RELOJ', 'otro-arranque')
    resultado = continuar_reunion(s.salida)
    assert resultado['tiempos']['espera_identificacion_s'] is None
    assert resultado['tiempos']['latencia_activa_s'] is not None


def test_continuacion_legacy_latencia_desconocida(tmp_path, modelos_falsos):
    s = solicitud(tmp_path, modo='pausa')
    preparar_reunion(s)
    datos = manifiesto(s.salida)
    datos.pop('tiempos')
    guardar_manifiesto(s.salida, datos)
    final = continuar_reunion(s.salida)
    assert final['tiempos']['latencia_activa_s'] is None
    assert final['tiempos']['latencia_tramo_s'] >= 0


def test_eventos_y_lock_del_recorrido_completo(tmp_path, modelos_falsos):
    s = solicitud(tmp_path)
    eventos = []

    def emisor(evento):
        eventos.append(evento)
        consulta = consultar_reunion(s.salida)
        assert consulta['activa'] and consulta['estado'] == 'procesando'
        assert consulta['etapas_vigentes'] is None and not consulta['artefactos']
        with pytest.raises(ejecucion.ReunionOcupada):
            with ejecucion._exclusivo(s.salida):
                pytest.fail('Se liberó el bloqueo dentro de la ejecución')

    assert procesar_reunion(s, emisor=emisor)['estado'] == 'completado'
    assert [e['estado'] for e in eventos if e['evento'] == 'fin'] == ['completado']
    assert not consultar_reunion(s.salida)['activa']


def test_cancelacion_de_fichas_no_publica_transcripcion(tmp_path, modelos_falsos):
    s = solicitud(tmp_path, modo='pausa')
    preparar_reunion(s)
    eventos = []
    final = continuar_reunion(s.salida, Decision('cancelar'), emisor=eventos.append)
    assert final['estado'] == eventos[-1]['estado'] == 'cancelado'
    assert 'transcription.json' not in final['artefactos']
    assert modelos_falsos['src.minutas'] == 0
    assert continuar_reunion(s.salida)['estado'] == 'completado'
    assert tuple(modelos_falsos.values()) == (1, 1, 1)


def test_cancelacion_en_worker_preserva_rama_independiente(tmp_path, modelos_falsos, monkeypatch):
    s = solicitud(tmp_path)
    worker = ejecucion._trabajador
    eventos = []

    def cancelar(modulo, args, *, emisor):
        if modulo == 'src.stt':
            raise ejecucion.Cancelado('cancelación simulada')
        return worker(modulo, args, emisor=emisor)

    monkeypatch.setattr(ejecucion, '_trabajador', cancelar)
    with pytest.raises(ejecucion.Cancelado):
        procesar_reunion(s, emisor=eventos.append)
    estado = consultar_reunion(s.salida)
    assert estado['estado'] == eventos[-1]['estado'] == 'cancelado'
    assert estado['etapas_vigentes'] == ['preparar', 'diarizar']
    assert estado['tiempos']['etapas']['transcribir']['estado'] == 'cancelada'
    monkeypatch.setattr(ejecucion, '_trabajador', worker)
    assert procesar_reunion(s)['estado'] == 'completado'
    assert tuple(modelos_falsos.values()) == (1, 1, 1)


def test_interrupcion_sin_lock_no_es_procesando(tmp_path, modelos_falsos):
    s = solicitud(tmp_path, modo='pausa')
    preparar_reunion(s)
    datos = manifiesto(s.salida)
    datos['estado'] = 'procesando'
    guardar_manifiesto(s.salida, datos)
    estado = consultar_reunion(s.salida)
    assert estado['estado'] == 'fallido' and not estado['activa']
    assert 'interrumpida' in estado['error']
    assert estado['etapas_vigentes'] == ['preparar', 'diarizar', 'transcribir']
    assert continuar_reunion(s.salida)['estado'] == 'completado'


@pytest.mark.parametrize('cantidad', [True, 0, -2, 1.5, '2'])
def test_num_speakers_entero_estricto(tmp_path, cantidad):
    from dataclasses import replace
    with pytest.raises(ValueError, match='entero positivo'):
        replace(solicitud(tmp_path), num_speakers=cantidad)


def test_reemplazo_endpoint_invalida_minuta_solamente(tmp_path, modelos_falsos, monkeypatch):
    from dataclasses import replace
    monkeypatch.setenv('OLLAMA_HOST', 'http://localhost:11434')
    s = replace(solicitud(tmp_path), minutas=ConfiguracionMinutas(permitir_remoto=True))
    procesar_reunion(s)
    monkeypatch.setenv('OLLAMA_HOST', 'http://localhost:11435')
    assert procesar_reunion(s)['estado'] == 'completado'
    assert tuple(modelos_falsos.values()) == (1, 1, 2)
    sin_permiso = replace(s, minutas=ConfiguracionMinutas())
    assert procesar_reunion(sin_permiso)['estado'] == 'completado'
    assert tuple(modelos_falsos.values()) == (1, 1, 2)


def test_stt_metadata_de_modelo_y_dispositivo(tmp_path, modelos_falsos):
    s = solicitud(tmp_path)
    procesar_reunion(s)
    metadata = manifiesto(s.salida)['etapas']['transcribir']['metadata']
    assert metadata['modelo'] == 'medium' and metadata['dispositivo'] == 'cpu'
    assert metadata['sha256_audio'] == sha256(s.salida / 'audio.wav')


def test_lock_sobrevive_al_padre_abruptamente_terminado(tmp_path):
    import os
    import subprocess
    import sys
    import time
    if os.name != 'posix':
        pytest.skip('herencia de flock y SIGKILL: prueba POSIX')
    carpeta = tmp_path / 'reunion'
    listo, salir = tmp_path / 'listo', tmp_path / 'salir'
    # timeit es un trabajador real y no requiere dependencias externas. El
    # La barrera tiene vencimiento y no requiere señalizar un PID ajeno.
    instruccion = (f'import pathlib, os, time; pathlib.Path({str(listo)!r}).write_text(str(os.getpid())); '
                   f'limite = time.monotonic() + 20; exec("while not pathlib.Path({str(salir)!r}).exists() and time.monotonic() < limite: time.sleep(0.02)")')
    script = ('from pathlib import Path\nfrom src.pipeline.ejecucion import _exclusivo, _trabajador\n'
              f'with _exclusivo(Path({str(carpeta)!r})):\n'
              f'    _trabajador("timeit", ["-n", "1", "-r", "1", {instruccion!r}], emisor=None)\n')
    padre = subprocess.Popen([sys.executable, '-c', script], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        limite = time.monotonic() + 10
        while not listo.exists() and padre.poll() is None and time.monotonic() < limite:
            time.sleep(.02)
        assert listo.exists(), 'El trabajador no alcanzó la barrera'
        padre.kill()
        padre.wait(timeout=5)
        assert consultar_reunion(carpeta)['activa']
        with pytest.raises(ejecucion.ReunionOcupada):
            with ejecucion._exclusivo(carpeta):
                pytest.fail('El hijo no conservó el bloqueo')
        salir.touch()
        limite = time.monotonic() + 5
        while consultar_reunion(carpeta)['activa'] and time.monotonic() < limite:
            time.sleep(.02)
        assert not consultar_reunion(carpeta)['activa']
    finally:
        salir.touch()
        if padre.poll() is None:
            padre.kill()
            padre.wait(timeout=5)
        padre.stderr.close()


@pytest.mark.parametrize('campo,valor,vigentes', [
    ('num_speakers', 4, ['preparar', 'transcribir']),
    ('modelo_stt', 'small', ['preparar', 'diarizar']),
    ('minutas', {'modelo': 'qwen2.5-7b', 'secciones': ['acciones']},
     ['preparar', 'diarizar', 'transcribir', 'asociar']),
])
def test_configuracion_incoherente_con_checkpoint(tmp_path, modelos_falsos, campo, valor, vigentes):
    s = solicitud(tmp_path)
    procesar_reunion(s)
    datos = manifiesto(s.salida)
    if campo == 'minutas':
        datos['solicitud'][campo].update(valor)
    else:
        datos['solicitud'][campo] = valor
    guardar_manifiesto(s.salida, datos)
    consulta = consultar_reunion(s.salida)
    assert consulta['estado'] == 'fallido'
    assert consulta['etapas_vigentes'] == vigentes


def test_reconstruccion_legacy_con_manifiesto_ingesta_perdido(tmp_path, modelos_falsos):
    s = solicitud(tmp_path)
    procesar_reunion(s)
    digest = sha256(s.salida / 'audio.wav')
    datos = manifiesto(s.salida)
    datos.pop('fuentes_conservadas')
    for f in datos['etapas']['preparar']['metadata']['fuentes']:
        f.pop('ruta_original')
    guardar_manifiesto(s.salida, datos)
    for fuente in s.fuentes:
        Path(fuente).unlink()
    (s.salida / 'ingesta.json').unlink()
    assert procesar_reunion(s)['estado'] == 'completado'
    assert sha256(s.salida / 'audio.wav') == digest


def test_publicacion_fallida_no_sustituye_checkpoint(tmp_path, modelos_falsos, monkeypatch):
    from src.pipeline import estado as almacenamiento
    from dataclasses import replace
    s = solicitud(tmp_path)
    procesar_reunion(s)
    previo = (s.salida / 'workflow.json').read_bytes()
    archivos = instantanea(s.salida, consultar_reunion(s.salida)['artefactos'])
    original = almacenamiento.os.replace
    eventos = []

    def fallar(origen, destino):
        if Path(destino) == s.salida / 'workflow.json':
            raise OSError('escritura simulada')
        return original(origen, destino)

    with monkeypatch.context() as m:
        m.setattr(almacenamiento.os, 'replace', fallar)
        with pytest.raises(OSError, match='escritura simulada'):
            procesar_reunion(replace(s, modelo_stt='small'), emisor=eventos.append)
    assert eventos[-1]['estado'] == 'fallido' and eventos[-1]['persistido'] is False
    assert (s.salida / 'workflow.json').read_bytes() == previo
    assert instantanea(s.salida, archivos) == archivos
    assert consultar_reunion(s.salida)['estado'] == 'completado'  # solicitud anterior
    assert not (s.salida / '.workflow.json.tmp').exists()


def test_cli_stt_metadata_es_json(tmp_path, monkeypatch, capsys):
    import sys
    import types
    from importlib import import_module
    import src.stt  # paquete real, sin importar Whisper

    fake = types.ModuleType('src.stt.asr_core')
    fake.DEFAULT_MODEL_SIZE = 'medium'
    esperado = {'model': 'medium', 'device': 'cpu', 'duration': 4.0, 'status': 'success'}
    fake.process_asr = lambda **kw: esperado
    monkeypatch.setitem(sys.modules, 'src.stt.asr_core', fake)
    # Importar con el módulo pesado sustituido, sin dejar el adaptador cacheado.
    sys.modules.pop('src.stt.__main__', None)
    try:
        cli = import_module('src.stt.__main__')
        monkeypatch.setattr(sys, 'argv', ['stt', str(tmp_path / 'audio.wav')])
        assert cli.main() == 0
        assert json.loads(capsys.readouterr().out) == esperado
    finally:
        sys.modules.pop('src.stt.__main__', None)


def test_diferentes_reuniones_no_comparten_lock(tmp_path):
    with ejecucion._exclusivo(tmp_path / 'a'):
        with ejecucion._exclusivo(tmp_path / 'b'):
            assert consultar_reunion(tmp_path / 'a')['activa']
            assert consultar_reunion(tmp_path / 'b')['activa']
