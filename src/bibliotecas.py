"""Carga de bibliotecas del sistema compartida entre el proyecto y su verificador."""

import ctypes
import platform
from ctypes.util import find_library


def cargar_libarchive():
    """Carga libarchive sin modificar PATH ni descargar binarios."""
    nombres = ("archive", "libarchive", "libarchive-13") if platform.system() == "Windows" else ("archive",)
    for nombre in nombres:
        ruta = find_library(nombre)
        if not ruta:
            continue
        try:
            biblioteca = ctypes.CDLL(ruta)
            biblioteca.archive_read_new
            return biblioteca
        except (OSError, AttributeError):
            continue
    raise OSError("No se encontró una libarchive cargable; consultar el README raíz.")