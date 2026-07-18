# Plan de Pruebas para la Integración de OCR (Corregido)

Este plan de pruebas detalla la estrategia de validación técnica, funcional y de rendimiento para asegurar la fiabilidad de la futura integración del módulo de reconocimiento de placas (OCR). Las pruebas de visión y procesamiento son estrictamente independientes de la interfaz gráfica y de Streamlit.

---

## 1. Estrategia de Pruebas Unitarias (Capa de Visión Pura)

Las pruebas unitarias del pipeline de visión se alojan bajo `tests/unit/ocr/` y no dependen en ningún caso de `st.session_state` ni de Streamlit.

### A. Casos de Prueba para la Infraestructura Existente (Fase 1)
* **Validación de `PlateResult`**: Verificar el correcto tipado de la dataclass.
* **Prueba inicial sobre imagen individual**: Procesar una imagen sintética aislada, sin video y sin invocar `VisionPipeline`, usando un mock de la dependencia opcional PaddleOCR.
* **Prueba de Hashing en `PaddleOCRPlateReader`**: Instanciar el lector y verificar que al ingresar una placa ficticia (ej: `"1024ABC"`), el método `_hash_plate` genera un hash SHA-256 en mayúsculas, truncado a 8 caracteres, y que el texto crudo se descarta si la anonimización está activa.

### B. Casos de Prueba para el Evaluador de Calidad e IoU
* **Prueba de IoU Nivel de Pixel (Sin Shapely)**: Proveer coordenadas de dos cajas delimitadoras y comprobar que la función matemática calcula correctamente la tasa de intersección sobre unión.
  * Rectángulos idénticos $\rightarrow$ IoU = `1.0`.
  * Sin solape $\rightarrow$ IoU = `0.0`.
  * Solape parcial $\rightarrow$ Validar contra cálculo analítico matemático.
* **Prueba de Nitidez**: Evaluar imágenes sintéticas de contraste alto frente a imágenes difuminadas con desenfoque gaussiano, comprobando el correcto orden de puntuación en el evaluador de nitidez Laplaciana.

### C. Casos de Prueba para `OcrConsensusManager`
* **Prueba de Votación y Distancia**: Alimentar el gestor con tres lecturas asociadas al mismo track: `["GHK492", "GHK492", "GHK472"]`. Verificar que la salida elegida es `GHK492`.
* **Prueba de Alternativas**: Asegurar que la bitácora del consenso retenga las lecturas perdedoras en una lista ordenada para la auditoría manual.

---

## 2. Estrategia de Pruebas de Integración y Adaptación de UI

Estas pruebas validan los contratos en los límites del sistema (frontera entre el motor de visión neutral y los controladores de Streamlit).

* **Prueba del Adaptador de Presentación**:
  * Proveer una instancia de `PlateReadingResult` y `PlateEvidence`.
  * Invocar `OcrPresentationAdapter.to_presentation_model`.
  * Comprobar que el diccionario resultante contiene la lectura enmascarada (ej. `***-492`) en lugar del texto crudo, y que todos los campos requeridos por la UI Streamlit están presentes.
* **Prueba de Integridad del Conteo**:
  * Conservar un snapshot inmutable de un contrato de aforo antes de adaptar resultados OCR neutrales.
  * Verificar que la adaptación y edición OCR no altera categoría, sentido, conteos, aprobación ni entradas de TPDA.
  * No importar Streamlit ni escribir en `st.session_state` desde estas pruebas de integración neutral.

`src/pavement_intelligence/vision/pipeline.py` queda fuera de alcance hasta la fase final. Sus pruebas de integración con video se habilitan únicamente cuando exista una tarea posterior y explícita para el hook opcional.

---

## 3. Pruebas de Calidad Bajo Condiciones Ambientales Complejas

Para evaluar el comportamiento del sistema ante video real desfavorable, se utilizará una matriz de pruebas basadas en clips de video de calibración:

| Condición del Test | Entrada de Prueba | Comportamiento Esperado | Criterio de Aceptación |
| :--- | :--- | :--- | :--- |
| **Baja Resolución** | Video aforo 480p pixelado | Descarte por tamaño de bbox | El detector descarta imágenes inferiores a `120x120px` sin hacer inferencias. |
| **Iluminación Nocturna** | Faros de frente (Glare) | Detección de baja confianza | El texto se lee parcialmente y el sistema lo clasifica como `status = confianza_baja`. |
| **Perspectiva / Ángulo** | Ángulo de cámara > 30° | Rectificación de homografía | Se aplica la corrección de perspectiva antes del OCR para re-alinear caracteres. |
| **Oclusión** | Auto detrás de camión | Detección de IoU alto (>0.15) | El evaluador detecta la proximidad de cajas y descarta el fotograma para evitar lecturas truncadas. |

---

## 4. Matrículas Ficticias de Validación (Juego de Datos de Prueba)

Se mantendrán las siguientes matrículas deliberadamente ficticias en los archivos de fixtures de test; no corresponden a observaciones, personas o vehículos reales:

* **`1024ABC`**: Boliviano clásico. Formato esperado correcto.
* **`5932XYZ`**: Boliviano clásico. Formato esperado correcto.
* **`GHK492`**: Para pruebas de variación y consenso (ej. `GHK4?2` corregido a `GHK492`).
* **`ABC-1234`**: Formato Mercosur para probar flexibilidad del validador de expresiones regulares.
* **`9999ZZZ`**: Registro duplicado para testear agrupamiento por ventanas de tiempo menores a 5 segundos.
* **`0000ERR`**: Lectura que debe marcarse automáticamente como `ilegible` en el pipeline.
