# Licencias y atribución de la muestra

| Carpeta | Fuente | Licencia | Cita |
|---|---|---|---|
| `slr61/` | OpenSLR 61 — https://www.openslr.org/61/ | **CC BY-SA 4.0** | Guevara-Rukoz, A. et al. (2020). *Crowdsourcing Latin American Spanish for Low-Resource Text-to-Speech.* LREC 2020. Copyright 2018, 2019 Google, Inc. |
| `cordeba/` | CORdeBA — https://huggingface.co/datasets/marianbasti/cordeba | **CC BY-NC-SA 4.0** (no comercial) | Caldiz, A., Palmieri, M., Gnecco, V., Moyano, S., Ruiz Arcodia, L., et al. (2024). *CordeBA: Corpus de Buenos Aires.* Universidad Nacional de La Plata |
| `humyn/` | Humyn Labs, *LATAM High-Fidelity ASR* — https://huggingface.co/datasets/humyn-labs/LATAM-High-Fidelity-ASR | CC BY 4.0 | Humyn Labs (2026) |
| `ami/` | AMI Meeting Corpus, anotaciones 1.6.2 y audio — https://groups.inf.ed.ac.uk/ami/corpus/ | CC BY 4.0 | Carletta, J. et al. (2005). *The AMI Meeting Corpus: A Pre-announcement.* MLMI 2005 |
| `icsi/` | ICSI Meeting Corpus, anotaciones NXT 1.0 y audio — https://groups.inf.ed.ac.uk/ami/icsi/ | CC BY 4.0 | Janin, A. et al. (2003). *The ICSI Meeting Corpus.* ICASSP 2003 |
| `voxconverse/` | VoxConverse — https://github.com/joonson/voxconverse | CC BY 4.0 | Chung, J. S. et al. (2020). *Spot the conversation: speaker diarisation in the wild.* Interspeech 2020 |
| `normalizado/` — Common Voice | Mozilla Common Voice 26 Rioplatense, vía Mozilla Data Collective | CC0 declarado en el mapa histórico; además se requiere aceptar términos MDC | Se conserva procedencia de TAR, licencia y condiciones aceptadas; no redistribuir el TAR desde este repositorio |
| `normalizado/` — CALLHOME Spanish | TalkBank, distribución procesada `talkbank/callhome` | Acceso restringido; condiciones de uso aceptadas por usuario autorizado | Mantener Parquet y audio fuera del repositorio; no inferir permiso de redistribución |
| `uba_games_figshare/` | Figshare, DOI `10.6084/m9.figshare.22647313.v2` (SIS) | CC BY 4.0 declarada en `fuentes.toml` | Sólo se adquirió la distribución Figshare v2, no los once archivos de CONICET |

Cambios respecto de las fuentes: las anotaciones se pasaron a tablas. La muestra distribuible no incluye audio original; tampoco incluye originales de acceso restringido. Los resultados estructurales se conservan con sus hashes y las rutas locales se generan al ejecutar los scripts.
`ami/reuniones.csv` incluye la partición de
[pyannote/AMI-diarization-setup](https://github.com/pyannote/AMI-diarization-setup).

`cordeba/` no se puede usar con fines comerciales. `slr61/` y `cordeba/`
obligan a compartir con la misma licencia lo que se derive de ellas.
