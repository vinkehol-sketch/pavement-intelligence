# Informe de implementación — Estimación Operativa de Congestión

## Alcance

Se implementó un dominio puro y determinista para estimar condiciones operativas de congestión. No está conectado todavía con `FrameAnalysisResult`, Streamlit, OpenCV ni el procesamiento de visión. No calcula velocidad, Nivel de Servicio ni cumplimiento normativo.

## Contratos

`src/pavement_intelligence/domain/traffic/congestion.py` contiene:

- `CongestionLevel`: `INSUFFICIENT_DATA`, `NORMAL`, `MODERATE` y `HIGH`.
- `CongestionInput`: timestamp, duración válida, muestras, vehículos en escena, flujo, acumulación, conteos por sentido, pausa y punto opcional.
- `CongestionThresholds`: configuración inmutable y validada.
- `CongestionEvidence`: transición, métricas, reglas, umbrales, advertencias y explicación legible.
- `CongestionAssessment`: resultado completo de cada evaluación.
- `CongestionAlert`: alerta neutral, estable y explícitamente no normativa.
- `CongestionEngine`: máquina de estados con `evaluate()` y `reset()`.

Las entradas y configuraciones rechazan negativos, NaN, infinitos, duraciones incoherentes, conteos inválidos, timestamps regresivos y umbrales incompatibles. Los conteos por sentido se copian a un mapping de solo lectura.

## Metodología

La evaluación utiliza únicamente variables disponibles y defendibles:

- vehículos presentes;
- cruces por minuto;
- delta de acumulación;
- tiempo válido de observación;
- cantidad de muestras;
- conteos por sentido.

Un flujo alto aislado representa utilización intensa, no congestión alta. `HIGH` exige una combinación severa de ocupación y acumulación creciente. La evidencia conserva las reglas activadas y los valores comparados.

## Umbrales demostrativos

La configuración predeterminada se identifica como “Configuración demostrativa inicial, pendiente de calibración por punto de monitoreo”.

| Variable | Entrada moderada | Salida moderada | Entrada alta | Salida alta |
|---|---:|---:|---:|---:|
| Vehículos en escena | 8 | 5 | 16 | 12 |
| Flujo veh/min | 40 | 30 | 60 | 45 |
| Acumulación | 2 | 1 | 5 | 2 |

Se requieren 10 segundos válidos y 3 muestras. HIGH se confirma tras 15 segundos sostenidos y la recuperación desde HIGH tras 5 segundos bajo umbrales de salida.

## Máquina de estados e histeresis

```text
INSUFFICIENT_DATA → NORMAL / MODERATE
NORMAL → MODERATE
MODERATE → NORMAL
MODERATE → candidato HIGH → HIGH confirmado
HIGH → MODERATE → NORMAL
```

Una condición severa inicia un candidato y mantiene el assessment en `MODERATE`. Si desaparece antes de 15 segundos, se cancela sin alerta. Al confirmarse, se crea una única alerta. Muestras posteriores reutilizan esa alerta sin duplicarla. La recuperación confirmada devuelve una alerta inactiva una vez y libera el estado activo.

## Tiempo, pausa y reset

El motor no consulta reloj del sistema. Usa `timestamp_seconds` para ordenar y `observation_duration_seconds` para acumular ventanas válidas. Durante una pausa, la duración debe permanecer congelada; nivel, candidato, recuperación y alerta no avanzan. Continuar acumula desde la duración válida previa.

`reset()` elimina nivel anterior, timestamps, candidato, temporizadores, alerta y evidencia. La siguiente secuencia vuelve a calentamiento.

## Alertas

Los IDs se derivan de forma estable del punto y del inicio del candidato. Toda alerta contiene evidencia, inicio, confirmación, punto opcional, estado activo, origen `OPERATIONAL_ESTIMATE` y `normative=False`. No depende de aprobación de aforo ni TPDA.

## Pruebas

Se añadieron 42 pruebas unitarias deterministas en `tests/unit/test_congestion_engine.py`. Cubren calentamiento, límites exactos, muestras insuficientes, estados, histeresis, candidato y confirmación HIGH, cancelación, alerta única, recuperación, pausa, continuación, reset, flujo alto estable, acumulación, direcciones, validaciones, configuración personalizada, inmutabilidad, determinismo y ausencia de Streamlit/OpenCV/escritura.

## Limitaciones

- Los umbrales no están calibrados con observaciones de campo.
- El motor consume métricas agregadas; el agregador temporal aún no existe.
- `accumulation_delta` debe definirse de forma consistente por el futuro agregador.
- No se persisten assessments ni alertas.
- No se integra todavía con UI, video, cámara, revisión u OCR.

## Siguiente paso recomendado

Implementar y probar aisladamente un `CongestionIntervalAggregator` que transforme secuencias de `FrameAnalysisResult` en `CongestionInput` cada segundo, sin modificar todavía Streamlit ni el motor.
