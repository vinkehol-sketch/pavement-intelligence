# Hoja de Ruta de Implementación de Doble Fuente

Este documento define el plan de desarrollo e integración progresiva en cuatro fases para dar soporte al procesamiento independiente de tránsito vehicular y lecturas OCR de matrículas.

---

## 1. Plan Progresivo de Integración (Fases A a D)

```
+------------------------------------------------------------------------+
| FASE A: Ejecución y Lotes Separados (MVP Recomendado)                  |
| -> Un video para conteo panorámico y un video diferente para OCR.       |
| -> Se ejecutan de forma secuencial y aislada.                          |
| -> Lotes y pantallas de revisión completamente independientes.          |
+------------------------------------------------------------------------+
                                   |
                                   v
+------------------------------------------------------------------------+
| FASE B: Alternación en la misma Sesión                                 |
| -> Dos fuentes (Tránsito y OCR) cargadas en la misma pestaña de la UI.  |
| -> Análisis alternado (el usuario conmuta la visualización).            |
| -> Sin procesamiento simultáneo de inferencias para proteger CPU.      |
+------------------------------------------------------------------------+
                                   |
                                   v
+------------------------------------------------------------------------+
| FASE C: Procesamiento Simultáneo Completo                              |
| -> Dos flujos reproduciendo en vivo de forma paralela en la pantalla.   |
| -> Controladores y subprocesos asíncronos independientes.               |
| -> Límites de hardware e inferencia intermitente (N frames) en CPU.    |
+------------------------------------------------------------------------+
                                   |
                                   v
+------------------------------------------------------------------------+
| FASE D: Asociación Espacial-Temporal por Evidencia                     |
| -> Motor de emparejamiento por ventana de coincidencia temporal.       |
| -> Panel para confirmación, rechazo o revocación manual del operador.  |
+------------------------------------------------------------------------+
```

---

## 2. Requerimientos para OCR Real en Producción

Para migrar la pantalla actual de placas sintéticas a lecturas físicas reales se debe incorporar:
1. **Localizador de Placa**: Un modelo YOLOv8-Plates o heurísticas de segmentación OpenCV para recortar el área rectangular de la matrícula dentro del bounding box del vehículo.
2. **Preprocesamiento**: Rotación (homografía para corregir perspectiva) e incremento de contraste adaptativo en el recorte.
3. **Inferencia**: Inicialización del lector `PaddleOCRPlateReader` bajo demanda.
4. **Anonimización en Origen**: Identificador derivado de SHA-256 y truncado a 8 caracteres, generado en el módulo de visión, y descarte de imágenes de matrículas legibles excepto las guardadas en la bitácora de evidencias.

---

## 3. Archivos que Codex Deberá Crear o Modificar

* **`src/pavement_intelligence/vision/analysis/ocr_controller.py`** (NUEVO):
  * Clase `PlateAnalysisController` para gestionar el estado del procesamiento OCR de placas, independiente del aforo.
* **`src/pavement_intelligence/ui/app.py`** (MODIFICAR):
  * Conectar y ordenar el menú de navegación para reflejar el Centro de Monitoreo Dual y las dos pantallas de revisión.
* **`src/pavement_intelligence/ui/pages/traffic_monitoring.py`** (MODIFICAR):
  * Reestructurar la pantalla agregando pestañas de Streamlit (`st.tabs`) para separar el reproductor de "Conteo Vehicular" del reproductor de "Reconocimiento OCR".
* **`src/pavement_intelligence/domain/traffic/association.py`** (NUEVO):
  * Heurística de asociación espacio-temporal por tolerancia configurable.

---

## 4. Primer Incremento Implementable (Fase A)

* **Alcance**:
  * Separar la interfaz del Centro de Monitoreo en dos secciones independientes ("Conteo y Clasificación" y "Lectura OCR").
  * Implementar el lector `PlateAnalysisController` para leer un video cerrado de placas de prueba y guardar las lecturas en `st.session_state["ocr_batch_readings"]` de forma independiente a los conteos.
* **Criterios de Aceptación**:
  * La inicialización, ejecución, pausa o error en la pestaña de Conteo no afecta la adquisición de la pestaña de Placas OCR.
  * Presionar "Finalizar" en Tránsito produce un lote con `validation_status = 'sin_revisar'` en el aforo, sin interferir en los registros OCR de la sesión.
* **Riesgo**: Sobrecarga de memoria en CPU si el usuario inicia ambos flujos simultáneamente sin GPU. *Mitigación*: Desactivar el botón de inicio de una fuente si la otra fuente está reproduciendo activamente.

La Fase D es opcional y no bloquea las fases anteriores. Sus candidatos se basan en evidencia, nunca en `track_id` compartidos entre cámaras, y solo adquieren estado confirmado mediante acción manual. Toda confirmación es reversible con auditoría y no puede retroalimentar ni alterar conteo, clasificación, sentido, aprobación, TPDA, ESAL o diseño de pavimentos.
