"""Modelo de las fichas del etiquetado (D8), sin Qt: el diálogo solo lo muestra y le pasa lo que hace el usuario.

- Una ficha por etiqueta de diarization.json, de mayor a menor tiempo de habla (empate: etiqueta menor).
- Cada ficha recorre su secuencia de fragmentos (D6) con «Otro fragmento» y muestra «fragmento i de n».
- Nombres: se quitan los espacios de los extremos y se reducen los internos a uno; vacío es `None`. Los que
  coinciden sin distinguir mayúsculas son la misma persona y llevan la primera forma escrita, en el orden de las
  fichas. Los que difieren solo en tildes no se unifican: `avisos_tildes` los informa antes de confirmar.
- Cierre: `confirmar` o `cerrar_sin_confirmar` devuelven una `Decision`; `aplicar` la ejecuta.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from asociacion import Asociacion, Turnos
from fragmentos import Fragmento, Fragmentos, fragmentos as calcular_fragmentos
from salida import escribir


def normalizar(nombre: str | None) -> str | None:
    if nombre is None:
        return None
    return " ".join(nombre.split()) or None


def _clave(nombre: str) -> str:
    """Misma persona: igual sin distinguir mayúsculas."""
    return nombre.casefold()


def _sin_tildes(nombre: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", nombre) if not unicodedata.combining(c)).casefold()


@dataclass
class Ficha:
    etiqueta: str
    tiempo_habla_s: float
    fragmentos: Fragmentos
    nombre: str = ""  # tal como lo escribió el usuario
    indice: int = 0   # cuántas veces pidió «Otro fragmento»

    @property
    def fragmento(self) -> Fragmento:
        return self.fragmentos.en(self.indice)

    @property
    def contador(self) -> str:
        n = len(self.fragmentos.secuencia)
        return f"fragmento {self.indice % n + 1} de {n}"

    @property
    def aviso_superposicion(self) -> bool:
        return self.fragmento.superpuesto


@dataclass(frozen=True)
class Etiquetado:
    """Lo que se escribe al confirmar: nombre final y fragmento en pantalla de cada etiqueta."""
    nombres: dict[str, str | None]
    clips: dict[str, tuple[float, float]]


class Cierre(Enum):
    VOLVER = "Volver a las fichas"
    SIN_NOMBRES = "Seguir sin nombres"
    CANCELAR = "Cancelar"


CIERRE_POR_DEFECTO = Cierre.VOLVER


@dataclass(frozen=True)
class Decision:
    accion: str  # "escribir" (con etiquetado o, si es None, sin nombres), "volver" o "cancelar"
    etiquetado: Etiquetado | None = None


class ModeloFichas:
    def __init__(self, asociacion: Asociacion):
        turnos = Turnos(asociacion.turnos)
        por_etiqueta = calcular_fragmentos(asociacion)
        fichas = [Ficha(e, sum(f - i for i, f in turnos.intervalos(e)) / 1000, por_etiqueta[e])
                  for e in turnos.etiquetas]
        self.fichas = sorted(fichas, key=lambda f: (-f.tiempo_habla_s, f.etiqueta))
        self._por_etiqueta = {f.etiqueta: f for f in self.fichas}

    @property
    def hay_fichas(self) -> bool:
        """Sin etiquetas (diarización vacía) se saltea el etiquetado."""
        return bool(self.fichas)

    def ficha(self, etiqueta: str) -> Ficha:
        return self._por_etiqueta[etiqueta]

    def escribir_nombre(self, etiqueta: str, texto: str) -> None:
        self.ficha(etiqueta).nombre = texto

    def otro_fragmento(self, etiqueta: str) -> Fragmento:
        f = self.ficha(etiqueta)
        f.indice += 1
        return f.fragmento

    def nombres(self) -> dict[str, str | None]:
        """Nombres normalizados y unificados, por etiqueta."""
        formas: dict[str, str] = {}
        resultado = {}
        for f in self.fichas:
            n = normalizar(f.nombre)
            resultado[f.etiqueta] = formas.setdefault(_clave(n), n) if n else None
        return resultado

    def sugerencias(self, etiqueta: str, prefijo: str = "") -> list[str]:
        """Nombres de las otras fichas que empiezan con `prefijo`, sin distinguir mayúsculas, sin repetir."""
        p = _clave(" ".join(prefijo.split()))
        nombres = self.nombres()
        vistos: list[str] = []
        for f in self.fichas:
            n = nombres[f.etiqueta]
            if f.etiqueta != etiqueta and n and n not in vistos and _clave(n).startswith(p):
                vistos.append(n)
        return vistos

    def avisos_tildes(self) -> list[tuple[str, str]]:
        """Pares de nombres distintos que solo difieren en tildes, en el orden de las fichas."""
        distintos = list(dict.fromkeys(n for n in self.nombres().values() if n))
        return [(a, b) for k, a in enumerate(distintos) for b in distintos[k + 1:]
                if _sin_tildes(a) == _sin_tildes(b)]

    def confirmar(self) -> Decision:
        clips = {f.etiqueta: (f.fragmento.start, f.fragmento.end) for f in self.fichas}
        return Decision("escribir", Etiquetado(nombres=self.nombres(), clips=clips))

    def cerrar_sin_confirmar(self, opcion: Cierre) -> Decision:
        if opcion is Cierre.SIN_NOMBRES:
            return Decision("escribir")
        return Decision("volver" if opcion is Cierre.VOLVER else "cancelar")


def aplicar(asociacion: Asociacion, decision: Decision, salida: str | Path | None = None) -> Path | None:
    """Escribe si la decisión lo pide; devuelve la ruta de transcription.json o None si no se escribió nada."""
    if decision.accion != "escribir":
        return None
    return escribir(asociacion, decision.etiquetado, salida=salida)
