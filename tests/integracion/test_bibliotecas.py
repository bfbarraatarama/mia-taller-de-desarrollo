from types import SimpleNamespace

import pytest

from src import bibliotecas as b


def test_libarchive_usa_nombre_del_sistema(monkeypatch):
    biblioteca = SimpleNamespace(archive_read_new=object())
    monkeypatch.setattr(b.platform, "system", lambda: "Linux")
    monkeypatch.setattr(b, "find_library", lambda n: "libarchive.so" if n == "archive" else None)
    monkeypatch.setattr(b.ctypes, "CDLL", lambda r: biblioteca)
    assert b.cargar_libarchive() is biblioteca


def test_libarchive_windows_alternativa_msys2(monkeypatch):
    biblioteca = SimpleNamespace(archive_read_new=object())
    monkeypatch.setattr(b.platform, "system", lambda: "Windows")
    monkeypatch.setattr(b, "find_library", lambda n: n + ".dll")

    def cargar(ruta):
        if ruta != "libarchive-13.dll":
            raise OSError("DLL no cargable")
        return biblioteca

    monkeypatch.setattr(b.ctypes, "CDLL", cargar)
    assert b.cargar_libarchive() is biblioteca


def test_libarchive_ausente(monkeypatch):
    monkeypatch.setattr(b, "find_library", lambda n: None)
    def sin_dll(nombre): raise OSError("no encontrada")
    monkeypatch.setattr(b.ctypes, "CDLL", sin_dll)
    monkeypatch.delenv("LIBARCHIVE", raising=False)
    with pytest.raises(OSError, match="libarchive"):
        b.cargar_libarchive()


def test_libarchive_windows_archiveint_directo(monkeypatch):
    """En Windows, si find_library no resuelve, se carga archiveint directamente (p.ej. System32)."""
    biblioteca = SimpleNamespace(archive_read_new=object())
    monkeypatch.setattr(b.platform, "system", lambda: "Windows")
    monkeypatch.setattr(b, "find_library", lambda n: None)
    def cargar(nombre):
        if nombre == "archiveint":
            return biblioteca
        raise OSError("no encontrada")
    monkeypatch.setattr(b.ctypes, "CDLL", cargar)
    monkeypatch.delenv("LIBARCHIVE", raising=False)
    assert b.cargar_libarchive() is biblioteca


def test_libarchive_variable_entorno(monkeypatch):
    """LIBARCHIVE apunta a una ruta explícita en cualquier plataforma."""
    biblioteca = SimpleNamespace(archive_read_new=object())
    monkeypatch.setenv("LIBARCHIVE", "/custom/libarchive.so")
    monkeypatch.setattr(b.ctypes, "CDLL", lambda r: biblioteca)
    assert b.cargar_libarchive() is biblioteca