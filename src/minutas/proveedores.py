"""Adaptadores livianos de Ollama y Bedrock; sin dependencia del agente anterior."""

from __future__ import annotations

import os
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from ..rutas import rutas_entorno
from .modelos import obtener_modelo


@dataclass(frozen=True)
class RespuestaModelo:
    contenido: str | dict[str, Any]
    tokens_entrada: int | None = None
    tokens_salida: int | None = None


class _RespuestaIncompleta(ValueError):
    def __init__(self, mensaje: str, tokens_entrada: int | None = None,
                 tokens_salida: int | None = None):
        super().__init__(mensaje)
        self.tokens_entrada = tokens_entrada
        self.tokens_salida = tokens_salida


class RespuestaEstructuradaAusente(_RespuestaIncompleta):
    """El proveedor respondió sin la salida estructurada requerida."""


class LimiteModelo(_RespuestaIncompleta):
    """Límite de contexto o generación reconocido, susceptible de subdivisión."""


class ClienteModelo(Protocol):
    nombre: str
    proveedor: str

    def responder(
        self, instrucciones: str, datos: str, esquema: dict[str, Any]
    ) -> RespuestaModelo: ...


def _campo(objeto: Any, nombre: str, defecto: Any = None) -> Any:
    if isinstance(objeto, dict):
        return objeto.get(nombre, defecto)
    return getattr(objeto, nombre, defecto)


def _cargar_entorno() -> None:
    """Compatible con el .env simple usado en el proyecto de agentes."""
    explicito = os.environ.get("MINUTAS_ENV_FILE")
    rutas = (Path(explicito),) if explicito else rutas_entorno()
    for ruta in rutas:
        if not ruta.is_file():
            continue
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            if linea.startswith("export "):
                linea = linea[len("export "):]
            clave, valor = (parte.strip() for parte in linea.split("=", 1))
            if not clave.isidentifier():
                continue
            if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
                valor = valor[1:-1]
            if not valor.startswith("op://"):
                os.environ.setdefault(clave, valor)


@dataclass(frozen=True)
class DestinoMinutas:
    tipo: str
    descripcion: str
    identidad: tuple
    host: str | None = None
    sesion_aws: Any = field(default=None, repr=False, compare=False)

    @property
    def huella(self) -> str:
        return hashlib.sha256(json.dumps(self.identidad, ensure_ascii=False).encode()).hexdigest()


def resolver_destino(modelo: str) -> DestinoMinutas:
    """Identidad de configuración del destino, sin incluir credenciales en el texto visible."""
    definicion = obtener_modelo(modelo)
    _cargar_entorno()
    if definicion.proveedor == 'bedrock':
        # Resolver configuración del SDK sin crear un cliente ni buscar credenciales.
        from botocore.session import Session
        try:
            sesion = Session()
            scoped = sesion.get_scoped_config()
            region = os.environ.get('AWS_REGION') or sesion.get_config_variable('region') or 'us-east-1'
            perfil = sesion.get_config_variable('profile')
            fips = bool(sesion.get_config_variable('use_fips_endpoint'))
            dualstack = bool(sesion.get_config_variable('use_dualstack_endpoint'))
            endpoint = None
            if not sesion.get_config_variable('ignore_configured_endpoint_urls'):
                servicios = sesion.full_config.get('services', {}).get(scoped.get('services'), {})
                endpoint = (os.environ.get('AWS_ENDPOINT_URL_BEDROCK_RUNTIME')
                            or os.environ.get('AWS_ENDPOINT_URL')
                            or servicios.get('bedrock_runtime', {}).get('endpoint_url')
                            or scoped.get('endpoint_url'))
            host = None
            if endpoint:
                url = urlparse(endpoint)
                if (url.scheme not in {'http', 'https'} or not url.hostname or url.username is not None
                        or url.password is not None or url.query or url.fragment or any(c.isspace() for c in endpoint)):
                    raise ValueError
                autoridad = f'[{url.hostname}]' if ':' in url.hostname else url.hostname
                host = f'{url.scheme}://{autoridad}' + (f':{url.port}' if url.port else '')
        except Exception as exc:
            raise ValueError(f'Configuración de destino Bedrock no admitida ({type(exc).__name__}).') from None
        texto = f'AWS Bedrock ({region})' + (f', servidor configurado {host}' if host else '')
        return DestinoMinutas('bedrock', texto, (definicion.identificador, region, endpoint, perfil, fips, dualstack),
                              sesion_aws=sesion)
    host = os.environ.get('OLLAMA_HOST') or 'http://localhost:11434'
    try:
        url = urlparse(host if '://' in host else f'http://{host}')
        if (url.scheme not in {'http', 'https'} or not url.hostname or url.username is not None
                or url.password is not None or url.query or url.fragment or any(c.isspace() for c in host)):
            raise ValueError
        puerto = url.port or (443 if url.scheme == 'https' else 80 if '://' in host else 11434)
    except ValueError:
        raise ValueError('OLLAMA_HOST no es una dirección HTTP(S) admitida.') from None
    local = url.hostname in {'localhost', '127.0.0.1', '::1'}
    # Fijar una dirección numérica local: no confiar en DNS, proxies o redirecciones.
    hostname = '127.0.0.1' if url.hostname == 'localhost' else url.hostname
    autoridad = f'[{hostname}]' if ':' in hostname else hostname
    normalizado = f'{url.scheme}://{autoridad}:{puerto}{url.path.rstrip("/")}'
    return DestinoMinutas('ollama_local' if local else 'ollama_externo',
                         f'Ollama ({url.hostname}:{puerto})',
                         (definicion.identificador, url.scheme, hostname, puerto, url.path.rstrip('/')),
                         normalizado)


