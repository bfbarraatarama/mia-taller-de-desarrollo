"""Carga de bibliotecas del sistema compartida entre el proyecto y su verificador."""

import ctypes
import os
import platform
from ctypes.util import find_library


def cargar_libarchive():
    """Carga libarchive sin modificar PATH ni descargar binarios.

    Orden de búsqueda:
    1. Variable de entorno LIBARCHIVE (ruta explícita, todas las plataformas).
    2. Nombres lógicos vía find_library; en Windows también carga directa por nombre,
       lo que permite encontrar archiveint.dll en System32 y otros directorios registrados.
    """
    ruta_env = os.environ.get("LIBARCHIVE")
    if ruta_env:
        try:
            biblioteca = ctypes.CDLL(ruta_env)
            biblioteca.archive_read_new
            return biblioteca
        except (OSError, AttributeError):
            pass

    en_windows = platform.system() == "Windows"
    # archiveint es el nombre de la DLL de libarchive incluida en Windows 11.
    nombres = ("archive", "libarchive", "libarchive-13", "archiveint") if en_windows else ("archive",)
    for nombre in nombres:
        ruta = find_library(nombre)
        # En Windows, si find_library no resuelve el nombre lógico, intentar la carga
        # directa: ctypes busca en System32 y las carpetas registradas con add_dll_directory.
        for candidato in ([ruta] if ruta else []) + ([nombre] if en_windows else []):
            try:
                biblioteca = ctypes.CDLL(candidato)
                biblioteca.archive_read_new
                return biblioteca
            except (OSError, AttributeError):
                continue
    raise OSError("No se encontró una libarchive cargable; consultar el README raíz.")