# Evaluación de la Etapa 3 (STT): resultados

WER de Whisper `medium` (idioma forzado a `es`, CPU) sobre 7 grabaciones de conversaciones espontáneas con varios hablantes. Los resultados crudos están en [`resultados/wer.json`](resultados/wer.json); la selección y los hashes, en [`manifiesto.json`](manifiesto.json). Procedimiento, normalización y exclusiones: [README](README.md).

## Datos

Son los únicos dos datasets descargados que reúnen español, habla espontánea, varios hablantes y transcripción de referencia:

| Dataset | Grabaciones | Hablantes por grabación | Tiempos en la referencia |
|---|---|---|---|
| Humyn LATAM | 4 (Perú ×2, Venezuela ×2) | 2 | Sí |
| CORdeBA (Buenos Aires) | 3 de 17 elegibles, sorteadas con semilla | 3 o 4 | **No** |

CALLHOME Spanish queda para una próxima evaluación.

Humyn solo transcribe entre 10,5 y 11,5 de los ~15 minutos de audio. Por eso el ASR se recorta a los segmentos que empiezan antes del último tiempo de la referencia. CORdeBA no tiene tiempos, así que se compara contra el ASR completo; si la referencia no cubriera todo el audio, el WER saldría pesimista (véase la discusión abajo).

## Resultados por grabación

| ID | Dataset | Duración | Audio evaluado | Palabras ref. | WER | Sust. | Elim. | Ins. |
|---|---|---|---|---|---|---|---|---|
| PER-1 | Humyn · Perú | 15:17 | 11:00 | 1.776 | **12,3 %** | 57 | 150 | 12 |
| PER-2 | Humyn · Perú | 15:24 | 10:30 | 1.778 | **17,3 %** | 66 | 213 | 28 |
| VEN-1 | Humyn · Venezuela | 15:41 | 11:00 | 1.552 | **21,7 %** | 84 | 239 | 14 |
| VEN-2 | Humyn · Venezuela | 15:00 | 11:30 | 1.559 | **27,8 %** | 191 | 221 | 22 |
| COR-0010 | CORdeBA | 17:26 | 17:26 | 2.881 | **45,2 %** | 728 | 446 | 128 |
| COR-0014 | CORdeBA | 15:11 | 15:11 | 2.283 | **47,0 %** | 454 | 544 | 75 |
| COR-0015 | CORdeBA | 15:11 | 15:11 | 2.388 | **35,8 %** | 480 | 246 | 129 |

## WER general

| Medida | WER |
|---|---|
| Promedio de las 7 grabaciones (el de `wer.json`) | **29,6 %** |
| Ponderado por palabras (14.217 palabras de referencia) | **31,8 %** |

Descomposición del error ponderado: 14,5 % sustituciones, 14,5 % eliminaciones y 2,9 % inserciones.

## Por dataset

| Dataset | Grabaciones | WER promedio | WER ponderado | Sust. | Elim. | Ins. |
|---|---|---|---|---|---|---|
| Humyn | 4 | 19,8 % | 19,5 % | 6,0 % | 12,3 % | 1,1 % |
| CORdeBA | 3 | 42,7 % | 42,8 % | 22,0 % | 16,4 % | 4,4 % |

(Las tres últimas columnas son porcentajes de las palabras de referencia.)

## Por país (dialecto)

Todo es español; la variable disponible es el origen de los hablantes.

| Origen | Grabaciones | WER ponderado |
|---|---|---|
| Perú | 2 | 14,8 % |
| Venezuela | 2 | 24,8 % |
| Argentina (CORdeBA) | 3 | 42,8 % |

## Por longitud de audio

Todas las grabaciones duran entre 15 y 17,5 minutos, así que no hay un rango real de duraciones que comparar. Dentro de cada dataset no se ve tendencia: en Humyn, 10:30 → 17,3 %, 11:00 → 12,3 % y 21,7 %, 11:30 → 27,8 %; en CORdeBA, 15:11 → 47,0 % y 35,8 %, 17:26 → 45,2 %. La diferencia entre grabaciones la explican el hablante y el tipo de transcripción, no el largo. La pregunta queda abierta hasta evaluar audios de otras duraciones.

## Otras dimensiones

