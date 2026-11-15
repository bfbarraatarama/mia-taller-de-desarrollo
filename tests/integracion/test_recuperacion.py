"""El reconocedor de cortes no inventa audio ni interpreta reportes de otras sesiones."""
import json
import wave
from pathlib import Path

from src.captura.recuperacion import grabaciones_interrumpidas


def test_solo_grabaciones_interrumpidas_legibles(tmp_path):
    for nombre, estado in [('a', 'grabando (si queda así, la grabación se interrumpió)'),
                           ('b', 'terminada'), ('c', 'grabando')]:
        (tmp_path / f'{nombre}.json').write_text(json.dumps({'archivo': f'{nombre}.wav', 'estado': estado}))
    for nombre in ('a', 'b'):
        with wave.open(str(tmp_path / f'{nombre}.wav'), 'wb') as f:
            f.setparams((1, 2, 16000, 0, 'NONE', 'none'))
            f.writeframes(b'\x00\x00' * 16000)
    assert [p.name for p in grabaciones_interrumpidas(tmp_path)] == ['a.wav']


def test_metadata_fuera_del_directorio_se_ignora(tmp_path):
    (tmp_path / 'a.json').write_text(json.dumps({'archivo': '../otro.wav', 'estado': 'grabando'}))
    assert grabaciones_interrumpidas(tmp_path) == []


def _grabacion(carpeta, muestras=16000):
    audio = carpeta / 'corte.wav'
    reporte = audio.with_suffix('.json')
    with wave.open(str(audio), 'wb') as f:
        f.setparams((1, 2, 16000, 0, 'NONE', 'none'))
        f.writeframes(b'\x00\x00' * muestras)
    reporte.write_text(json.dumps({'archivo': audio.name, 'estado': 'grabando'}))
    return audio, reporte


def test_aceptacion_persistente_e_idempotente(tmp_path):
    from src.captura.recuperacion import aceptar_recuperacion, consultar_grabaciones_interrumpidas
    import subprocess
    import sys
    audio, reporte = _grabacion(tmp_path)
    originales = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (audio, reporte)}
    g, = consultar_grabaciones_interrumpidas(tmp_path)
    assert consultar_grabaciones_interrumpidas(tmp_path) == [g]  # no aceptar equivale a no marcar
    assert not g.marca.exists()
    assert aceptar_recuperacion(g) == audio
    marca = (g.marca.read_bytes(), g.marca.stat().st_mtime_ns)
    assert aceptar_recuperacion(g) == audio
    assert (g.marca.read_bytes(), g.marca.stat().st_mtime_ns) == marca
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (audio, reporte)} == originales
    assert consultar_grabaciones_interrumpidas(tmp_path) == []
    resultado = subprocess.check_output([sys.executable, '-c',
        'import sys; from src.captura.recuperacion import grabaciones_interrumpidas; '
        'print(grabaciones_interrumpidas(sys.argv[1]))', str(tmp_path)], text=True)
    assert resultado.strip() == '[]'


def test_cambio_del_audio_o_reporte_requiere_nueva_aceptacion(tmp_path):
    import pytest
    from src.captura.recuperacion import aceptar_recuperacion, consultar_grabaciones_interrumpidas
    audio, reporte = _grabacion(tmp_path)
    g, = consultar_grabaciones_interrumpidas(tmp_path)
    aceptar_recuperacion(g)
    _grabacion(tmp_path, 24000)
    nuevo, = consultar_grabaciones_interrumpidas(tmp_path)
    assert nuevo != g
    with pytest.raises(ValueError, match='cambiaron'):
        aceptar_recuperacion(g)
    aceptar_recuperacion(nuevo)
    reporte.write_text(json.dumps({'archivo': audio.name, 'estado': 'grabando', 'otro': 1}))
    assert consultar_grabaciones_interrumpidas(tmp_path)
    with pytest.raises(ValueError, match='cambiaron'):
        aceptar_recuperacion(nuevo)


def test_marca_corrupta_no_oculta_grabacion(tmp_path):
    from src.captura.recuperacion import aceptar_recuperacion, consultar_grabaciones_interrumpidas
    _grabacion(tmp_path)
    g, = consultar_grabaciones_interrumpidas(tmp_path)
    aceptar_recuperacion(g)
    g.marca.write_text('{')
    assert consultar_grabaciones_interrumpidas(tmp_path) == [g]
    aceptar_recuperacion(g)
    assert consultar_grabaciones_interrumpidas(tmp_path) == []


