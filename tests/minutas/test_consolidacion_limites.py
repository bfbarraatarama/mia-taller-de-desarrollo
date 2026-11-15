"""Regresiones con datos sintéticos y proveedores dobles, sin red."""
from __future__ import annotations

import json
import random
import sys
from dataclasses import replace
from itertools import combinations
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.minutas import ConfiguracionMinutas, SECCIONES_MINUTA, generar_minuta
from src.minutas.contratos import modelo_minuta
from src.minutas.entrada import leer_transcripcion, representar_intervenciones
from src.minutas.generacion import (
    _agrupar_minutas, _cobertura, _datos_minutas, _fragmentar_intervenciones,
    _preparar_prompts, _presupuesto, _union_minutas,
)
from src.minutas.proveedores import LimiteModelo, RespuestaEstructuradaAusente, RespuestaModelo, construir_cliente


def entrada(n=4, texto='Tarea sintética. ' * 42):
    return {'segments': [dict(start=i * 2, end=i * 2 + 1, speaker='SPEAKER_00',
                              name=None, text=texto, overlap=False, ambiguous=False)
                         for i in range(n)]}


def elemento(i, texto, **campos):
    return {'texto': texto, 'ids_intervenciones': [i], 'id_ancla': i, **campos}


class Simulado:
    nombre = 'sintetico'
    proveedor = 'ollama'

    def __init__(self, funcion):
        self.funcion = funcion
        self.llamadas = []

    def responder(self, instrucciones, datos, esquema):
        self.llamadas.append((instrucciones, datos, esquema))
        return self.funcion(instrucciones, datos, esquema)


def decodificar(datos):
    # Los avisos de reparación son texto adicional; la entrada JSON sigue intacta.
    return json.JSONDecoder().raw_decode(datos)[0]


def config(secciones=('temas',), **kwargs):
    return ConfiguracionMinutas(secciones=secciones, **{'max_caracteres_bloque': 1000, **kwargs})


def ejecutar(tmp_path, cliente, cfg, datos=None):
    r = generar_minuta(datos if datos is not None else entrada(), tmp_path,
                       configuracion=cfg, cliente=cliente)
    return json.loads(r.json.read_text()), json.loads(r.manifiesto.read_text())


def todos_ids(minuta, seccion='temas'):
    return {i for registro in minuta[seccion] for i in registro['ids_intervenciones']}


@pytest.mark.parametrize('tam', [550, 1600, 12000])
def test_bloqueo_original_y_parcial_individual_grande(tmp_path, tam):
    def responder(_, datos, esquema):
        bloque = decodificar(datos)
        assert 'intervenciones' in bloque  # ningún par completo cabe
        i = bloque['intervenciones'][0]['id']
        return RespuestaModelo({'temas': [elemento(i, f'{i} ' + 'x' * tam)]})
    cliente = Simulado(responder)
    salida, meta = ejecutar(tmp_path, cliente, config())
    assert todos_ids(salida) == {f'I{i:06d}' for i in range(1, 5)}
    assert len(salida['temas']) == 4
    assert meta['consolidacion']['motivos_union']['presupuesto'] == 1
    assert meta['llamadas_modelo'] == 4
    assert all(len(datos) <= 1000 for _, datos, _ in cliente.llamadas)


def test_bloqueo_en_nivel_posterior(tmp_path):
    def responder(_, datos, esquema):
        bloque = decodificar(datos)
        if 'intervenciones' in bloque:
            i = bloque['intervenciones'][0]['id']
            return RespuestaModelo({'temas': [elemento(i, i + 'x' * 300)]})
        ids = list(dict.fromkeys(i for m in bloque['minutas_parciales']
                                  for e in m['temas'] for i in e['ids_intervenciones']))
        return RespuestaModelo({'temas': [{**elemento(ids[0], 'y' * 700), 'ids_intervenciones': ids}]})
    salida, meta = ejecutar(tmp_path, Simulado(responder), config())
    assert todos_ids(salida) == {f'I{i:06d}' for i in range(1, 5)}
    assert len(salida['temas']) == 2
    assert meta['consolidacion']['niveles'] == 2
    assert meta['consolidacion']['motivos_union']['presupuesto'] == 1
    assert meta['llamadas_modelo'] == 6


