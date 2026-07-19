# Informe de Auditoría Técnica: Motor de Estimación Operativa de Congestión

**Proyecto:** Pavement Intelligence
**Módulo Movilidad:** `src/pavement_intelligence/domain/traffic/congestion.py`
**Módulo de Tests:** `tests/unit/test_congestion_engine.py`
**Clasificación Final:** **APROBADA**

Este informe presenta la auditoría técnica independiente sobre la implementación del motor de **Estimación Operativa de Congestión** (EOC) realizada por Codex.

---

## 1. Verificación de Contratos y Estructuras Públicas

Se han auditado los contratos definidos en `congestion.py`:
* **`CongestionLevel`**: Enum string con los cuatro estados definidos (`INSUFFICIENT_DATA`, `NORMAL`, `MODERATE`, `HIGH`). **Correcto.**
* **`CongestionInput`**: Dataclass congelada (`frozen=True`) para las métricas del intervalo. Implementa validadores rigurosos en `__post_init__` que rechazan valores inválidos (negativos, nulos, infinitos, timestamps regresivos y duraciones de observación inconsistentes con el timestamp del video). **Correcto.**
* **`CongestionThresholds`**: Dataclass congelada para los límites. Valida que los límites de salida sean siempre menores o iguales a los de entrada, y que los límites de nivel alto superen a los del nivel moderado. **Correcto.**
* **`CongestionEvidence`**, **`CongestionAssessment`** y **`CongestionAlert`**: Dataclasses congeladas e inmutables que encapsulan los resultados. La alerta establece explícitamente `normative=False` y `origin="OPERATIONAL_ESTIMATE"`, evitando confusión con niveles de servicio reglamentarios. **Correcto.**

---

## 2. Auditoría de la Máquina de Estados e Histeresis

* **Transiciones y Temporización**:
  * La inicialización empieza correctamente en `INSUFFICIENT_DATA`.
  * Se requiere que transcurran mínimo `10.0` segundos de observación y se acumulen al menos `3` muestras antes de emitir estimaciones (`NORMAL` o `MODERATE`).
  * La condición de congestión severa coloca el estado en `MODERATE` y marca el candidato a `HIGH` como pendiente.
  * Si la condición persiste de forma ininterrumpida durante `15.0` segundos (`high_confirmation_seconds`), el estado transiciona a `HIGH` y emite una alerta única.
  * Si la condición desaparece antes de los 15 segundos, el candidato se cancela limpiamente sin generar alertas huérfanas.
* **Histeresis**:
  * Implementa umbrales independientes de entrada y salida para evitar oscilaciones rápidas cerca de los límites (ej: entrada a moderado con 8 vehículos en escena; salida hacia normal solo con 5 o menos).
  * La salida del estado `HIGH` requiere una confirmación de recuperación sostenida de `5.0` segundos bajo los umbrales de salida. **Correcto.**

---

## 3. Comportamiento ante Pausas, Resets y Anomalías

* **Pausas**: Si `sample.is_paused` es `True`, el motor no altera los temporizadores internos de candidatos o recuperaciones y retiene el estado y la alerta actuales. La duración del intervalo no puede incrementarse durante la pausa (se lanza un error si ocurre).
* **Reset**: El método `reset()` borra toda la memoria de estados, timestamps, alertas y candidatos, volviendo al calentamiento inicial de forma determinista y segura.
* **Independencia Tecnológica**: La implementación no importa ni tiene acoplamientos con Streamlit, OpenCV, YOLO, ByteTrack, bases de datos, ni realiza escrituras en disco. Es una biblioteca de cálculo puro.

---

## 4. Cobertura y Resultados de Pruebas

Se ejecutó la suite de pruebas unitarias obteniendo los siguientes resultados:
* **Pruebas Coleccionadas**: 42 casos de prueba.
* **Pruebas Aprobadas**: 42 pasadas (100% de éxito en 0.06 segundos).
* **Cobertura Funcional**:
  * Calentamiento inicial y descarte por muestras insuficientes.
  * Transición con histeresis y bandas muertas.
  * Candidato a congestión alta y confirmación temporal exacta a los 15 segundos.
  * Pausa de reproducción y prevención de incremento de marcas de tiempo.
  * Reinicio completo (`reset()`) y reutilización segura de la misma instancia del motor.
  * Inmutabilidad de los diccionarios de conteo y copias defensivas de solo lectura (`MappingProxyType`).
  * Validación ante tipos inválidos, valores infinitos o NaN.

* **Vacíos de Cobertura**: Ninguno identificado para el alcance MVP definido. Las pruebas evalúan comportamiento lógico y no detalles internos de la implementación.

---

## 5. Coherencia Documental

La implementación en código es 100% coherente con los cuatro documentos metodológicos originales creados bajo `docs/mobility/`:
* Se respetan exactamente los nombres de los estados, umbrales demostrativos y la nomenclatura no normativa.
* El enmascaramiento y no mezcla de datos sintéticos con reales a nivel de UI se mantiene protegido.
* El informe de implementación de Codex describe fielmente las limitaciones actuales (como la necesidad de un agregador de intervalos).
