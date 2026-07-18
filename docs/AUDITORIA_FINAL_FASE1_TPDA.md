# Informe de Auditoría Técnica y Funcional: Cierre de la Fase 1
**Proyecto:** Pavement Intelligence (Plataforma de Análisis de Tránsito y Diseño de Pavimentos)  
**Estado:** Auditoría Final de Solo Lectura Aprobada  
**Fecha:** 2026-07-17  

---

## 1. Alcance de la Auditoría
Este informe evalúa el estado del software y del diseño metodológico tras el cierre de la **Fase 1: Aforo y TPDA** implementada por Codex. La auditoría se realiza de forma estrictamente de solo lectura, sin modificar código de producción o pruebas, contrastando la base de código actual con la especificación de integración técnica de referencia:

* [ARQUITECTURA_FLUJO_TPDA_ESAL_DISENO.md](file:///D:/proyecto%20Vial/pavement_intelligence/docs/ARQUITECTURA_FLUJO_TPDA_ESAL_DISENO.md)
* [CIERRE_FASE1_AFORO_TPDA.md](file:///D:/proyecto%20Vial/pavement_intelligence/docs/CIERRE_FASE1_AFORO_TPDA.md)

---

## 2. Verificaciones Realizadas (Checklist de 14 Puntos Obligatorios)

1. **Fórmulas no Duplicadas en UI:**  
   *Confirmado.* Se verificó que `src/pavement_intelligence/ui/pages/survey_tpda.py` no tiene la operación `24.0 /` ni llama directamente a subfunciones matemáticas como `calculate_tpda` o `project_traffic_exponential`. Toda la matemática se delega en la función central del dominio `calculate_tpda_workflow`.
2. **Expansión Temporal Única:**  
   *Confirmado.* El motor metodológico en `tpda_workflow.py` evalúa de forma excluyente el método de expansión. Si la duración es menor a 24 horas, se aplica *o bien* la expansión uniforme $24/\text{duración}$ *o bien* el factor temporal documentado, pero nunca ambos.
3. **No Mapeo Automático de Camiones a C2:**  
   *Confirmado.* En `classify_visual_events`, los vehículos etiquetados originalmente como `CAMION` o `TRUCK` se clasifican bajo la categoría temporal `CAMION_NO_CONFIRMADO` (`PENDING_TRUCK_CATEGORY`), evitando la asignación automática por defecto.
4. **Bloqueo por Categoría Pendiente:**  
   *Confirmado.* Si la cantidad de `CAMION_NO_CONFIRMADO` es mayor a 0, el estado metodológico resultante cambia a `BLOCKED_BY_CLASSIFICATION` y deshabilita la bandera `methodologically_fit_for_next_phase` para evitar el avance técnico.
5. **Aislamiento de Datos Sintéticos:**  
   *Confirmado.* Si el indicador `is_synthetic` es `True`, el estado metodológico es forzado a `VALID_FOR_DEMONSTRATION` (si fue explícitamente reconocido por el usuario) o `BLOCKED_BY_SYNTHETIC_DATA` (si no lo fue). Esto garantiza que los datos de prueba nunca alcancen el estado de producción `VALIDO_PARA_CONTINUAR`.
6. **Factores $f_n$ y $f_e$ No Oficiales:**  
   *Confirmado.* Ambos factores se registran con el estado `DEFINIDO_POR_USUARIO_NO_OFICIAL`. En caso de que se configure un factor diferente a 1.0 (identidad) sin declarar su fuente formal, el flujo bloquea la aptitud metodológica emitiendo un warning de expansión.
7. **Lineal A Excluida:**  
   *Confirmado.* El método de proyección `LINEAR_A` no existe dentro de las opciones admisibles del enum `ProjectionMethod`. La UI de Streamlit solo lo menciona conceptualmente con fines educativos como "experimental y no seleccionable".
8. **Independencia de FDD y FDC:**  
   *Confirmado.* Los factores de dirección ($F_{DD}$) y de carril ($F_{DC}$) se aplican únicamente al final sobre el volumen total proyectado para calcular el tránsito por carril de diseño. No alteran ni modifican el cálculo del TPDA base.
9. **Conservación de Resultados Desactualizados:**  
   *Confirmado.* Si se edita una variable del formulario, el sistema calcula un nuevo fingerprint de entrada. El resultado anterior en la sesión no se borra ni se sobrescribe silenciosamente; se mantiene visible y se le asigna el estado `DESACTUALIZADO_REQUIERE_RECALCULO` exigiendo un recálculo manual.
10. **Contrato Formal Único:**  
    *Confirmado.* El objeto resultante de los cálculos se almacena de forma estructurada e independiente bajo la clave de sesión `tpda_phase1_result`, el cual contiene todos los metadatos técnicos.
11. **No Consumo Prematuro:**  
    *Confirmado.* No se encontraron referencias a la clave de sesión `tpda_phase1_result` ni importaciones del flujo en las pantallas inactivas de Pesaje o ESAL.
12. **Cálculos y Estados de Dominio:**  
    *Confirmado.* El estado metodológico de aptitud se determina dinámicamente mediante las reglas de negocio de `calculate_tpda_workflow` en `tpda_workflow.py`, y no por lógica visual de la interfaz.
13. **Metadatos de Trazabilidad Completa:**  
    *Confirmado.* El objeto `TPDAWorkflowResult` almacena de forma inalterable las claves requeridas: `calculation_id`, `batch_id`, `source`, `automatic_counts`, `corrected_counts`, `pending_categories`, `declared_duration_hours`, `verified_duration_hours`, `duration_source`, `expansion_method`, `final_expansion_factor`, `tpda_base_total`, `tpda_by_category`, `projection_method`, `growth_rate_percent`, `design_period_years`, `projected_traffic_total`, `directional_factor`, `lane_distribution_factor`, `warnings`, `assumptions`, `is_synthetic`, `calculated_at` y `schema_version`.
14. **Calidad de Pruebas Unitarias:**  
    *Confirmado.* Las 120 pruebas automatizadas pasan de forma exitosa (0 fallas). En particular, se validó que `test_tpda_workflow.py` y `test_survey_tpda_ui.py` evalúan explícitamente escenarios límite (aforos parciales de 2h, aforos de 24h sin evidencia, bloqueos de reclasificación de camiones y desactualizaciones de parámetros en UI).

---

## 3. Comparativa con la Arquitectura

### Coincidencias
* **Inmutabilidad y Aislamiento:** El resultado de la Fase 1 se encapsula en una estructura inmutable (`TPDAWorkflowResult`), evitando la dispersión de datos primitivos en la sesión.
* **Trazabilidad Integral:** Se conservan las huellas digitales del lote auditado, previniendo discrepancias técnicas.

### Desviaciones
* *Ninguna detectada en el flujo de tránsito.* La implementación se apega de forma exacta a los lineamientos arquitectónicos y añade una validación estricta del origen temporal del CSV de entrada que no estaba contemplada en el diseño inicial.

### Deuda Técnica
* **Normalización de Geotecnia:** Los datos de suelos en `soil_study.py` aún se almacenan de manera cruda y primitiva. Se recomienda migrar este módulo para que genere un `SoilStudyResult` inmutable antes de conectar el módulo de diseño final de pavimentos.

### Riesgos de Integración
* **Riesgo de Traspaso Desactualizado:** Si bien la UI de TPDA marca visualmente como "DESACTUALIZADO" cuando cambia una entrada, si el usuario decide avanzar de pestaña en Streamlit sin recalcular, la sesión podría contener un resultado obsoleto. Se requerirá un check de validación al inicio de la fase de Pesaje.

---

## 4. Campos a Consumir por `WeighingResult` y Transferencia

### Campos que Pesaje/ESAL consumirán de `tpda_phase1_result`:
* `projected_traffic_by_category`: Para mapear los volúmenes de tránsito proyectado y aplicar los factores de daño por tipo de camión.
* `is_synthetic`: Para heredar la marca de datos de simulación en el cálculo final de ESAL.
* `methodologically_fit_for_next_phase`: Debe ser estrictamente `True` para habilitar cualquier cálculo de ESAL basado en tránsito real.

### Campos que NO deben transferirse automáticamente:
* Los factores de daño del catálogo: Deben definirse localmente en ESAL y no importarse del aforo.
* Las configuraciones de báscula de pesaje: Son exclusivas de la estación WIM.

### Condiciones exactas para habilitar el botón de transferencia a Pesaje:
1. `tpda_phase1_result` debe existir en la sesión.
2. `tpda_phase1_result.methodologically_fit_for_next_phase` debe ser `True` (o en su defecto `VALID_FOR_DEMONSTRATION` con advertencia de datos sintéticos aceptados).
3. `tpda_phase1_result.is_stale` debe ser `False`.

---

## 5. Checklist de Inspección Visual Manual para Streamlit

Al no contar con un navegador web gráfico interactivo en este entorno, se define la siguiente lista de verificación manual para que el ingeniero de control de calidad valide visualmente la interfaz de Streamlit en un navegador real:

- [ ] **Etiquetas de Entrada:** Comprobar que los campos de factores de expansión ($f_n$ y $f_e$) muestren con claridad la etiqueta "Definido por el usuario (No oficial)".
- [ ] **Advertencias de Cobertura:** Cargar un CSV sin marcas temporales y verificar que aparezca el recuadro amarillo indicando: *"El archivo o registro fue declarado como aforo de 24 horas, pero su cobertura temporal no puede verificarse automáticamente."*
- [ ] **Estados Metodológicos:** Verificar que al registrar reclasificaciones parciales de camiones, el widget de estado muestre `BLOQUEADO_POR_CLASIFICACION` en color amarillo/rojo.
- [ ] **Botones de Registro:** Validar que el botón *"Registrar reclasificación"* se deshabilite si no se ingresa un revisor y una justificación técnica en los campos de texto.
- [ ] **Mensajes Sintéticos:** Validar que al activar el modo demostrativo sintético, aparezca un cartel rojo prominente advirtiendo: *"DATOS SINTÉTICOS - DEMOSTRACIÓN MVP"*.
- [ ] **Comportamiento al Recalcular:** Cambiar la duración de un aforo calculado de 24h a 12h y confirmar que el recuadro del cálculo anterior cambie inmediatamente a color rojo con la leyenda: *"DESACTUALIZADO - REQUIERE RECALCULO"*.

---

## 6. Recomendación Final

### **`APROBADO PARA IMPLEMENTAR TDPA → PESAJE`**

*La Fase 1 de Aforo y TPDA de Pavement Intelligence cumple con todos los criterios de seguridad metodológica, consistencia conceptual, contratos formales y cobertura de pruebas automatizadas.*
