"""Fronteras de consentimiento y destino: proveedores sustituidos, sin red."""
from __future__ import annotations

import json
import sys
import types

import pytest

from src.minutas import ConfiguracionMinutas, generar_minuta
from src.minutas.__main__ import main
from src.minutas.proveedores import construir_cliente, resolver_destino
from .test_minutas import transcripcion


@pytest.fixture(autouse=True)
def entorno(monkeypatch, tmp_path):
    monkeypatch.setenv('MINUTAS_ENV_FILE', str(tmp_path / 'sin.env'))
    monkeypatch.setenv('OLLAMA_HOST', 'http://localhost:11434')
    monkeypatch.setenv('AWS_CONFIG_FILE', str(tmp_path / 'sin.aws'))
    monkeypatch.setenv('AWS_SHARED_CREDENTIALS_FILE', str(tmp_path / 'sin.credentials'))
    for clave in ('AWS_PROFILE', 'AWS_DEFAULT_PROFILE', 'AWS_ENDPOINT_URL_BEDROCK_RUNTIME',
                  'AWS_ENDPOINT_URL', 'AWS_REGION', 'AWS_DEFAULT_REGION', 'AWS_USE_FIPS_ENDPOINT',
                  'AWS_USE_DUALSTACK_ENDPOINT', 'AWS_IGNORE_CONFIGURED_ENDPOINT_URLS'):
        monkeypatch.delenv(clave, raising=False)


@pytest.fixture
def proveedor(monkeypatch):
    llamadas = []
    fallar = [False]

    class Ollama:
        def __init__(self, **kwargs):
            llamadas.append(('cliente_ollama', kwargs))

        def chat(self, **kwargs):
            llamadas.append(('chat', kwargs))
            if fallar[0]:
                raise ConnectionError('secreto-que-no-debe-publicarse')
            return {'message': {'content': json.dumps({'resumen': 'Se revisó el informe.'})}}

        def generate(self, **kwargs):
            llamadas.append(('descarga', kwargs))

    class Bedrock:
        def converse(self, **kwargs):
            llamadas.append(('converse', kwargs))
            return {'output': {'message': {'content': [{'toolUse': {
                'name': 'finalizar_minuta', 'input': {'resumen': 'Se revisó el informe.'}}}]}},
                'stopReason': 'tool_use'}

    def cliente_bedrock(*args, **kwargs):
        llamadas.append(('cliente_bedrock', kwargs))
        return Bedrock()

    monkeypatch.setitem(sys.modules, 'ollama', types.SimpleNamespace(Client=Ollama))
    monkeypatch.setitem(sys.modules, 'boto3', types.SimpleNamespace(
        Session=lambda **kw: types.SimpleNamespace(client=cliente_bedrock)))
    return llamadas, fallar


def _cli(tmp_path, modelo, *args):
    entrada = tmp_path / 'transcription.json'
    entrada.write_text(json.dumps(transcripcion()), encoding='utf-8')
    return main(['--entrada', str(entrada), '--salida', str(tmp_path / 'resultado'),
                 '--modelo', modelo, '--secciones', 'resumen', *args])


@pytest.mark.parametrize('modelo', ['qwen2.5-7b', 'nova-lite', 'claude-opus-4.5'])
def test_denegacion_autonoma_no_crea_cliente_ni_descarga(tmp_path, monkeypatch, proveedor, modelo):
    monkeypatch.setenv('OLLAMA_HOST', 'https://modelo.example')
    assert _cli(tmp_path, modelo) == 1
    assert proveedor[0] == []
    assert not (tmp_path / 'resultado' / 'minutes.json').exists()


@pytest.mark.parametrize('host,tipo,acciones', [
    ('http://localhost:11434', 'ollama_local', ['cliente_ollama', 'chat', 'cliente_ollama', 'descarga']),
    ('https://modelo.example', 'ollama_externo', ['cliente_ollama', 'chat']),
])
def test_descarga_solo_servidor_local_tras_inferencia(tmp_path, monkeypatch, proveedor, host, tipo, acciones):
    monkeypatch.setenv('OLLAMA_HOST', host)
    assert _cli(tmp_path, 'qwen2.5-7b', *(['--permitir-remoto'] if tipo == 'ollama_externo' else [])) == 0
    llamadas = proveedor[0]
    assert [n for n, _ in llamadas] == acciones
    destino = resolver_destino('qwen2.5-7b')
    for nombre, datos in llamadas:
        if nombre == 'cliente_ollama':
            assert datos['host'] == destino.host
            assert datos['trust_env'] is False and datos['follow_redirects'] is False
        elif nombre == 'chat':
            assert 'Luisa' in datos['messages'][1]['content']
            assert 'images' not in datos['messages'][1]
        elif nombre == 'descarga':
            assert datos['keep_alive'] == 0 and datos['prompt'] == ''
    meta = json.loads((tmp_path / 'resultado' / 'ejecucion_minutas.json').read_text())
    assert meta['destino'] == tipo and meta['huella_destino'] == destino.huella
    assert meta['configuracion']['permitir_remoto'] == (tipo == 'ollama_externo')
    assert 'destino_autorizado' not in meta['configuracion']