def test_wav_corrupto_o_sustituido_por_enlace_no_se_ofrece(tmp_path):
    import pytest
    audio, _ = _grabacion(tmp_path)
    audio.write_bytes(b'no wav')
    assert grabaciones_interrumpidas(tmp_path) == []
    audio, _ = _grabacion(tmp_path)
    otro = tmp_path / 'otro.wav'
    audio.rename(otro)
    try:
        audio.symlink_to(otro)
    except OSError:
        pytest.skip('el entorno no permite enlaces simbólicos')
    assert grabaciones_interrumpidas(tmp_path) == []


def test_omision_persistente_sin_aceptacion_ni_perdida(tmp_path):
    import subprocess
    import sys
    from src.captura.recuperacion import consultar_grabaciones_interrumpidas, omitir_aviso_recuperacion

    audio, reporte = _grabacion(tmp_path)
    originales = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (audio, reporte)}
    g, = consultar_grabaciones_interrumpidas(tmp_path)
    assert not g.marca.exists()
    assert omitir_aviso_recuperacion(g) == audio
    marca = (g.marca.read_bytes(), g.marca.stat().st_mtime_ns)
    assert json.loads(marca[0])['decision'] == 'omitida'
    assert omitir_aviso_recuperacion(g) == audio
    assert (g.marca.read_bytes(), g.marca.stat().st_mtime_ns) == marca
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (audio, reporte)} == originales
    assert consultar_grabaciones_interrumpidas(tmp_path) == []
    resultado = subprocess.check_output([sys.executable, '-c',
        'import sys; from src.captura.recuperacion import grabaciones_interrumpidas; '
        'print(grabaciones_interrumpidas(sys.argv[1]))', str(tmp_path)], text=True)
    assert resultado.strip() == '[]'
    otro = tmp_path / 'otro.wav'
    otro.write_bytes(audio.read_bytes())
    otro.with_suffix('.json').write_text(json.dumps({'archivo': otro.name, 'estado': 'grabando'}))
    assert grabaciones_interrumpidas(tmp_path) == [otro]


def test_omision_no_oculta_audio_o_reporte_modificado(tmp_path):
    import pytest
    from src.captura.recuperacion import consultar_grabaciones_interrumpidas, omitir_aviso_recuperacion

    audio, reporte = _grabacion(tmp_path)
    g, = consultar_grabaciones_interrumpidas(tmp_path)
    omitir_aviso_recuperacion(g)
    _grabacion(tmp_path, 24000)
    nuevo, = consultar_grabaciones_interrumpidas(tmp_path)
    assert nuevo != g
    with pytest.raises(ValueError, match='cambiaron'):
        omitir_aviso_recuperacion(g)
    omitir_aviso_recuperacion(nuevo)
    reporte.write_text(json.dumps({'archivo': audio.name, 'estado': 'grabando', 'otro': 1}))
    assert consultar_grabaciones_interrumpidas(tmp_path)
    with pytest.raises(ValueError, match='cambiaron'):
        omitir_aviso_recuperacion(nuevo)


def test_compatibilidad_marca_aceptacion_anterior(tmp_path):
    from src.captura.recuperacion import aceptar_recuperacion, consultar_grabaciones_interrumpidas

    audio, _ = _grabacion(tmp_path)
    g, = consultar_grabaciones_interrumpidas(tmp_path)
    g.marca.write_text(json.dumps(g.identidad()))
    marca = (g.marca.read_bytes(), g.marca.stat().st_mtime_ns)
    assert consultar_grabaciones_interrumpidas(tmp_path) == []
    assert aceptar_recuperacion(g) == audio
    assert (g.marca.read_bytes(), g.marca.stat().st_mtime_ns) == marca


def test_decision_desconocida_no_oculta_grabacion(tmp_path):
    from src.captura.recuperacion import consultar_grabaciones_interrumpidas, omitir_aviso_recuperacion

    _grabacion(tmp_path)
    g, = consultar_grabaciones_interrumpidas(tmp_path)
    omitir_aviso_recuperacion(g)
    g.marca.write_text(json.dumps({**g.identidad(), 'version': 2, 'decision': 'desconocida'}))
    assert consultar_grabaciones_interrumpidas(tmp_path) == [g]