@pytest.mark.parametrize('secciones', [s for n in range(1, 6) for s in combinations(SECCIONES_MINUTA, n)])
def test_todas_las_selecciones_con_recuperacion(tmp_path, secciones):
    def responder(_, datos, esquema):
        bloque = decodificar(datos)
        if 'intervenciones' not in bloque:
            assert list(esquema['properties']) == ['resumen']
            return RespuestaModelo({'resumen': 'Síntesis global.'})
        i = bloque['intervenciones'][0]['id']
        salida = {}
        for k in esquema['properties']:
            if k == 'resumen':
                salida[k] = ('Resumen ' + i + 'z' * 600 if secciones == ('resumen',) else 'Resumen ' + i)
            else:
                e = elemento(i, f'{k} {i} ' + 'x' * 550)
                if k == 'acciones':
                    e.update(responsable='Ana', plazo=None)
                salida[k] = [e]
        return RespuestaModelo(salida)
    salida, meta = ejecutar(tmp_path, Simulado(responder), config(secciones))
    assert tuple(salida) == secciones
    for k in secciones:
        if k != 'resumen':
            assert todos_ids(salida, k) == {f'I{i:06d}' for i in range(1, 5)}
    assert meta['consolidacion']['uniones_locales'] >= 1
    if 'resumen' in secciones and len(secciones) > 1:
        assert salida['resumen'] == 'Síntesis global.'
        assert meta['consolidacion']['sintesis_resumen'] == 1
        assert len(meta['consolidacion']['sha256_prompt_resumen']) == 64
    elif secciones == ('resumen',):
        assert all(f'I{i:06d}' in salida['resumen'] for i in range(1, 5))
        assert meta['consolidacion']['concatenaciones_resumen'] == 1


def test_union_preserva_anclas_campos_y_evidencias():
    tipo = modelo_minuta(('acciones',))
    a = elemento('I000001', 'Enviar informe', responsable='Ana', plazo=None)
    b = {**a, 'ids_intervenciones': ['I000001', 'I000002']}
    c = {**a, 'responsable': 'Luis'}
    d = {**a, 'id_ancla': 'I000002', 'ids_intervenciones': ['I000002']}
    minutas = [tipo.model_validate({'acciones': [a]}), tipo.model_validate({'acciones': [b, c, d]})]
    salida = _union_minutas(minutas, tipo).model_dump()['acciones']
    assert salida == [b, c, d]
    assert _cobertura(minutas, ('acciones',)) == _cobertura([_union_minutas(minutas, tipo)], ('acciones',))
    assert minutas[0].model_dump()['acciones'] == [a]


@pytest.mark.parametrize('motivo', ['limite_modelo', 'formato', 'evidencias', 'referencia_fuera_del_grupo'])
def test_recuperacion_consolidacion_sin_perder_evidencias(tmp_path, motivo):
    def responder(_, datos, esquema):
        bloque = decodificar(datos)
        if 'intervenciones' in bloque:
            i = bloque['intervenciones'][0]['id']
            return RespuestaModelo({'temas': [elemento(i, 'x' * 300)]}, 10, 5)
        if motivo == 'limite_modelo':
            raise LimiteModelo('Simulado', 20, 8)
        if motivo == 'formato':
            return RespuestaModelo('no es JSON', 20, 8)
        if motivo == 'referencia_fuera_del_grupo':
            return RespuestaModelo({'temas': [elemento('I999999', 'falsa')]}, 20, 8)
        return RespuestaModelo({'temas': []}, 20, 8)
    salida, meta = ejecutar(tmp_path, Simulado(responder), config(reintentos_formato=1))
    assert todos_ids(salida) == {f'I{i:06d}' for i in range(1, 5)}
    clave = 'formato' if motivo == 'referencia_fuera_del_grupo' else motivo
    assert meta['consolidacion']['motivos_union'][clave] >= 1
    assert meta['llamadas_con_tokens_entrada'] == meta['llamadas_modelo']
    assert meta['llamadas_con_tokens_salida'] == meta['llamadas_modelo']
    assert meta['tokens_entrada'] >= 40


def test_no_acepta_id_real_pero_fuera_de_las_parciales(tmp_path):
    # I000004 existe en la transcripción, no en el primer grupo de parciales.
    def responder(_, datos, esquema):
        bloque = decodificar(datos)
        if 'intervenciones' in bloque:
            i = bloque['intervenciones'][0]['id']
            return RespuestaModelo({'temas': [elemento(i, i + 'x' * 300)]})
        return RespuestaModelo({'temas': [elemento('I000004', 'dato no recibido')]})
    salida, meta = ejecutar(tmp_path, Simulado(responder), config(reintentos_formato=0))
    assert all('dato no recibido' not in e['texto'] for e in salida['temas'])
    assert meta['consolidacion']['motivos_union']['formato'] >= 1
    assert todos_ids(salida) == {f'I{i:06d}' for i in range(1, 5)}


