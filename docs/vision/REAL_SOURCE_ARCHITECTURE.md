# Arquitectura Técnica para Integración de Fuentes Reales

Este documento define la arquitectura técnica y el reparto de responsabilidades para integrar transmisiones de video físico y cámaras locales en el Centro de Monitoreo de Tránsito sin generar acoplamientos rígidos con Streamlit.

---

## 1. Diseño Arquitectónico Modular

La arquitectura separa estrictamente la entrada de datos (fuentes de video/cámara), la lógica de procesamiento (controlador y pipeline de visión) y la capa de presentación (Streamlit).

```
+-------------------------------------------------------------------------------+
|                             CAPA DE ADQUISICIÓN                               |
|   +-----------------------------------------------------------------------+   |
|   |                       Interfáz FrameSource                            |   |
|   |           [VideoFileSource]           [CameraSource]                  |   |
|   +-----------------------------------------------------------------------+   |
+-------------------------------------------------------------------------------+
                                        |
                                        | (Entrega de FrameResult BGR)
                                        v
+-------------------------------------------------------------------------------+
|                            CAPA DE CONTROL NEUTRAL                            |
|   +-----------------------------------------------------------------------+   |
|   |                      TrafficAnalysisController                        |   |
|   |   - Controla estado: PLAY, PAUSE, RESET, STOP                         |   |
|   |   - Encolamiento y llamadas a VisionPipeline                          |   |
|   +-----------------------------------------------------------------------+   |
+-------------------------------------------------------------------------------+
                                        |
                                        | (Ejecución de inferencias)
                                        v
+-------------------------------------------------------------------------------+
|                             CAPA DE PROCESAMIENTO                             |
|   +-----------------------------------------------------------------------+   |
|   |                            VisionPipeline                             |   |
|   |   - YOLOv8 Detector + ByteTrack                                       |   |
|   |   - Conteo por VirtualLineCounter                                     |   |
|   +-----------------------------------------------------------------------+   |
+-------------------------------------------------------------------------------+
                                        |
                                        | (Retorna FrameAnalysisResult BGR)
                                        v
+-------------------------------------------------------------------------------+
|                             CAPA DE PRESENTACIÓN                              |
|   +-----------------------------------------------------------------------+   |
|   |                      Adaptador de Presentación                        |   |
|   |   - Conversión BGR a RGB, serialización y empaquetado de métricas    |   |
|   +-----------------------------------------------------------------------+   |
|                                       |
|                                       v
|   +-----------------------------------------------------------------------+   |
|   |                 Páginas Streamlit (Centro de Monitoreo)                |   |
|   |   - st.image, st.metric, st.session_state                             |   |
|   +-----------------------------------------------------------------------+   |
+-------------------------------------------------------------------------------+
```

---

## 2. Definición de Responsabilidades

### A. Capa de Adquisición (`FrameSource`)
* **Responsabilidad**: Conectarse al hardware de la cámara o abrir el archivo de video. Lee fotograma a fotograma en formato de matriz BGR de OpenCV y expone metadatos del flujo (FPS, resolución).
* **Independencia**: No tiene noción de YOLO, del pipeline de conteo, ni de Streamlit.

### B. Capa de Control (`TrafficAnalysisController`)
* **Responsabilidad**: Orquestar el flujo de análisis.
  * Mantiene las referencias a la fuente activa (`FrameSource`) y al pipeline de análisis (`VisionPipeline`).
  * Expone `start()`, `pause()`, `resume()`, `reset()`, `finish()` y `close()`.
  * Llama secuencialmente a `FrameSource.read()` y le pasa el frame resultante a `VisionPipeline.process_frame()`.
  * Empaqueta el fotograma anotado y los eventos generados en un resultado tipado: `FrameAnalysisResult`.
* **Independencia**: **El controlador es una clase pura de Python. No importa ni utiliza ninguna variable o función de Streamlit (`st.xxx`).** Esto permite ejecutar auditorías, simulaciones o ejecuciones en consola (`headless`) usando el mismo controlador.

### C. Capa de Procesamiento (`VisionPipeline`)
* **Responsabilidad**: Procesar el frame crudo para detectar y realizar el seguimiento de vehículos, determinar cruces de línea virtual y dibujar overlays gráficos de inferencia (bounding boxes y líneas).
* **Independencia**: Solo procesa matrices de NumPy y devuelve objetos del dominio (`TrafficEvent`). No conoce el origen del frame ni la UI.

### D. Capa de Presentación (Streamlit / Adaptador)
* **Adaptador**: Convierte el frame BGR de OpenCV a formato RGB compatible con Streamlit y transforma las métricas crudas en estructuras listas para la UI.
* **Página Streamlit**: Dibuja los componentes en pantalla, gestiona la interacción del usuario con botones (Play/Pause/Reset) y actualiza los placeholders dinámicos.

---

## 3. Contratos de Interfaz Clave

### A. FrameAnalysisResult (Tipado Neutral)
```python
@dataclass(frozen=True)
class FrameAnalysisResult:
    frame_index: int
    timestamp_seconds: float
    source_type: str
    annotated_frame: np.ndarray | None
    detections: tuple[Mapping[str, object], ...]
    active_tracks: tuple[int, ...]
    crossing_events: tuple[TrafficEvent, ...]
    category_counts: Mapping[str, int]
    direction_counts: Mapping[int, int]
    vehicles_in_scene: int
    total_crossings: int
    processing_fps: float
    warnings: tuple[str, ...]
    end_of_source: bool
    congestion: str
```

---

## 4. Trazabilidad e Integridad del Aforo

### A. Conservación de Eventos para Revisión Oficial (Sin Aprobación Automática)
* Al finalizar, cada `TrafficEvent` pasa por `build_traffic_event_batch`; el lote validado se entrega a las claves oficiales de revisión (`vision_events_raw`, `vision_events_reviewed` y `vision_batch_metadata`).
* Al crearse, su estado inicial es de forma obligatoria `sin_revisar`.
* La visualización es informativa. **Ningún vehículo se aprueba automáticamente y el monitoreo no transfiere datos directamente a TPDA.** La revisión, aprobación y cualquier transferencia manual posterior son acciones separadas en sus pantallas oficiales.

### B. Prevención de Mezcla de Métricas Sintéticas y Reales
* Se utiliza la clave booleana `st.session_state["is_synthetic_review"]` para marcar el origen del lote.
* Si el operador inicia un análisis real (cámara en vivo o video pregrabado):
  1. El sistema verifica si existen datos sintéticos demostrativos en curso.
  2. Si es así, limpia por completo la memoria de eventos temporales:
     ```python
     if st.session_state.get("is_synthetic_review", False):
         st.session_state["vision_events_raw"] = []
         st.session_state["vision_events_reviewed"] = []
         st.session_state["traffic_review_approved"] = False
         st.session_state["is_synthetic_review"] = False
     ```
  3. Esto asegura que el reporte final de aforo contenga únicamente datos reales medidos por el pipeline físico.

### C. Ciclo de vida

Pausar mantiene la fuente abierta y continuar conserva su posición. Reiniciar cierra y reabre la fuente y crea detector, ByteTrack, contador, eventos y `VisionPipeline` nuevos. Finalizar, cambiar de fuente y cualquier error cierran explícitamente; `close()` es idempotente. `YOLODetectorTracker` no se cachea porque `model.track(..., persist=True)` conserva tracking mutable.
