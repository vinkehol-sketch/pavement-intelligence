# Informe de implementación — Congestion Runtime

## Alcance

Se implementó una capa coordinadora neutral que transforma, exactamente uno por llamada, resultados compatibles con `FrameAnalysisResult` mediante `CongestionIntervalAggregator` y `CongestionEngine`, y expone un `TrafficCongestionSnapshot`. No se integró Streamlit ni se modificaron el controlador, el pipeline de visión, OCR, aforos, TPDA u otros dominios.

## Arquitectura

El flujo queda desacoplado en tres etapas:

```text
FrameAnalysisResult (contrato estructural)
    → CongestionIntervalAggregator.add()
    → CongestionInput
    → CongestionEngine.evaluate()
    → CongestionAssessment
    → TrafficCongestionSnapshot
```

`TrafficCongestionCoordinator` recibe agregador y motor por inyección. No construye dependencias globales, no consulta reloj, no escribe archivos y no importa visión o UI. El contrato de frame se expresa mediante un `Protocol`, evitando que el dominio cargue NumPy u OpenCV.

El contrato real no incluye la identidad de fuente: solo contiene `source_type`. Por ello `source_id` se establece explícitamente mediante `set_source()` antes de procesar.

## Contratos

- `CongestionRuntimeState`: estados del ciclo de vida.
- `TrafficCongestionSnapshot`: vista tipada, congelada y directamente consumible por una futura presentación.
- `TrafficCongestionCoordinator`: único dueño del ciclo coordinado de agregador y motor.

El snapshot contiene fuente, estado, nivel actual y previo, flujo, escena, acumulación, direcciones, duración, muestras, candidato HIGH, tiempo candidato, alerta, evidencia, warnings y banderas de pausa/final. `origin` es siempre `OPERATIONAL_ESTIMATE` y `normative` es siempre `false`.

`direction_counts` se copia a un `MappingProxyType`; `warnings` se copia a tupla. La alerta y la evidencia provienen del motor y ya son dataclasses congeladas con colecciones internas inmutables. No se incluyen imágenes, HTML ni objetos de Streamlit.

## Máquina de estados

```text
IDLE ──muestra──> WARMING_UP ──datos suficientes──> ACTIVE
                      │                                │
                      └──────── pausa ────────────────┤
                                                       v
                                                     PAUSED
                                                       │ resume
                                                       └──> WARMING_UP o ACTIVE

WARMING_UP / ACTIVE / PAUSED ──finish o fin──> FINISHED
fallo de validación/agregador/motor ──────────> ERROR
reset desde cualquier estado ─────────────────> IDLE
```

`set_source()` no activa procesamiento. La primera muestra válida determina calentamiento; el estado pasa a `ACTIVE` cuando el motor deja `INSUFFICIENT_DATA`.

## Flujo de una muestra

El coordinador valida el contrato mínimo y el timestamp, entrega el resultado sin modificarlo al agregador, evalúa el `CongestionInput` producido y proyecta la evaluación en el snapshot. Los warnings del resultado se combinan con los warnings de evidencia sin alterar ninguno de los objetos de entrada.

Un resultado de fin de fuente no se agrega ni se evalúa: conserva las métricas, evidencia y alerta de la última muestra y solo marca el snapshot final. Si la fuente termina antes de una muestra válida, se genera un snapshot final vacío con nivel `INSUFFICIENT_DATA`.

## Pausa y continuación

`pause()` conserva nivel, candidato, alerta, métricas y duración. `process_paused_state()` devuelve el mismo snapshot pausado y, si recibe un resultado, solo notifica su timestamp al agregador con `is_paused=True`; no crea muestras o eventos y no invoca al motor.

Los timestamps opcionales de `pause()` y `resume()` permiten delimitar explícitamente una pausa cuando el reloj de una fuente continúa avanzando. En fuentes que dejan de leer durante la pausa, no son necesarios. La siguiente muestra válida retoma desde el último límite comunicado.

La doble pausa y el doble resume son idempotentes cuando ya existe un lote iniciado. Pausar antes de la primera muestra se rechaza explícitamente.

## Reset y cambio de fuente

`reset()` reinicia conjuntamente agregador y motor y elimina snapshot, fuente, tipo, error y estado del lote. Es idempotente.

La política elegida para cambio de fuente exige reset explícito. Reasignar la misma fuente es idempotente; establecer otra fuente con un lote vinculado genera `RuntimeError`. Así nunca se conserva ventana, nivel, candidato o alerta de una fuente anterior.

## Finalización

`finish()` no agrega, no evalúa y no avanza tiempo. Conserva el último snapshot, lo marca `is_final=True`, deja `is_paused=False` y mueve el runtime a `FINISHED`. Llamadas repetidas devuelven la misma instancia final, por lo que no duplican muestras, eventos o alertas. Procesar después de finalizar requiere reset.

No existe aprobación de aforo, transferencia a TPDA ni persistencia asociada a la finalización.

## Manejo de errores

Se validan resultado nulo o estructuralmente incorrecto, timestamp inválido, fuente vacía, secuencia sin fuente, mezcla de fuentes, estados incompatibles y contratos básicos de colecciones.

Las excepciones del agregador o motor no se convierten en resultados exitosos: el coordinador pasa a `ERROR`, conserva un mensaje controlado en `error_message` y vuelve a lanzar la excepción original. Esto evita ocultar errores de programación. Mientras permanece en `ERROR` no acepta nuevas muestras; `reset()` es el único mecanismo de recuperación.

Los errores de uso que ocurren fuera del procesamiento —por ejemplo pausar en `IDLE` o cambiar de fuente sin reset— se rechazan sin convertir un lote intacto en error de cálculo.

## Pruebas

`tests/unit/test_congestion_runtime.py` cubre estado inicial, calentamiento, activación, NORMAL, MODERATE, candidato HIGH, confirmación, alerta estable, evidencia, pausa, exclusión temporal, resume, reset, fuente, fin, idempotencia, errores inyectados, recuperación, entradas inválidas, no mutación, copias defensivas, determinismo, contratos reales, flujo alto sin HIGH, acumulación, limpieza de alerta, carácter no normativo y ausencia de dependencias prohibidas.

Las secuencias funcionales usan el agregador y motor reales. Los fakes se limitan a resultados de frame y a fallos deliberados de dependencias. No usan video, red, OpenCV, YOLO, ByteTrack, reloj real o `sleep`.

## Limitaciones

- La identidad de fuente debe suministrarse externamente porque `FrameAnalysisResult` no la contiene.
- Una pausa de fuente cuyo timestamp continúa avanzando debe informar al menos un resultado pausado o límites opcionales de timestamp para excluir ese intervalo.
- El runtime mantiene estado solo en memoria y no persiste snapshots o alertas.
- Los umbrales y ventanas siguen siendo demostrativos y requieren calibración por punto de monitoreo.

## Integración futura con dashboard

El siguiente paso recomendado es crear un adaptador de presentación en `traffic_monitoring.py` que posea el coordinador durante una sesión, traduzca acciones de UI a `set_source`, `pause`, `resume`, `reset` y `finish`, y renderice exclusivamente `TrafficCongestionSnapshot`. Esa integración debe mantener fuera del dominio cualquier caché, imagen, widget, HTML o estado de sesión de Streamlit.
