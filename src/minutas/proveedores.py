"""Adaptadores livianos de Ollama y Bedrock; sin dependencia del agente anterior."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from rutas import rutas_entorno
from .modelos import obtener_modelo


@dataclass(frozen=True)
class RespuestaModelo:
    contenido: str | dict[str, Any]
    tokens_entrada: int | None = None
    tokens_salida: int | None = None


class RespuestaEstructuradaAusente(ValueError):
    """El proveedor respondió sin la salida estructurada requerida."""


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


class ClienteOllama:
    proveedor = "ollama"

    def __init__(self, nombre: str, *, num_ctx: int, temperatura: float, max_tokens: int) -> None:
        try:
            import httpx
            import ollama
        except ImportError as exc:
            raise RuntimeError("Instalá el paquete 'ollama' para usar modelos locales.") from exc
        self.nombre = nombre
        self._cliente = ollama.Client(host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
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
            raise RuntimeError(f"Error al invocar Ollama ({self.nombre}): {exc}") from exc
        razon = _campo(resultado, "done_reason")
        if razon in ("length", "max_tokens"):
            raise ValueError("Ollama interrumpió la respuesta por límite de generación.")
        entrada = _campo(resultado, "prompt_eval_count")
        if entrada is not None and entrada >= self._num_ctx - 512:
            raise ValueError("La entrada se aproximó al límite de contexto de Ollama.")
        mensaje = _campo(resultado, "message")
        contenido = _campo(mensaje, "content") if mensaje is not None else None
        if not contenido:
            raise RespuestaEstructuradaAusente("Ollama no devolvió contenido.")
        return RespuestaModelo(contenido, entrada, _campo(resultado, "eval_count"))


class ClienteBedrock:
    proveedor = "bedrock"

    def __init__(self, nombre: str, *, temperatura: float, max_tokens: int) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("Instalá el paquete 'boto3' para usar Bedrock.") from exc
        self.nombre = nombre
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
        self._cliente = boto3.client("bedrock-runtime", region_name=region)
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
            raise RuntimeError(f"Error al invocar AWS Bedrock ({self.nombre}): {exc}") from exc
        if respuesta.get("stopReason") == "max_tokens":
            raise ValueError("Bedrock interrumpió la respuesta por límite de generación.")
        bloques = respuesta.get("output", {}).get("message", {}).get("content", [])
        llamadas = [bloque["toolUse"] for bloque in bloques if "toolUse" in bloque]
        llamada = next((c for c in llamadas if c.get("name") == nombre_herramienta), None)
        if llamada is None or not isinstance(llamada.get("input"), dict):
            raise RespuestaEstructuradaAusente(
                "Bedrock no devolvió la herramienta estructurada solicitada."
            )
        uso = respuesta.get("usage") or {}
        return RespuestaModelo(
            llamada["input"], uso.get("inputTokens"), uso.get("outputTokens")
        )


def construir_cliente(
    modelo: str, *, permitir_remoto: bool, temperatura: float,
    num_ctx: int, max_tokens: int,
) -> ClienteModelo:
    definicion = obtener_modelo(modelo)
    if definicion.requiere_remoto and not permitir_remoto:
        raise ValueError("El uso de Bedrock requiere permitir_remoto=True.")

    _cargar_entorno()

    if definicion.proveedor == "bedrock":
        return ClienteBedrock(
            definicion.identificador,
            temperatura=temperatura,
            max_tokens=max_tokens,
        )

    return ClienteOllama(
        definicion.identificador,
        num_ctx=num_ctx,
        temperatura=temperatura,
        max_tokens=max_tokens,
    )