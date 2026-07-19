# Contratos de la Estimación Operativa de Congestión

Estos contratos corresponden al motor neutral versionado en el commit `946aaea`. La estimación es operativa, explicable y **no normativa**: no representa Nivel de Servicio ni sustituye una metodología calibrada.

## CongestionLevel

Enum string con cuatro estados:

- `INSUFFICIENT_DATA`
- `NORMAL`
- `MODERATE`
- `HIGH`

## CongestionInput

Dataclass inmutable con variables disponibles y defendibles:

- `timestamp_seconds`: tiempo explícito de la fuente.
- `observation_duration_seconds`: tiempo válido de observación; no avanza en pausa.
- `sample_count`: muestras válidas acumuladas.
- `vehicles_in_scene`: tracks activos.
- `vehicles_per_minute`: flujo agregado.
- `accumulation_delta`: variación de acumulación.
- `direction_counts`: conteos no negativos por sentido, copiados a un mapping de solo lectura.
- `is_paused`: indica pausa explícita.
- `monitoring_point_id`: identificador opcional del punto.

No incluye velocidad en km/h. El contrato rechaza negativos, NaN, infinito, tipos incompatibles, duraciones mayores que el timestamp, conteos por sentido negativos y puntos vacíos.

## CongestionThresholds

Dataclass inmutable, validada y configurable por punto de monitoreo. Los defaults son una “Configuración demostrativa inicial, pendiente de calibración por punto de monitoreo”.

| Campo | Default |
|---|---:|
| `minimum_observation_seconds` | 10.0 |
| `minimum_sample_count` | 3 |
| `moderate_scene_enter` / `exit` | 8 / 5 |
| `high_scene_enter` / `exit` | 16 / 12 |
| `moderate_flow_enter` / `exit` | 40 / 30 |
| `high_flow_enter` / `exit` | 60 / 45 |
| `moderate_accumulation_enter` / `exit` | 2 / 1 |
| `high_accumulation_enter` / `exit` | 5 / 2 |
| `high_confirmation_seconds` | 15.0 |
| `recovery_confirmation_seconds` | 5.0 |

Los umbrales de salida no pueden superar los de entrada y los umbrales altos deben superar los moderados.

## CongestionEvidence

Evidencia inmutable y explicable con:

- nivel anterior y resultante;
- candidato HIGH pendiente y tiempo acumulado;
- métricas observadas;
- reglas activadas;
- umbrales comparados;
- advertencias;
- suficiencia de datos;
- resumen legible.

## CongestionAssessment

Resultado inmutable de cada llamada a `evaluate()`:

- timestamp;
- nivel anterior y actual;
- evidencia;
- alerta asociada, si existe;
- indicador `alert_emitted` para distinguir la emisión inicial.

## CongestionAlert

Alerta neutral con ID estable, nivel, inicio, confirmación, punto opcional, mensaje, evidencia y estado activo. Siempre declara:

```python
origin = "OPERATIONAL_ESTIMATE"
normative = False
```

Se emite una sola vez al confirmar HIGH durante 15 segundos válidos. La recuperación confirmada durante 5 segundos devuelve la alerta cerrada. No aprueba aforos ni transfiere datos a TPDA.

## CongestionEngine

Recibe `CongestionThresholds`, evalúa una muestra por llamada, conserva solo estado mínimo para histéresis/temporización y expone `reset()`. No importa Streamlit, OpenCV o visión; no usa reloj real, estado global ni escritura en disco.
