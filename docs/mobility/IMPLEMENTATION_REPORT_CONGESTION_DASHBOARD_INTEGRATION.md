# Informe de implementación — Integración de congestión en el dashboard

## Alcance

Se integró la Estimación Operativa de Congestión al Centro de Monitoreo Streamlit para video pregrabado y cámara mediante la cadena existente:

```text
TrafficAnalysisController
    → FrameAnalysisResult
    → TrafficCongestionCoordinator
    → TrafficCongestionSnapshot
    → CongestionPresentationState
    → Streamlit
```

La página no calcula flujo, acumulación, histéresis, confirmación HIGH, recuperación, reglas o IDs de alerta. El modo de imagen demostrativa conserva su dashboard sintético claramente separado.

No se modificaron `CongestionEngine`, `CongestionIntervalAggregator`, `TrafficCongestionCoordinator`, `TrafficAnalysisController`, `VisionPipeline`, YOLO, ByteTrack, OCR, `traffic_review.py`, TPDA, pesaje, ESAL, geotecnia o pavimentos.

## Arquitectura final

`ui/utils/congestion_presentation.py` transforma un snapshot inmutable en textos, etiquetas, unidades y variantes visuales. No importa Streamlit, OpenCV, el motor ni el agregador.

`ui/utils/congestion_session.py` posee el ciclo de vida por sesión, construye el coordinador con el agregador y motor reales, deduplica resultados, guarda snapshots/presentación y mantiene alertas operativas. No importa Streamlit: recibe un mapping de sesión, lo que permite pruebas unitarias aisladas.

`traffic_monitoring.py` se limita a obtener el resultado real, pasarlo una vez al helper, guardar el resultado de presentación y renderizarlo con componentes nativos ya usados por la página.

## Claves de sesión

- `traffic_congestion_coordinator`: coordinador exclusivo del lote real actual.
- `traffic_congestion_snapshot`: último snapshot tipado.
- `traffic_congestion_presentation`: última vista formateada.
- `traffic_congestion_error`: error controlado del cálculo de congestión.
- `traffic_congestion_source_id`: identidad explícita de fuente.
- `traffic_congestion_last_processed_frame_key`: clave estable del último resultado entregado.
- `traffic_congestion_alerts`: alertas operativas únicas o actualizadas por `alert_id`.

Estas claves no reutilizan estado sintético, revisión, aprobación, TPDA u OCR. El coordinador permanece en `st.session_state`, igual que el controlador real, y no se comparte entre usuarios o pestañas.

## Ciclo de vida

### Inicio

Después de que el controlador abre la fuente y devuelve `SourceInfo`, se crea un coordinador nuevo y se vincula a `metadata.source_id`. Se limpian snapshot, presentación, error, alertas y clave de frame previos. El punto de monitoreo se entrega como metadato neutral.

### Procesamiento

Cada `FrameAnalysisResult` real pasa por `process_congestion_result_once()`. Si es nuevo, el coordinador agrega y evalúa exactamente una vez. La UI recibe únicamente `CongestionPresentationState`.

### Pausa y continuación

Pausar el controlador llama también a `coordinator.pause()`. Se conserva el snapshot con `is_paused=True`; no se agrega una muestra ni se avanza observación o confirmación HIGH. Continuar llama a `resume()` y la siguiente muestra real retoma la ventana existente. Si se pausa antes de la primera muestra, el coordinador continúa en `IDLE` y se iniciará con el siguiente resultado válido.

### Reinicio

El reset del controlador devuelve la fuente reiniciada. El coordinador ejecuta `reset()`, vuelve a vincular el mismo `source_id` y elimina snapshot, presentación, alertas, error y deduplicación. La siguiente muestra vuelve a calentamiento.

### Cambio de fuente

Cambiar entre imagen, video o cámara cierra el controlador anterior y limpia por completo la sesión de congestión. Iniciar una fuente real siempre crea otro coordinador, por lo que no se conservan ventana, nivel o alerta.

### Finalización

Finalizar el análisis o preparar el lote de revisión llama a `finish_congestion_session()` una sola vez de forma idempotente. El snapshot final se conserva para visualización. No se crea aprobación, no se alteran conteos y no se genera entrada TPDA.

## Prevención de duplicados

La clave estable es:

```text
(source_id, frame_index, timestamp_seconds, end_of_source)
```

