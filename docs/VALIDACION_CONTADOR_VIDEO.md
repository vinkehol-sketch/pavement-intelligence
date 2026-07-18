# Validación funcional del contador vehicular

Fecha: 2026-07-17  
Estado: **corrección controlada aplicada y revalidada; IDs inválidos ya no contaminan el contador**.

## Resultado ejecutivo de línea base (antes de la corrección)

Se procesaron los 377 fotogramas completos de `car-detection.mp4` con ByteTrack, primero con `data/models/yolov8n.pt` y después con `data/models/yolov8s.pt`. Ambos modelos usaron exactamente el mismo video, resolución, línea, confianza, clases y parámetros de seguimiento.

El contador bruto produjo 4 eventos con YOLOv8n y 1 con YOLOv8s. Sin embargo, 3 de los 4 eventos de YOLOv8n y el único evento de YOLOv8s usan `track_id=-1`, que significa que ByteTrack todavía no asignó un ID válido. El pipeline actual entrega ese valor al contador como si fuera un track normal; por eso los totales brutos no son todavía confiables para Aforo/TPDA.

Esta sección conserva la línea base histórica. El comportamiento fue corregido y sus resultados actualizados se documentan en “Corrección controlada y revalidación”, al final del documento.

## Dependencia dinámica de ByteTrack

Al activar `YOLO.track()` se descubrió que Ultralytics requiere `lap>=0.5.12`, aunque la inferencia simple mediante `YOLO.predict()` no lo necesita y `pip check` no lo había señalado.

| Verificación | Resultado |
|---|---|
| Paquete instalado | `lap 0.5.13` |
| Entorno | exclusivamente `.venv-new` |
| Ruta importada | `D:\proyecto Vial\pavement_intelligence\.venv-new\Lib\site-packages\lap\__init__.py` |
| Import real | correcto |
| `pip check` | `No broken requirements found.` |
| Otras dependencias dinámicas nuevas | ninguna detectada |

Se añadió `lap>=0.5.12` a `pyproject.toml` y `requirements.txt`. No se instaló nada globalmente.

Como comprobación adicional, `tests/unit/test_vision_counting.py` terminó con **14 pruebas aprobadas y 0 fallidas**. Un primer intento encontró una restricción de escritura de pytest en `AppData\Temp`; al dirigir exclusivamente su carpeta temporal al proyecto, la suite terminó correctamente. No fue un error del contador.

## Punto de entrada y flujo existente

- Ejecución desatendida: `scripts/run_headless_vision.py`.
- Detección y ByteTrack: `YOLODetectorTracker` en `src/pavement_intelligence/vision/detection/yolo_detector.py`.
- Orquestación: `VisionPipeline` en `src/pavement_intelligence/vision/pipeline.py`.
- Historial, cruce y deduplicación: `VirtualLineCounter` en `src/pavement_intelligence/vision/counting/virtual_line.py`.
- Exportación: `export_corrected_records` en `src/pavement_intelligence/vision/pipeline.py`.
- Consumidor de interfaz: `src/pavement_intelligence/ui/pages/video_analysis.py`.

El recorrido comprobado fue:

`detección → ByteTrack → historial por track_id → cruce de línea → deduplicación por track_id → evento CSV`

## Configuración utilizada

| Parámetro | Valor |
|---|---|
| Video | `data/videos/samples/car-detection.mp4` |
| Fotogramas | 377 |
| FPS fuente | 12.5 |
| Resolución | 768 × 432 |
| Modelos | `data/models/yolov8n.pt`, `data/models/yolov8s.pt` |
| Dispositivo | CPU |
| Confianza mínima | 0.45 |
| Tamaño de inferencia | 640 |
| Clases | `car`, `motorcycle`, `bus`, `truck` |
| Tracker | `bytetrack.yaml`, perfil predeterminado |
| Línea | `(100, 360) → (1180, 360)` |
| Tolerancia | 3 px |
| Cooldown | 3 fotogramas |
| Edad máxima del estado | 30 fotogramas |

La línea se mantuvo sin cambios. Su extremo derecho excede el ancho de imagen, pero matemáticamente conserva una horizontal en `y=360` que cubre el cuadro.

## Métricas comparativas

Para este diagnóstico, “track creado” es un ID no negativo único emitido por ByteTrack. “Track confirmado” es un ID no negativo observado en al menos dos fotogramas; no pretende sustituir el estado interno de confirmación del tracker.

