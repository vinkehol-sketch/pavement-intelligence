# Auditoría de Integración de Fuentes de Video y Cámara Reales

Este documento presenta la auditoría de los componentes y abstracciones existentes en el proyecto Pavement Intelligence para capturar, procesar y visualizar transmisiones de video en tiempo real y cámaras locales.

---

## 1. Análisis de Componentes de Captura Existentes

Se ha auditado el directorio `src/pavement_intelligence/vision/capture/` y se identificaron los siguientes contratos e implementaciones funcionales:

### A. Contratos e Interfaces (`src/pavement_intelligence/vision/capture/base.py`)
* **`FrameSource`** (antes `AbstractVideoSource`): Clase abstracta (ABC) que define el contrato puro para la lectura secuencial de fotogramas, independiente de Streamlit y del pipeline de inferencia.
  * Métodos definidos: `open()`, `read()`, `close()`, `is_open()`, `source_info()`.
  * Context Manager integrado: Permite el uso seguro con sentencias `with` para la liberación garantizada de recursos.
* **`FrameResult`**: Dataclass que encapsula la salida de la lectura de un fotograma:
  * `frame` (`Optional[np.ndarray]`): Matriz de píxeles en formato BGR de OpenCV.
  * `frame_number` (`int`): Indice secuencial del frame.
  * `timestamp_ms` (`float`): Marca de tiempo del frame en milisegundos.
  * `success` (`bool`): Indica si el frame se leyó correctamente.
  * `source_id` (`str`): Identificador textual del origen del video.
* **`SourceInfo`**: Dataclass congelada (`frozen=True`) con los metadatos de la fuente (FPS, resolución, total de frames).

### B. Implementación de Video Pregrabado (`src/pavement_intelligence/vision/capture/file_source.py`)
* **`VideoFileSource`**: Implementación de `FrameSource` para archivos locales (`.mp4`, `.avi`, `.mov`, `.mkv`).
  * Utiliza `cv2.VideoCapture` de OpenCV bajo el capó.
  * Implementa `reset()`, permitiendo reposicionar el puntero de reproducción al inicio (`CAP_PROP_POS_FRAMES = 0`) de manera eficiente sin reabrir el archivo.
  * Proporciona la resolución (`width`, `height`) y el número total de frames (`total_frames`).

### C. Implementación de Cámara Local (`src/pavement_intelligence/vision/capture/camera_source.py`)
* **`CameraSource`**: Implementación de `FrameSource` para dispositivos físicos mediante el índice del canal de captura (ej. cámara `0` integrada o USB).
  * Inicializa `cv2.VideoCapture(camera_index)`.
  * Valida que el índice sea un entero válido en el rango `[0, 9]`.
  * Implementa la lectura de flujo dinámico incrementando el contador de frames y estimando marcas de tiempo basadas en los FPS del hardware.

---

## 2. Componentes de Inferencia y Overlays Existentes

### A. Pipeline de Visión (`src/pavement_intelligence/vision/pipeline.py`)
* **`VisionPipeline`**: Componente de orquestación. Recibe un frame crudo a través de `process_frame` y:
  * Ejecuta la detección YOLOv8 y el tracking a través de `AbstractDetectorTracker`.
  * Dibuja de manera nativa (mediante OpenCV `cv2.line`, `cv2.rectangle`, `cv2.putText`) los overlays de visualización: línea virtual de conteo, rectángulos de delimitación (bounding boxes), centroides, y etiquetas de texto de clases/ID de seguimiento.
  * Invoca al contador virtual `VirtualLineCounter` para detectar cruces de línea.
  * Retorna una tupla conteniendo el frame modificado (`np.ndarray`) y una lista de nuevos objetos `TrafficEvent` generados en ese frame.

---

## 3. Puntos de Reutilización de Código

Existe un alto grado de desacoplamiento que permite la reutilización sin duplicación:
1. **Detección y Tracking**: La clase `YOLODetectorTracker` se mantiene intacta; se inicializa con la ruta del modelo y los parámetros de confianza, abstrayéndose de si la fuente de frames es una cámara o un archivo.
2. **Fuentes de Captura**: Tanto `VideoFileSource` como `CameraSource` exponen la misma interfaz `FrameSource`. El controlador interactúa polimórficamente mediante `read()` y `source_info()`; `read_frame()` se conserva como alias histórico.
3. **Overlays**: No es necesario escribir código de dibujo en Streamlit. El frame de retorno de `VisionPipeline.process_frame()` ya viene pre-anotado listo para renderizarse.

---

## 4. Flujo implementado y límites

```text
VideoFileSource / CameraSource
→ TrafficAnalysisController
→ VisionPipeline existente
→ FrameAnalysisResult y TrafficEvent
→ Streamlit
→ build_traffic_event_batch
→ revisión manual
```

Pausar no cierra la fuente y continuar retoma la posición. Reiniciar crea detector, tracker, contador, eventos y pipeline nuevos. Finalización, cambio de fuente y errores cierran explícitamente; el cierre es idempotente. Las métricas reales nunca se mezclan con las sintéticas. La cámara física queda pendiente de validación manual. No existe aprobación automática ni transferencia directa a TPDA.
