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
    with pytest.raises(OSError, match="libarchive"):
        b.cargar_libarchive()