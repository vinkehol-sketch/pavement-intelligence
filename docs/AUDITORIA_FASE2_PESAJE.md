# Informe de Auditoría Técnica y Funcional: Fase 2 (Integración TPDA → Pesaje)
**Proyecto:** Pavement Intelligence (Plataforma de Análisis de Tránsito y Diseño de Pavimentos)  
**Estado:** Auditoría de Fase 2 Realizada (Solo Lectura)  
**Fecha:** 2026-07-17  

---

## 1. Alcance de la Auditoría
Este informe presenta la auditoría técnica e independiente de la **Fase 2: Integración TPDA → Pesaje**. Se evalúa el cumplimiento de las reglas metodológicas de pesaje vial, la inmutabilidad de los contratos de tránsito, la coherencia física de cargas por eje, la propagación de marcas sintéticas y el aislamiento de módulos respecto a la futura fase de ESAL. La auditoría es de solo lectura y no modifica código ni pruebas del proyecto.

---

## 2. Archivos Revisados
Se auditaron exhaustivamente los siguientes archivos clave en el espacio de trabajo:
* **Módulo de Dominio de Pesaje:** [workflow.py](file:///D:/proyecto%20Vial/pavement_intelligence/src/pavement_intelligence/weighing/workflow.py)
* **Página de Interfaz de Pesaje:** [weighing.py](file:///D:/proyecto%20Vial/pavement_intelligence/src/pavement_intelligence/ui/pages/weighing.py)
* **Página de Interfaz de Tránsito:** [survey_tpda.py](file:///D:/proyecto%20Vial/pavement_intelligence/src/pavement_intelligence/ui/pages/survey_tpda.py)
* **Pruebas Automatizadas de Pesaje:** [test_weighing_workflow.py](file:///D:/proyecto%20Vial/pavement_intelligence/tests/unit/test_weighing_workflow.py) y [test_weighing_ui.py](file:///D:/proyecto%20Vial/pavement_intelligence/tests/unit/test_weighing_ui.py)
* **Módulo de ESAL (Verificación de aislamiento):** [esal_calculator.py](file:///D:/proyecto%20Vial/pavement_intelligence/src/pavement_intelligence/ui/pages/esal_calculator.py)
* **Documentación técnica:** [INTEGRACION_TPDA_PESAJE.md](file:///D:/proyecto%20Vial/pavement_intelligence/docs/INTEGRACION_TPDA_PESAJE.md) y [ARQUITECTURA_FLUJO_TPDA_ESAL_DISENO.md](file:///D:/proyecto%20Vial/pavement_intelligence/docs/ARQUITECTURA_FLUJO_TPDA_ESAL_DISENO.md)

---

## 3. Pruebas Ejecutadas
Se ejecutó la suite completa de pruebas unitarias y de simulación de UI (`streamlit.testing.v1`):
* **Comando:** `$env:PYTHONPATH = "src"; .\.venv-new\Scripts\python.exe -m pytest -v`
* **Resultados:** **153 pruebas aprobadas, 0 fallidas** (tiempo de ejecución: 18.39 segundos).
* ** pip check:** **No broken requirements found.** (Verificado de manera exitosa).

---

## 4. Contrato TPDA → Pesaje
Se confirmó que el módulo de Pesaje consume **única y exclusivamente** el resultado oficial de tránsito en la clave:
`st.session_state["tpda_phase1_result"]`

No existe acoplamiento con claves prohibidas o informales (`tpda_result`, `traffic_counts_corrected`, `events`, etc.).

### Estructura de Transferencia (`WeighingInputFromTPDA`)
El contrato se genera mediante la función `build_weighing_input_from_tpda` como una copia de datos inmutable. Contiene todos los campos requeridos:
* `source_tpda_result_id` y `source_tpda_fingerprint` (identificador y huella de vigencia).
* `tpda_methodological_status` (debe ser `VALID_TO_CONTINUE` o `VALID_FOR_DEMONSTRATION`).
* `projected_traffic_by_category` y `base_tpda_by_category` (desglosado por categorías de la ABC).
* `growth_rate_percent`, `design_period_years`, `directional_factor` ($F_{DD}$), `lane_distribution_factor` ($F_{DC}$) y `projected_design_lane_traffic`.
* `is_synthetic` (booleano de datos sintéticos) y `demonstration_mode` (modo demostrativo).
* `reviewer`, `warnings` y `assumptions`.

*Observación de campos para ESAL:* Todos los campos requeridos para el cálculo de ESAL posterior (factores direccionales, carril y periodos) están incluidos en el contrato.

---

## 5. Validación de Categorías
* **CAMION_NO_CONFIRMADO Bloqueado:** No se permite asignar configuraciones de eje a la clase genérica `CAMION_NO_CONFIRMADO`. Si el aforo de origen contiene camiones sin clasificar, la transferencia es rechazada de inmediato.
* **Sin Ejes Automáticos:** Se ratifica que no se infieren ejes, configuraciones o pesos de manera implícita a partir de las clases visuales de YOLO. El software obliga al ingreso explícito o a la lectura detallada del CSV.
* **Separación de Vehículos Livianos:** Las categorías livianas (`MOTO`, `AUTO`, `CAMIONETA`, `MINIBUS`) se conservan a nivel estadístico de volumen de tránsito, pero se les excluye del requerimiento de asignación de cargas por eje en el pesaje, separando el daño estructural de la geometría general.
* **Manejo de Discrepancias:**
  - Si una categoría proyectada pesada no posee muestras de pesaje, el workflow no falla pero emite advertencias metodológicas claras.
  - Si el CSV de pesaje tiene categorías ausentes en el TPDA o de tránsito cero, la importación se rechaza para evitar datos huérfanos.

---

## 6. Validación de Ejes y Configuraciones
Se audita la representación inambigua de los ejes físicos:
* **Tipos soportados:** `simple_single` (1 eje), `simple_dual` (1 eje), `tandem` (2 ejes) y `tridem` (3 ejes).
* **Atributos por eje:** Se registran por separado la posición del grupo, el tipo de eje, la carga en kN y el origen. No se permiten tipos de ejes desconocidos (`unknown`).
* **Coherencia Física:** Cada vehículo (`WeighingObservation`) expone `gross_weight_kn` (peso bruto) y `axle_load_sum_kn` (suma de ejes). Si la diferencia entre ambos supera la tolerancia (ajustable, por defecto 5%), el registro se marca con advertencia o bloquea la aptitud técnica.
* **Suficiencia para ESAL:** Las configuraciones son totalmente explícitas y no ambiguas. Permiten a la fase posterior de ESAL calcular factores de equivalencia ($LEF$) aplicando directamente los factores de daño de la cuarta potencia por tipo de eje sin suposiciones adicionales.

---

## 7. Auditoría de Unidades
La unidad interna canónica de cálculo y almacenamiento en todo el workflow es el **kiloNewton (kN)**.
* **Conversión de Entrada:** Se validan de forma explícita las constantes físicas:
  - $\text{kN} \to \text{kN}$ (factor 1.0)
  - $\text{kg} \to \text{kN}$ (factor 0.00980665)
  - $\text{tonelada} \to \text{kN}$ (factor 9.80665)
* **Seguridad:** Cargas negativas, nulas o infinitas disparan excepciones de validación en el dominio.
* **UI:** La pantalla muestra claramente el texto *"Unidad interna canónica: kN"* y realiza la conversión en el backend antes de escribir la sesión.

---

## 8. Datos Sintéticos y Modo Demostrativo
El software implementa un flujo dual seguro para la hackatón:

### Flujo Productivo (Real)
* Requiere `is_synthetic = False` en TPDA y en todas las observaciones de carga.
* Si es consistente y válido, alcanza el estado `VALID_TO_CONTINUE` y la aptitud `APTO_PARA_ESAL`.

### Flujo Demostrativo (Sintético)
* Habilitado si el TPDA o las cargas WIM son sintéticas (ej. cargando `pesaje_vehicular.csv`).
* Exige que el usuario marque explícitamente la casilla: *"Reconozco que la cadena contiene datos sintéticos y es solo demostrativa"*.
* Si se reconoce, alcanza el estado `VALID_FOR_DEMONSTRATION` y la aptitud `APTO_SOLO_DEMOSTRACION`. Si no se reconoce, el flujo se bloquea bajo `BLOCKED_BY_SYNTHETIC_DATA`.
* *Este diseño es óptimo:* Protege la rigurosidad técnica al tiempo que permite una simulación de extremo a extremo defendible en la hackatón.

---

## 9. Invalidación y Conservación
* **Firmas de entrada:** La huella digital `input_fingerprint` de pesaje se genera serializando todo el lote de entrada (`WeighingWorkflowInput`).
* **Sincronización:** `weighing_result_is_stale` evalúa si el TPDA actual cambió o si la muestra de pesaje fue editada. Si hay cualquier desajuste de firmas, el resultado anterior se marca como desactualizado en la UI (`DESACTUALIZADO: cambió TPDA...`).
* **Preservación sin Borrado Silencioso:** Los cálculos desactualizados o históricos no se eliminan de la sesión. Al adoptar una nueva muestra, se archivan en `weighing_history` y `weighing_result_history`, permitiendo la reversión completa de los datos por parte del usuario.

---

## 10. Aislamiento respecto de ESAL
* **Consumo Prematuro Inexistente:** Se inspeccionó `esal_calculator.py` y se corroboró la total ausencia de consumo de `weighing_phase2_result` o `weighing_input_from_tpda`.
* Los indicadores `APTO_PARA_ESAL` y `APTO_SOLO_DEMOSTRACION` se exponen en pantalla como estados informativos de preparación metodológica y no realizan ninguna conexión automática silenciosa.

---

## 11. Cobertura de Pruebas
La suite de 153 pruebas unitarias y funcionales del proyecto provee una cobertura excelente para:
- Límites de tolerancia (peso bruto vs. suma de ejes).
- Conversiones de unidades métricas (kg, toneladas, kN) y rechazo de lb u otras no canónicas.
- Comportamientos de re-transferencias manuales con archivado de históricos.
- Invalidación automática del pesaje cuando se altera el tránsito de origen.
- Aislamiento e inmutabilidad de los contratos en sesión.

---

## 12. Checklist de Inspección Visual Manual para Streamlit

Al no contar con navegador gráfico automatizado, se recomienda al revisor humano validar los siguientes comportamientos visuales en Streamlit:

- [ ] **Origen del Tránsito:** Confirmar que la subsección 1 muestre un bloque JSON ordenado con el ID de TPDA, huella de tránsito y bandera sintética.
- [ ] **Decisión de Reemplazo:** Adoptar una muestra manual de pesaje, luego intentar subir un CSV y comprobar que Streamlit muestre el selector de radio para elegir explícitamente entre: *Conservar actual*, *Reemplazar e histórico* o *Cancelar*.
- [ ] **Advertencia de Datos Sintéticos:** Cargar el CSV demostrativo y validar que la UI bloquee el cálculo hasta que se tilde la casilla de reconocimiento de datos sintéticos.
- [ ] **Etiquetas de Unidades:** Verificar que el selector manual de unidades muestre claramente kg, toneladas y kN.
- [ ] **Visualización de Resultados Desactualizados:** Modificar una celda en Aforo y TPDA, regresar a la pantalla de Pesaje y comprobar que se visualice un recuadro de error indicando: *"DESACTUALIZADO: cambió TPDA..."* pero manteniendo el detalle del resultado anterior al final de la página.

---

## 13. Desviaciones y Bloqueos
* **Desviaciones:** *Ninguna*. La implementación sigue al pie de la letra el documento de diseño arquitectónico y corrige las vulnerabilidades de la fase previa.
* **Bloqueos:** *Ninguno*. La integración es segura y el módulo de pesaje está completamente cerrado e independiente.

---

## 14. Recomendación Final

### **`APROBADO PARA IMPLEMENTAR PESAJE → ESAL`**

*La Fase 2 de Integración TPDA → Pesaje está técnicamente cerrada, inmutable y verificada mediante pruebas automatizadas. El sistema está en condiciones óptimas para iniciar el diseño y desarrollo de la conexión de pesajes hacia el motor matemático de ESAL ($W_{18}$).*
