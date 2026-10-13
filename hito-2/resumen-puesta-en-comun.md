# Hito 2 — Síntesis para la puesta en común

**Equipo:** Luisa, Bruno, Matías y Felipe · **Alcance:** sistema de transcripción, separación de hablantes y minutas de reuniones en castellano.

## Pregunta y método

**¿Existen datos reales y utilizables para evaluar el producto?** Se adquirieron y verificaron fuentes por módulo, se fijaron 25 niveles a priori y se analizaron volumen, completitud, corrección, vigencia, representatividad, confiabilidad y cinco formas de *leakage*. Los cuatro entregables y los comandos para reproducirlos están en el [README del Hito 2](README.md).

La muestra integra audio y transcripciones rioplatenses (OpenSLR 61, CORdeBA, Common Voice y Humyn), referencias temporales de hablantes (AMI, ICSI, VoxConverse, CALLHOME y Figshare) y minutas con enlaces a evidencia (AMI, en inglés). Las nuevas cinco tablas normalizadas se verificaron por hashes y contrato estructural; los originales restringidos no se versionan.

## Evidencia principal

| Módulo | Resultado y límite |
|---|---|
| Transcripción | 15,0 h y 44 hablantes en las fuentes históricas rioplatenses; Common Voice añade 10.393 clips de lectura. Cumple C5: **97,5 %** de clips con edad, género y acento; no permite aún decidir R2 por hablante. |
| Separación de hablantes | Fuentes históricas: 700 sesiones, 236 h. Figshare suma **nueve sesiones**, no 219; CALLHOME aporta 140 registros, no 140 sesiones verificadas. |
| Aptitud acústica | **105/106** archivos seleccionados se decodificaron; la muestra mezcla originales y derivados, por lo que esta tasa no se extrapola. En CALLHOME, **2/15** registros muestreados tienen anotaciones muy posteriores al final del audio. |
| Minuta | AMI aporta 105 reuniones con resumen, decisiones y acciones enlazadas; son en inglés y predominantemente actuadas. |
| Integral | **Cero** reuniones disponibles en castellano con audio, transcripción, hablantes temporizados y minuta simultáneamente. |

**Balance de los 25 niveles:** 11 cumplen, siete no, tres cumplen parcialmente y cuatro quedan sin decidir (G1, R2, F3 y M3). En *leakage*, no se detectaron colaboradores identificados compartidos entre los splits originales de Common Voice, pero la exposición previa a preentrenamiento no pudo excluirse. La partición de futuros conjuntos debe respetar colaboradores, series y sesiones; CALLHOME carece de grupos independientes verificables.

## Veredicto y trabajo futuro

**Ajustar el alcance y continuar por módulo.** No se puede sostener todavía la evaluación integral en castellano. Se requiere un conjunto propio consentido de al menos diez reuniones con referencias completas; además, auditar temporalmente CALLHOME, establecer las reglas de puntuación, validar referencias textuales y calibrar el juez de minutas. La ausencia de una referencia conjunta es la principal limitación, no una razón para atribuir rendimiento a modelos que todavía no se evaluaron.

**Para el docente:** consultar [`1-mapa-de-fuentes.md`](1-mapa-de-fuentes.md), [`2-eda-de-viabilidad.md`](2-eda-de-viabilidad.md), [`3-datasheet.md`](3-datasheet.md) y [`4-veredicto.md`](4-veredicto.md). Las mediciones y limitaciones están en [`notebooks/eda_viabilidad.ipynb`](notebooks/eda_viabilidad.ipynb); el procedimiento completo y sus restricciones de acceso se detallan en [`README.md`](README.md).
