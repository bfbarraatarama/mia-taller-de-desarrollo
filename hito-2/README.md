# Hito 2 — Dataset preparado y EDA de viabilidad

**Equipo:** Luisa, Bruno, Matías, Felipe · [Canvas](../canvas.md)

**Alcance:** reuniones en inglés; transcribir y separar hablantes.

**Veredicto: ajustar el alcance.** Hay 171,6 h de reuniones con audio,
transcripción y hablantes (AMI e ICSI). Todo es presencial y de 2001–2005: la
videollamada se mide aparte, con reuniones propias.

| # | Documento |
|---|---|
| 1 | [Mapa de fuentes](1-mapa-de-fuentes.md) |
| 2 | [EDA de viabilidad](2-eda-de-viabilidad.md) |
| 3 | [Datasheet abreviada](3-datasheet.md) |
| 4 | [Veredicto](4-veredicto.md) |
| | [Niveles](niveles-a-priori.md) · [Muestra](muestra/) · [Notebook](notebooks/eda_viabilidad.ipynb) · [Resumen de una página](resumen-puesta-en-comun.md) |

## Cómo se reproduce

Python 3.12 o posterior y [`uv`](https://docs.astral.sh/uv/). Desde la raíz del repo:

```bash
uv venv .venv && uv pip install -r hito-2/requirements.txt

# Notebook sobre la muestra del repo (sin red)
.venv/bin/jupyter nbconvert --to notebook --execute --inplace hito-2/notebooks/eda_viabilidad.ipynb

# Opcional: regenerar la muestra desde las fuentes (100 MB, ~10 min)
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
├── notebooks/eda_viabilidad.ipynb
├── scripts/descargar_fuentes.py, armar_muestra.py
└── muestra/                                     18 MB
    ├── ami/          171 reuniones: turnos, participantes, índice de audio, 16 extractos;
    │                 minutas de referencia de 142 (resumen, decisiones, acciones, problemas)
    ├── icsi/         75 reuniones: ídem, 8 extractos
    └── voxconverse/  448 sesiones: quién habla cuándo
```

El audio completo (26,1 GB) no está en el repo: cada reunión tiene su URL en
`reuniones.csv`.
