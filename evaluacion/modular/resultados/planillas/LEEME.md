# Planilla de minutas (evaluación modular, issue #13)

La marca una persona que **no** ejecutó la inferencia (D17), con el mismo criterio que la calidad de la respuesta
de la definición de la PoC (§2.3).

Para cada reunión:
1. Leer la minuta producida, `<reunión>.minuta.md`.
2. En `<reunión>.csv`, para cada ítem de la minuta de referencia (traducida automáticamente; el original en inglés
   está en `referencia_original`), escribir en `recuperado`:
   - `sí` si la minuta producida lo recupera, aunque sea con otras palabras;
   - `no` si no lo recupera.
   Una **acción** cuenta como recuperada solo si también coincide su responsable (en estas reuniones, el rol:
   «Diseñador industrial», «Gerente de proyecto»…; en IB4005 la referencia no nombra responsables).
3. `observaciones` es libre: dudas, ítems parcialmente recuperados, errores de la traducción.

No cambiar las otras columnas ni el orden de las filas. `python -m evaluacion.modular evaluar` resume lo marcado
sin modificar la planilla.
