# Licencias y atribución de los resultados STT

`asr/<ID>.json` contiene la transcripción que Whisper produjo a partir del audio de cada grabación. Es un derivado de ese audio y hereda la licencia de su fuente. El audio, las referencias de texto y los originales **no** se publican aquí.

| Archivos | Fuente | Licencia | Cita |
|---|---|---|---|
| `asr/COR-*.json` | CORdeBA — https://huggingface.co/datasets/marianbasti/cordeba | **CC BY-NC-SA 4.0**: atribución, **uso no comercial** y compartir bajo la misma licencia | Caldiz, A., Palmieri, M., Gnecco, V., Moyano, S., Ruiz Arcodia, L., et al. (2024). *CordeBA: Corpus de Buenos Aires.* Universidad Nacional de La Plata |
| `asr/PER-*.json`, `asr/VEN-*.json` | Humyn Labs, *LATAM High-Fidelity ASR* — https://huggingface.co/datasets/humyn-labs/LATAM-High-Fidelity-ASR | CC BY 4.0: atribución | Humyn Labs (2026) |
| `wer.json` | Cifras agregadas calculadas con las referencias de ambas fuentes; no contiene texto | Se publica con la atribución de las dos fuentes. Los resultados de CORdeBA quedan bajo CC BY-NC-SA 4.0 | — |

Cambios respecto de las fuentes: el audio se transcribió con Whisper `medium` (idioma `es`) y el resultado se guarda como JSON de segmentos con tiempos y palabras.

Las mismas fuentes figuran en [`hito-2/muestra/LICENCIAS.md`](../../../hito-2/muestra/LICENCIAS.md). `../manifiesto.json` solo guarda hashes y metadatos, sin texto de las fuentes. Mientras el repositorio incluya los derivados de CORdeBA, no debe usarse con fines comerciales.