| Métrica | YOLOv8n | YOLOv8s |
|---|---:|---:|
| Fotogramas procesados | 377 | 377 |
| Detecciones vehiculares entregadas | 32 | 19 |
| Detecciones sin ID (`-1`) | 11 | 6 |
| Tracks creados con ID válido | 5 | 3 |
| Tracks confirmados por observación | 5 | 1 |
| Observaciones medias por track confirmado | 4.2 | 11.0 |
| Continuidad media dentro del span | 0.910 | 0.733 |
| Tracks con pérdida y recuperación | 2 | 1 |
| Tracks que cambiaron de clase | 1 | 0 |
| Cruces brutos | 4 | 1 |
| Cruces con ID válido | 1 | 0 |
| Cruces con ID `-1` | 3 | 1 |
| Tracks confirmados que no cruzaron | 4 | 1 |
| Repeticiones de un mismo ID en eventos | 2 | 0 |
| Pares heurísticos de fragmentación | 0 | 0 |
| Tiempo total | 12.155 s | 18.788 s |
| FPS efectivo | 31.015 | 20.066 |

YOLOv8n fue aproximadamente 1.55 veces más rápido y produjo mayor cobertura. YOLOv8s mantuvo un track principal más largo, pero omitió más pasos por la línea y no generó ningún cruce con ID válido.

## Eventos producidos

### YOLOv8n

| Fotograma | Segundo | ID | Clase | Confianza | Dirección | Evaluación |
|---:|---:|---:|---|---:|---:|---|
| 65 | 5.20 | 1 | car | 0.5700 | 1 | Cruce real con ID válido |
| 97 | 7.76 | -1 | car | 0.4883 | 1 | Vehículo visible, identidad no confirmada |
| 223 | 17.84 | -1 | car | 0.5731 | -1 | Vehículo visible, pero estado `-1` mezclado entre objetos |
| 346 | 27.68 | -1 | car | 0.5747 | -1 | Vehículo visible, identidad no confirmada |

Totales brutos por categoría: `AUTO=4`. Direcciones: `1=2`, `-1=2`.

### YOLOv8s

| Fotograma | Segundo | ID | Clase | Confianza | Dirección | Evaluación |
|---:|---:|---:|---|---:|---:|---|
| 226 | 18.08 | -1 | car | 0.5068 | -1 | Vehículo visible, identidad no confirmada |

Total bruto por categoría: `AUTO=1`. Dirección: `-1=1`.

## Estabilidad, continuidad y deduplicación

### ID `-1`

El defecto principal está en el límite entre tracker y contador. `YOLODetectorTracker` convierte una detección sin ID en `track_id=-1`; `VisionPipeline` no la descarta y `VirtualLineCounter` guarda historial para `-1` como si fuera un vehículo único.

En YOLOv8n hubo 11 observaciones con `-1`, repartidas entre fotogramas 62 y 346. En el fotograma 223 aparecieron simultáneamente dos detecciones sin ID: una `car` cerca de la línea y otra `bus` más arriba. Ambas se procesaron con el mismo identificador. Esto mezcla vehículos y lados de línea distintos, puede invertir la dirección y permite nuevos conteos cuando la limpieza elimina y recrea el estado `-1`.

Los 3 eventos `-1` de YOLOv8n reutilizan el mismo ID; por eso la métrica de repeticiones es 2. La deduplicación funciona para IDs válidos persistentes, pero no protege contra el ID centinela compartido.

### Cambio `car/bus`

El track válido 10 de YOLOv8n tuvo 7 observaciones entre los fotogramas 230 y 236: seis como `car` y una como `bus`. Además, detecciones `car` y `bus` solapadas quedaron sin ID alrededor de los fotogramas 223–229. No generaron un segundo evento válido del track 10, pero confirman oscilación de clase sobre el mismo automóvil cenital.

### Pérdidas y recuperaciones

- YOLOv8n: 2 de 5 tracks válidos presentan al menos un salto de fotograma; aun así son muy cortos, con sólo 4.2 observaciones de media.
- YOLOv8s: el único track confirmado tiene 11 observaciones en un span de 15 fotogramas y un salto máximo de 5.
- No se hallaron pares claros de fragmentación entre IDs válidos usando una ventana de 30 fotogramas y 100 px, pero esta métrica no cubre las detecciones `-1`.

## Línea y orientación

La inspección visual confirma vehículos reales moviéndose a través de la horizontal. No es un caso de orientación incorrecta ni de ausencia de cruces físicos.

