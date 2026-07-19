# Metodología MVP: Estimación Operativa de Congestión

## Alcance

La Estimación Operativa de Congestión (EOC) clasifica condiciones observadas mediante métricas agregadas de presencia, flujo y acumulación. Es una estimación **no normativa**, pendiente de calibración por punto de monitoreo. No calcula velocidad en km/h ni Nivel de Servicio mientras no exista calibración espacial válida.

## Datos y calentamiento

El motor consume `CongestionInput` con timestamps explícitos. Requiere simultáneamente:

- 10 segundos válidos de observación;
- al menos 3 muestras.

Antes de cumplir ambos requisitos devuelve `INSUFFICIENT_DATA`. Una pausa puede avanzar el timestamp externo, pero no `observation_duration_seconds`; por tanto no avanza calentamiento, candidato HIGH o recuperación.

## Clasificación

- `NORMAL`: métricas bajo umbrales de entrada.
- `MODERATE`: ocupación elevada, flujo alto o acumulación positiva; también es el nivel visible mientras HIGH espera confirmación.
- `HIGH`: combinación severa y sostenida de escena ocupada y acumulación creciente.

El flujo alto aislado no produce automáticamente HIGH. Puede indicar circulación intensa pero eficiente y se conserva como señal moderada/de apoyo.

## Reglas demostrativas

- MODERATE por escena desde 8 vehículos; salida a NORMAL con 5 o menos y las demás métricas bajo sus umbrales de salida.
- Candidato HIGH por escena de 16 o más junto con acumulación moderada, o acumulación de 5 o más junto con escena de al menos 8.
- Los umbrales de flujo 40/30 y 60/45 aportan evidencia e histéresis, pero el flujo alto por sí solo no confirma HIGH.

Todos los umbrales son configurables mediante `CongestionThresholds` y deben calibrarse por punto.

## Histéresis y tiempo

Los umbrales de entrada son superiores a los de salida para evitar oscilaciones. HIGH se maneja en dos fases:

1. condición severa → candidato pendiente, assessment `MODERATE`;
2. condición sostenida durante exactamente 15 segundos válidos → `HIGH` y una alerta.

Si desaparece antes, el candidato se cancela sin alerta. Una alerta HIGH no se duplica en muestras posteriores. Para salir de HIGH, las métricas deben permanecer bajo los umbrales de salida durante 5 segundos válidos; después se pasa a `MODERATE` y se cierra la alerta.

## Reset y anomalías

`reset()` elimina nivel, timestamps, candidato, temporizadores, alerta y evidencia, y obliga a un nuevo calentamiento. Timestamps o duraciones regresivas se rechazan; una pausa que incremente tiempo válido también se rechaza.

El motor no consulta `datetime.now()`, `time.time()` ni reloj monotónico interno. La misma secuencia explícita produce los mismos resultados.

## Límites operativos

- No hay agregador temporal todavía.
- No existe integración con Streamlit, visión, revisión u OCR.
- No hay persistencia de assessments o alertas.
- No existe aprobación automática del aforo ni transferencia directa a TPDA.