Un rerun con la misma clave reutiliza la presentación almacenada y no vuelve a llamar al coordinador. `end_of_source` forma parte de la clave para distinguir el resultado terminal de un último frame con índice o timestamp coincidente.

Las alertas se almacenan por `alert_id`. Una alerta activa repetida actualiza la misma entrada; una alerta cerrada reemplaza su estado anterior sin crear otra fila.

## Presentación

El adaptador mapea exclusivamente valores ya resueltos:

- `INSUFFICIENT_DATA` → “Datos insuficientes”, con el resumen de segundos y muestras faltantes producido por el motor.
- `NORMAL` → “Tránsito normal”.
- `MODERATE` → “Congestión moderada”, incluyendo reglas activadas.
- candidato HIGH → conserva el nivel real y muestra segundos válidos acumulados/requeridos.
- `HIGH` → “Congestión alta” y el mensaje de alerta real.

Las unidades visibles son `veh/min`, vehículos, `veh/min` de acumulación y segundos. Siempre se muestra “Estimación operativa; no corresponde a un Nivel de Servicio normativo”. La velocidad permanece como “No calibrada”.

## Diferencia entre modo sintético y real

La imagen demostrativa continúa mostrando sus tarjetas, gráfico y alertas sintéticas con distintivos visibles. No crea coordinador o snapshot real.

Video y cámara muestran solo métricas del `FrameAnalysisResult` y del `TrafficCongestionSnapshot`: flujo agregado, escena, acumulación, tiempo válido, candidato, alerta, evidencia y warnings. No renderizan cifras de congestión sintéticas ni `result.congestion`.

## Errores

Una excepción del coordinador se registra mediante logging, se copia a `traffic_congestion_error` y detiene únicamente la estimación. La presentación anterior puede mantenerse mientras el análisis vehicular continúa si resulta seguro. No se inventa un nivel. El botón Reiniciar recupera agregador, motor, snapshot y deduplicación conjuntamente.

## Pruebas

Se añadieron pruebas puras para niveles, calentamiento, HIGH pendiente/confirmado, etiquetas, unidades, evidencia, warnings, pausa, final, origen y alertas. Las pruebas de sesión cubren creación, reset, cambio de fuente, deduplicación de frames y alertas, pausa, resume, finalización, error controlado y aislamiento respecto de aprobación/TPDA.

AppTest cubre:

- modo de imagen sintética sin coordinador;
- video real con snapshot y rerun sin muestra duplicada;
- cámara seleccionada sin abrir hardware;
- métricas reales, velocidad no calibrada y leyenda no normativa;
- navegación a revisión preservada y ausencia de transferencia automática.

Las regresiones del dashboard y la cadena de congestión se ejecutan sin cargar video o YOLO en pruebas unitarias.

## Validación headless local

Se recorrió `traffic_monitoring_demo.mp4` con `VideoFileSource`, `TrafficAnalysisController`, YOLO/ByteTrack locales y el coordinador real:

- 64 frames válidos y 64 muestras;
- 1 resultado terminal, para 65 claves únicas;
- primera estimación `INSUFFICIENT_DATA`;
- snapshot final correcto;
- fuente cerrada;
- ningún resultado duplicado.

El video dura 8 segundos y el umbral metodológico mínimo es 10 segundos, por lo que todas las estimaciones permanecieron correctamente en `INSUFFICIENT_DATA`. La interfaz no promovió artificialmente el nivel.

## Limitaciones y riesgos pendientes

- El video local es demostrativo y no alcanza el calentamiento de 10 segundos.
- Una prueba de HIGH visible necesita una secuencia autorizada de al menos 25 segundos válidos con condiciones severas sostenidas.
- La carga inicial de YOLO en CPU puede producir una pausa visible.
- La cámara física depende de permisos e índice del sistema y no se abrió automáticamente.
- El coordinador vive en memoria de sesión; cerrar la pestaña o reiniciar el servidor elimina su estado.
- Los umbrales continúan siendo demostrativos y requieren calibración por punto.

## Checklist manual pendiente

- Confirmar visualmente el layout en navegador ancho y estrecho.
- Validar con video de campo autorizado de más de 10 segundos.
- Verificar una secuencia HIGH y su recuperación con material controlado.
- Probar cámara física solo con autorización del operador.
- Confirmar legibilidad de evidencia y alertas con el tema desplegado.
