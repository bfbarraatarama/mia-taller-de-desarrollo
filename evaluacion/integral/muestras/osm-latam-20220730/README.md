# Reunión externa de evaluación integral: OSM LatAm

- Fuente: [Junta OsmLatAm Julio 2022 Argentina](https://peertube.openstreetmap.fr/videos/watch/e8177007-3a34-4926-abed-b5dbc1700631), 30 de julio de 2022. [Acta](https://wiki.openstreetmap.org/wiki/ES:LatAm/Eventos/20220730_Reuni%C3%B3n_virtual).
- Licencia declarada por el publicador en los metadatos de PeerTube: Public Domain Dedication (id 7). No constituye consentimiento directo obtenido por el equipo.
- Grabación descargada (MP4, 412657265 bytes): SHA-256 `6cab42348f0460b9eda679bdeea820c5da476417280e2b82ac2269685537423e`.
- Fragmento continuo: 00:43:08–00:48:47 sobre el WAV completo extraído, 339 s. Se localizaron los temas y el compromiso mediante una transcripción auxiliar de Whisper `small` (38:00–62:00), anterior a las corridas del baseline; no se utiliza esa transcripción como referencia. Las notas deben contrastarse directamente con la grabación y el acta antes del procesamiento formal.

## Adquisición

Desde la raíz del repositorio, conservar los originales fuera del repositorio. La API puede cambiar sus URL; verificar el hash antes de usar el archivo descargado.

```bash
curl -fsSL 'https://peertube.openstreetmap.fr/api/v1/videos/e8177007-3a34-4926-abed-b5dbc1700631' -o ../osm-latam-20220730.metadata.json
URL=$(python3 - <<'PY'
import json
from pathlib import Path

m = json.loads(Path('../osm-latam-20220730.metadata.json').read_text())
archivos = m.get('files', []) + [a for p in m.get('streamingPlaylists', []) for a in p.get('files', [])]
print(next(a['fileUrl'] for a in archivos if a.get('fileUrl') and a.get('size') == 412657265))
PY
) && curl -fL "$URL" -o ../osm-latam-20220730.original
printf '%s  %s\n' 6cab42348f0460b9eda679bdeea820c5da476417280e2b82ac2269685537423e ../osm-latam-20220730.original | sha256sum -c -
ffmpeg -i ../osm-latam-20220730.original -map 0:a:0 -ac 1 -ar 16000 -c:a pcm_s16le ../osm-latam-20220730.wav
ffmpeg -ss 00:43:08 -i ../osm-latam-20220730.wav -t 00:05:39 -c:a pcm_s16le ../osm-latam-20220730-muestra.wav
```

FFmpeg de referencia: 6.1.1-3ubuntu5. La entrada versionada permite repetir la evaluación sin descargar la grabación completa. Verificar su hash contra `procedencia.json`. La versión de FFmpeg puede cambiar los bytes de los derivados; no sustituir silenciosamente el fragmento congelado.

## Registro de procedencia y entrada

Desde la raíz del repositorio, con los tres archivos de adquisición disponibles en el directorio padre:

```bash
.venv/bin/python - <<'PYREGISTRO'
import json
import shutil
from pathlib import Path
from src.ingesta.audio import FS, sha256, verificar_wav

base = Path('evaluacion/integral/muestras/osm-latam-20220730')
meta = Path('../osm-latam-20220730.metadata.json')
original = Path('../osm-latam-20220730.original')
fragmento = Path('../osm-latam-20220730-muestra.wav')
m = json.loads(meta.read_text(encoding='utf-8'))
assert m['uuid'] == 'e8177007-3a34-4926-abed-b5dbc1700631'
assert m['licence']['id'] == 7 and m['licence']['label'] == 'Public Domain Dedication'
assert original.stat().st_size == 412657265
assert sha256(original) == '6cab42348f0460b9eda679bdeea820c5da476417280e2b82ac2269685537423e'
assert verificar_wav(fragmento) == 339 * FS
assert not (base / 'audio.wav').exists() and not (base / 'procedencia.json').exists()
shutil.copyfile(fragmento, base / 'audio.wav')
datos = {
    'titulo': m['name'], 'url': m['url'],
    'url_metadatos': 'https://peertube.openstreetmap.fr/api/v1/videos/' + m['uuid'],
    'licencia': m['licence']['label'], 'licencia_peertube': m['licence'],
    'evidencia': 'Declaración de licencia del publicador en los metadatos de PeerTube.',
    'seleccion': 'Fragmento continuo localizado con Whisper small y contrastado con el audio y el acta; FFmpeg 6.1.1-3ubuntu5.',
    'sha256_metadatos': sha256(meta), 'sha256_original': sha256(original),
    'sha256_fragmento': sha256(base / 'audio.wav'),
    'inicio_s': 2588, 'fin_s': 2927,
}
(base / 'procedencia.json').write_text(json.dumps(datos, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(datos, ensure_ascii=False, indent=2))
PYREGISTRO
```

El integrante que no opera las corridas escribe `referencia.md` con las marcas relativas al fragmento, antes de congelarlo. Verificar la documentación, la procedencia, las notas y el audio antes de versionar; no versionar la transcripción auxiliar ni la grabación completa. La selección está asistida por un ASR diferente del baseline, no es una muestra aleatoria ni un corpus representativo.

## Corridas formales

Desde la raíz del repositorio, en el hardware de referencia, usar el [protocolo integral](../../README.md), con:

```bash
MUESTRA=evaluacion/integral/muestras/osm-latam-20220730
SESION=resultados/evaluacion-integral/baseline
.venv/bin/python -m evaluacion.integral.evaluar preparar "$SESION" \
    --audio "$MUESTRA/audio.wav" --notas "$MUESTRA/referencia.md" \
    --autor 'NOMBRE REAL DEL AUTOR DE LAS NOTAS' --tipo formal \
    --equipo 'Máquina de Matías: RTX 3050 Laptop, 6 GB VRAM, 31 GB RAM' \
    --procedencia "$MUESTRA/procedencia.json"
```

Sustituir el autor por quien efectivamente elaboró las notas. La identificación de hablantes se apoya en la escucha y, cuando haga falta, en los nombres visibles en la grabación original, sin consultar las notas de calidad para decidir qué nombres introducir. Ejecutar las cinco corridas y generar el reporte según el protocolo general. El archivo de referencia no se suministra al modelo.
