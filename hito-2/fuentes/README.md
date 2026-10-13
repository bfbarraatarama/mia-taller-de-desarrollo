# Fuentes de datos

Este directorio contiene la documentación individual de las fuentes evaluadas para el Hito 2. Su propósito es conservar la evidencia de procedencia, accesibilidad, composición, anotaciones, condiciones de uso y riesgos que fundamenta la selección de datos.

Las fichas complementan el [mapa de fuentes](../1-mapa-de-fuentes.md), pero no lo reemplazan. El mapa sigue siendo el documento principal que consolida las fuentes consideradas, su estado de obtención y las decisiones de selección.

## 1. Organización

Se utiliza una ficha individual para cada fuente seleccionada cuya estructura, adquisición o utilización requiera documentación específica.

Las alternativas evaluadas pero no seleccionadas pueden agruparse en `otras-fuentes.md`, siempre que queden registrados los motivos de su evaluación y descarte. No es necesario elaborar una ficha extensa para cada alternativa.

Los datos derivados que modifican sustancialmente una fuente original, como una traducción de transcripciones y minutas, deben documentar su procedimiento de transformación y conservar la trazabilidad con el origen.

## 2. Contenido de las fichas

Cada ficha se organiza mediante las siguientes secciones. Cuando un punto no corresponda, se indica «No aplica»; cuando la información no se haya podido establecer, se indica «No sabemos» y, cuando corresponda, qué falta verificar.

### Uso previsto y estado

- Módulo del producto al que contribuye.
- Función de la fuente dentro de la evaluación.
- Estado de selección, consistente con el mapa de fuentes.
- Alcance y limitaciones del uso previsto.

La selección de una fuente y su adquisición son estados distintos. Una fuente seleccionada puede no haberse descargado todavía.

### Identificación y procedencia

- Nombre, responsables y propósito original.
- Publicación o documentación primaria.
- Identificador y ubicación de acceso.
- Versión o edición de referencia.
- Período de recolección, cuando se conozca.

### Acceso y condiciones de uso

- Mecanismo de adquisición y requisitos técnicos.
- Acceso efectivamente verificado, con fecha y responsable.
- Pasos manuales indispensables, permisos y restricciones.
- Licencia de los datos y referencia a sus condiciones.
- Consideraciones de privacidad, consentimiento y redistribución.

La existencia de una página pública no constituye por sí sola evidencia de acceso efectivo. Las condiciones de licencia que no se hayan podido verificar quedan expresamente pendientes.

### Composición y anotaciones

- Unidad de observación y volumen disponible.
- Idioma, variedad lingüística y contexto de grabación.
- Organización de grabaciones, sesiones y participantes.
- Referencias disponibles: texto, intervalos temporales, hablantes, minutas o evidencias, según corresponda.
- Procedimiento de generación, anotación y revisión de las referencias.
- Identificadores disponibles y alcance de las identidades de hablante.

No se atribuyen a la fuente anotaciones, alineamientos o identidades persistentes que su documentación o sus datos no permitan verificar.

### Riesgos por propiedad

Examinar, con relación al uso previsto:

- Volumen.
- Completitud.
- Corrección.
- Vigencia.
- Representatividad.
- Confiabilidad.

Se distinguen los riesgos anticipados de los problemas observados después de obtener y procesar los datos. Las mediciones se calculan en el notebook de EDA, no se mantienen independientemente en las fichas.

### Obtención y uso en la muestra

- Plan de adquisición y responsable.
- Resultado efectivo de la adquisición.
- Archivos y anotaciones obtenidos.
- Criterios de selección y exclusión.
- Transformaciones necesarias y su trazabilidad.
- Tablas de la muestra que utilizan la fuente.
- Diferencias entre lo esperado y lo obtenido.

Los identificadores técnicos, versiones fijadas y hashes deben corresponder con la configuración de adquisición y el manifiesto de la muestra.

### Limitaciones y pendientes

Registrar las incertidumbres que afecten la interpretación o utilización de la fuente, así como las verificaciones todavía necesarias.

No presentar una limitación pendiente como un defecto demostrado ni una hipótesis como un resultado medido.

### Referencias

Incluir las referencias primarias necesarias para verificar procedencia, composición, anotaciones, acceso y condiciones de uso.

## 3. Responsabilidades documentales

Para evitar duplicaciones y contradicciones se mantiene la siguiente distribución:

| Información | Documento de referencia |
|---|---|
| Comparación, selección y resultado de obtención de las fuentes | `1-mapa-de-fuentes.md` |
| Detalle documental y limitaciones de cada fuente | Ficha individual |
| Requisitos y niveles necesarios | `niveles-a-priori.md` |
| Versiones e identificadores técnicos de adquisición | `fuentes.toml`, cuando se incorpore |
| Esquema y significado de las tablas normalizadas | Documentación del esquema de la muestra |
| Archivos generados, transformaciones e integridad | `muestra/MANIFIESTO.json` |
| Licencias y atribuciones aplicables a la muestra | `muestra/LICENCIAS.md` |
| Mediciones y búsquedas de leakage | `notebooks/eda_viabilidad.ipynb` |
| Interpretación de viabilidad | `2-eda-de-viabilidad.md` |
| Descripción de la muestra entregada | `3-datasheet.md` |
| Decisión global de continuidad | `4-veredicto.md` |

Las fichas pueden remitir a estas fuentes de verdad, pero no deben mantener copias independientes de sus resultados o contratos normativos.

## 4. Criterios de mantenimiento

- Conservar el trabajo existente que siga siendo válido y trazable.
- Registrar explícitamente las diferencias entre documentación original, datos obtenidos y transformaciones propias.
- No inventar información faltante ni inferir atributos personales de los hablantes.
- No declarar una fuente representativa únicamente por su tamaño o idioma.
- Distinguir hechos verificados, estimaciones y riesgos no resueltos.
- Actualizar el mapa y los documentos principales cuando los resultados modifiquen las conclusiones del Hito 2.

Las fichas documentan las fuentes. La decisión sobre la viabilidad del proyecto se fundamenta en el EDA y se expresa en el veredicto.