**Tipo de error.** Es la dimensión que más explica los datos:
- En Humyn dominan las eliminaciones (12,3 %), y las sustituciones son bajas (6,0 %).
- En CORdeBA las sustituciones (22,0 %) son casi cuatro veces las de Humyn, y también hay más eliminaciones e inserciones.

**Cantidad de hablantes.** Con dos hablantes (Humyn), 19,5 %; con tres (COR-0014 y COR-0015), 41,3 %; con cuatro (COR-0010), 45,2 %. Va en la dirección esperable (más hablantes, más solapamiento), pero está totalmente confundida con el dataset, así que no es una conclusión.

## Conclusiones

1. **El WER general es 29,6 % (31,8 % ponderado), pero mezcla dos regímenes distintos:** ~20 % en Humyn y ~43 % en CORdeBA. El promedio global no representa a ninguno, y con 7 grabaciones es solo orientativo.
2. **La brecha entre datasets se explica sobre todo por cómo se transcribió la referencia, no por una peor transcripción de Whisper.** CORdeBA escribe lo que se oye ("hacemo", "estamo", "muuy", "caarceles") e incluye muletillas ("eee", "ehh", "emm"). Whisper escribe la forma estándar, y cada una cuenta como sustitución. Esto coincide con las sustituciones, 22,0 % frente a 6,0 %. También influyen el solapamiento y los números (Whisper escribe cifras y la referencia, palabras).
3. **La falta de tiempos en CORdeBA no parece ser la causa principal.** Si la referencia no cubriera todo el audio, habría muchas inserciones, como pasó con Humyn sin recortar, donde fueron 674 en PER-1. En CORdeBA son 4,4 % y las palabras por minuto de la referencia (150–165) son similares a las de Humyn (136–169). El sesgo pesimista existe pero es secundario.
4. **Dentro de Humyn, Perú (14,8 %) rinde mejor que Venezuela (24,8 %).** VEN-2 tiene muchas sustituciones (191, frente a 57–84 en las demás). No se investigó la causa; con 2 grabaciones por país no se puede atribuir al dialecto.
5. **Las eliminaciones son el error más frecuente en Humyn,** en parte por muletillas ("eh", "mmm") presentes en la referencia y ausentes en el ASR (visto en PER-1 y PER-2).

## Comparación con la evaluación modular

La [evaluación modular](../modular/README.md) (#13) también publica un WER de Whisper `medium`: 26,9 % en total (27,0 % solo en Figshare; [`metricas_stt.json`](../modular/resultados/metricas_stt.json)). **No es comparable** con el 29,6 % de acá:

| | STT (este documento) | Modular |
|---|---|---|
| Datos | Humyn y CORdeBA: conversaciones de ~15 min | 74 tareas de UBA Games (Figshare, dos personas jugando, 13.125 palabras) y 5 clips leídos de OpenSLR y Common Voice |
| Normalización | Minúsculas, **sin acentos**, signos y símbolos eliminados | Minúsculas, signos y símbolos reemplazados por espacios, **acentos conservados** |
| Agregado | Promedio simple de las grabaciones (31,8 % ponderado por palabras) | Suma de errores sobre suma de palabras |

El cálculo del WER es el mismo (la alineación de `evaluacion/modular/metricas_stt.py`); cambian los datos y la normalización. Quitar los acentos hace que "sí" y "si" coincidan, lo que favorece a este documento.

## Licencias

Los `asr/COR-*.json` son derivados de CORdeBA (CC BY-NC-SA 4.0, solo uso no comercial). Atribución y condiciones por archivo: [`resultados/LICENCIAS.md`](resultados/LICENCIAS.md).

## Limitaciones

- Muestra pequeña (7 grabaciones, 4 de un dataset, 3 de otro); no se calcularon intervalos de confianza.
- No se normalizan muletillas, números ni la ortografía fonética de CORdeBA; probablemente una normalización más agresiva acercaría los dos datasets.
- Las comparaciones por país, cantidad de hablantes y longitud están confundidas con el dataset y la grabación.
- Referencias de Humyn recortadas a 10,5–11,5 min; las de CORdeBA no.
- Los WER son de una única corrida de Whisper `medium` en CPU.
