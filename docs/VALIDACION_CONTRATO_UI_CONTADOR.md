# Validación del contrato UI–contador

Fecha: 2026-07-17  
Alcance: contrato técnico entre la salida real del contador y la pantalla de revisión manual.  
Estado: **validado sin modificar UI ni conectar TPDA**.

## Configuración provisional confirmada

La fuente reproducible de la configuración validada es:

`data/processed/validation_counter/line_y360/configuration.json`

| Parámetro | Valor confirmado |
|---|---|
| Modelo | `data/models/yolov8n.pt` (`yolov8n.pt`) |
| Línea | horizontal, `(100,360) → (1180,360)` |
| Identificador lógico de lote | `main_line` |
| Resolución validada | 768 × 432 |
| Dispositivo | CPU |
| Seguimiento | ByteTrack, `bytetrack.yaml` |
| Confianza mínima | 0.45 |
| Tamaño de inferencia | 640 |
| Clases | `car`, `motorcycle`, `bus`, `truck` |
| Tolerancia | 3 px |
| Cooldown | 3 fotogramas |
| Edad máxima de estado | 30 fotogramas |
| Historia mínima | 3 posiciones |
| Desplazamiento mínimo | 10 px |
| Salto temporal máximo | 10 fotogramas |
| Versión contractual | `mvp-yolov8n-line360-v1` |

`Settings.yolo_model_path`, el modelo validado y el valor predeterminado del detector coinciden en YOLOv8n. Los valores por defecto de `VisionPipeline` coinciden con historia, desplazamiento, salto, cooldown y edad máxima validados.

`scripts/run_headless_vision.py` es una utilidad genérica histórica: conserva confianza 0.25 y línea central si no recibe argumentos. **No es la fuente de configuración provisional del MVP** y no debe ejecutarse sin parámetros para reproducir esta validación. No se cambiaron sus valores porque esta tarea prohíbe modificar parámetros técnicos. Antigravity debe consumir los metadatos del lote o el JSON de configuración validado, no inferir configuración desde ese script.

## Estructura real de `TrafficEvent`

Todos los campos del evento son obligatorios y no nulos en el contrato del adaptador. `TrafficEvent.to_dict()` serializa a un diccionario plano; redondea confianza a 4 decimales, segundo de video a 2 y centroides a 1.

| Campo | Tipo | Valores/regla | Nulo | Ejemplo real |
|---|---|---|---|---|
| `event_id` | `str` | cadena no vacía; identificador único | No | `evt_1784320762118_1` |
| `track_id` | `int` | entero `>=0`; `bool` no admitido | No | `1` |
| `original_class` | `str` | `car`, `motorcycle`, `bus`, `truck` | No | `car` |
| `category` | `str` | `AUTO`, `MOTO`, `BUS`, `CAMION`, `DESCONOCIDO`; preliminar | No | `AUTO` |
| `confidence` | `float` | finito, `0.0–1.0`; confianza media del track | No | `0.5857` |
| `frame_number` | `int` | entero `>=0` | No | `65` |
| `video_second` | `float` | finito, `>=0`; `frame_number/fps` | No | `5.2` |
| `direction` | `int` | exclusivamente `1` o `-1` | No | `1` |
| `centroid_x` | `float` | numérico finito, píxeles | No | `379.7` |
| `centroid_y` | `float` | numérico finito, píxeles | No | `353.7` |
| `source` | `str` | nombre/fuente no vacía | No | `car-detection.mp4` |
| `processing_date` | `str` | ISO 8601 | No | `2026-07-17T16:39:22.118815` |
| `data_origin` | `str` | cadena no vacía; actualmente `OBSERVADO_POR_VIDEO` | No | `OBSERVADO_POR_VIDEO` |

`original_class` ya representa la clase consolidada por mayoría, no la clasificación puntual del fotograma. `category` es el mapeo preliminar de esa clase y no debe interpretarse como clasificación ABC detallada.

## Adaptador desacoplado

Se creó:

`src/pavement_intelligence/integration/traffic_event_adapter.py`

Funciones públicas:

- `adapt_traffic_event_for_review(event)`: acepta `TrafficEvent` o `Mapping`, valida y devuelve una copia.
- `build_traffic_event_batch(events, metadata)`: adapta la colección y añade metadatos técnicos de lote.
- `TrafficEventContractError`: error explícito para entradas incompatibles.

El adaptador no importa Streamlit, no modifica el contador, no muta el evento original, no decide categorías C2/C3/tractocamión y no escribe ni lee claves TPDA/ESAL.

### Campos de revisión inicializados

| Campo | Valor inicial | Semántica |
|---|---|---|
| `validation_status` | `sin_revisar` | estado de auditoría |
| `corrected_category` | `null` | categoría aún no confirmada |
| `correction_reason` | `""` | nota opcional |
| `reviewed` | `false` | revisión pendiente |
| `reviewed_by` | `""` | auditor aún no asignado |
| `reviewed_at` | `null` | fecha aún no asignada |
| `include_in_final_count` | `true` | inclusión preliminar, sujeta a revisión |

Estos campos se añaden a una copia y no sobrescriben `original_class`, `category`, confianza ni datos de cruce.

## Metadatos de lote

`model_name` y `line_id` no se añadieron a `TrafficEvent`. Se agrupan en un contenedor compatible:

```json
{
  "metadata": {
    "model_name": "yolov8n.pt",
    "line_id": "main_line",
    "line_y": 360,
    "source_video": "car-detection.mp4",
    "processing_date": "2026-07-17T16:39:22.118815",
    "configuration_version": "mvp-yolov8n-line360-v1"
  },
  "events": []
}
```