def destino_modelo(modelo: str) -> str:
    return resolver_destino(modelo).tipo


def comprobar_autorizacion(destino: DestinoMinutas, permitir_remoto: bool,
                           destino_autorizado: str | None = None) -> None:
    if destino_autorizado is not None and destino.huella != destino_autorizado:
        raise PermissionError('El destino configurado cambió; se requiere una nueva autorización.')
    if destino.tipo != 'ollama_local' and permitir_remoto is not True:
        raise PermissionError('El destino externo requiere autorización explícita para esta ejecución (permitir_remoto=True).')


def liberar_modelo_ollama(nombre: str, *, destino: DestinoMinutas) -> None:
    """Descarga local best effort, solo sobre el destino de una inferencia iniciada."""
    if destino.tipo != 'ollama_local':
        return
    try:
        import ollama
        cliente = ollama.Client(host=destino.host, timeout=2, trust_env=False, follow_redirects=False)
        cliente.generate(model=nombre, prompt='', keep_alive=0)
    except Exception:
        pass


class ClienteOllama:
    proveedor = "ollama"

    def __init__(self, nombre: str, *, num_ctx: int, temperatura: float, max_tokens: int,
                 destino: DestinoMinutas) -> None:
        try:
            import httpx
            import ollama
        except ImportError as exc:
            raise RuntimeError("Instalá el paquete 'ollama' para usar modelos locales.") from exc
        self.nombre = nombre
        self.destino = destino
        try:
            self._cliente = ollama.Client(host=destino.host, trust_env=False, follow_redirects=False)
        except Exception as exc:
            raise RuntimeError(f'No se pudo inicializar Ollama: {type(exc).__name__}') from None
        self._errores_proveedor = (
            ConnectionError, httpx.HTTPError,
            getattr(ollama, "ResponseError", ConnectionError),
        )
        self._num_ctx = num_ctx
        self._temperatura = temperatura
        self._max_tokens = max_tokens

    def responder(
        self, instrucciones: str, datos: str, esquema: dict[str, Any]
    ) -> RespuestaModelo:
        try:
            resultado = self._cliente.chat(
                model=self.nombre,
                messages=[
                    {"role": "system", "content": instrucciones},
                    {"role": "user", "content": datos},
                ],
                format=esquema,
                options={
                    "temperature": self._temperatura,
                    "seed": 0,
                    "num_ctx": self._num_ctx,
                    "num_predict": self._max_tokens,
                },
            )
        except self._errores_proveedor as exc:
            raise RuntimeError(f"Error al invocar Ollama ({self.nombre}): {type(exc).__name__}") from None
        razon = _campo(resultado, "done_reason")
        entrada = _campo(resultado, "prompt_eval_count")
        salida = _campo(resultado, "eval_count")
        if razon in ("length", "max_tokens"):
            raise LimiteModelo("Ollama interrumpió la respuesta por límite de generación.", entrada, salida)
        if entrada is not None and (entrada >= self._num_ctx - 512
                                    or entrada + self._max_tokens > self._num_ctx):
            raise LimiteModelo("La entrada se aproximó al límite de contexto de Ollama.", entrada, salida)
        mensaje = _campo(resultado, "message")
        contenido = _campo(mensaje, "content") if mensaje is not None else None
        if not contenido:
            raise RespuestaEstructuradaAusente("Ollama no devolvió contenido.", entrada, salida)
        return RespuestaModelo(contenido, entrada, salida)


