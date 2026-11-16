# Proposal

## Why

Los criterios «Cobertura de los casos borde» (7/7 escenarios de §2.1 que hacen lo que dice su «Entonces», con la entrada conservada) y «Recuperación ante interrupciones» (1/1 prueba con 5 s perdidos o menos, el archivo procesable y listado como interrumpido al reiniciar) de la [definición de la PoC, §2.3](../../../../../hito-3/definicion-de-la-poc.md#23-criterios-de-aceptación) no están medidos. El checkpoint del Hito 4 (Clase 10, 17/11/2026) pide el estado contra todos los criterios, con evidencia. Lo pide el issue #15.

## What Changes

| Pieza | Qué hace |
|---|---|
| Entradas fijadas | Una entrada por escenario, con su SHA-256 en un manifiesto, armada desde datos públicos o ya congelados |
| Corrida | Cada escenario pasa por el pipeline de la aplicación (`src.pipeline ejecutar`), como lo haría el usuario |
| Comprobaciones automáticas | Lo verificable sin juicio humano de cada «Entonces», sobre los archivos que deja la aplicación |
| Prueba de recuperación | Grabación de 2 min o más con la captura de la aplicación, cierre forzado (`kill -9`), medición de lo perdido, proceso del archivo y lista de interrumpidas |
| Protocolo para un tercero | Lista para recorrer cada escenario con la aplicación abierta y marcar sí o no (§2.3) |

**Alcance de esta entrega (decisión D1):** los escenarios que no requieren grabar personas (2.1.2 a 2.1.5) y la recuperación. El happy path usa la reunión de prueba del issue #14 y 2.1.1 necesita una grabación con terminología especializada: quedan pendientes y así se declaran.

**Fuera de alcance:** cambiar la aplicación, umbrales nuevos y la evaluación de calidad y latencia (#14).

## Capabilities

### New Capabilities
- `escenarios-funcionales`: entradas fijadas por escenario, corrida por el pipeline, comprobaciones automáticas, prueba de recuperación y protocolo para un tercero.

## Impact

| Qué | Detalle |
|---|---|
| Código nuevo | `evaluacion/escenarios/` y `tests/evaluacion/test_escenarios*.py` |
| Reutiliza | La muestra congelada y `leer_miembro` de `evaluacion/modular`, la captura (`src.captura.captura`), `consultar_grabaciones_interrumpidas` y el pipeline |
| Datos | ICSI Bro015 (32 MB, CC BY 4.0, Universidad de Edimburgo) en `hito-2/.cache/icsi_audio/` |
| Equipo | Bruno (#14): reunión de prueba para el happy path. Un tercero que no ejecutó las corridas recorre el protocolo |
