from types import SimpleNamespace

import pytest
from packaging.requirements import Requirement

from src import verificar_entorno as v
from src.rutas import DIRECTORIO_PROYECTO
from src.verificar_entorno import cumple, leer_restricciones, normalizar_nombre, requisitos_directos

VERSIONES_VERIFICADAS = {"torch": "==2.8.0", "torchaudio": "==2.8.0", "torchcodec": "==0.7.0",
                         "pyannote-audio": "==4.0.7"}


def test_constraints_fija_las_versiones_verificadas():
    r = leer_restricciones()
    for nombre, espec in VERSIONES_VERIFICADAS.items():
        assert r[nombre] == espec
    for requisito in requisitos_directos():
        nombre = normalizar_nombre(requisito.name)
        assert nombre in r, f"{nombre} no está en constraints.txt"


def test_constraints_no_tiene_etiquetas_locales_ni_duplicados():
    lineas = [l.split("#", 1)[0].strip() for l in v.RESTRICCIONES.read_text(encoding="utf-8").splitlines()]
    nombres = [normalizar_nombre(l.split("==")[0]) for l in lineas if l]
    assert len(nombres) == len(set(nombres))
    assert not any("+cpu" in l or "+cu" in l for l in lineas)


def test_requisitos_directos_coinciden_con_restricciones():
    r = leer_restricciones()
    for requisito in requisitos_directos():
        version = r[normalizar_nombre(requisito.name)].removeprefix("==")
        assert requisito.specifier.contains(version, prereleases=True), requisito.name


@pytest.mark.parametrize("perfil", ["cpu", "cu128"])
def test_perfiles_usan_entorno_comun_y_variantes_locales(perfil):
    lineas = (DIRECTORIO_PROYECTO / f"requirements-{perfil}.txt").read_text(encoding="utf-8").splitlines()
    assert "-r requirements.txt" in lineas
    assert f"--extra-index-url https://download.pytorch.org/whl/{perfil}" in lineas
    r = leer_restricciones()
    requisitos = [Requirement(l) for l in lineas if l and not l.startswith(("#", "-"))]
    assert {q.name for q in requisitos} == {"torch", "torchaudio"}
    for q in requisitos:
        version = str(q.specifier).removeprefix("==")
        assert version.endswith("+" + perfil)
        assert cumple(version, r[q.name])
    general = (DIRECTORIO_PROYECTO / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert "-c constraints.txt" in general and "-e .[test]" in general


@pytest.mark.parametrize("problema", [None, "ausente", "version", "sin_restriccion", "extra"])
def test_verificador_versiones(monkeypatch, problema):
    restricciones = leer_restricciones()
    instalados = {n: s.removeprefix("==") for n, s in restricciones.items()}
    instalados.update(torch="2.8.0+cu128", torchaudio="2.8.0+cu128", **{"mia104-poc": "0.1.0"})
    if problema == "ausente":
        del instalados["openai-whisper"]
    elif problema == "version":
        instalados["openai-whisper"] = "20000101"
    elif problema == "sin_restriccion":
        del restricciones["openai-whisper"]
    elif problema == "extra":
        instalados["paquete-extra"] = "1.0"
    monkeypatch.setattr(v, "leer_restricciones", lambda: restricciones)
    monkeypatch.setattr(v.metadata, "distributions", lambda: [
        SimpleNamespace(metadata={"Name": n}, version=vers) for n, vers in instalados.items()
    ])
    monkeypatch.setattr(v, "verificar_comando", lambda *args, **kwargs: True)
    monkeypatch.setattr(v, "_resultados", [])
    v.verificar_versiones()
    estados = [estado for estado, _, _ in v._resultados]
    assert ("FALLA" in estados) == (problema in {"ausente", "version", "sin_restriccion"})
    assert ("AVISO" in estados) == (problema in {"sin_restriccion", "extra"})


@pytest.mark.parametrize("codigo", [0, 1])
def test_comando_informa_codigo_de_salida(monkeypatch, codigo):
    monkeypatch.setattr(v.shutil, "which", lambda nombre: "/ruta/herramienta")
    monkeypatch.setattr(v.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=codigo, stdout=" ", stderr=""))
    monkeypatch.setattr(v, "_resultados", [])
    assert v.verificar_comando("herramienta", ("-v",)) == (codigo == 0)
    assert v._resultados[0][0] == ("OK" if codigo == 0 else "FALLA")


