# Estrategia de reproducción e inferencia en Streamlit

## Principio

Streamlit reejecuta la página ante interacciones. El Centro de Monitoreo no usa `while True`, `sleep` ni un bucle local bloqueante. La página utiliza `st.fragment(run_every=0.15)` exclusivamente mientras el controlador está en `RUNNING`; cada ejecución procesa como máximo un fotograma y vuelve a ceder el control a Streamlit.

```text
fragmento programado
→ TrafficAnalysisController.process_next()
→ FrameSource.read()
→ VisionPipeline.process_frame()
→ FrameAnalysisResult
→ conversión BGR/RGB y render
```

## Estado y controles

El controlador se conserva por sesión bajo claves con prefijo `traffic_analysis_`. No existe estado de UI dentro de `vision/`.

- **Iniciar análisis / cámara:** abre la fuente de forma explícita, crea un pipeline nuevo y empieza a programar el fragmento.
- **Pausar:** cambia a `PAUSED`; no lee frames y no cierra la fuente.
- **Continuar:** vuelve a `RUNNING` desde la misma posición.
- **Reiniciar:** cierra y reabre la fuente y crea detector, ByteTrack, contador, eventos y pipeline nuevos.
- **Finalizar / detener / cambiar fuente:** cierra explícitamente el recurso.
- **Error:** el controlador pasa a `ERROR`, devuelve una advertencia y cierra la fuente.

`VideoFileSource.close()` y `CameraSource.close()` son idempotentes. El controlador garantiza cierre también si falla la creación del pipeline después de abrir la fuente. No se usa `__del__` como garantía principal.

## Modelo y aislamiento entre lotes

`YOLODetectorTracker` usa `model.track(..., persist=True)`, por lo que su instancia contiene estado mutable de ByteTrack. No se comparte mediante `st.cache_resource`: cada lote y reinicio obtiene detector, tracker, contador y pipeline nuevos. Esta decisión evita heredar IDs, trayectorias, conteos o eventos. Una futura optimización solo podría cachear pesos si se separan técnicamente del tracker mutable.

## Métricas y revisión

El modo imagen muestra únicamente datos sintéticos. Video y cámara muestran únicamente `FrameAnalysisResult`: tracks activos, cruces, categorías, direcciones, tiempo y FPS real. Al iniciar análisis real se retira inmediatamente cualquier lote sintético previo; un lote real ya finalizado no se borra sin una acción explícita.

Al pulsar **Finalizar y revisar**:

```text
TrafficEvent
→ build_traffic_event_batch
→ lote pendiente
→ traffic_review.py
```

No hay aprobación automática ni transferencia directa a TPDA. OCR permanece separado.

## Cámara local

La cámara se abre solo mediante acción explícita con índice 0 o 1. La disponibilidad, permisos y liberación física deben validarse manualmente en el equipo objetivo. Pausar mantiene el dispositivo abierto para poder continuar; `Detener cámara`, cambiar de fuente, finalizar o un error lo liberan.
