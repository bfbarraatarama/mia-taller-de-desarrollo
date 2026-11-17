# Tasks

En cada tarea, primero los tests de sus escenarios. Meta del martes 17/11: grupos 1 a 4 y el contrato de la tarea 5.1 (criterio «Funcionamiento modular» de §2.3).

## 1. Preparación

- [x] 1.1 Estructura de `evaluacion/modular/` (`__main__` con `preparar`, `inferir` y `evaluar`), `tests/evaluacion/` y configuración TOML versionada con la semilla 20261010
- [x] 1.2 Consultar los pendientes del diseño (D14 a D17)

## 2. Originales

- [x] 2.1 Verificación contra `fuentes.toml` y `fuentes.lock.json`, con el comando del Hito 2 en el mensaje · escenarios: Original con hash distinto, Original ausente
- [x] 2.2 Obtener Common Voice 26 rioplatense (Matías, con `MDC_API_KEY`) y `wavs.rar` de Figshare (con el ok de Matías), y verificarlos

## 3. Selección y normalización

- [x] 3.1 Selección de clips · escenarios: Clips de personas distintas, Misma semilla, misma muestra
- [x] 3.2 Selección de sesiones de Figshare · escenario: Sesiones excluidas
- [x] 3.3 Selección de reuniones de AMI (series distintas, con acción, cerca de la mediana)
- [x] 3.4 Audio a WAV de 16 kHz, mono y PCM16 · escenario: Clip de OpenSLR

## 4. Traducción y manifiesto

- [x] 4.1 Traducción con MarianMT en revisión fija · escenarios: Traducción repetible, Marca de sintético
- [x] 4.2 Manifiesto y `--verificar` · escenarios: Archivo alterado, Muestra intacta

## 5. Inferencia y contratos

- [x] 5.1 Contratos de los cuatro módulos desde lo guardado · escenarios: Todas válidas, Una salida fuera de contrato
- [x] 5.2 `inferir` con verificación previa y reutilización · escenarios: Muestra alterada, Reutilización
- [x] 5.3 Corrida en GPU (RTX 3050, 6 GB) sobre la muestra completa; revisar antes con `nvidia-smi` que la GPU esté libre

## 6. Métricas

- [x] 6.1 WER y CER · escenario: Normalización
- [x] 6.2 DER y JER con `der.py` · escenario: Misma configuración que S26
- [x] 6.3 Atribución de palabras · escenarios: Palabra en superposición, Correspondencia de etiquetas
- [x] 6.4 Planilla de minutas · escenarios: Planilla sin marcar, Planilla marcada
- [x] 6.5 Evaluación sin inferencia · escenario: Recalcular métricas

## 7. Exposición y cierre

- [x] 7.1 Informe de exposición previa · escenario: Fuente de desarrollo excluida
- [ ] 7.2 Marcado de la planilla de minutas por una persona que no ejecutó la inferencia
- [x] 7.3 `evaluacion/modular/README.md`, registro de pruebas con los resultados y enlace desde `docs/validacion-integracion.md`