def test_limite_en_extraccion_subdivide_sin_cambiar_id_o_tiempos(tmp_path):
    texto = 'Alfa beta gamma delta. ' * 10
    def responder(_, datos, esquema):
        bloques = decodificar(datos)
        if 'intervenciones' not in bloques:
            raise LimiteModelo('Simulado')
        [i] = bloques['intervenciones']
        assert i['id'] == 'I000001' and (i['inicio'], i['fin']) == (0, 1)
        if len(i['texto']) > 65:
            raise LimiteModelo('Simulado', 8, 4)
        return RespuestaModelo({'temas': [elemento(i['id'], i['texto'])]}, 8, 4)
    cliente = Simulado(responder)
    salida, meta = ejecutar(tmp_path, cliente, config(), entrada(1, texto))
    partes = [decodificar(d)['intervenciones'][0]['texto'] for _, d, _ in cliente.llamadas
              if 'intervenciones' in decodificar(d) and len(decodificar(d)['intervenciones'][0]['texto']) <= 65]
    assert ''.join(partes) == texto.strip()
    assert todos_ids(salida) == {'I000001'}
    assert meta['consolidacion']['subdivisiones_extraccion'] == 3
    assert meta['bloques_extraccion'] == 4
    assert meta['llamadas_con_tokens_entrada'] == 7  # solo extracciones; la consolidación no informa uso


def test_presupuesto_fragmentos_unicode_y_control_sin_perder_texto():
    texto = ('mañana 😀 " ' + '\\ y\n' + '字' * 20) * 100
    intervenciones, _ = leer_transcripcion(entrada(1, texto))
    cfg = config(max_caracteres_bloque=1000)
    prompt, _, _ = _preparar_prompts(cfg.secciones)
    cabe = _presupuesto(cfg, prompt, modelo_minuta(cfg.secciones).model_json_schema())
    bloques = _fragmentar_intervenciones(intervenciones, cabe, cfg.max_caracteres_bloque)
    assert all(cabe(representar_intervenciones(b)) for b in bloques)
    assert all(i.id == 'I000001' and i.inicio == 0 and i.fin == 1 for b in bloques for i in b)
    # El contexto puede repetir fragmentos al comienzo de un bloque.
    assert ''.join(b[-1].texto for b in bloques) == texto.strip()


def test_reintento_no_reenvia_respuesta_invalida_extensa(tmp_path):
    llamadas = []
    def responder(instrucciones, datos, esquema):
        llamadas.append((instrucciones, datos))
        assert len(datos) <= 1000
        assert 'MARCADOR_NO_REENVIAR' not in instrucciones + datos
        if len(llamadas) == 1:
            return RespuestaModelo('MARCADOR_NO_REENVIAR' * 10000, 4, 5)
        i = decodificar(datos)['intervenciones'][0]['id']
        return RespuestaModelo({'temas': [elemento(i, 'correcto')]}, 5, 3)
    salida, meta = ejecutar(tmp_path, Simulado(responder), config(), entrada(1))
    assert len(llamadas) == 2 and salida['temas'][0]['texto'] == 'correcto'
    assert meta['tokens_entrada'] == 9 and meta['tokens_salida'] == 8


@pytest.mark.parametrize('error', [RuntimeError('Red no disponible'), LimiteModelo('Siempre saturado')])
def test_fallo_extraccion_no_reemplaza_resultados_previos(tmp_path, error):
    bueno = Simulado(lambda *_: RespuestaModelo({'temas': []}))
    ejecutar(tmp_path, bueno, config(), entrada(1))
    antes = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    def responder(*_):
        raise error
    cliente = Simulado(responder)
    with pytest.raises(type(error)):
        generar_minuta(entrada(1), tmp_path, configuracion=config(), cliente=cliente, sobrescribir=True)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == antes
    assert len(cliente.llamadas) == (1 if isinstance(error, RuntimeError) else 9)


def test_fallo_red_en_consolidacion_no_se_oculta(tmp_path):
    def responder(_, datos, esquema):
        bloque = decodificar(datos)
        if 'minutas_parciales' in bloque:
            raise RuntimeError('Sin red')
        return RespuestaModelo({'temas': []})
    with pytest.raises(RuntimeError, match='Sin red'):
        ejecutar(tmp_path, Simulado(responder), config())
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('campo,valor', [('num_ctx', True), ('max_tokens_salida', 256.5),
                                         ('max_caracteres_bloque', 1000.5), ('reintentos_formato', 1.5),
                                         ('temperatura', float('nan')), ('temperatura', True)])
