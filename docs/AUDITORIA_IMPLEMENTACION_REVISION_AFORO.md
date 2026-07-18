# Auditoría de implementación — Revisión del aforo automático

Fecha: 2026-07-17  
Decisión: **APROBADA CON CORRECCIONES**.

## Alcance

Se auditó e integró `traffic_review.py` con el contrato oficial de `traffic_event_adapter.py`. La pantalla puede consumir eventos reales en memoria, CSV y lotes JSON sin duplicar validaciones técnicas ni alterar los datos originales del contador.

No se modificaron visión, ByteTrack, YOLO, línea `y=360`, TPDA, ESAL, AASHTO, resultados de calibración ni CSV demostrativos. No existe escritura de `traffic_counts_corrected` hacia `tpda_result`.

## Archivos revisados

- `src/pavement_intelligence/ui/pages/traffic_review.py`
- `src/pavement_intelligence/integration/traffic_event_adapter.py`
- `tests/unit/test_traffic_review.py`
- `tests/unit/test_traffic_event_adapter.py`
- `docs/VALIDACION_CONTRATO_UI_CONTADOR.md`
- `docs/AUDITORIA_CONTRATO_SALIDA_CONTADOR.md`
- `docs/UX_REVISION_AFORO_AUTOMATICO.md`
- `data/processed/validation_counter/line_y360/batch_ui_contract_example.json`
- `data/processed/validation_counter/line_y360/events.csv`
- `src/pavement_intelligence/config/vehicle_catalog.yaml`

## Correcciones aplicadas

### Adaptador obligatorio

`initialize_reviewed_events` llama a `adapt_traffic_event_for_review` para cada fila. Los lotes JSON con metadatos pasan además por `build_traffic_event_batch`. Se eliminó de la UI la validación propia de `track_id`, los valores predeterminados silenciosos de dirección/frame/confianza y la creación manual duplicada de campos de revisión.

Una entrada inválida produce `TrafficEventContractError`; no se convierte en evento descartado ni entra parcialmente a sesión.

### Categorías centrales

La lista de categorías confirmables ya no está escrita dentro de `traffic_review.py`. Se obtiene de:

`src/pavement_intelligence/config/vehicle_catalog.yaml`

mediante `load_yaml_catalog_cached` y `get_vehicle_categories`.

Categorías vigentes:

`MOTO, AUTO, CAMIONETA, MINIBUS, BUS, C2, C3, TRACTOCAMION, ARTICULADO, OTRO_PESADO`.

Esto mantiene compatibilidad con el futuro agregado para TPDA sin crear una enumeración paralela.

### Tratamiento de `CAMION`

- `category="CAMION"` permanece inmutable.
- La presentación usa exclusivamente `CATEGORIA_MAP["CAMION"] = "Camión no confirmado"`.
- `corrected_category` comienza en `null`.
- La aprobación queda bloqueada mientras no se elija una categoría central válida.
- La clasificación manual de un camión exige justificación aunque el operador seleccione estado `aceptado`.
- No existe conversión automática a C2, C3, tractocamión u otra clase vial.

Se eliminó el sentinel de estado `CAMION_NO_CONFIRMADO`; no era una categoría del catálogo y mezclaba presentación con dominio.

### Inmutabilidad

Los campos técnicos se toman de `REQUIRED_EVENT_FIELDS` y quedan fuera de los cambios admitidos:

- `event_id`, `track_id`, `original_class`, `category`, `confidence`;
- `frame_number`, `video_second`, `direction`;
- `centroid_x`, `centroid_y`, `source`, `processing_date`, `data_origin`.

`apply_review_update` sólo admite:

- `validation_status`, `corrected_category`, `correction_reason`;
- `reviewed`, `reviewed_by`, `reviewed_at`, `include_in_final_count`.

Si se intenta modificar un campo técnico, lanza `ValueError`. Cada actualización crea trazabilidad de revisor/fecha e invalida una aprobación previa.

### Eventos manuales

Se adoptó un contrato separado y explícito:

- `event_id` y `manual_event_id`: namespace `manual:<uuid>`;
- `track_id=null`, nunca `-1` ni un entero que simule ByteTrack;
- `data_origin="manual"`;
- `original_class`, `category`, confianza, frame y centroides: `null`, porque no fueron producidos por visión;
- `corrected_category`: categoría confirmada tomada del catálogo central;
- responsable, fecha y justificación: obligatorios;
- inclusión final: sólo si el registro satisface esas reglas.

La aprobación detecta registros manuales incompletos, IDs incorrectos o categorías ajenas al catálogo.

## Importación CSV y JSON

La pantalla admite `.csv` y `.json` UTF-8/UTF-8 con BOM.

Flujo:

1. Leer bytes sin modificar sesión.
2. Parsear el archivo completo.
3. Validar todas las filas mediante el adaptador.
4. Rechazar IDs de evento duplicados.
5. Sólo entonces reemplazar el lote de sesión.

