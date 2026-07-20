# Informe de implementación — CongestionIntervalAggregator

## Alcance

Se implementó un agregador temporal neutral que transforma resultados compatibles con `FrameAnalysisResult` en `CongestionInput`. No está conectado con el controlador, Streamlit o visión; no usa imágenes, velocidad, reloj real ni persistencia.

## Contrato de entrada

`CongestionIntervalAggregator.add()` consume los campos realmente disponibles:

- `timestamp_seconds`;
- `vehicles_in_scene`;
- `crossing_events`;
- `direction_counts` para validación de integridad;
- `source_type`;
- `end_of_source`.

Además recibe explícitamente `source_id`, `monitoring_point_id` opcional e `is_paused`. El ID explícito es necesario porque el contrato actual de `FrameAnalysisResult` solo contiene el tipo de fuente, no su identidad.

## Ventana y flujo

La configuración demostrativa usa una ventana deslizante de 60 segundos. El flujo se calcula exclusivamente con cruces únicos:

```text
vehicles_per_minute = eventos únicos retenidos / duración efectiva × 60
duración efectiva = min(ventana configurada, tiempo válido observado)
```

Durante calentamiento se escala con la duración observada real. Si todavía no existe intervalo temporal, el flujo es cero. Las detecciones por frame y los tracks históricos no se cuentan como flujo.

## Deduplicación y direcciones

Cada cruce requiere `event_id` estable y dirección entera o nombre neutral no vacío. Los IDs repetidos se ignoran mientras permanezcan en la ventana. Eventos y claves de deduplicación expiran juntos, por lo que la memoria no crece indefinidamente.

`direction_counts` se reconstruye desde eventos únicos retenidos. Los conteos acumulados del resultado de frame no se suman, evitando doble conteo.

## Escena y acumulación

`vehicles_in_scene` usa siempre la observación válida más reciente. La acumulación es una pendiente temporal:

```text
accumulation_delta = (escena actual − escena anterior) / segundos reales × 60
```

Se expresa como vehículos por minuto. Una banda muerta demostrativa de un vehículo elimina oscilaciones mínimas; cambios mayores conservan signo. Timestamps repetidos producen pendiente cero porque no existe intervalo defendible.

## Tiempo y pausa

La duración válida se forma únicamente con diferencias entre timestamps explícitos de muestras no pausadas. Una pausa:

- no añade muestra ni eventos;
- actualiza el último timestamp visto para excluir el intervalo pausado;
- no cambia duración, flujo o acumulación;
- devuelve una copia de la última entrada con `is_paused=True`, si existe.

No se usa `datetime.now()`, `time.time()`, reloj monotónico o `sleep`.

## Reset, fuente y fin

`reset()` borra ventana, eventos, deduplicación, escena, timestamps, duración, muestras, fuente, punto y última salida. Cambiar `source_id` o `monitoring_point_id` sin reset genera un error explícito, evitando mezclar lotes.

`end_of_source=True` devuelve la última muestra válida sin añadir muestras o eventos, ni incrementar duración.

## Validaciones

Se rechazan ventana no positiva/no finita, timestamps negativos/regresivos/no finitos, escena inválida, conteos de dirección negativos, IDs ausentes, direcciones vacías, fuente/punto vacíos y cambios de fuente sin reset.

## Pruebas

Se añadieron 39 pruebas en `tests/unit/test_congestion_interval_aggregator.py`. Cubren estado inicial, flujo, calentamiento, múltiples eventos, duplicados, expiración, direcciones, escena, acumulación positiva/negativa/estable, timestamps repetidos, pausa, continuación, reset, fuentes, fin, memoria acotada, determinismo, contrato real y secuencia agregador→motor.

Las pruebas usan fakes mínimos; no cargan YOLO, videos, OpenCV ni Streamlit.

## Limitaciones

- La ventana de 60 segundos y la banda muerta requieren calibración por punto.
- La tasa de acumulación de dos puntos es intencionalmente simple; no usa suavizado estadístico.
- Un evento expirado puede volver a aceptarse si reaparece mucho después con el mismo ID, decisión necesaria para mantener deduplicación acotada.
- La pausa debe notificarse al agregador para excluir correctamente el intervalo.

## Siguiente paso recomendado

Crear un adaptador de aplicación neutral que coordine `TrafficAnalysisController`, `CongestionIntervalAggregator` y `CongestionEngine`, con pruebas mediante fakes, antes de modificar `traffic_monitoring.py`.
