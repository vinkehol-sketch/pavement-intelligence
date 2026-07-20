# Plan de Pruebas para Monitoreo con Doble Fuente

Este plan de pruebas define la estrategia de aseguramiento de calidad (QA) para verificar el correcto aislamiento de las fuentes de tráfico y OCR, el control de concurrencia y el motor de asociación espacio-temporal por evidencia.

---

## 1. Pruebas Unitarias Aisladas (Visión y Asociación)

Estas pruebas no dependen de Streamlit y se ejecutan directamente en `pytest` en la ruta `tests/unit/test_dual_source_logic.py`.

### A. Pruebas de Aislamiento de Sesiones
* **`test_independent_state_transitions`**:
  * *Acción*: Instanciar `TrafficAnalysisController` y `PlateAnalysisController`. Poner uno en estado `RUNNING` y el otro en `PAUSED`.
  * *Verificación*: Comprobar que los estados y los contadores de frames de cada controlador se modifican de forma independiente y que llamar a `reset()` en uno no altera la memoria del otro.

### B. Pruebas del Motor de Asociación Heurística (Fase D)
* **`test_successful_association_within_tolerance`**:
  * *Entrada*: Un evento de tránsito de camión en $t=12.0$ (sentido `N-S`) y una lectura de placa en $t=13.5$ (sentido `N-S`). Tolerancia = `3.0` segundos.
  * *Verificación*: `OptionalSourceAssociation` evalúa el caso, clasifica la relación como `CANDIDATE` con un puntaje de coincidencia alto y rellena los datos de evidencia.
* **`test_rejection_due_to_direction_mismatch`**:
  * *Entrada*: Vehículo en $t=12.0$ (sentido `N-S`), placa en $t=13.0$ (sentido `S-N`).
  * *Verificación*: La asociación se marca como `UNASSOCIATED` o se descarta debido a la discrepancia en la dirección.
* **`test_ambiguity_handling_with_multiple_candidates`**:
  * *Entrada*: Vehículos en $t=12.0$ y $t=12.5$ en el mismo carril. Lectura de placa en $t=12.2$.
  * *Verificación*: El motor clasifica ambas sugerencias automáticas en estado `AMBIGUOUS`, requiriendo la intervención y confirmación manual del operador.
* **`test_association_is_optional_reversible_and_non_authoritative`**:
  * *Acción*: Crear un candidato, confirmarlo manualmente y revocar después la confirmación con identidad y motivo.
  * *Verificación*: La transición conserva la evidencia y la auditoría, y no modifica conteo, clasificación, sentido, aprobación, TPDA, ESAL ni diseño de pavimentos.
* **`test_track_ids_are_source_local`**:
  * *Acción*: Producir identificadores de seguimiento iguales o diferentes en ambas cámaras.
  * *Verificación*: El motor no utiliza `track_id` para asociar fuentes y solo considera la evidencia declarada por el contrato.

---

## 2. Pruebas de Integración y Sesión Streamlit

* **`test_session_keys_isolation`**:
  * *Acción*: Simular el inicio de adquisición simultáneo de ambas fuentes usando `AppTest` de Streamlit.
  * *Verificación*: Comprobar que la interacción con los controles de la pestaña "Lectura OCR" altera únicamente las claves con prefijo `plate_session_` en `st.session_state` y no toca ninguna clave `traffic_session_`.
* **`test_concurrency_lock`**:
  * *Acción*: Iniciar reproducción de video de tránsito. Intentar iniciar reproducción de video OCR en CPU.
  * *Verificación*: Verificar que el botón de inicio de OCR se bloquea o que la tasa de refresco del fragmento se limita para evitar sobrecargas de CPU.

---

## 3. Matriz de Pruebas de Asociación ante Escenarios Viales Complejos

| Escenario de Tránsito | Entrada Cámara Tránsito | Entrada Cámara OCR | Comportamiento Esperado | Criterio de Aceptación |
| :--- | :--- | :--- | :--- | :--- |
| **Paso de Convoy** | 3 vehículos en 2 segundos | 3 placas en 2 segundos | Clasificación `AMBIGUOUS` en los 3 registros. | El sistema impide la asociación automática de los 3 registros e inyecta la alerta visual para forzar la auditoría manual. |
| **Desfase de Relojes** | Vehículo registrado en t=10 | Placa registrada en t=25 | Clasificación `UNASSOCIATED`. | La diferencia temporal supera el umbral límite y los eventos permanecen desvinculados. |
| **Error de Lectura** | Vehículo Camión detectado | Placa no leída (Ilegible) | No se crea asociación. | La lectura OCR se almacena con `status = ILLEGIBLE` y el evento de tránsito continúa huérfano. |
| **Confirmación de Operador**| Estado inicial `CANDIDATE` | Estado inicial `CANDIDATE` | Estado cambia a `MANUALLY_CONFIRMED`. | Al presionar "Confirmar Asociación", se guarda la identidad del revisor; una revocación posterior exige otra acción manual, motivo y trazabilidad. |