La línea `y=360` está al 83.3 % de la altura del cuadro, cerca del borde de entrada inferior. Varios vehículos apenas están entrando cuando alcanzan la línea y todavía carecen de ID confirmado. Esto reduce la oportunidad de que ByteTrack acumule historial antes del cruce. La mezcla de direcciones (`1` y `-1`) no concuerda con la referencia manual previa, que marca todos los cruces como `-1`; los eventos `-1` muestran que parte de esa incoherencia proviene de mezclar objetos distintos, no necesariamente del movimiento real.

No se movió la línea durante esta validación.

## Comparación con conteo manual previo

Existe `data/processed/reports/manual_count_test_video.csv`, con 6 registros `AUTO` y dirección `-1`. Su informe asociado declara que fue estimado mediante fotogramas clave, por lo que es una referencia preliminar y no ground truth certificado.

| Modelo | Referencia manual | Conteo bruto | Diferencia absoluta | Error agregado |
|---|---:|---:|---:|---:|
| YOLOv8n | 6 | 4 | 2 | 33.33 % |
| YOLOv8s | 6 | 1 | 5 | 83.33 % |

Si sólo se aceptan eventos con ID válido, los totales técnicamente confiables serían 1 para YOLOv8n y 0 para YOLOv8s. No se recalcula un “error” con esos valores porque el software actual todavía no aplica ese filtro y la referencia manual no está certificada.

## Falsos positivos, omisiones y coherencia visual

- Los cinco fotogramas de evento contienen vehículos visibles; no se observó un evento generado sobre fondo vacío.
- Esto no valida la identidad: cuatro eventos carecen de ID confirmado.
- Respecto de la referencia de 6 autos, YOLOv8n omite al menos 2 cruces brutos y YOLOv8s al menos 5.
- YOLOv8n es más coherente con la cantidad esperada y conserva el único cruce con ID válido.
- YOLOv8s ofrece detecciones puntuales más confiables en la validación anterior, pero con confianza 0.45 pierde continuidad suficiente para contar este video.

## Archivos exportados

Carpeta: `data/processed/validation_counter/`

- `events_yolov8n.csv`, `events_yolov8s.csv`: eventos brutos.
- `category_summary_yolov8n.csv`, `category_summary_yolov8s.csv`: cruces por categoría.
- `detections_tracks_yolov8n.csv`, `detections_tracks_yolov8s.csv`: detecciones y cruces por fotograma.
- `track_summary_yolov8n.csv`, `track_summary_yolov8s.csv`: estabilidad y clases por ID válido.
- `possible_fragmentations_yolov8n.csv`, `possible_fragmentations_yolov8s.csv`: candidatos heurísticos.
- `comparative_metrics.csv`: comparación agregada.
- `manual_comparison.csv`: comparación por categoría con la referencia previa.
- `configuration.json`: configuración y rutas de pesos.
- `metrics.json`: métricas completas y eventos.

No se generó un nuevo video: el sistema tiene una opción existente para video procesado, pero las tablas y la inspección puntual fueron suficientes y evitan duplicar un MP4 completo.

## Recomendación para el MVP

Con la configuración actual, YOLOv8n funciona mejor para este MVP: obtiene 4 cruces brutos frente a 1, conserva el único evento con ID válido y procesa a 31 FPS frente a 20 FPS. Esta recomendación es provisional y no significa que el contador esté listo para producción.

Ajustes sugeridos, **no aplicados**:

1. No enviar al contador detecciones con `track_id < 0`; conservarlas sólo como diagnóstico.
2. Exigir un ID confirmado y una historia mínima antes de habilitar un cruce.
3. Resolver la categoría del evento con clase dominante del historial, no sólo con la clase instantánea del cruce.
4. Después de corregir `-1`, evaluar de forma controlada una línea más alta para dar tiempo de confirmación al tracker antes del cruce.
5. Si aún hay omisiones, variar una sola condición por prueba: primero línea, luego confianza y finalmente parámetros de ByteTrack.
6. Crear una anotación manual cuadro a cuadro certificada para medir falsos positivos, omisiones y error real.

## Limitación de dominio COCO

El video es cenital y muestra vehículos de juguete o a escala. Los pesos COCO están entrenados principalmente con escenas y objetos de escala natural. Esto explica detecciones intermitentes, oscilación `car/bus`, baja continuidad y diferencias importantes entre modelos. Un modelo especializado o ajuste fino podría ser necesario después de corregir primero el contrato de IDs.

