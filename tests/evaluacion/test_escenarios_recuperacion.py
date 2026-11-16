"""Issue #15, grupo 3: prueba de recuperación ante un corte forzado (requisito «Prueba de recuperación»)."""

from __future__ import annotations

import sys
import textwrap

from evaluacion.escenarios.recuperacion import medir_corte

CAPTURA_FALSA = textwrap.dedent('''
    """Imita a src.captura.captura: .json «grabando» al empezar y WAV escrito mientras graba."""
    import json, sys, time
    from datetime import datetime
    from pathlib import Path
    import numpy as np
    import soundfile as sf
    carpeta = Path(sys.argv[1]); carpeta.mkdir(parents=True, exist_ok=True)
    nombre = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    wav = sf.SoundFile(carpeta / f"{nombre}.wav", "w", 16000, 1, "PCM_16")
    sf._snd.sf_command(wav._file, 0x1061, sf._ffi.NULL, 1)  # SFC_SET_UPDATE_HEADER_AUTO, como la captura
    (carpeta / f"{nombre}.json").write_text(json.dumps({"archivo": f"{nombre}.wav", "estado": "grabando"}))
    while True:
        wav.write(np.zeros(1600, dtype="int16")); time.sleep(0.1)
''')


def test_corte_forzado(tmp_path):
    script = tmp_path / "captura_falsa.py"
    script.write_text(CAPTURA_FALSA, encoding="utf-8")
    carpeta = tmp_path / "grabaciones"
    r = medir_corte([sys.executable, str(script), str(carpeta)], carpeta, segundos=2.0)
    assert r["grabado_s"] >= 2.0
    assert -0.2 <= r["perdido_s"] < 0.6  # resolución de la medición: sondeo de 50 ms y escrituras de 0,1 s
    assert r["duracion_wav_s"] > 1.4
    assert r["listada_como_interrumpida"] is True
    assert r["wav_valido"] is True
    assert r["cumple_perdida"] is True  # 5 s o menos


def test_sin_grabacion(tmp_path):
    r = medir_corte([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path / "vacia", segundos=0.5,
                    espera_inicio_s=1.0)
    assert r["error"] and r["cumple_perdida"] is False