Los seis metadatos son obligatorios: cadenas no vacías salvo `line_y`, que debe ser entero no negativo. Este diseño evita duplicarlos en cada evento y no rompe CSV/JSON existentes.

Ejemplo materializado con el evento real:

`data/processed/validation_counter/line_y360/batch_ui_contract_example.json`

## Validaciones y rechazos

El adaptador rechaza:

- campos obligatorios ausentes;
- `track_id=None`, `-1`, negativos, booleanos o no enteros;
- `original_class` fuera de las cuatro clases vehiculares admitidas;
- categoría preliminar fuera del conjunto permitido;
- confianza no numérica, infinita o fuera de `0–1`;
- `frame_number` negativo o no entero;
- `video_second` negativo/no numérico;
- `direction` distinta de `1/-1`;
- centroides no numéricos o no finitos;
- fuente, ID u origen vacíos;
- fecha de procesamiento no ISO 8601;
- metadatos de lote obligatorios ausentes o inválidos.

No completa silenciosamente un evento técnico incompleto. Los únicos valores predeterminados son campos nuevos de revisión manual.

## Auditoría de exportación

`VisionPipeline` impide que IDs inválidos generen `TrafficEvent`; el adaptador vuelve a validar el límite de integración. El CSV real no contiene IDs negativos.

`export_corrected_records`:

- conserva `original_class`, `category`, confianza y demás columnas si se le entregan;
- añade `status="AUTOMATICO"` y `notes=""` si faltan;
- genera `corrected_events.csv`, `corrected_events.json` y resumen por `category/direction/status`;
- no valida por sí solo el contrato crudo y puede asignar `direction=0` si el campo falta, porque su responsabilidad histórica es exportar registros corregidos.

Por ello, la secuencia segura es **adaptar/validar primero y exportar después**. No debe usarse el valor devuelto por `export_corrected_records` como lista de eventos: esa función devuelve un diccionario de rutas (`csv`, `json`, `summary`).

El CSV validado puede recargarse sin pérdida importante:

- `track_id`, `frame_number`, `direction`: `int64`;
- `confidence`, `video_second`, centroides: `float64`;
- IDs, clases, categoría, fuente, fecha y origen: cadenas.

## Compatibilidad con datos existentes

Archivo probado:

`data/processed/validation_counter/line_y360/events.csv`

Resultado:

- 13 columnas esperadas y 1 fila real;
- `track_id=1`, válido;
- `original_class=car` conservada;
- `category=AUTO` conservada como preliminar;
- `confidence=0.5857`, numérica;
- `direction=1`, válida;
- `frame_number=65`, entero;
- `video_second=5.2`, coherente con `65/12.5`;
- ningún ID inválido ni valor nulo.

No se inventaron filas faltantes.

## Pruebas ejecutadas

Se creó `tests/unit/test_traffic_event_adapter.py` con 14 casos que cubren los 12 requisitos solicitados, incluyendo parametrización de valores inválidos.

| Comprobación | Resultado |
|---|---|
| Pruebas nuevas de contrato | 14 aprobadas |
| Pruebas del contador | 22 aprobadas |
| Suite completa | 55 aprobadas, 0 fallidas |
| `pip check` | `No broken requirements found.` |

## Instrucciones exactas para Antigravity

1. Importar `adapt_traffic_event_for_review` y, si se muestran metadatos, `build_traffic_event_batch` desde `pavement_intelligence.integration`.
2. Para eventos en memoria: ejecutar `adapt_traffic_event_for_review(event)` sobre cada `TrafficEvent` de `pipeline.events`.
3. Para eventos CSV: cargar `events.csv`, convertir filas a diccionarios y pasar cada fila por el mismo adaptador.
4. Capturar `TrafficEventContractError` y marcar el lote como no consumible; no corregir silenciosamente IDs, dirección ni frame.
5. Mostrar `category` como categoría automática preliminar y `original_class` como clase visual consolidada.
6. Editar únicamente los campos de revisión. No sobrescribir los campos técnicos originales.
7. Leer configuración reproducible desde `line_y360/configuration.json` o usar el `metadata` del lote. No deducirla desde defaults del script headless.
8. No escribir `tpda_result`. La pantalla debe producir datos revisados separados; la aprobación manual seguirá siendo obligatoria.

Ejemplo mínimo:

```python
from pavement_intelligence.integration import adapt_traffic_event_for_review

review_rows = [adapt_traffic_event_for_review(event) for event in pipeline.events]
```

## Riesgos pendientes

- La configuración provisional todavía está materializada como artefacto validado, no como única configuración runtime consumida por todos los entry points; el script headless genérico conserva defaults históricos distintos.
- El CSV no conserva un esquema externo formal; los consumidores deben usar el adaptador.
- `event_id` se basa en tiempo de sistema e ID de track; no existe garantía persistente entre reprocesamientos del mismo video.
- La referencia manual sigue sin ser ground truth certificado.
- La cobertura automática continúa siendo 1 de 6 preliminares; revisión manual obligatoria.
- `model_name` y `line_id` sólo existen a nivel de lote, por diseño compatible.

## Confirmaciones de alcance

- No se modificó ninguna página Streamlit ni lógica visual.
- No se modificaron TPDA, ESAL, AASHTO ni CSV demostrativos.
- No se conectó el conteo con TPDA.
- No se renombró ni modificó `TrafficEvent`.
