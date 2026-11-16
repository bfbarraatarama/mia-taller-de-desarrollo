"""Tarea 2.1: originales verificados antes de seleccionar (requisito «Originales verificados»)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from evaluacion.modular.__main__ import main
from evaluacion.modular.originales import Original, OriginalInvalido, verificar_originales


def original_en(cache: Path, clave: str, contenido: bytes | None, *, md5: bool = False,
                obtener: str = "python -I hito-2/scripts/descargar_fuentes.py x") -> Original:
    """Original fijado con el hash de `contenido`; si se pasa None no se escribe el archivo."""
    if contenido is not None:
        ruta = cache / clave
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(contenido)
    datos = contenido or b"esperado"
    return Original(
        nombre=Path(clave).stem, clave=clave, bytes=len(datos),
        sha256=None if md5 else hashlib.sha256(datos).hexdigest(),
        md5=hashlib.md5(datos).hexdigest() if md5 else None,
        obtener=obtener,
    )


def test_original_con_hash_distinto(tmp_path):
    original = original_en(tmp_path, "uba_games/figshare-v2/wavs.rar", b"RAR verdadero", md5=True)
    (tmp_path / original.clave).write_bytes(b"RAR alterado!")  # mismo tamaño, otro contenido
    with pytest.raises(OriginalInvalido) as error:
        verificar_originales({"figshare_audio": original}, tmp_path)
    mensaje = str(error.value)
    assert "wavs.rar" in mensaje
    assert original.md5 in mensaje
    assert hashlib.md5(b"RAR alterado!").hexdigest() in mensaje


def test_original_ausente(tmp_path):
    original = original_en(
        tmp_path, "common_voice/cv.tar.gz", None,
        obtener="MDC_API_KEY=… python -I hito-2/scripts/descargar_fuentes.py common_voice")
    with pytest.raises(OriginalInvalido) as error:
        verificar_originales({"common_voice": original}, tmp_path)
    mensaje = str(error.value)
    assert "descargar_fuentes.py common_voice" in mensaje
    assert "MDC_API_KEY" in mensaje


def test_originales_verificados(tmp_path):
    a = original_en(tmp_path, "a/uno.zip", b"uno")
    b = original_en(tmp_path, "b/dos.rar", b"dos", md5=True)
    hashes = verificar_originales({"uno": a, "dos": b}, tmp_path)
    assert hashes == {"uno": hashlib.sha256(b"uno").hexdigest(), "dos": hashlib.sha256(b"dos").hexdigest()}


def test_tamano_distinto_falla_sin_leer_todo(tmp_path):
    original = original_en(tmp_path, "a/uno.zip", b"uno")
    (tmp_path / original.clave).write_bytes(b"uno mas largo")
    with pytest.raises(OriginalInvalido, match="bytes"):
        verificar_originales({"uno": original}, tmp_path)


def test_preparar_no_escribe_con_original_invalido(tmp_path, capsys):
    """Original con hash distinto, a nivel del comando: código 1 y ningún manifiesto."""
    raiz = Path(__file__).resolve().parents[2]
    config = tmp_path / "config.toml"
    config.write_text(
        (raiz / "evaluacion/modular/config.toml").read_text(encoding="utf-8")
        .replace('cache = "hito-2/.cache"', f'cache = "{tmp_path / "cache"}"')
        .replace('salida = "evaluacion/modular/datos"', f'salida = "{tmp_path / "datos"}"'),
        encoding="utf-8")
    assert main(["preparar", "--config", str(config)]) == 1
    assert "descargar_fuentes.py" in capsys.readouterr().err
    assert not (tmp_path / "datos").exists()
