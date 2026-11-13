"""Verificación de archivos extraídos contra el listado de un RAR (u otro archivo comprimido) con 7-Zip.

No extrae nada (design.md §11). Lista las entradas con `7z l -slt -ba` (ruta, tamaño y CRC32), rechaza rutas
internas absolutas o con `..`, y compara cada archivo de la carpeta extraída con su entrada: tamaño y CRC32
(calculado con `zlib.crc32`). Además devuelve el SHA-256 de cada archivo verificado, para el manifiesto.

Uso como módulo:
    from evaluacion.rar7z import verificar
    resultados = verificar("wavs.rar", "extraidos", ["wavs/S26/s26.objects.04.channel1.wav"])
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import zlib
from dataclasses import dataclass
from pathlib import Path

MENSAJE_INSTALAR = (
    "No se encontró 7-Zip. Instalalo desde https://www.7-zip.org/ (Windows) o con `sudo apt install 7zip` / "
    "`sudo dnf install p7zip-plugins` (Linux), o indicá la ruta del ejecutable en la variable de entorno SIETE_ZIP."
)


class ErrorVerificacion(Exception):
    """El archivo comprimido, su listado o un archivo extraído no pasan la verificación."""


@dataclass(frozen=True)
class Entrada:
    ruta: str              # ruta interna normalizada con "/"
    tamano: int
    crc32: int | None      # None en carpetas o si 7-Zip no informa CRC
    es_carpeta: bool


@dataclass(frozen=True)
class Verificado:
    ruta_interna: str
    archivo: Path
    tamano: int
    crc32: str             # 8 dígitos hexadecimales en mayúscula, como lo muestra 7-Zip
    sha256: str


# --- 7-Zip --------------------------------------------------------------------------------------------------

def localizar_7zip(entorno: dict | None = None) -> Path:
    """Busca, en orden: la variable SIETE_ZIP, `7z`/`7zz`/`7za` en PATH y `%ProgramFiles%\\7-Zip\\7z.exe`."""
    entorno = os.environ if entorno is None else entorno
    candidatos = [entorno.get("SIETE_ZIP")]
    candidatos += [shutil.which(n) for n in ("7z", "7zz", "7za")]
    for clave in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        if entorno.get(clave):
            candidatos.append(str(Path(entorno[clave]) / "7-Zip" / "7z.exe"))
    for c in candidatos:
        if c and Path(c).is_file():
            return Path(c)
    raise ErrorVerificacion(MENSAJE_INSTALAR)


def version_7zip(siete_zip: Path | None = None) -> str:
    """Primera línea del encabezado de 7-Zip (por ejemplo, '7-Zip 22.01 (x64) : ...')."""
    exe = siete_zip or localizar_7zip()
    r = subprocess.run([str(exe), "i"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    for linea in (r.stdout or "").splitlines():
        if linea.strip():
            return linea.strip()
    return "desconocida"


# --- rutas y listado ----------------------------------------------------------------------------------------

_UNIDAD = re.compile(r"^[A-Za-z]:")


def ruta_segura(ruta: str) -> str:
    """Normaliza una ruta interna a separadores "/" y rechaza las absolutas, con unidad, UNC o con `..`."""
    if ruta is None or not str(ruta).strip():
        raise ErrorVerificacion("ruta interna vacía en el listado")
    original = str(ruta)
    normal = original.replace("\\", "/")
    if normal.startswith("/") or _UNIDAD.match(normal):
        raise ErrorVerificacion(f"ruta interna absoluta no permitida: {original!r}")
    partes = [p for p in normal.split("/") if p not in ("", ".")]
    if any(p == ".." for p in partes):
        raise ErrorVerificacion(f"ruta interna con '..' no permitida: {original!r}")
    if not partes:
        raise ErrorVerificacion(f"ruta interna vacía: {original!r}")
    return "/".join(partes)


def parsear_listado(texto: str) -> dict[str, Entrada]:
    """Interpreta la salida de `7z l -slt -ba`: bloques `Clave = valor` separados por líneas vacías."""
    entradas: dict[str, Entrada] = {}
    bloque: dict[str, str] = {}

    def cerrar():
        if not bloque:
            return
        if "Path" not in bloque:
            raise ErrorVerificacion(f"bloque del listado sin 'Path': {bloque}")
        ruta = ruta_segura(bloque["Path"])
        carpeta = bloque.get("Folder", "-") == "+" or "D" in bloque.get("Attributes", "")[:1]
        tamano = int(bloque.get("Size") or 0)
        crc = bloque.get("CRC", "").strip()
        entradas[ruta] = Entrada(ruta=ruta, tamano=tamano, crc32=int(crc, 16) if crc else None, es_carpeta=carpeta)
        bloque.clear()

    for linea in texto.splitlines():
        if not linea.strip():
            cerrar()
            continue
        clave, sep, valor = linea.partition(" = ")
        if not sep:
            continue  # líneas sin "Clave = valor" (avisos de 7-Zip)
        if clave == "Path" and "Path" in bloque:
            cerrar()  # nuevo bloque sin línea vacía intermedia
        bloque[clave.strip()] = valor
    cerrar()
    return entradas


def listar(archivo_comprimido, siete_zip: Path | None = None) -> dict[str, Entrada]:
    """Lista las entradas del archivo comprimido (sin extraer). Falla si 7-Zip no puede leerlo."""
    archivo_comprimido = Path(archivo_comprimido)
    if not archivo_comprimido.is_file():
        raise ErrorVerificacion(f"no existe el archivo comprimido: {archivo_comprimido}")
    exe = siete_zip or localizar_7zip()
    base = [str(exe), "l", "-slt", "-ba"]
    r = subprocess.run(base + ["-sccUTF-8", str(archivo_comprimido)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0 and "sccUTF-8" in (r.stderr or "") + (r.stdout or ""):  # 7-Zip sin -scc
        r = subprocess.run(base + [str(archivo_comprimido)], capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        detalle = (r.stderr or r.stdout or "").strip().splitlines()
        raise ErrorVerificacion(f"7-Zip no pudo listar {archivo_comprimido.name} (código {r.returncode}): "
                                f"{detalle[-1] if detalle else 'sin detalle'}")
    return parsear_listado(r.stdout or "")


# --- verificación de archivos extraídos ---------------------------------------------------------------------

def huella(archivo) -> tuple[int, int, str]:
    """(tamaño, CRC32, SHA-256) de un archivo, en una sola lectura."""
    crc, sha, tamano = 0, hashlib.sha256(), 0
    with open(archivo, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            crc = zlib.crc32(bloque, crc)
            sha.update(bloque)
            tamano += len(bloque)
    return tamano, crc & 0xFFFFFFFF, sha.hexdigest()


def verificar_extraido(archivo, entrada: Entrada) -> Verificado:
    """Compara un archivo extraído con su entrada del listado: existencia, tamaño y CRC32."""
    archivo = Path(archivo)
    if entrada.es_carpeta:
        raise ErrorVerificacion(f"la entrada {entrada.ruta} es una carpeta, no un archivo")
    if not archivo.is_file():
        raise ErrorVerificacion(f"falta el archivo extraído {archivo} (entrada {entrada.ruta})")
    tamano, crc, sha = huella(archivo)
    if tamano != entrada.tamano:
        raise ErrorVerificacion(f"{archivo}: tamaño {tamano} distinto del de la entrada {entrada.ruta} ({entrada.tamano})")
    if entrada.crc32 is None:
        raise ErrorVerificacion(f"la entrada {entrada.ruta} no tiene CRC en el listado")
    if crc != entrada.crc32:
        raise ErrorVerificacion(f"{archivo}: CRC32 {crc:08X} distinto del de la entrada {entrada.ruta} "
                                f"({entrada.crc32:08X})")
    return Verificado(ruta_interna=entrada.ruta, archivo=archivo, tamano=tamano, crc32=f"{crc:08X}", sha256=sha)


def verificar(archivo_comprimido, carpeta_extraida, rutas_internas, siete_zip: Path | None = None,
              listado: dict[str, Entrada] | None = None) -> list[Verificado]:
    """Verifica cada ruta interna pedida: que esté en el listado y que `carpeta_extraida/<ruta>` coincida."""
    listado = listar(archivo_comprimido, siete_zip) if listado is None else listado
    carpeta_extraida = Path(carpeta_extraida)
    resultados = []
    for pedida in rutas_internas:
        ruta = ruta_segura(pedida)
        if ruta not in listado:
            raise ErrorVerificacion(f"la ruta {ruta} no está en {Path(archivo_comprimido).name}")
        resultados.append(verificar_extraido(carpeta_extraida / ruta, listado[ruta]))
    return resultados
