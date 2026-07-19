# Plan de pruebas del motor de congestión

La suite implementada está en `tests/unit/test_congestion_engine.py` y usa timestamps deterministas, sin tiempo real ni `sleep`.

## Suficiencia y estados

- Datos insuficientes durante calentamiento.
- Límite exacto de 10 segundos.
- Duración suficiente con menos de 3 muestras.
- Estado NORMAL.
- Entrada a MODERATE por escena y acumulación.
- Flujo alto estable clasificado como MODERATE, nunca HIGH aislado.

## Histéresis

- Entrada MODERATE en el límite 8.
- Permanencia en MODERATE dentro de la banda muerta.
- Salida a NORMAL en 5 con las demás métricas bajo salida.
- Umbrales personalizados.
- Rechazo de configuraciones incoherentes.

## HIGH y alertas

- Creación de candidato HIGH.
- Sin confirmación antes de 15 segundos.
- Confirmación exactamente a 15 segundos.
- Cancelación si desaparece la condición.
- HIGH sostenido sin alertas duplicadas.
- ID estable y alerta `origin=OPERATIONAL_ESTIMATE`, `normative=False`.
- Recuperación confirmada durante 5 segundos y cierre de alerta.

## Pausa y reset

- Pausa sin avance del candidato.
- Continuación desde el tiempo válido anterior.
- Rechazo de duración que avance durante pausa.
- Reset completo y nuevo calentamiento.

## Validación de contratos

- Negativos, NaN e infinito.
- Conteos y tipos inválidos.
- Conteos por sentido negativos.
- Copia defensiva e inmutabilidad.
- Duración inconsistente.
- Timestamp y duración regresivos.
- Defaults identificados como demostrativos.
- Determinismo de secuencias.

## Independencia

La suite inspecciona el módulo para confirmar ausencia de Streamlit, OpenCV, estado de sesión, TPDA, aprobación y escritura de archivos. La suite específica contiene 42 pruebas y el commit `946aaea` fue validado con 617 pruebas totales.

## Pruebas futuras

El futuro agregador temporal requerirá pruebas independientes de ventanas, frames faltantes, pausa y conversión de `FrameAnalysisResult` a `CongestionInput`. Estas pruebas no deben introducir integración UI en el dominio.
