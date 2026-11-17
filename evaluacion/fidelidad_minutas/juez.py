"""Juez local y agregación de votos sobre ítems de referencia."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from src.minutas.proveedores import ClienteOllama, resolver_destino

from .archivos import REUNIONES_EJEMPLO, leer_csv, sha256
from .inferencia import modelo_local

MODELO_JUEZ = "m-prometheus-3b-i1:q4_k_m"
PROMPT = Path(__file__).parent / "prompts" / "juez_v1.md"
GGUF = Path(__file__).parent / "M-Prometheus-3B.i1-Q4_K_M.gguf"
GGUF_SHA256 = "03a2d4c481720b834d074428ab71567c751bc6998fee49cb5002d42d5e8913d0"
GGUF_REVISION = "3d55806f3c809b6caccea702fd7e250fd5d16748"
ETIQUETAS = ("sí", "no", "incierto", "no_evaluable")


@dataclass(frozen=True)
class Ejemplo:
    reunion: str
    minuta: str
    items: tuple[dict[str, str], ...]
    csv: Path
    markdown: Path
    sha_csv: str
    sha_markdown: str

    def verificar(self) -> None:
        if sha256(self.csv) != self.sha_csv or sha256(self.markdown) != self.sha_markdown:
            raise ValueError(f"El par de ejemplo {self.reunion} fue alterado.")


def cargar_ejemplos(carpeta: Path) -> tuple[Ejemplo, ...]:
    ejemplos = []
    for reunion in REUNIONES_EJEMPLO:
        csv, md = carpeta / f"{reunion}.csv", carpeta / f"{reunion}.minuta.md"
        sha_csv, sha_md = sha256(csv), sha256(md)
        filas = leer_csv(csv)
        ids = [f["item_id"] for f in filas]
        if not filas or len(set(ids)) != len(ids) or any(f["reunion"] != reunion for f in filas):
            raise ValueError(f"Planilla inválida para {reunion}.")
        if any(f["recuperado"] not in ("sí", "no", "") for f in filas):
            raise ValueError(f"Etiqueta humana inválida para {reunion}.")
        ejemplo = Ejemplo(reunion, md.read_text(encoding="utf-8"),
                               tuple({"referencia": f["referencia"], "recuperado": f["recuperado"]}
                                     for f in filas if f["recuperado"] in ("sí", "no")),
                               csv, md, sha_csv, sha_md)
        ejemplo.verificar()
        ejemplos.append(ejemplo)
    return tuple(ejemplos)


def agregar(resultados: list[str]) -> str:
    if not resultados or any(x not in ETIQUETAS for x in resultados):
        raise ValueError("Votos inválidos o ausentes.")
    conteo = Counter(resultados)
    maximo = max(conteo.values())
    ganadores = [etiqueta for etiqueta, n in conteo.items() if n == maximo]
    return ganadores[0] if len(ganadores) == 1 else "incierto"


class RespuestaJuez(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resultado: str
    observaciones: str
    citas: list[str] = []

    @field_validator("resultado")
    @classmethod
    def etiqueta(cls, valor: str) -> str:
        if valor not in ETIQUETAS:
            raise ValueError("Etiqueta inválida.")
        return valor


def validar_respuesta(datos: object) -> tuple[RespuestaJuez, str]:
    if not isinstance(datos, dict):
        raise ValueError("El juez no devolvió un objeto.")
    contenido = dict(datos)
    citas = contenido.get("citas")
    advertencia = ""
    if not isinstance(citas, list) or not all(isinstance(c, str) for c in citas):
        contenido["citas"] = []
        advertencia = "Citas ausentes o malformadas."
    try:
        respuesta = RespuestaJuez.model_validate(contenido)
    except ValidationError as exc:
        raise ValueError("Respuesta del juez fuera del esquema.") from exc
    if respuesta.resultado in ("incierto", "no_evaluable") and not respuesta.observaciones.strip():
        raise ValueError("Falta la explicación de una abstención.")
    return respuesta, advertencia


class Juez:
    def __init__(self) -> None:
        self.identidad = modelo_local(MODELO_JUEZ)
        if self.identidad is None:
            raise RuntimeError("No se pudo identificar el modelo del juez.")
        if not GGUF.is_file() or sha256(GGUF) != GGUF_SHA256:
            raise RuntimeError("Falta el GGUF del juez o su SHA-256 no coincide con la revisión fijada.")
        generador = modelo_local("qwen2.5:7b", requerido=False)
        if generador is not None and self.identidad["digest"] == generador["digest"]:
            raise ValueError("El juez y el generador tienen el mismo modelo.")
        self.prompt = PROMPT.read_text(encoding="utf-8")
        self.prompt_sha = sha256(PROMPT)
        self.identidad.update({
            "fuente": "mradermacher/M-Prometheus-3B-i1-GGUF", "revision": GGUF_REVISION,
            "archivo": GGUF.name, "sha256_gguf": GGUF_SHA256,
            "sha256_modelfile": sha256(Path(__file__).parent / "Modelfile"),
            "parametros": {"temperature": 0, "seed": 0, "num_ctx": 32768, "num_predict": 1024},
        })
        destino = resolver_destino("qwen2.5-7b")
        if destino.tipo != "ollama_local":
            raise ValueError("El juez requiere Ollama local.")
        self.cliente = ClienteOllama(MODELO_JUEZ, num_ctx=32768, temperatura=0, max_tokens=1024, destino=destino)

    def evaluar(self, referencia: str, minuta: str, ejemplo: Ejemplo) -> tuple[RespuestaJuez, str]:
        ejemplo.verificar()
        identidad = modelo_local(MODELO_JUEZ)
        if identidad is None or identidad["digest"] != self.identidad["digest"] or sha256(PROMPT) != self.prompt_sha:
            raise ValueError("El modelo o prompt del juez cambió durante la ejecución.")
        datos = json.dumps({"minuta_ejemplo": ejemplo.minuta, "items_ejemplo": ejemplo.items,
                            "minuta_objetivo": minuta, "referencia_objetivo": referencia},
                           ensure_ascii=False, separators=(",", ":"))
        esquema = RespuestaJuez.model_json_schema()
        if len((self.prompt + datos + json.dumps(esquema)).encode("utf-8")) > 2 * (32768 - 1024 - 512):
            raise ValueError("El ejemplo y la minuta exceden el presupuesto del juez.")
        ultimo = None
        for _ in range(3):
            respuesta = self.cliente.responder(self.prompt, datos, esquema)
            try:
                contenido = json.loads(respuesta.contenido) if isinstance(respuesta.contenido, str) else respuesta.contenido
                return validar_respuesta(contenido)
            except (ValueError, ValidationError) as exc:
                ultimo = exc
        raise ValueError("El juez no produjo una respuesta válida tras tres intentos.") from ultimo
