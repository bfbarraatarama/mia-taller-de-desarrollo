# Etapa 5 — Generación de minutas

Módulo independiente de la interfaz y de los modelos de diarización y transcripción. Recibe `transcription.json` conforme al contrato de `hito-3/pipeline-etapas-y-herramientas.md`, genera una minuta estructurada con contenido en español y la presenta en Markdown. La decisión técnica de la PoC sigue siendo ejecutar `qwen2.5:7b` localmente; AWS Bedrock se admite solo de forma opcional y explícita para contenido autorizado.

## Dependencias

Python 3.12. Desde la raíz del repositorio, sin `uv`:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r src/minutas/requirements.txt
```

Para Ollama, instalar el servicio local y descargar previamente el modelo: `ollama pull qwen2.5:7b`. Para Bedrock, configurar las credenciales habituales de `boto3` y `AWS_REGION` en el entorno o en el `.env` de la raíz; no guardar credenciales en Git. También se admite `MINUTAS_ENV_FILE` para indicar otro `.env`. Una referencia sin resolver `op://` no se carga como credencial.

## Uso

Desde la raíz del repositorio:

```bash
PYTHONPATH=src .venv/bin/python -m minutas \
    --entrada resultados/transcription.json \
    --salida resultados/reunion_01 \
    --modelo qwen2.5-7b
```

Para pruebas explícitamente autorizadas con Bedrock:

```bash
PYTHONPATH=src .venv/bin/python -m minutas \
    --entrada datos_autorizados/transcription.json \
    --salida resultados/prueba_bedrock \
    --modelo nova-lite \
    --permitir-remoto
```

También se puede invocar desde Python:

```python
from minutas import generar_minuta

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
| `qwen2.5-7b` | Qwen 2.5 (7B) — local | Ollama |
| `nova-lite` | Amazon Nova Lite — Bedrock | AWS Bedrock |
| `claude-opus-4.5` | Claude Opus 4.5 — Bedrock | AWS Bedrock |

Qwen es la opción predeterminada. Las opciones Bedrock requieren `permitir_remoto=True` en la API o `--permitir-remoto` en la CLI, además de credenciales y permisos AWS válidos.

La API y la CLI rechazan identificadores arbitrarios. Los identificadores técnicos pertenecen al catálogo y no deben solicitarse al usuario final. La disponibilidad efectiva de un modelo depende del servidor Ollama o del acceso a Bedrock; el catálogo declara opciones admitidas, no comprueba automáticamente su disponibilidad.

El procesamiento de Qwen es local siempre que `OLLAMA_HOST` apunte a un servidor local. Un servidor Ollama externo también puede implicar transferencia de transcripciones.

## Selección del contenido

La minuta puede incluir cualquier combinación no vacía de las secciones `resumen`, `temas`, `decisiones`, `problemas` y `acciones`. Por defecto se solicitan las cinco, preservando el comportamiento inicial.

Desde la terminal, `--secciones` recibe los nombres separados por comas:

```bash
PYTHONPATH=src .venv/bin/python -m minutas \
    --entrada resultados/transcription.json \
    --salida resultados/reunion_01 \
    --secciones resumen,decisiones,problemas,acciones
```

Desde Python:

```python
from minutas import generar_minuta

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

La importación requiere que `src/` esté disponible en `PYTHONPATH` o que el proyecto se empaquete al integrar los módulos. No es necesario instalar el proyecto de agentes anterior.

## Contratos

La entrada exige una lista `segments`; cada intervención contiene `start`, `end` (segundos no negativos, inicio menor que fin), `speaker`, `name`, `text`, `overlap` y `ambiguous`. Se admiten campos adicionales que incorpore el módulo anterior, sin alterar estos campos obligatorios. Las intervenciones se ordenan de forma estable y reciben identificadores internos `I000001`, `I000002`, etc.; no se inventan marcas temporales nuevas.

La salida contiene:

| Archivo | Contenido |
|---|---|
| `minutes.json` | Minuta estructurada con exactamente las secciones solicitadas. Los elementos de las listas contienen referencias a las intervenciones. |
| `minutes.md` | Presentación ejecutiva determinística del JSON, con tiempos tomados del archivo de entrada. |
| `ejecucion_minutas.json` | Modelo, proveedor, parámetros, hashes de entrada y prompts, uso de tokens cuando esté disponible y duración. |