## Aptitud para integración con Aforo y TPDA

La cadena técnica ejecuta detección, tracking, historial, cruce y exportación, pero **todavía no conviene conectar automáticamente sus totales con Aforo y TPDA**. Antes debe corregirse o filtrarse `track_id=-1` y repetirse esta prueba. Los CSV exportados sí pueden emplearse para auditoría y corrección manual, manteniendo separados los eventos confiables de los no confirmados.

---

## Corrección controlada y revalidación

### Defectos corregidos

1. `VisionPipeline` valida el ID antes de llamar a `VirtualLineCounter`. Rechaza `None`, `-1`, booleanos, valores no enteros y cualquier entero negativo. La caja puede seguir dibujándose como `sin_track`, pero no crea historial, no altera lados y no emite eventos.
2. El cruce exige por defecto 3 posiciones, evidencia en ambos lados, al menos 10 px de desplazamiento y una separación máxima de 10 fotogramas entre observaciones consecutivas. Los valores son parámetros explícitos de `VisionPipeline` y `VirtualLineCounter`.
3. La clase final usa mayoría del historial del track; un empate se resuelve por confianza acumulada. La confianza del evento es el promedio del historial válido.
4. La limpieza ya no elimina un ID contado sólo porque esté ausente en el fotograma de limpieza. Conserva la deduplicación hasta superar `max_state_age_frames`.
5. Se añadieron métricas backend de IDs descartados, tracks con/sin historia suficiente, eventos emitidos y bloqueos por duplicación, oscilación o historia insuficiente. No se agregó ninguna obligación a la interfaz.

### Archivos modificados

- `src/pavement_intelligence/vision/detection/base.py`
- `src/pavement_intelligence/vision/pipeline.py`
- `src/pavement_intelligence/vision/counting/virtual_line.py`
- `tests/unit/test_vision_counting.py`
- `docs/VALIDACION_CONTADOR_VIDEO.md`

No se modificaron `survey_tpda.py`, Streamlit, TPDA, ESAL, AASHTO ni los CSV demostrativos.

### Pruebas añadidas

Se cubren explícitamente los ocho escenarios solicitados:

1. `track_id=-1` nunca genera evento.
2. `track_id=None` nunca genera evento.
3. Un track válido con historia insuficiente no cruza.
4. Un track válido con historia suficiente sí cruza.
5. La oscilación `car/bus` conserva categoría estable por mayoría.
6. Un ID no se cuenta dos veces por oscilación.
7. Una pérdida corta y recuperación no duplica el evento.
8. Detecciones sin ID no contaminan el historial válido.

Resultado de toda la suite: **30 aprobadas, 0 fallidas**, en 7.78 s.

### Configuración de revalidación

Se ejecutó sólo YOLOv8n, primero como se pidió, sobre los 377 fotogramas completos. Se mantuvieron el video, CPU, confianza 0.45, tamaño 640, ByteTrack predeterminado, clases COCO vehiculares, resolución 768 × 432, línea `(100,360)→(1180,360)`, tolerancia 3, cooldown 3 y edad máxima 30. La línea no fue movida.

Los nuevos parámetros de robustez fueron los valores predeterminados documentados: historia mínima 3, desplazamiento mínimo 10 px y salto temporal máximo 10 fotogramas.

### Comparación YOLOv8n antes/después

| Métrica | Antes | Después |
|---|---:|---:|
| Fotogramas | 377 | 377 |
| Detecciones vehiculares | 32 | 32 |
| Detecciones con ID inválido observadas | 11 | 11 |
| Detecciones con ID inválido que entraron al contador | 11 | 0 |
| Detecciones con ID inválido descartadas | 0 | 11 |
| Tracks válidos creados | 5 | 5 |
| Tracks confirmados / con historia suficiente | 5 | 5 |
| Tracks descartados por historia insuficiente | no registrado | 0 |
| Cruces brutos | 4 | 1 |
| Cruces con ID válido | 1 | 1 |
| Eventos contaminados por `-1` | 3 | 0 |
| Repeticiones de ID entre eventos | 2 | 0 |
| Direcciones | `1:2`, `-1:2` | `1:1` |
| Categorías | `AUTO:4` | `AUTO:1` |
| Eventos bloqueados por duplicación | no registrado | 0 |
| Eventos bloqueados por oscilación | no registrado | 0 |
| Intentos bloqueados por historia insuficiente | no registrado | 0 |
| Continuidad media de tracks | 0.910 | 0.910 |
| Tiempo | 12.155 s | 13.895 s |
| FPS efectivo | 31.015 | 27.132 |