Los errores muestran un mensaje claro y conservan íntegro el lote anterior. Un SHA-256 evita recargar el mismo archivo en cada rerun.

Para eventos provenientes directamente del contador se calcula una huella `counter:<sha256>`. Si cambia mientras la fuente activa también es el contador, se considera un video/lote nuevo y se limpia la revisión anterior. Un archivo subido no es reemplazado accidentalmente por eventos viejos de sesión.

## Prueba con datos reales

### JSON

`batch_ui_contract_example.json` cargó correctamente:

- modelo: `yolov8n.pt`;
- línea: `main_line`, `y=360`;
- evento real: `track_id=1`, `AUTO`, dirección `1`;
- confianza `0.5857`, frame `65`, segundo `5.2`;
- `data_origin=OBSERVADO_POR_VIDEO`.

### CSV

`line_y360/events.csv` cargó y se adaptó con:

- enteros para track, frame y dirección;
- flotantes para confianza, tiempo y centroides;
- fecha y origen conservados;
- ninguna fila nula, duplicada o con ID inválido.

No se inventaron metadatos al cargar CSV. El diccionario de metadatos queda vacío si la fuente no los proporciona.

## Estructura final de `session_state`

| Clave | Contenido | Reinicio con lote nuevo |
|---|---|---|
| `vision_events_raw` | copia técnica validada | Sí |
| `vision_events_reviewed` | copias adaptadas/editables | Sí |
| `vision_batch_metadata` | modelo, línea, video y versión si existen | Sí |
| `traffic_counts_corrected` | agregado revisado, nunca TPDA | Sí, a `{}` |
| `traffic_review_approved` | aprobación humana del lote actual | Sí, a `False` |
| `is_synthetic_review` | origen sintético | Sí |
| `traffic_review_source_fingerprint` | identidad del lote | Sí |

Al editar, descartar o agregar un evento se ejecuta `invalidate_review_approval`: aprobación `False` y conteos corregidos `{}`. Los metadatos y campos técnicos permanecen intactos.

`tpda_result` no se inicializa, actualiza ni elimina desde esta pantalla.

## Criterios de aprobación comprobados

“Aprobar Aforo Revisado” permanece bloqueado cuando:

- hay filas `sin_revisar` o `requiere_revision`;
- existe `CAMION` incluido sin categoría confirmada válida;
- existe `DESCONOCIDO` incluido sin resolución válida;
- una corrección, descarte o reclasificación carece de justificación;
- un evento manual carece de namespace, categoría, responsable, fecha o justificación;
- los datos son sintéticos y no se confirmó esa condición;
- no queda ningún evento final válido.

Una edición posterior a aprobación invalida la aprobación y el agregado anterior.

## Lógica duplicada eliminada

Se eliminaron de la UI:

- validación local de IDs y descarte automático de `-1`;
- defaults silenciosos para campos técnicos ausentes;
- lista hardcodeada de categorías ABC;
- sentinel `CAMION_NO_CONFIRMADO`;
- IDs manuales `9999+n`;
- commits parciales de CSV;
- edición directa de campos revisables sin invalidar aprobación.

Se mantienen validaciones visuales propias de la interfaz, filtros, etiquetas, alertas y reglas de habilitación del botón.

## Pruebas

`tests/unit/test_traffic_review.py` contiene 21 casos, incluidos los 14 escenarios solicitados y regresiones adicionales de duplicados/catálogo/justificación.

| Ejecución | Resultado |
|---|---|
| `test_traffic_review.py` | 21 aprobadas |
| Adaptador + contador | 36 aprobadas |
| Suite completa | 65 aprobadas, 0 fallidas |
| `pip check` | `No broken requirements found.` |

## Riesgos pendientes

- La cobertura automática del video validado continúa siendo baja; la revisión manual sigue siendo obligatoria.
- La identidad de lote en eventos de contador se basa en contenido; no existe todavía un ID persistente de ejecución almacenado en base de datos.
- Los eventos manuales usan un contrato de revisión deliberadamente distinto de `TrafficEvent`; no deben volver a pasar por el adaptador de eventos automáticos.
- Los CSV no transportan metadatos de modelo/línea; para trazabilidad completa debe preferirse el JSON de lote.
- No se realizó una prueba de navegador interactiva; la lógica está cubierta mediante funciones puras y suite automatizada.

## Decisión

**APROBADA CON CORRECCIONES.**

Las correcciones críticas de contrato, inmutabilidad, carga atómica, categorías y sesión fueron aplicadas y verificadas. La pantalla está aprobada para revisión manual del MVP y generación de `traffic_counts_corrected` en sesión.

No está aprobada para transferencia automática a TPDA. Esa integración debe permanecer aislada hasta una autorización y validación específicas posteriores.