class ClienteBedrock:
    proveedor = "bedrock"

    def __init__(self, nombre: str, *, temperatura: float, max_tokens: int, destino: DestinoMinutas) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("Instalá el paquete 'boto3' para usar Bedrock.") from exc
        self.nombre = nombre
        from botocore.config import Config
        _, region, endpoint, _, fips, dualstack = destino.identidad
        try:
            self._cliente = boto3.Session(botocore_session=destino.sesion_aws).client(
                "bedrock-runtime", region_name=region, endpoint_url=endpoint,
                config=Config(ignore_configured_endpoint_urls=True, use_fips_endpoint=fips,
                              use_dualstack_endpoint=dualstack, proxies={}))
        except Exception as exc:
            raise RuntimeError(f"No se pudo inicializar AWS Bedrock: {type(exc).__name__}") from None
        self._temperatura = temperatura
        self._max_tokens = max_tokens

    def responder(
        self, instrucciones: str, datos: str, esquema: dict[str, Any]
    ) -> RespuestaModelo:
        # El proveedor del proyecto de agentes utilizaba una herramienta
        # sintética para obtener salidas estructuradas también en Bedrock.
        nombre_herramienta = "finalizar_minuta"
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            respuesta = self._cliente.converse(
                modelId=self.nombre,
                system=[{"text": instrucciones + "\nInvocá la herramienta finalizar_minuta."}],
                messages=[{"role": "user", "content": [{"text": datos}]}],
                inferenceConfig={"temperature": self._temperatura, "maxTokens": self._max_tokens},
                toolConfig={"tools": [{"toolSpec": {
                    "name": nombre_herramienta,
                    "description": "Entregar la minuta estructurada en español.",
                    "inputSchema": {"json": esquema},
                }}]},
            )
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Error al invocar AWS Bedrock ({self.nombre}): {type(exc).__name__}") from None
        uso = respuesta.get("usage") or {}
        entrada, salida = uso.get("inputTokens"), uso.get("outputTokens")
        if respuesta.get("stopReason") in {"max_tokens", "model_context_window_exceeded"}:
            raise LimiteModelo("Bedrock interrumpió la respuesta por límite de generación o contexto.", entrada, salida)
        razon = respuesta.get("stopReason")
        if razon in {"guardrail_intervened", "content_filtered"}:
            raise RuntimeError("Bedrock bloqueó la generación por sus controles de contenido.")
        bloques = respuesta.get("output", {}).get("message", {}).get("content", [])
        llamadas = [bloque["toolUse"] for bloque in bloques if "toolUse" in bloque]
        llamada = llamadas[0] if len(llamadas) == 1 else None
        if (razon in {"malformed_model_output", "malformed_tool_use"}
                or llamada is None or llamada.get("name") != nombre_herramienta
                or not isinstance(llamada.get("input"), dict)):
            raise RespuestaEstructuradaAusente(
                "Bedrock no devolvió la herramienta estructurada solicitada.", entrada, salida
            )
        return RespuestaModelo(llamada["input"], entrada, salida)


def construir_cliente(
    modelo: str, *, permitir_remoto: bool, temperatura: float,
    num_ctx: int, max_tokens: int, destino_autorizado: str | None = None,
) -> ClienteModelo:
    definicion = obtener_modelo(modelo)
    destino = resolver_destino(modelo)
    try:
        comprobar_autorizacion(destino, permitir_remoto, destino_autorizado)
    except PermissionError as exc:
        raise ValueError(str(exc)) from None

    if definicion.proveedor == "bedrock":
        return ClienteBedrock(
            definicion.identificador,
            temperatura=temperatura,
            max_tokens=max_tokens,
            destino=destino,
        )

    return ClienteOllama(
        definicion.identificador,
        num_ctx=num_ctx,
        temperatura=temperatura,
        max_tokens=max_tokens,
        destino=destino,
    )