Los elementos de listas incluyen `texto`, `ids_intervenciones` e `id_ancla`. Las acciones incorporan `responsable` y `plazo`, con `null` cuando no constan. Una categoría seleccionada sin elementos produce una lista vacía. Las categorías no seleccionadas no aparecen en la salida. No se solicitan ni inventan título, fecha o participantes que no estén disponibles en la transcripción. El JSON no reproduce el XML de AMI: toma sus categorías abstractivas como referencia y permite seleccionar exclusivamente las que correspondan.

Las definiciones semánticas de las secciones se mantienen en `prompts/secciones_v1.json`. Las instrucciones generales de extracción y consolidación están en `prompts/extraccion_v1.md` y `prompts/consolidacion_v1.md`. Cada ejecución compone los prompts con las definiciones solicitadas y registra sus hashes SHA-256, junto con las secciones elegidas.

Todos estos archivos conservan la versión 1 durante el desarrollo actual. El contenido semántico y los nombres de campos que ve el modelo están en español; los nombres de parámetros técnicos del protocolo HTTP/SDK y los identificadores de hablantes se mantienen según sus contratos.

## Reuniones extensas y fallos

El presupuesto `max_caracteres_bloque` es un margen conservador, **no un conteo exacto de tokens**. Por defecto se limita a 12.000 caracteres de entrada estructurada por bloque y se solicita `num_ctx=16384` en Ollama; ambas opciones son configurables por CLI. Los bloques comparten hasta dos intervenciones de contexto. Cuando hay varios bloques, se consolidan recursivamente con el segundo prompt, conservando las referencias. Si una intervención individual supera el presupuesto, se informa el problema: dividirla asignándole tiempos ficticios sería incorrecto.

Ollama informa cuántos tokens recibió; si se acerca demasiado al contexto declarado, se produce un error explícito para evitar aceptar una respuesta potencialmente truncada. El parámetro `max_tokens_salida` se aplica mediante `num_predict` en Ollama y `maxTokens` en Bedrock. Si el modelo devuelve JSON inválido, campos ausentes, referencias inexistentes o no entrega la salida estructurada requerida, se reintenta la solicitud hasta dos veces y luego se informa el fallo. Los errores de conexión, autenticación y permisos de los proveedores no se reintentan como errores de formato. Cuando el modelo declara un `id_ancla` existente pero lo omite de `ids_intervenciones`, el programa incorpora ese mismo identificador a las evidencias y registra la normalización en `ejecucion_minutas.json`. No se cambian anclas ni se generan identificadores nuevos. La validación de referencias garantiza **existencia**, pero no demuestra fidelidad semántica. Esa última dimensión corresponde a la evaluación posterior de la PoC.

No se reemplazan archivos existentes de manera predeterminada; `--sobrescribir` habilita una ejecución repetida sobre el mismo directorio. Las tres salidas se preparan antes de publicarse; ante errores recuperables de escritura se eliminan las nuevas salidas parciales o se restauran los archivos anteriores al sobrescribir. Cada reemplazo es atómico de manera individual, pero el conjunto de tres archivos no constituye una transacción atómica frente a cortes abruptos del proceso o pérdidas de energía. El manifiesto se publica al final y contiene el hash del JSON. El input debe conservarse en su ubicación original: el manifiesto registra su hash, no una segunda copia. Los modelos no garantizan reproducibilidad bit a bit aunque se fije la temperatura.

## Pruebas técnicas

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s src/minutas/tests -v
PYTHONPATH=src .venv/bin/python -m minutas --help
```

Las pruebas automatizadas utilizan un proveedor simulado: validan contratos, salida, referencias, reintentos, fragmentación, consolidación y construcción de solicitudes para ambos adaptadores sin enviar datos. No sustituyen pruebas de inferencia real, integración con Matías ni evaluación de calidad con AMI o reuniones propias, que se realizarán cuando corresponda.

La GUI actual abre `minuta.md`, mientras que el contrato del Hito 3 exige `minutes.md`. Esa diferencia deberá resolverse al integrar la etapa 5, sin generar archivos duplicados para compensarla.