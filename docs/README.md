# Documentación técnica de la PoC

La [definición del Hito 3](../hito-3/definicion-de-la-poc.md) es la fuente de alcance y criterios de aceptación. Esta documentación reúne el diseño de la implementación integrada y sus decisiones posteriores. El [README raíz](../README.md) es el punto de entrada para instalación, ejecución y pruebas generales.

## Diseño transversal

- [Arquitectura y decisiones de integración](arquitectura.md): responsabilidades, alternativas y fundamentos de las decisiones transversales.
- [Orquestación de reuniones](orquestacion.md): checkpoints, vigencia, exclusión, recuperación de fuentes y medición.
- [Continuidad y confidencialidad](continuidad-y-confidencialidad.md): reapertura, captura interrumpida y autorización de transferencias.
- [Interfaz y presentación de resultados](interfaz-y-presentacion.md): distribución, temas, visores y agrupación.
- [Temporalidad de la transcripción](temporalidad-transcripcion.md): cuantización, integridad textual y tratamiento de la incertidumbre.

## Guías por componente

| Componente | Guía y decisiones específicas | Evaluación o registro de desarrollo |
|---|---|---|
| Captura e ingesta | [Captura](captura/README.md), [arquitectura](arquitectura.md#señal-de-entrada-y-asociación) | [Notas y mediciones originales](captura/NOTAS-TECNICAS.md) |
| Diarización | [Diarización](diarizacion/README.md) | [Evaluación y resultados](../evaluacion/diarizacion/README.md), [OpenSpec](diarizacion/openspec/changes/etapa-2-diarizacion/) |
| STT | [Transcripción automática](stt/README.md) | [Ejemplo y análisis](stt/README.md#ejemplo-y-pruebas) |
| Asociación | [Asociación y etiquetado](asociacion/README.md) | [Evaluación](../evaluacion/asociacion/README.md), [OpenSpec](asociacion/openspec/changes/etapa-4-asociacion-etiquetado/) |
| Minutas | [Generación](minutas/README.md), [consolidación de reuniones extensas](minutas/consolidacion-de-minutas.md) | [Validación de integración](validacion-integracion.md) |

## Evidencia y alcance de la validación

- [Validación de la integración](validacion-integracion.md): procedimientos, resultados funcionales, límites y evaluación pendiente.
- [Evaluación integral del baseline](../evaluacion/integral/README.md): protocolo reproducible de calidad y latencia.
- [Hito 2](../hito-2/README.md): fuentes y análisis de viabilidad, preservados como entregable académico anterior.
- [Criterios de aceptación del Hito 3](../hito-3/definicion-de-la-poc.md#23-criterios-de-aceptación): referencia normativa de la evaluación de la PoC.

La documentación de `src/` remite a estas guías. Los procedimientos y resultados específicos de evaluación se encuentran en `evaluacion/`. Los registros originales de OpenSpec describen el estado de cada etapa durante su desarrollo; conservan sus rutas y comandos históricos como evidencia, no como instrucciones vigentes. Sus configuraciones apuntan a las ubicaciones actuales; ejecutar su CLI desde `docs/diarizacion/` o `docs/asociacion/`, respectivamente.
