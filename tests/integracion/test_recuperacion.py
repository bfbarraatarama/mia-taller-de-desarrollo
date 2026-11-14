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
