"""Tarea 5.2: inferencia sobre la muestra verificada (requisito «Inferencia sobre la muestra verificada»)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluacion.modular.config import cargar_config
from evaluacion.modular.inferencia import ARCHIVOS_ESPERADOS, MuestraAlterada, inferir
from tests.evaluacion.test_contratos import armar

RAIZ = Path(__file__).resolve().parents[2]


class EjecutorFalso:
    """Registra cada comando y escribe los archivos que dejaría el módulo real."""

    def __init__(self):
        self.comandos = []

    def __call__(self, comando: list[str], carpeta: Path, fuente: str) -> int:
        self.comandos.append(comando)
        carpeta.mkdir(parents=True, exist_ok=True)
        for nombre in ARCHIVOS_ESPERADOS[fuente]:
            (carpeta / nombre).write_text(f'{{"archivo": "{nombre}"}}', encoding="utf-8")
        if fuente == "figshare":
            (carpeta / "workflow.json").write_text('{"estado": "completado"}', encoding="utf-8")
        return 0


def config_en(tmp_path):
    manifiesto, datos, _ = armar(tmp_path)
    inferencia = tmp_path / "inferencia-nueva"
    ruta = tmp_path / "config.toml"
    ruta.write_text(
        (RAIZ / "evaluacion/modular/config.toml").read_text(encoding="utf-8")
        .replace('salida = "evaluacion/modular/datos"', f'salida = "{datos}"')
        .replace('manifiesto = "evaluacion/modular/muestra.manifest.json"', f'manifiesto = "{manifiesto}"')
        .replace('inferencia = "evaluacion/modular/inferencia"', f'inferencia = "{inferencia}"'),
        encoding="utf-8")
    return cargar_config(ruta)


def test_comandos_por_fuente(tmp_path):
    config, falso = config_en(tmp_path), EjecutorFalso()
    resumen = inferir(config, ejecutar=falso)
    assert resumen == {"ejecutados": 3, "reutilizados": 0}
    por_modulo = {c[2]: c for c in falso.comandos}
    assert set(por_modulo) == {"src.stt", "src.pipeline", "src.minutas"}
    pipeline = por_modulo["src.pipeline"]
    assert pipeline[3] == "ejecutar" and pipeline[4].endswith("figshare/S22/01/audio.wav")
    assert pipeline[pipeline.index("--modelo") + 1] == "qwen2.5-7b"
    assert pipeline[pipeline.index("--secciones") + 1] == "resumen,temas,decisiones,problemas,acciones"
    assert por_modulo["src.stt"][por_modulo["src.stt"].index("--model") + 1] == "medium"
    assert por_modulo["src.minutas"][por_modulo["src.minutas"].index("--entrada") + 1].endswith(
        "ami/r1/transcription.json")
    registro = json.loads((config.inferencia / "figshare-S22-01" / "inferencia.json").read_text(encoding="utf-8"))
    assert registro["codigo"] == 0 and registro["configuracion"]["modelo_stt"] == "medium"
    assert str(tmp_path) not in json.dumps(registro)  # sin rutas de la máquina


def test_muestra_alterada(tmp_path):
    config, falso = config_en(tmp_path), EjecutorFalso()
    (config.salida / "clips/clip-c1/audio.wav").write_bytes(b"otro audio")
    try:
        inferir(config, ejecutar=falso)
    except MuestraAlterada as e:
        assert "clips/clip-c1/audio.wav" in str(e)
    else:
        raise AssertionError("debía fallar")
    assert falso.comandos == []  # no se cargó ningún modelo


def test_reutilizacion(tmp_path):
    config, falso = config_en(tmp_path), EjecutorFalso()
    inferir(config, ejecutar=falso)
    salidas = {p: p.stat().st_mtime_ns for p in config.inferencia.rglob("*") if p.is_file()}
    segundo = EjecutorFalso()
    assert inferir(config, ejecutar=segundo) == {"ejecutados": 0, "reutilizados": 3}
    assert segundo.comandos == []
    assert {p: p.stat().st_mtime_ns for p in config.inferencia.rglob("*") if p.is_file()} == salidas


def test_rehacer_y_salida_incompleta(tmp_path):
    config = config_en(tmp_path)
    inferir(config, ejecutar=EjecutorFalso())
    (config.inferencia / "clip-c1" / "asr.json").unlink()  # quedó incompleta: se vuelve a correr
    otro = EjecutorFalso()
    assert inferir(config, ejecutar=otro) == {"ejecutados": 1, "reutilizados": 2}
    assert inferir(config, ejecutar=EjecutorFalso(), rehacer=True) == {"ejecutados": 3, "reutilizados": 0}


def test_fallo_de_un_modulo_no_se_reutiliza(tmp_path):
    config = config_en(tmp_path)

    def falla(comando, carpeta, fuente):
        return 1

    resumen = inferir(config, ejecutar=falla)
    assert resumen["ejecutados"] == 3 and resumen["fallidos"] == ["ami-r1", "clip-c1", "figshare-S22-01"]
    assert inferir(config, ejecutar=EjecutorFalso()) == {"ejecutados": 3, "reutilizados": 0}


def test_cambio_de_codigo_vuelve_a_inferir(tmp_path, monkeypatch):
    config = config_en(tmp_path)
    inferir(config, ejecutar=EjecutorFalso())
    original = __import__("evaluacion.modular.inferencia", fromlist=["huella_codigo"]).huella_codigo
    # Cambia solo el código de las minutas: se rehacen AMI y Figshare (usan la Etapa 5), no el clip.
    monkeypatch.setattr("evaluacion.modular.inferencia.huella_codigo",
                        lambda tipo: original(tipo) + ("x" if tipo in ("ami", "figshare") else ""))
    otro = EjecutorFalso()
    assert inferir(config, ejecutar=otro) == {"ejecutados": 2, "reutilizados": 1}
    assert {c[2] for c in otro.comandos} == {"src.pipeline", "src.minutas"}


def test_huella_de_codigo_por_tipo():
    from evaluacion.modular.inferencia import huella_codigo
    assert len({huella_codigo(t) for t in ("clip", "figshare", "ami")}) == 3
    assert huella_codigo("clip") == huella_codigo("clip")


def test_salida_alterada_no_se_reutiliza(tmp_path):
    config = config_en(tmp_path)
    inferir(config, ejecutar=EjecutorFalso())
    (config.inferencia / "clip-c1" / "asr.json").write_text('{"cambiado": true}', encoding="utf-8")
    otro = EjecutorFalso()
    assert inferir(config, ejecutar=otro) == {"ejecutados": 1, "reutilizados": 2}
    assert [c[2] for c in otro.comandos] == ["src.stt"]


def test_pipeline_no_completado_no_se_reutiliza(tmp_path):
    config = config_en(tmp_path)
    inferir(config, ejecutar=EjecutorFalso())
    (config.inferencia / "figshare-S22-01" / "workflow.json").write_text('{"estado": "cancelado"}', encoding="utf-8")
    assert inferir(config, ejecutar=EjecutorFalso()) == {"ejecutados": 1, "reutilizados": 2}