def test_comando_ausente(monkeypatch):
    monkeypatch.setattr(v.shutil, "which", lambda nombre: None)
    monkeypatch.setattr(v, "_resultados", [])
    assert not v.verificar_comando("herramienta", ())
    assert v._resultados[0][0] == "FALLA"


@pytest.mark.parametrize("instalada, espec, esperado", [
    ("2.8.0+cpu", "==2.8.0", True), ("2.8.0+cu128", "==2.8.0", True), ("2.15.0", "==2.8.0", False),
    ("0.7.0", "==0.7.0", True), ("0.7.0", "==0.7.*", True), ("0.17.0", "==0.7.*", False),
])
def test_cumple_sigue_pep_440(instalada, espec, esperado):
    assert cumple(instalada, espec) is esperado


def test_linea_no_reconocida(tmp_path):
    ruta = tmp_path / "constraints.txt"
    ruta.write_text("torch>=2.8\n", encoding="utf-8")
    with pytest.raises(ValueError):
        leer_restricciones(ruta)


def test_restriccion_duplicada(tmp_path):
    ruta = tmp_path / "constraints.txt"
    ruta.write_text("pyannote.audio==4.0.7\npyannote-audio==4.0.7\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicada"):
        leer_restricciones(ruta)


def _mock_ffmpeg_base(monkeypatch, tmp_path):
    """Fija el entorno mínimo para probar verificar_ffmpeg en modo Windows."""
    monkeypatch.setattr(v.os, "name", "nt")
    monkeypatch.setattr(v.sys, "path", [])
    monkeypatch.setattr(v, "DLL_FFMPEG_POR_DEFECTO", tmp_path / "readme_path")
    monkeypatch.delenv("DIARIZACION_FFMPEG_DLL_DIR", raising=False)
    monkeypatch.setattr(v, "verificar_comando", lambda *a, **kw: True)
    monkeypatch.setattr(v, "_resultados", [])


def test_verificar_ffmpeg_dll_en_directorio_ffmpeg(monkeypatch, tmp_path):
    """avcodec-*.dll en el mismo directorio que ffmpeg.exe (p.ej. WinGet) → OK sin FALLA."""
    carpeta_bin = tmp_path / "bin"
    carpeta_bin.mkdir()
    (carpeta_bin / "avcodec-61.dll").touch()
    _mock_ffmpeg_base(monkeypatch, tmp_path)
    monkeypatch.setattr(v.shutil, "which",
                        lambda cmd: str(carpeta_bin / f"{cmd}.exe") if cmd in ("ffmpeg", "ffprobe") else None)
    v.verificar_ffmpeg()
    temas = {tema: estado for estado, tema, _ in v._resultados}
    assert temas.get("FFmpeg para torchcodec") == "OK"
    assert all(estado != "FALLA" for estado, tema, _ in v._resultados if "torchcodec" in tema.lower())


def test_verificar_ffmpeg_dll_en_ruta_readme(monkeypatch, tmp_path):
    """avcodec-*.dll en la ruta del README pero sin .pth → OK + FALLA de .pth."""
    readme_path = tmp_path / "readme_path"
    readme_path.mkdir()
    (readme_path / "avcodec-61.dll").touch()
    _mock_ffmpeg_base(monkeypatch, tmp_path)
    monkeypatch.setattr(v, "DLL_FFMPEG_POR_DEFECTO", readme_path)
    monkeypatch.setattr(v.shutil, "which", lambda cmd: None)
    v.verificar_ffmpeg()
    temas = {tema: estado for estado, tema, _ in v._resultados}
    assert temas.get("FFmpeg para torchcodec") == "OK"
    assert temas.get("FFmpeg para torchcodec (.pth)") == "FALLA"


def test_verificar_ffmpeg_sin_dll(monkeypatch, tmp_path):
    """Sin avcodec-*.dll en ninguna ubicación → FALLA."""
    _mock_ffmpeg_base(monkeypatch, tmp_path)
    monkeypatch.setattr(v.shutil, "which", lambda cmd: None)
    v.verificar_ffmpeg()
    assert any(estado == "FALLA" and "torchcodec" in tema.lower() for estado, tema, _ in v._resultados)