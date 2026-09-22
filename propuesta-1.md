# Problema

La creación de presentaciones constituye una actividad frecuente en contextos académicos, técnicos y profesionales. Sin embargo, existe una brecha considerable entre las ideas, conceptos y argumentos que una persona desea comunicar y su materialización en una presentación visual coherente, clara y consistente.

En muchos casos, el contenido inicial ya existe en alguna forma relativamente estructurada: notas, títulos, listas de conceptos, ecuaciones, figuras, resultados o una secuencia argumental preliminar. Aun así, transformar ese material en una presentación requiere una cantidad significativa de trabajo adicional que no está directamente relacionada con el desarrollo conceptual del contenido. Es necesario decidir la distribución de los elementos, organizar cada diapositiva, mantener una jerarquía visual, seleccionar tamaños y posiciones, conservar consistencia entre diapositivas y realizar sucesivas correcciones a medida que evoluciona el contenido.

Este problema se vuelve especialmente relevante en presentaciones técnicas sujetas a modificaciones frecuentes. Una ecuación puede cambiar durante el desarrollo de un trabajo, una figura puede ser reemplazada por una versión actualizada o una diapositiva puede necesitar ser reorganizada sin modificar el resto de la presentación. En interfaces de edición predominantemente gráficas, estos cambios suelen requerir operaciones manuales repetitivas sobre tamaños, posiciones, alineaciones y estilos.

Las herramientas actuales de inteligencia artificial generativa permiten reducir parte del esfuerzo de creación inicial mediante instrucciones en lenguaje natural. Sin embargo, esto introduce otra dificultad: el resultado no siempre conserva una representación suficientemente estructurada y controlable. Una presentación puede resultar adecuada en una primera generación, pero ser difícil de modificar de manera precisa, local y predecible. Ante una interpretación incorrecta o una necesidad que no puede expresarse adecuadamente mediante nuevas instrucciones, el usuario puede terminar recurriendo nuevamente a una edición manual costosa.

Existe entonces una tensión entre dos formas de trabajo:

* **Edición manual:** ofrece un alto grado de control, pero obliga al usuario a traducir continuamente sus ideas a operaciones concretas de composición visual.
* **Generación mediante inteligencia artificial:** reduce el esfuerzo de creación, pero puede dificultar modificaciones posteriores y reducir el control sobre el artefacto generado.

Además, las presentaciones de una misma persona, grupo u organización suelen compartir características que no se especifican explícitamente cada vez: densidad de información, relación entre texto e imágenes, forma de introducir ecuaciones, estructura de títulos, organización visual, progresión argumental y otras decisiones de comunicación.

El problema puede sintetizarse entonces como:

**¿Cómo reducir el esfuerzo necesario para transformar ideas y contenido técnico en una presentación, y para modificarla posteriormente mediante interacciones naturales, sin perder control estructural, editabilidad, consistencia y capacidad de intervención directa sobre el resultado?**

El objetivo no es únicamente automatizar la generación inicial. Se busca reducir la distancia entre **pensar qué se quiere comunicar** y **materializarlo y mantenerlo como una presentación**, sin convertir la inteligencia artificial en el único medio posible para modificar el producto obtenido.

# Posible solución

Se propone explorar un sistema de creación y edición de presentaciones asistido por inteligencia artificial, basado en una representación programática y estructurada del documento.

La solución tendría los siguientes componentes principales:

* **Entrada simplificada:** descripción de la presentación mediante un archivo de texto estructurado, por ejemplo Markdown.
* **Representación intermedia:** estructura interna que separe contenido, intención comunicacional, estilo y composición.
* **Perfil de estilo:** caracterización obtenida a partir de presentaciones previas y de las interacciones posteriores del usuario.
* **Agente de inteligencia artificial:** interpretación de instrucciones y planificación de las modificaciones necesarias.
* **Herramientas específicas:** operaciones controladas para crear, modificar, compilar y validar la presentación.
* **Representación final editable:** generación de un documento que pueda continuar siendo modificado directamente por el usuario.
* **Interfaz interactiva:** visualización del resultado, historial de cambios e ingreso de nuevas instrucciones.

## Flujo general

El flujo propuesto sería:

**ideas y contenido → interpretación → estructura interna → planificación → generación/modificación → compilación → visualización → corrección**

El proceso sería iterativo: el usuario podría continuar introduciendo instrucciones después de obtener una primera versión.

## Entrada

El usuario podría definir cada diapositiva mediante elementos simples, por ejemplo:

* título;
* ideas principales;
* listas;
* ecuaciones;
* figuras o rutas a archivos;
* resultados;
* restricciones;
* indicaciones sobre la intención comunicacional.

La entrada debería concentrarse principalmente en **qué se quiere comunicar**, evitando exigir una definición exhaustiva de posiciones, tamaños y demás parámetros gráficos.

## Representación intermedia

Entre la entrada del usuario y la presentación final se propone una capa estructurada que permita representar explícitamente:

* contenido;
* objetivo comunicacional de cada diapositiva;
* recursos asociados;
* restricciones;
* estilo;
* composición prevista.

Esta capa permitiría desacoplar la interpretación de las ideas de su implementación concreta en la presentación.

También facilitaría modificaciones localizadas sin necesidad de regenerar completamente el documento.

## Perfil de estilo

A partir de presentaciones anteriores podrían extraerse patrones recurrentes tales como:

* densidad de información;
* cantidad y longitud habitual de listas;
* proporción entre texto, figuras y ecuaciones;
* estructuras de diapositiva frecuentes;
* formas de introducir conceptos;
* tratamiento de conclusiones;
* progresión narrativa;
* preferencias visuales;
* uso de determinadas composiciones.

El perfil podría actualizarse además mediante las interacciones con el usuario.

