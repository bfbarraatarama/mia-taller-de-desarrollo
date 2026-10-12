# Hito 2 — Dataset preparado y EDA de viabilidad

**Equipo:** Luisa, Bruno, Matías, Felipe · [Canvas](../canvas.md)

**Alcance:** producto en castellano, evaluado por módulo.

**Veredicto: ajustar el alcance.** Hay datos para evaluar cada módulo por
separado. No hay ninguna reunión en castellano con audio, transcripción,
hablantes y minuta: el producto completo se evalúa con reuniones propias.

| Módulo | Fuentes | Idioma |
|---|---|---|
| Transcripción | OpenSLR 61, CORdeBA, Humyn LATAM | Castellano rioplatense |
| Separación de hablantes | AMI, ICSI, VoxConverse, Humyn LATAM | Inglés (no depende del idioma) |
| Minuta | AMI, con sus enlaces de evidencia | Inglés; se traduce al castellano |
| De punta a punta | Reuniones propias | Castellano |

| # | Documento |
|---|---|
| 1 | [Mapa de fuentes](1-mapa-de-fuentes.md) |
| 2 | [EDA de viabilidad](2-eda-de-viabilidad.md) |
| 3 | [Datasheet abreviada](3-datasheet.md) |
| 4 | [Veredicto](4-veredicto.md) |
| | [Niveles](niveles-a-priori.md) · [Muestra](muestra/) · [Notebook](notebooks/eda_viabilidad.ipynb) · [Resumen de una página](resumen-puesta-en-comun.md) |

## Cómo se reproduce

Python 3.12 o posterior, [`uv`](https://docs.astral.sh/uv/) y `ffmpeg`. Desde la raíz del repo:

```bash
uv venv .venv && uv pip install -r hito-2/requirements.txt

# Notebook sobre la muestra del repo (sin red)
.venv/bin/jupyter nbconvert --to notebook --execute --inplace hito-2/notebooks/eda_viabilidad.ipynb

# Opcional: regenerar la muestra desde las fuentes (3,2 GB, ~40 min)
.venv/bin/python -I hito-2/scripts/descargar_fuentes.py
.venv/bin/python -I hito-2/scripts/armar_muestra.py
```

## Estructura

```
hito-2/
├── 1-mapa-de-fuentes.md … 4-veredicto.md
├── niveles-a-priori.md
├── resultados_eda.csv, resultados_leakage.csv   salida del notebook
├── figuras/                                     salida del notebook
├── notebooks/eda_viabilidad.ipynb               una sección por módulo
├── scripts/descargar_fuentes.py, armar_muestra.py
└── muestra/
    ├── slr61/        transcripciones, índice de audio
    ├── cordeba/      índice de grabaciones y turnos
    ├── humyn/        índice de grabaciones y turnos en castellano
    ├── ami/          turnos, participantes, índice de audio,
    │                 minutas y evidencias
    ├── icsi/         turnos, hablantes, índice de audio
    └── voxconverse/  quién habla cuándo
```

**El repo no tiene audio.** Los scripts lo dejan en disco (`.cache/` y
`muestra/**/*.flac`, ignorados por git): 44 clips de OpenSLR 61 y 24
extractos de 30 s de AMI e ICSI. El audio completo de AMI e ICSI se baja con
la URL de cada reunión en `reuniones.csv`.
