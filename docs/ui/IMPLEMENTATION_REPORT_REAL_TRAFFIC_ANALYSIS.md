# Informe de implementación — Análisis real de tráfico

## Resultado

El Centro de Monitoreo dispone de tres fuentes claramente separadas:

- **Imagen demostrativa:** dashboard sintético, sin inferencia.
- **Video pregrabado:** fotogramas locales procesados por el `VisionPipeline` existente con YOLOv8 y ByteTrack.
- **Cámara en vivo:** la misma arquitectura y pipeline mediante índice local 0 o 1.

No se integró OCR. No existe aprobación automática ni transferencia directa a TPDA.

## Auditoría y reutilización

La auditoría encontró componentes reutilizables:

- `VisionPipeline.process_frame()` ya ejecuta detector/tracker, línea virtual, cajas, categorías, `track_id`, conteo y emisión de `TrafficEvent`.
- `AbstractVideoSource` y `FileVideoSource` ya ofrecían una base parcial para captura local.
- `build_traffic_event_batch()` es el adaptador oficial e inmutable hacia revisión.
- `traffic_review.py` recibe `vision_events_raw`, `vision_events_reviewed` y metadatos, y mantiene aprobación/TPDA como acciones manuales posteriores.

No se duplicó el pipeline. La antigua página `video_analysis.py` procesa un archivo completo con un `while`, escribe temporales y resultados; no se reutilizó ese patrón dentro del Centro de Monitoreo porque bloquearía los reruns.

Se observó que el tracking separado importa un contrato `DetectionResult` no presente en `detection/base.py`. No afecta este flujo porque `YOLODetectorTracker` usa ByteTrack integrado mediante `model.track`; no se alteró ese módulo.

## Arquitectura

```text
VideoFileSource / CameraSource
        ↓ un frame
TrafficAnalysisController
        ↓
VisionPipeline existente
        ↓
FrameAnalysisResult + TrafficEvent
        ↓
Streamlit (st.fragment, 150 ms)
        ↓ al finalizar
build_traffic_event_batch
        ↓
Revisión manual del aforo
```

`FrameSource` define `open`, `read`, `close`, `is_open` y `source_info`. Los nombres históricos `AbstractVideoSource` y `FileVideoSource` se conservan como aliases compatibles.

El controlador no importa Streamlit, no escribe archivos y procesa un frame por llamada. El pipeline se crea de forma perezosa después de abrir la fuente, por lo que una cámara inexistente falla antes de cargar YOLO y una cámara válida usa su resolución real para la línea horizontal.

## Resultado neutral

`FrameAnalysisResult` contiene índice, timestamp, tipo de fuente, frame anotado, detecciones, tracks activos, nuevos cruces, conteos por categoría y dirección, vehículos en escena, total, FPS, advertencias, fin de fuente y congestión operativa.

La congestión usa umbrales explícitos en `CongestionThresholds`, basados en flujo, vehículos en escena y tiempo acumulado. Se presenta como “Estimación operativa, no nivel de servicio normativo”. No usa velocidad: la UI muestra “Velocidad: no calibrada” y omite ocupación normativa.

## Video probado

- Archivo: `data/samples/ui/assets/traffic_monitoring_demo.mp4`.
- Resolución: 1672 × 766.
- Fuente: 8 FPS, 64 frames, 8 segundos.
- Modelo local: `data/models/yolov8n.pt`, CPU, confianza 0.45, inferencia 640.
- Prueba manual: tres frames procesados, con 12, 11 y 10 tracks activos.
- FPS observado: 0.51 en el primer frame (carga/calientamiento), 19.07 y 24.30 en los siguientes.
- Los frames anotados conservaron resolución 766 × 1672 × 3 y la fuente fue cerrada correctamente.

Este MP4 se generó previamente desde una referencia visual sintética. Aunque la inferencia ejecutada es real, no constituye un aforo de campo.

## Cámara

No se abrió una cámara física automáticamente: no hay confirmación de dispositivo disponible y una prueba automática podría bloquear hardware del usuario. La apertura, lectura, error de dispositivo y liberación se probaron con `VideoCapture` simulado. En la UI, la cámara solo se abre mediante “Iniciar cámara”.

## Estado e interacción

Las claves reales usan el prefijo `traffic_analysis_`. Los controles son:

- Iniciar análisis / Iniciar cámara;
- Pausar;
- Continuar;
- Reiniciar;
- Finalizar análisis / Detener cámara;
- Finalizar y revisar.

El fragmento procesa un frame por actualización, sin `while True`. Finalizar cierra la fuente y conserva eventos. “Finalizar y revisar” pasa los eventos por el adaptador oficial, invalida cualquier aprobación previa, marca el lote como real y navega a revisión; no aprueba ni crea entrada TPDA.

## Riesgos pendientes

- La carga inicial del modelo en CPU produce una pausa visible.
- El FPS depende del hardware; Streamlit puede omitir actualizaciones visuales aunque el controlador mantenga el orden de frames.
- La cámara requiere permisos del sistema y un índice válido.
- No existe calibración espacial para velocidad ni ocupación normativa.
- El video local disponible es demostrativo; debe validarse con material de campo autorizado antes de uso operativo.
- El hook OCR futuro debe asociarse por `track_id`, `event_id` y frames seleccionados, sin bloquear ni modificar conteos.

## Correcciones posteriores a auditoría

- El inicio de video o cámara ejecuta una transición explícita que retira inmediatamente un lote sintético anterior, reinicia métricas/temporales demostrativos y conserva un lote real ya finalizado hasta una nueva finalización explícita.
- `YOLODetectorTracker` **no se cachea**: `model.track(..., persist=True)` mantiene ByteTrack mutable dentro de la instancia. Cada lote crea detector, tracker, contador y pipeline nuevos para impedir tracks o eventos heredados. Cachear solo los pesos exigiría separar el modelo de su tracker, fuera del alcance de esta corrección menor.
- `TrafficAnalysisController.start()` cierra la fuente si falla la apertura o la creación del pipeline. `finish()` garantiza cierre mediante `finally`; pausa no cierra, continuar conserva posición, reset cierra y reabre, y el cambio de fuente cierra el controlador anterior.
- `close()` permanece idempotente en video y cámara. No se añadió `__del__`: la liberación principal y comprobada es explícita en todas las rutas controladas.
- Git confirma que `camera_source.py` es un archivo nuevo no rastreado, sin historial previo ni versión reemplazada.

## Uso

1. Ejecutar `streamlit run src/pavement_intelligence/ui/app.py`.
2. Abrir **Monitoreo de tráfico**.
3. Elegir **Video pregrabado** o **Cámara en vivo**.
4. Para video, seleccionar el archivo local mostrado y pulsar **Iniciar análisis**.
5. Para cámara, elegir 0 o 1 y pulsar **Iniciar cámara**.
6. Usar Pausar, Continuar o Reiniciar.
7. Pulsar **Finalizar y revisar** para crear el lote pendiente y abrir la revisión manual.