La diferencia de FPS es orientativa: fueron ejecuciones separadas y no un benchmark repetido. El filtro no cambia la inferencia ni ByteTrack, por lo que las 32 detecciones y los 5 IDs válidos permanecen iguales.

### Resultado real corregido

Quedó un evento válido:

| Fotograma | Segundo | ID | Clase estable | Categoría | Confianza promedio | Dirección |
|---:|---:|---:|---|---|---:|---:|
| 65 | 5.20 | 1 | car | AUTO | 0.5857 | 1 |

Las 11 detecciones `track_id=-1` quedaron registradas como descartadas y ninguna aparece en el historial del contador. No persisten eventos duplicados en esta ejecución.

### Estabilidad de clase

El track 10 todavía contiene la oscilación observacional `bus|car`, pero su clase estable es `car`: 6 de 7 observaciones, proporción dominante 0.8571. No cruzó la línea y no emitió evento. El evento del track 1 conserva `car/AUTO`. Por tanto, la oscilación puntual ya no puede cambiar arbitrariamente la categoría final, aunque la limitación visual COCO continúa existiendo.

### Métricas de historia y cruces

- Tracks válidos creados: 5.
- Tracks con historia suficiente: 5.
- Tracks con historia insuficiente: 0.
- Tracks con cruce válido: 1.
- Proporción de tracks con historia suficiente que alcanzó un cruce: **20 %** (1 de 5).
- Eventos emitidos: 1.
- Eventos bloqueados por duplicación: 0.
- Eventos bloqueados por oscilación: 0.
- Intentos bloqueados por historia insuficiente: 0.

La ausencia de más cruces no se debe a la nueva historia mínima: los cinco tracks válidos alcanzaron tres posiciones y ningún intento fue bloqueado por esa regla.

### Decisión sobre la línea

La línea está en `y=360`, aproximadamente 72 px sobre el borde inferior: 16.7 % de la altura desde abajo, o 83.3 % desde arriba. Sólo 1 de 5 tracks válidos alcanzó a demostrar un cruce. Varios IDs se crean cuando el vehículo ya está por encima de la línea, y otro aparece abajo pero se pierde antes de consolidar el paso. Esto indica que la proximidad al borde sí contribuye de forma importante, junto con las detecciones intermitentes del dominio cenital.

No se cambió la línea. Para una prueba posterior, manteniendo todas las demás variables fijas, se sugieren dos candidatas horizontales:

- `y=320`: 112 px desde el borde inferior, 25.9 % de la altura.
- `y=300`: 132 px desde el borde inferior, 30.6 % de la altura.

Debe probarse primero `y=320`; sólo si la continuidad sigue siendo insuficiente, probar `y=300`. Estas posiciones son candidatas de calibración, no cambios aprobados.

### Archivos de revalidación

En `data/processed/validation_counter/`:

- `events_yolov8n_after_fix.csv`
- `track_summary_yolov8n_after_fix.csv`
- `diagnostics_yolov8n_after_fix.csv`
- `category_summary_yolov8n_after_fix.csv`
- `metrics_yolov8n_after_fix.json`
- `configuration_yolov8n_after_fix.json`

### Decisión de integración con Aforo y TPDA

El defecto de identidad quedó corregido: sólo eventos con ID válido pueden alimentar una exportación. Sin embargo, el resultado automático sigue siendo 1 frente a la referencia manual preliminar de 6 autos, y sólo 20 % de los tracks válidos cruza la línea. Por esta omisión elevada, **todavía no debe conectarse automáticamente el total con Aforo y TPDA**.

Sí puede avanzarse a una prueba controlada de línea y continuar exportando los eventos para auditoría/corrección manual. La conexión automática debe esperar a que una calibración de una sola variable mejore la cobertura sin reintroducir duplicaciones.

---

## Calibración controlada de posición de línea

Fecha: 2026-07-17.

Se compararon `y=360`, `y=320` y `y=300` sobre los mismos 377 fotogramas. La única variable modificada fue la coordenada Y de la línea horizontal. Se conservaron YOLOv8n, confianza 0.45, imagen 640, CPU, clases vehiculares COCO, ByteTrack predeterminado, tolerancia 3, cooldown 3, edad máxima 30, historia mínima 3, desplazamiento mínimo 10 px, salto máximo 10, estabilización por mayoría y deduplicación corregida.

