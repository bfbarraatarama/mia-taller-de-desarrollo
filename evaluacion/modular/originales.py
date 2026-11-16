"""Verificación de los originales de la muestra (requisito «Originales verificados»).

No descarga nada: si falta un original o no coincide, el error indica el comando del Hito 2 que lo obtiene.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Original:
    """Archivo original fijado: ruta relativa a la caché del Hito 2, tamaño y hash esperados."""

    nombre: str
    clave: str
    bytes: int
    sha256: str | None
    md5: str | None
    obtener: str


class OriginalInvalido(Exception):
    """Uno o más originales faltan o no coinciden con su hash fijado."""

    def __init__(self, problemas: list[str]):
        self.problemas = problemas
        super().__init__("Originales sin verificar:\n" + "\n".join(f"- {p}" for p in problemas))


def _hashes(ruta: Path) -> tuple[str, str]:
    """SHA-256 y MD5 en una sola lectura (wavs.rar pesa 722 MB)."""
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(bloque)
            md5.update(bloque)
    return sha.hexdigest(), md5.hexdigest()


def _problema(original: Original, cache: Path) -> tuple[str | None, str | None]:
    """Devuelve (problema, sha256 encontrado)."""
    ruta = cache / original.clave
    if not ruta.is_file():
        return f"{original.clave}: falta en {cache}. Para obtenerlo: {original.obtener}", None
    tamano = ruta.stat().st_size
    if tamano != original.bytes:
        return (f"{original.clave}: tiene {tamano} bytes y se esperan {original.bytes}. "
                f"Para obtenerlo de nuevo: {original.obtener}"), None
    sha, md5 = _hashes(ruta)
    if original.sha256 and sha != original.sha256:
        return f"{original.clave}: SHA-256 esperado {original.sha256}, encontrado {sha}", None
    if not original.sha256 and original.md5 and md5 != original.md5:
        return f"{original.clave}: MD5 esperado {original.md5}, encontrado {md5}", None
    return None, sha


def verificar_originales(originales: dict[str, Original], cache: Path) -> dict[str, str]:
    """Verifica todos los originales y devuelve el SHA-256 de cada uno; informa todos los problemas juntos."""
    problemas, hashes = [], {}
    for nombre, original in originales.items():
        problema, sha = _problema(original, Path(cache))
        if problema:
            problemas.append(problema)
        else:
            hashes[nombre] = sha
    if problemas:
        raise OriginalInvalido(problemas)
    return hashes
