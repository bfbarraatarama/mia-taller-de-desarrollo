# Design

## Context

Ver `proposal.md — Why` para la motivación. El pipeline ya existe y funciona; este cambio no modifica código. El desafío es definir cómo ejecutar la validación funcional de forma reproducible y coordinada entre dos entornos que no comparten acceso: Windows/CPU (Luisa) y Linux/GPU (compañeros del equipo).

El pipeline sigue el grafo de dependencias: `preparar → diarizar → transcribir → asociar → minuta`. El estado se persiste en `workflow.json` tras cada etapa. Los artefactos intermedios son verificables por SHA-256. La GUI lanza cada etapa pesada en un subproceso separado; la CLI puede usarse directamente con `python -m src.pipeline`.

Hallazgos externos pendientes (Matías Caccia, Fedora 43 / cu128): torchcodec sin `libnppicc.so.12`, `localizar_7zip` sin verificación de RAR, README sin sección Fedora. Estos están fuera del scope de este cambio y se coordinan por separado.

## Goals / Non-Goals

**Goals:**
- Definir un conjunto mínimo de escenarios de validación funcional ejecutables por cada responsable en su entorno
- Separar con claridad las tareas de Windows/CPU de las de Linux/GPU
- Registrar los hallazgos de cada validación como evidencia de cierre de la issue #18
- Proveer un archivo de audio de prueba compartido que todos puedan usar sin depender de grabaciones propias

**Non-Goals:**
- Automatizar los escenarios como tests de pytest (eso requeriría hardware real o mocks complejos de sounddevice)
- Corregir los hallazgos de Matías Caccia (fuera de scope de este cambio)
- Validar modelos de LLM específicos ni calidad de las minutas generadas (solo que se producen)

## Decisions

### D1 — Archivo de audio de prueba compartido

**Decisión:** usar el ejemplo ideal generado por `evaluacion/asociacion/ejemplo_ideal/generar.py` como entrada canónica de validación funcional. Ya incluye 3 hablantes, duración controlada (~60 s) y es reproducible con `-D`.

**Alternativa descartada:** usar grabaciones reales propias de cada validador. Requeriría coordinar que todos graben algo similar, impide comparar resultados entre plataformas.

### D2 — Separación de responsabilidades por plataforma

**Decisión:** cada responsable ejecuta en su entorno y registra los resultados en un documento de evidencia (tabla con fecha, plataforma, escenario, resultado, observaciones). No se bloquea entre sí.

**Alternativa descartada:** esperar la validación Linux antes de considerar completa la validación Windows. Bloquea innecesariamente el avance de Luisa en la issue.

### D3 — Captura en vivo es opcional para Linux/GPU

**Decisión:** los escenarios de captura (spec `validacion-funcional/captura`) son opcionales en entornos sin micrófono físico disponible en el momento de la validación. Se pueden ejecutar con un archivo de audio ya grabado usando la ruta de ingesta directa. Se marcan explícitamente en las tareas.

**Alternativa descartada:** requerir captura en vivo en todos los entornos. No es viable en servidores GPU sin periféricos de audio.

### D4 — Hallazgos de Linux/GPU no bloquean el cierre de Windows/CPU

**Decisión:** los hallazgos de Matías Caccia (torchcodec/cu128, 7zip/RAR, README Fedora) se registran como pendientes externos y no bloquean el cierre de las tareas de Luisa. La issue #18 se puede cerrar parcialmente o con nota sobre los pendientes Linux si las correcciones requieren coordinación adicional.

## Risks / Trade-offs

- **[Riesgo] La validación de captura en vivo en Windows requiere micrófono activo** → Mitigation: se puede usar el tono de prueba de `captura.py --tono` como sustituto del audio real de micrófono.
- **[Riesgo] La generación de minuta requiere un modelo LLM disponible** → Mitigation: usar un modelo local pequeño (ollama) o documentar el resultado como "pendiente de modelo" si no hay LLM configurado; el criterio de aceptación mínimo es que las etapas preparar/diarizar/transcribir/asociar completen correctamente.
- **[Riesgo] Los hallazgos de Linux/GPU permanecen sin corrección** → Mitigation: registrarlos explícitamente en `PR_ISSUE_18.md` como pendientes de coordinación con responsable identificado (Matías Caccia).
- **[Trade-off] Validación manual vs. automática**: la validación funcional es manual porque requiere hardware real (micrófono, GPU) o setup específico. Los tests automatizados cubren la corrección del código; esta validación cubre que el sistema funciona como aplicación integrada.

## Open Questions

- ¿Qué modelo LLM está disponible en el entorno Windows/CPU para la etapa `minuta`? Si no hay modelo configurado, la validación del flujo principal puede detenerse en la etapa `asociar` y documentarse como resultado parcial aceptable.
- ¿Los compañeros de Linux/GPU pueden ejecutar la validación funcional antes del cierre de la issue, o se registra como pendiente para un sprint posterior?