Por ejemplo, instrucciones repetidas como:

* “menos texto”;
* “dar más importancia a la figura”;
* “evitar dos columnas en este tipo de diapositivas”;
* “presentar primero la idea y después la ecuación”;

podrían utilizarse como nueva evidencia acerca de sus preferencias.

El objetivo sería disponer de una representación progresivamente refinada de **cómo suele comunicar el usuario**, y no únicamente de una plantilla gráfica fija.

## Agente y herramientas

El modelo de lenguaje funcionaría principalmente como intérprete y planificador.

Las modificaciones concretas podrían ejecutarse mediante herramientas específicas, por ejemplo:

* crear o eliminar una diapositiva;
* insertar o modificar texto;
* insertar una ecuación;
* insertar o reemplazar una figura;
* reorganizar elementos;
* cambiar una composición;
* dividir o combinar diapositivas;
* modificar tamaños relativos;
* compilar la presentación;
* detectar errores;
* inspeccionar el resultado generado.

Esta separación permitiría aprovechar la flexibilidad del lenguaje natural sin delegar necesariamente todas las operaciones al modelo de lenguaje.

## Beamer como posible representación final

Una alternativa para la representación final es **LaTeX con Beamer**.

Su utilización aportaría:

* representación textual y estructurada;
* integración natural de ecuaciones;
* separación entre presentación y archivos de figuras;
* reproducibilidad;
* compilación automática;
* control preciso de los elementos;
* compatibilidad con sistemas de control de versiones;
* posibilidad de edición manual independiente del sistema de inteligencia artificial.

La gestión externa de recursos resulta especialmente útil para presentaciones técnicas.

Por ejemplo:

```text
figures/
├── resultados_modelo.pdf
├── arquitectura.pdf
└── convergencia.pdf
```

Si `convergencia.pdf` es generado nuevamente por otro programa, puede reemplazarse el archivo existente y recompilar la presentación. La nueva figura aparecería automáticamente conservando la composición ya definida.

No sería necesario:

* eliminar manualmente la figura anterior;
* volver a insertarla;
* reconstruir su tamaño;
* volver a alinearla;
* repetir el proceso ante cada actualización.

Una ventaja equivalente aparece con las ecuaciones, que permanecerían expresadas directamente como código LaTeX editable.

Beamer constituye, sin embargo, **una decisión dentro de la solución propuesta y no una condición del problema**.

## Edición iterativa

Luego de generar una primera versión, el usuario podría continuar interactuando mediante lenguaje natural.

Por ejemplo:

> En la diapositiva 8, eliminá el texto de la derecha, aumentá el tamaño de la figura y dejá la conclusión debajo.

El sistema debería:

* identificar la diapositiva y los elementos involucrados;
* interpretar la intención;
* determinar las operaciones necesarias;
* modificar únicamente la región afectada;
* compilar nuevamente;
* comprobar que el documento siga siendo válido.

Una propiedad deseable sería la **localidad de las modificaciones**:

**una instrucción local debería producir el mínimo conjunto de cambios necesario, preservando el resto de la presentación.**

## Edición humana

La generación mediante inteligencia artificial no reemplazaría la edición convencional.

El usuario tendría dos vías complementarias:

* modificar la presentación mediante instrucciones en lenguaje natural;
* intervenir directamente sobre su representación programática.

Esto permitiría utilizar la inteligencia artificial cuando reduzca trabajo y recurrir a la edición directa cuando resulte más precisa o conveniente.

## Interfaz

Una posible interfaz podría integrar:

* visualización del PDF compilado;
* entrada de instrucciones;
* historial de interacciones;
* recompilación automática;
* navegación entre diapositivas;
* acceso opcional a la representación estructurada o al código generado.

El núcleo del proyecto, sin embargo, estaría en la interpretación, representación y modificación controlada de la presentación. La interfaz actuaría principalmente como soporte del ciclo de interacción.

# Aspectos de inteligencia artificial involucrados

La propuesta permite abordar distintos problemas propios de sistemas basados en inteligencia artificial:

* interpretación de instrucciones en lenguaje natural;
* extracción de intención comunicacional;
* generación estructurada;
* utilización de herramientas;
* planificación de acciones;
* recuperación de ejemplos previos;
* extracción y adaptación de estilo;
* mantenimiento de contexto entre múltiples interacciones;
* edición localizada;
* validación y corrección automática.

# Posibles criterios de evaluación

El sistema podría evaluarse mediante tareas de creación y modificación controladas.

Algunas métricas posibles son:

* porcentaje de presentaciones que compilan correctamente;
* cumplimiento de las instrucciones solicitadas;
* preservación del contenido no afectado;
* cantidad de modificaciones innecesarias;
* consistencia con presentaciones previas;
* cantidad de iteraciones requeridas para alcanzar el resultado deseado;
* evaluación humana del resultado;
* capacidad de modificar correctamente figuras, ecuaciones y composición sin afectar otras regiones.

También podrían compararse distintas arquitecturas, por ejemplo:

* generación directa de código;
* generación mediante herramientas;
* generación mediante representación intermedia y herramientas;
* incorporación adicional de información extraída de presentaciones previas.

# Síntesis

El problema no consiste simplemente en generar presentaciones automáticamente, sino en **reducir el esfuerzo necesario para crearlas y mantenerlas sin sacrificar el control del usuario sobre el resultado**.

La solución propuesta explora un sistema en el que la inteligencia artificial interpreta contenido e instrucciones, utiliza conocimiento derivado de presentaciones anteriores y opera sobre una representación estructurada y editable.

El principio central puede sintetizarse como:

**la inteligencia artificial debería reducir la distancia entre la intención del autor y la presentación resultante, sin transformar al resultado en un artefacto opaco o dependiente de la propia inteligencia artificial para continuar siendo modificado.**