@pytest.mark.parametrize('host', ['localhost:11434', 'https://modelo.example'])
def test_fallo_inferencia_no_filtra_error_proveedor_ni_descarga_externo(tmp_path, proveedor, monkeypatch, capsys, host):
    monkeypatch.setenv('OLLAMA_HOST', host)
    proveedor[1][0] = True
    assert _cli(tmp_path, 'qwen2.5-7b', '--permitir-remoto') == 1
    acciones = [n for n, _ in proveedor[0]]
    assert acciones[:2] == ['cliente_ollama', 'chat']
    assert ('descarga' in acciones) == host.startswith('localhost')
    assert 'secreto-que-no-debe-publicarse' not in capsys.readouterr().err
    assert not (tmp_path / 'resultado' / 'minutes.json').exists()


def test_entrada_invalida_no_contacta_ni_descarga(tmp_path, proveedor):
    with pytest.raises(ValueError):
        generar_minuta({'segments': []}, tmp_path)
    assert proveedor[0] == []


def test_huella_previa_no_autoriza_otro_destino(tmp_path, monkeypatch, proveedor):
    huella = resolver_destino('qwen2.5-7b').huella
    monkeypatch.setenv('OLLAMA_HOST', 'https://modelo.example')
    cfg = ConfiguracionMinutas(permitir_remoto=True, destino_autorizado=huella, secciones=('resumen',))
    with pytest.raises(ValueError, match='destino configurado cambió'):
        generar_minuta(transcripcion(), tmp_path, configuracion=cfg)
    assert proveedor[0] == []


@pytest.mark.parametrize('host,tipo,normalizado', [
    ('localhost', 'ollama_local', 'http://127.0.0.1:11434'),
    ('http://localhost', 'ollama_local', 'http://127.0.0.1:80'),
    ('http://[::1]:11434', 'ollama_local', 'http://[::1]:11434'),
    ('https://localhost.example', 'ollama_externo', 'https://localhost.example:443'),
    ('http://127.0.0.2:11434', 'ollama_externo', 'http://127.0.0.2:11434'),
])
def test_destino_ollama_se_resuelve_sin_cliente(host, tipo, normalizado, proveedor, monkeypatch):
    monkeypatch.setenv('OLLAMA_HOST', host)
    destino = resolver_destino('qwen2.5-7b')
    assert (destino.tipo, destino.host) == (tipo, normalizado)
    assert proveedor[0] == []


@pytest.mark.parametrize('host', ['http://localhost@otro.example', 'ftp://localhost', 'http://localhost?a=secreto',
                                  'http://localhost:99999', 'http://localhost#secreto'])
def test_destino_ollama_invalido_no_inicializa_cliente(host, proveedor, monkeypatch):
    monkeypatch.setenv('OLLAMA_HOST', host)
    with pytest.raises(ValueError, match='OLLAMA_HOST') as e:
        resolver_destino('qwen2.5-7b')
    assert host not in str(e.value)
    assert proveedor[0] == []


def test_bedrock_endpoint_de_perfil_y_precedencia(tmp_path, monkeypatch, proveedor):
    archivo = tmp_path / 'aws'
    archivo.write_text('[profile prueba]\nregion = us-west-2\nservices = prueba-servicios\n'
                      'endpoint_url = https://general.example\n[services prueba-servicios]\n'
                      'bedrock_runtime =\n  endpoint_url = https://especifico.example\n')
    monkeypatch.setenv('AWS_CONFIG_FILE', str(archivo))
    monkeypatch.setenv('AWS_PROFILE', 'prueba')
    d1 = resolver_destino('nova-lite')
    assert 'especifico.example' in d1.descripcion and 'us-west-2' in d1.descripcion
    assert proveedor[0] == []
    monkeypatch.setenv('AWS_ENDPOINT_URL_BEDROCK_RUNTIME', 'https://ambiente.example')
    d2 = resolver_destino('nova-lite')
    assert d2.huella != d1.huella
    with pytest.raises(ValueError, match='destino configurado cambió'):
        construir_cliente('nova-lite', permitir_remoto=True, temperatura=0, num_ctx=4096,
                          max_tokens=1024, destino_autorizado=d1.huella)
    assert proveedor[0] == []
    construir_cliente('nova-lite', permitir_remoto=True, temperatura=0, num_ctx=4096,
                      max_tokens=1024, destino_autorizado=d2.huella)
    datos = proveedor[0][0][1]
    assert datos['endpoint_url'] == 'https://ambiente.example' and datos['region_name'] == 'us-west-2'
    assert datos['config'].ignore_configured_endpoint_urls is True
    monkeypatch.setenv('AWS_IGNORE_CONFIGURED_ENDPOINT_URLS', 'true')
    d3 = resolver_destino('nova-lite')
    assert d3.huella != d2.huella and 'ambiente.example' not in d3.descripcion


