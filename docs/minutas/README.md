# Generación de minutas

Módulo independiente de la interfaz y de los modelos de diarización y transcripción. Recibe `transcription.json` conforme al contrato de `hito-3/pipeline-etapas-y-herramientas.md`, genera una minuta estructurada con contenido en español y la presenta en Markdown. `qwen2.5:7b` es el modelo predeterminado; AWS Bedrock se admite de forma opcional y explícita para contenido autorizado. Todos los modelos son experimentales, según la actualización fechada de la [definición de la PoC](../../hito-3/definicion-de-la-poc.md#311-el-modelo).

## Decisiones de diseño

Se separa la generación de los modelos acústicos y de la GUI: recibe una transcripción estructurada que puede evaluarse de forma independiente, incluso con una referencia corregida. El catálogo cerrado evita opciones que no tienen un adaptador implementado y permite compartir el selector entre clientes. Se mantiene Qwen como predeterminado del baseline; Nova Lite y Claude Opus 4.5 se admiten para experimentar con capacidades de cómputo adicionales, no para demostrar equivalencia entre ejecución local y remota.

Se utiliza una salida estructurada validada en lugar de una minuta libre en Markdown: los identificadores de intervención permiten localizar evidencias y reutilizar el mismo resultado para presentación y evaluación. Las referencias verificables son una condición de trazabilidad, no una comprobación de que el texto generado sea verdadero. La selección de secciones modifica el esquema y la generación para evitar producir contenido no solicitado. La extracción por bloques y la consolidación permiten procesar reuniones que exceden el contexto utilizable; sus decisiones, alternativas y condiciones de terminación están en [Consolidación de minutas extensas](consolidacion-de-minutas.md).

## Dependencias

Usar el entorno general de Python 3.12 del [README raíz](../../README.md#entorno-único-para-todo-el-repositorio), que incluye los adaptadores y las pruebas de minutas.

Para Ollama, instalar el servicio local y descargar previamente el modelo: `ollama pull qwen2.5:7b`. Para Bedrock, configurar las credenciales habituales de `boto3` y `AWS_REGION` en el entorno o en el `.env` de la raíz; no guardar credenciales en Git. También se admite `MINUTAS_ENV_FILE` para indicar otro `.env`. Una referencia sin resolver `op://` no se carga como credencial.

## Uso

Desde la raíz del repositorio:

```bash
.venv/bin/python -m src.minutas \
    --entrada resultados/transcription.json \
    --salida resultados/reunion_01 \
    --modelo qwen2.5-7b
```

Para pruebas explícitamente autorizadas con Bedrock:

```bash
.venv/bin/python -m src.minutas \
    --entrada datos_autorizados/transcription.json \
    --salida resultados/prueba_bedrock \
    --modelo nova-lite \
    --permitir-remoto
```

También se puede invocar desde Python:

```python
from src.minutas import generar_minuta

resultado = generar_minuta(
    "resultados/transcription.json",
    "resultados/reunion_01",
    modelo="qwen2.5-7b",
)
print(resultado.markdown)
```

## Modelos disponibles

Los modelos seleccionables se definen exclusivamente en `src/minutas/modelos.py`. Cada entrada incluye una clave estable, un nombre visible, el proveedor, el identificador técnico, una descripción y la indicación de procesamiento remoto.

La API `listar_modelos()` permite que la interfaz gráfica construya un selector sin duplicar la configuración. La clave seleccionada se proporciona mediante `modelo` en `generar_minuta()` o mediante `--modelo` en la CLI.

Opciones iniciales:

| Clave | Nombre visible | Proveedor |
|---|---|---|
| `qwen2.5-7b` | Qwen 2.5 (7B) — Ollama | Ollama |
| `nova-lite` | Amazon Nova Lite — Bedrock | AWS Bedrock |
| `claude-opus-4.5` | Claude Opus 4.5 — Bedrock | AWS Bedrock |

Qwen es la opción predeterminada. Bedrock y Ollama externo requieren `permitir_remoto=True` en la API o `--permitir-remoto` en la CLI para cada nueva generación; Bedrock requiere además credenciales y permisos AWS válidos. No se hereda la autorización entre solicitudes.

La API y la CLI rechazan identificadores arbitrarios. Los identificadores técnicos pertenecen al catálogo y no deben solicitarse al usuario final. La disponibilidad efectiva de un modelo depende del servidor Ollama o del acceso a Bedrock; el catálogo declara opciones admitidas, no comprueba automáticamente su disponibilidad.

Para la política de transferencia, el procesamiento mediante Ollama solo se considera local cuando el destino es loopback. Un servidor Ollama externo implica transferencia de transcripciones. La política de autorización y sus límites se fundamentan en [Reanudación y confidencialidad](../continuidad-y-confidencialidad.md).

## Selección del contenido

La minuta puede incluir cualquier combinación no vacía de las secciones `resumen`, `temas`, `decisiones`, `problemas` y `acciones`. Por defecto se solicitan las cinco, preservando el comportamiento inicial.

Desde la terminal, `--secciones` recibe los nombres separados por comas:

```bash
.venv/bin/python -m src.minutas \
    --entrada resultados/transcription.json \
    --salida resultados/reunion_01 \
    --secciones resumen,decisiones,problemas,acciones
```

Desde Python:

```python
from src.minutas import generar_minuta

resultado = generar_minuta(
    "resultados/transcription.json",
    "resultados/reunion_01",
    secciones=("resumen", "decisiones", "problemas", "acciones"),
)
```

También se puede establecer `secciones` en `ConfiguracionMinutas`; no debe proporcionarse simultáneamente mediante ambos mecanismos.

La selección determina el esquema JSON enviado al LLM, los campos exigidos en la validación, las secciones de la consolidación y el contenido de `minutes.md`. No se generan categorías adicionales para después ocultarlas.

Las cuatro categorías `resumen`, `decisiones`, `problemas` y `acciones` permiten una salida compatible en categorías con las minutas abstractivas de AMI. Esto no implica equivalencia completa con su formato ni constituye todavía una evaluación.

## Rutas

`src/rutas.py` es la fuente central de las ubicaciones de los prompts, las definiciones y los nombres de los archivos de salida. El directorio de resultados lo proporciona quien invoque el módulo; el paquete no impone una ubicación global.

La implementación integrada importa `src` como paquete desde la raíz o tras instalar el proyecto en modo editable. No es necesario instalar el proyecto de agentes anterior.

## Contratos

La entrada del flujo integrado exige una lista no vacía `segments`; cada intervención contiene `start`, `end` (segundos no negativos, inicio menor que fin), `speaker`, `name`, `text`, `overlap` y `ambiguous`. Se admiten campos adicionales que incorpore el módulo anterior, sin alterar estos campos obligatorios. Las intervenciones se ordenan de forma estable y reciben identificadores internos `I000001`, `I000002`, etc.; no se inventan marcas temporales nuevas.

La salida contiene:

| Archivo | Contenido |
|---|---|
| `minutes.json` | Minuta estructurada con exactamente las secciones solicitadas. Los elementos de las listas contienen referencias a las intervenciones. |
| `minutes.md` | Presentación ejecutiva determinística del JSON, con tiempos tomados del archivo de entrada. |
| `ejecucion_minutas.json` | Modelo, proveedor, parámetros, hashes de entrada y prompts, uso de tokens cuando esté disponible y duración. |

Los elementos de listas incluyen `texto`, `ids_intervenciones` e `id_ancla`. Las acciones incorporan `responsable` y `plazo`, con `null` cuando no constan. Una categoría seleccionada sin elementos produce una lista vacía. Las categorías no seleccionadas no aparecen en la salida. No se solicitan ni inventan título, fecha o participantes que no estén disponibles en la transcripción. El JSON no reproduce el XML de AMI: toma sus categorías abstractivas como referencia y permite seleccionar exclusivamente las que correspondan.

Las definiciones semánticas de las secciones se mantienen en `src/minutas/prompts/secciones_v1.json`. Las instrucciones generales de extracción y consolidación están en `src/minutas/prompts/extraccion_v1.md` y `src/minutas/prompts/consolidacion_v1.md`. Cada ejecución compone los prompts con las definiciones solicitadas y registra sus hashes SHA-256, junto con las secciones elegidas.

Todos estos archivos conservan la versión 1 durante el desarrollo actual. El contenido semántico y los nombres de campos que ve el modelo están en español; los nombres de parámetros técnicos del protocolo HTTP/SDK y los identificadores de hablantes se mantienen según sus contratos.

## Reuniones extensas y fallos

El presupuesto `max_caracteres_bloque` limita los caracteres de entrada estructurada (12.000 por defecto), junto con una estimación del contexto efectivo, no un conteo exacto de tokens. El contexto solicitado a Ollama es `num_ctx=16384` por defecto. Los límites de contexto y generación del modelo se verifican y las intervenciones extensas pueden dividirse sin modificar sus identificadores ni inventar tiempos. Si el proveedor notifica un límite, la extracción se subdivide de manera acotada; si no puede concluir, se informa el error sin publicar resultados incompletos.

En la consolidación se prefiere la síntesis jerárquica. Si no puede avanzarse respetando el presupuesto, se conserva la salida estructurada por unión local y se intenta sintetizar el resumen por separado cuando corresponda. La pérdida de cobertura de identificadores por sección también activa la unión local. La minuta puede ser menos compacta y el resumen puede incluir síntesis parciales; el manifiesto y la interfaz identifican estas situaciones. Véase [Consolidación de minutas extensas](consolidacion-de-minutas.md) para las decisiones, condiciones de terminación y limitaciones.

Los errores de formato tienen hasta dos reintentos por defecto, sin reenviar la respuesta inválida. Los errores de conexión, autenticación, permisos y controles de contenido no se reintentan como errores de formato. Si el modelo declara un `id_ancla` existente pero lo omite de `ids_intervenciones`, se incorpora ese identificador y se registra la normalización. La validación de referencias exige que pertenezcan a las evidencias recibidas, pero no demuestra fidelidad semántica.

No se reemplazan archivos existentes de manera predeterminada; `--sobrescribir` habilita una ejecución repetida sobre el mismo directorio. Las tres salidas se preparan antes de publicarse; ante errores recuperables de escritura se eliminan las nuevas salidas parciales o se restauran los archivos anteriores al sobrescribir. Cada reemplazo es atómico de manera individual, pero el conjunto de tres archivos no constituye una transacción atómica frente a cortes abruptos del proceso o pérdidas de energía. El manifiesto se publica al final y contiene el hash del JSON. El input debe conservarse en su ubicación original: el manifiesto registra su hash, no una segunda copia. Los modelos no garantizan reproducibilidad bit a bit aunque se fije la temperatura.

## Pruebas técnicas

```bash
.venv/bin/python -m pytest -q -rs tests/minutas
.venv/bin/python -m src.minutas --help
```

Las pruebas automatizadas utilizan un proveedor simulado: validan contratos, salida, referencias, reintentos, fragmentación, consolidación y construcción de solicitudes para ambos adaptadores sin enviar datos. Las pruebas integradas del workflow se ejecutan también desde `tests/integracion/`. Ninguna de estas suites sustituye la inferencia real ni la evaluación de calidad con AMI o reuniones propias.

La GUI integrada consulta y abre `minutes.md`, conforme al contrato del Hito 3; no se genera ningún alias `minuta.md`.