def test_configuracion_rechaza_tipos_invalidos(campo, valor):
    with pytest.raises(ValueError):
        ConfiguracionMinutas(**{campo: valor})


@pytest.mark.parametrize('cambio', [{'num_ctx': 2048}, {'num_ctx': 65536}, {'max_tokens_salida': 9000}])
def test_presupuesto_imposible_no_invoca_proveedor(tmp_path, cambio):
    cliente = Simulado(lambda *_: pytest.fail('No corresponde invocar el modelo'))
    with pytest.raises(ValueError, match='contexto|generación'):
        ejecutar(tmp_path, cliente, replace(config(), **cambio), entrada(1))
    assert not cliente.llamadas and not list(tmp_path.iterdir())


def test_reagrupamiento_con_tamanos_aleatorios_siempre_reduce_o_une():
    rng = random.Random(904)
    tipo = modelo_minuta(('acciones',))
    for _ in range(100):
        parciales = [tipo.model_validate({'acciones': [elemento(f'I{i:06d}', 'x' * rng.randrange(1, 1700),
                                                               responsable=None, plazo=None)]})
                     for i in range(rng.randrange(2, 35))]
        grupos = _agrupar_minutas(parciales, lambda d: len(d) <= 1000)
        assert [m for g in grupos for m in g] == parciales
        assert all(len(g) == 1 or len(_datos_minutas(g)) <= 1000 for g in grupos)
        assert _cobertura(parciales, ('acciones',)) == _cobertura([_union_minutas(parciales, tipo)], ('acciones',))


@pytest.mark.parametrize('razon', ['max_tokens', 'model_context_window_exceeded', 'content_filtered',
                                   'guardrail_intervened', 'malformed_tool_use', 'malformed_model_output'])
def test_bedrock_motivos_de_fin_no_aceptan_herramienta_parcial(razon):
    respuesta = {'stopReason': razon, 'usage': {'inputTokens': 25, 'outputTokens': 11},
                 'output': {'message': {'content': [{'toolUse': {'name': 'finalizar_minuta', 'input': {}}}]}}}
    with patch('boto3.Session.client', return_value=SimpleNamespace(converse=lambda **kw: respuesta)):
        cliente = construir_cliente('nova-lite', permitir_remoto=True, temperatura=0,
                                    num_ctx=16384, max_tokens=4096)
        tipo = (LimiteModelo if razon in {'max_tokens', 'model_context_window_exceeded'} else
                RuntimeError if razon in {'content_filtered', 'guardrail_intervened'} else RespuestaEstructuradaAusente)
        with pytest.raises(tipo) as exc:
            cliente.responder('instrucciones', 'datos', {})
        if isinstance(exc.value, (LimiteModelo, RespuestaEstructuradaAusente)):
            assert exc.value.tokens_entrada == 25 and exc.value.tokens_salida == 11


def test_bedrock_no_acepta_dos_llamadas_estructuradas():
    herramienta = {'toolUse': {'name': 'finalizar_minuta', 'input': {}}}
    respuesta = {'stopReason': 'tool_use', 'output': {'message': {'content': [herramienta, herramienta]}}}
    with patch('boto3.Session.client', return_value=SimpleNamespace(converse=lambda **kw: respuesta)):
        cliente = construir_cliente('nova-lite', permitir_remoto=True, temperatura=0, num_ctx=16384, max_tokens=4096)
        with pytest.raises(RespuestaEstructuradaAusente):
            cliente.responder('instrucciones', 'datos', {})


@pytest.mark.parametrize('razon,entrada', [('length', 40), ('stop', 13000)])
def test_ollama_limites_con_uso_reportado(razon, entrada):
    respuesta = {'done_reason': razon, 'prompt_eval_count': entrada, 'eval_count': 15,
                 'message': {'content': '{}'}}
    falso = SimpleNamespace(Client=lambda **kw: SimpleNamespace(chat=lambda **kw: respuesta))
    with patch.dict(sys.modules, {'ollama': falso}):
        cliente = construir_cliente('qwen2.5-7b', permitir_remoto=False, temperatura=0, num_ctx=16384, max_tokens=4096)
        with pytest.raises(LimiteModelo) as exc:
            cliente.responder('instrucciones', 'datos', {})
        assert exc.value.tokens_entrada == entrada and exc.value.tokens_salida == 15