def test_bedrock_autorizado_registra_destino_y_no_descarga(tmp_path, proveedor):
    assert _cli(tmp_path, 'nova-lite', '--permitir-remoto') == 0
    assert [n for n, _ in proveedor[0]] == ['cliente_bedrock', 'converse']
    assert 'Luisa' in proveedor[0][1][1]['messages'][0]['content'][0]['text']
    meta = json.loads((tmp_path / 'resultado' / 'ejecucion_minutas.json').read_text())
    assert meta['destino'] == 'bedrock' and meta['huella_destino'] == resolver_destino('nova-lite').huella
    assert meta['configuracion']['permitir_remoto'] is True


def test_bedrock_sdk_real_usa_perfil_y_destino_actuales_sin_red(tmp_path, monkeypatch):
    import boto3
    from botocore.stub import Stubber
    config = tmp_path / 'aws'
    config.write_text('[profile anterior]\nregion=us-east-1\n[profile actual]\nregion=us-west-2\n'
                      'endpoint_url=https://bedrock.example.invalid\n')
    credenciales = tmp_path / 'credentials'
    credenciales.write_text('[anterior]\naws_access_key_id=PRUEBAANTERIOR\naws_secret_access_key=falso-anterior\n'
                             '[actual]\naws_access_key_id=PRUEBAACTUAL\naws_secret_access_key=falso-actual\n')
    monkeypatch.setenv('AWS_CONFIG_FILE', str(config))
    monkeypatch.setenv('AWS_SHARED_CREDENTIALS_FILE', str(credenciales))
    monkeypatch.setenv('AWS_EC2_METADATA_DISABLED', 'true')
    for clave in ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN',
                  'AWS_SECURITY_TOKEN', 'AWS_DEFAULT_PROFILE'):
        monkeypatch.delenv(clave, raising=False)
    monkeypatch.setattr(boto3, 'DEFAULT_SESSION', boto3.Session(profile_name='anterior'))
    monkeypatch.setenv('AWS_PROFILE', 'actual')
    monkeypatch.setenv('HTTPS_PROXY', 'http://proxy.example.invalid:3128')
    destino = resolver_destino('nova-lite')
    cliente = construir_cliente('nova-lite', permitir_remoto=True, temperatura=0, num_ctx=4096,
                                 max_tokens=1024, destino_autorizado=destino.huella)
    sdk = cliente._cliente
    assert sdk.meta.endpoint_url == 'https://bedrock.example.invalid'
    assert sdk.meta.region_name == 'us-west-2'
    assert sdk._request_signer._credentials.access_key == 'PRUEBAACTUAL'
    assert sdk.meta.config.proxies == {}
    with Stubber(sdk) as stub:
        stub.add_client_error('converse', service_error_code='AccessDeniedException', service_message='prueba')
        with pytest.raises(RuntimeError, match='Error al invocar AWS Bedrock'):
            cliente.responder('instrucciones', 'datos sintéticos', {'type': 'object'})
        stub.assert_no_pending_responses()


@pytest.mark.parametrize('host,esperado', [
    ('http://localhost:11434', 'http://127.0.0.1:11434/api/chat'),
    ('https://servidor.example.invalid', 'https://servidor.example.invalid/api/chat'),
])
def test_ollama_sdk_no_sigue_redireccion_ni_usa_proxy_del_entorno(host, esperado, monkeypatch):
    pytest.importorskip('ollama', reason='falta el SDK real de Ollama')
    import httpx
    monkeypatch.setenv('OLLAMA_HOST', host)
    monkeypatch.setenv('HTTP_PROXY', 'http://proxy.example.invalid:3128')
    monkeypatch.setenv('HTTPS_PROXY', 'http://proxy.example.invalid:3128')
    llamadas = []
    def responder(self, request):
        llamadas.append(str(request.url))
        return httpx.Response(307, headers={'location': 'https://otro.example.invalid/api/chat'})
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', responder)
    destino = resolver_destino('qwen2.5-7b')
    cliente = construir_cliente('qwen2.5-7b', permitir_remoto=destino.tipo != 'ollama_local',
                                 temperatura=0, num_ctx=4096, max_tokens=1024)
    try:
        http = cliente._cliente._client
        assert http.trust_env is False and http.follow_redirects is False
        with pytest.raises(RuntimeError, match='Error al invocar Ollama'):
            cliente.responder('instrucciones', 'datos sintéticos', {'type': 'object'})
        assert llamadas == [esperado]
    finally:
        cliente._cliente.close()