### Resultados

| Métrica | y=360 | y=320 | y=300 |
|---|---:|---:|---:|
| Tracks válidos | 5 | 5 | 5 |
| Tracks con historia suficiente | 5 | 5 | 5 |
| Cruces válidos | 1 | 0 | 0 |
| Dirección 1 | 1 | 0 | 0 |
| Dirección -1 | 0 | 0 | 0 |
| AUTO | 1 | 0 | 0 |
| IDs inválidos descartados | 11 | 11 | 11 |
| Eventos duplicados bloqueados | 0 | 0 | 0 |
| Eventos bloqueados por oscilación | 0 | 0 | 0 |
| Tracks que no alcanzaron la línea | 4 | 5 | 5 |
| Tiempo | 13.724 s | 15.331 s | 12.351 s |
| FPS efectivo | 27.470 | 24.591 | 30.524 |

Las diferencias de velocidad corresponden a ejecuciones individuales y no deben interpretarse como efecto causal de la línea: la posición no cambia el coste de inferencia.

### Comparación con referencia manual preliminar

| Posición | Automático | Referencia preliminar | Diferencia absoluta | Posibles omitidos | Posibles falsos positivos | Observaciones |
|---|---:|---:|---:|---:|---:|---|
| y=360 | 1 | 6 | 5 | 5 | 0 observados | El único evento tiene ID válido y corresponde visualmente a un auto real. |
| y=320 | 0 | 6 | 6 | 6 | 0 observados | Ningún ID persistió hasta interceptar la línea. |
| y=300 | 0 | 6 | 6 | 6 | 0 observados | Elevar más la línea aumentó la distancia que el track debía sobrevivir. |

La referencia de seis autos continúa siendo preliminar y no se usó como valor objetivo para ajustar parámetros.

### Revisión visual

Se guardó una imagen del fotograma 65 por configuración. En `y=360`, el centro del track 1 cambia de lado y produce un evento coherente en dirección 1. En `y=320` y `y=300`, el mismo auto está claramente visible y su caja intersecta visualmente la horizontal, pero el centroide sigue aproximadamente en `y=354`; el ID desaparece cerca de `y=339`, antes de que el centro alcance cualquiera de las líneas elevadas.

No se observaron cruces falsos por detección temprana en ninguna posición. En `y=320` y `y=300` tampoco hubo eventos de vehículos que comenzaran directamente al otro lado: esos tracks quedaron correctamente como trayectorias sin cruce, porque carecían de puntos válidos a ambos lados.

La dirección del único cruce (`1`) es coherente con el desplazamiento observado desde la parte inferior hacia la superior del cuadro. Las líneas elevadas no ofrecen eventos con los cuales comparar sentido.

### Interpretación

Elevar la línea no corrige las omisiones. Los IDs válidos son demasiado cortos: algunos se crean cuando el vehículo ya pasó `y=320/y=300`, y el track que sí comienza debajo desaparece antes de llegar. La falta de cruces en las posiciones elevadas se debe a continuidad de detección/tracking frente al dominio cenital, no a historia mínima, deduplicación u oscilación; todas esas métricas permanecieron estables.

La línea actual está a 72 px del borde inferior. `y=320` está a 112 px y `y=300` a 132 px. Dar más distancia previa al tracker sólo ayudaría si el ID se mantuviera durante ese recorrido; en este video ocurre lo contrario.

### Decisión

De las tres posiciones probadas, se recomienda **mantener `y=360`**. Es la única que produce un cruce válido, sin falsos positivos ni duplicaciones, y es la más cercana a la referencia manual preliminar. `y=320` y `y=300` deben descartarse para la configuración actual.

Esto no convierte todavía `y=360` en una configuración automática definitiva del MVP: su cobertura es 1 de 6 respecto de la referencia preliminar. Puede conservarse como configuración provisional para demostración auditada, con revisión manual obligatoria. Antes de alimentar Aforo/TPDA automáticamente debe resolverse la intermitencia de detección/tracking o evaluarse un modelo adaptado al video cenital, manteniendo pruebas de una sola variable.

### Artefactos separados

- `data/processed/validation_counter/line_y360/`
- `data/processed/validation_counter/line_y320/`
- `data/processed/validation_counter/line_y300/`
- `data/processed/validation_counter/line_calibration_comparison.csv`

Cada carpeta contiene configuración, métricas, eventos, resumen de tracks, diagnósticos, resumen por categoría y una evidencia visual con la línea dibujada.
