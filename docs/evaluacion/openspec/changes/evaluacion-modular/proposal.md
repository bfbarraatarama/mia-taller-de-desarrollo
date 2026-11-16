# Proposal

## Why

El criterio «Funcionamiento modular» de la [definición de la PoC, §2.3](../../../../../hito-3/definicion-de-la-poc.md#23-criterios-de-aceptación) exige 4/4 módulos con el 100 % de sus salidas dentro del contrato del módulo siguiente, sobre una **muestra congelada con su SHA-256 en un manifiesto**: 5 clips de OpenSLR y Common Voice, 3 sesiones de Figshare y 3 reuniones de AMI traducidas, chequeada con un script de contratos. El plan 4.1 la ubicaba en la semana 7. Hoy no existe: [`docs/validacion-integracion.md`](../../../../validacion-integracion.md) aclara que los manifiestos del Hito 2 y de Figshare (S26) no la acreditan, y la evaluación de la asociación sobre grabaciones propias no se puede repetir sola. Lo pide el issue #13.

## What Changes

| Pieza | Qué hace |
|---|---|
| Muestra congelada | 3 clips de OpenSLR 61 y 2 de Common Voice 26 rioplatense, 3 sesiones completas de Figshare v2 y 3 reuniones de AMI con turnos y minuta traducidos, elegidos con semilla y fijados por SHA-256 |
| Traducción de AMI | MarianMT local (`Helsinki-NLP/opus-mt-en-es`), marcada como sintética |
| Ejecutor `preparar` | Verifica originales, selecciona, traduce, normaliza y escribe el manifiesto |
| Ejecutor `inferir` | Corre cada módulo sobre su material y la cadena real 2→3→4→5 en Figshare; guarda todas las salidas |
| Ejecutor `evaluar` | Contratos de los 4 módulos y métricas sin umbral desde lo guardado, sin volver a inferir |
| Métricas | WER y CER (STT), DER y JER (diarización), palabras bien atribuidas (asociación), planilla sí/no de ítems (minutas) |
| Exposición previa | Informe de qué datos de la muestra tocaron el desarrollo o el entrenamiento de los modelos |

**Fuera de alcance:** la reunión de prueba, la latencia y la calidad integral (#14), los escenarios de 2.1 y la recuperación (#15), los cambios en las etapas (#16, #17), y umbrales nuevos: las métricas se registran sin umbral, como dice 2.3.

## Capabilities

### New Capabilities
- `muestra-evaluacion`: obtención verificada, selección con semilla, traducción, normalización y manifiesto SHA-256 de la muestra de 2.3.
- `evaluacion-modular`: inferencia por módulo y en cadena, contratos de los 4 módulos, métricas sin umbral, planilla de minutas e informe de exposición.

### Modified Capabilities
<!-- Ninguna: no hay specs existentes en docs/evaluacion/openspec/specs/. -->

## Impact

| Qué | Detalle |
|---|---|
| Código nuevo | `evaluacion/modular/` (ejecutor y configuración TOML), `tests/evaluacion/` |
| Código reutilizado sin cambios | `hito-2/scripts/descargar_fuentes.py` y `armar_muestra.py`, `evaluacion/diarizacion/der.py`, los validadores de `src/diarizacion`, `src/stt`, `src/asociacion` y `src/minutas`, y el pipeline de `src/pipeline` |
| Dependencias | `transformers` y `sentencepiece` para MarianMT (unos 300 MB de modelo); `jiwer` para WER/CER, o una implementación propia de Levenshtein |
| Datos | Common Voice requiere cuenta en Mozilla Data Collective (`MDC_API_KEY`); `wavs.rar` de Figshare pesa 722 MB. Originales y derivados de audio quedan en `hito-2/.cache` y en `evaluacion/modular/datos/`, fuera de Git |
| GPU | Una corrida de unos 30 a 60 minutos en la máquina de referencia (RTX 3050 Laptop, 6 GB) |
| Equipo | Felipe (STT): el WER y la normalización. Luisa (diarización): reutiliza su `der.py` y su política de etiquetas. Bruno (minutas): la planilla de ítems y la configuración del modelo |
