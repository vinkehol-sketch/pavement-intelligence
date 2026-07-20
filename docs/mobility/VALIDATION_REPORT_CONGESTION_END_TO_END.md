# Validación end-to-end de la Estimación Operativa de Congestión

## Resultado ejecutivo

La integración evaluada es funcional y reproducible. Las secuencias controladas
demostraron calentamiento, NORMAL, MODERATE, candidato HIGH, confirmación HIGH,
alerta única, recuperación, pausa, reset, cambio de fuente y finalización
idempotente. La corrida headless con video real recorrió 647 frames sin duplicar
muestras ante reruns y cerró la fuente correctamente.

No se encontró un defecto reproducible en producción y no se modificó código de
producción. La inspección visual humana en navegador queda pendiente porque esta
sesión no dispuso de un navegador integrado; los tres AppTest de Streamlit sí
fueron aprobados y se deja un checklist manual exacto.

## Entorno y alcance

- Fecha: 2026-07-20.
- Rama: `main`.
- Commit principal: `5eb2a80` (`feat(ui): integrate operational congestion monitoring`).
- Dependencias inmediatas evaluadas: `5125d75` (runtime) y `2aef3d4`
  (agregador temporal).
- Python 3.14.6, Streamlit 1.59.2, OpenCV 5.0.0.93 y Ultralytics 8.4.100.
- Modelo local: `data/models/yolov8n.pt`, CPU, confianza 0,45, imagen 640.
- No se descargaron datos ni modelos y no se hizo commit ni push.

La arquitectura se mantuvo sin desvíos:

`TrafficAnalysisController → FrameAnalysisResult → TrafficCongestionCoordinator
→ TrafficCongestionSnapshot → presentación Streamlit`.

La página entrega cada resultado al helper de sesión; el coordinador usa el
agregador y el motor. La presentación solo formatea el snapshot. No se hallaron
cálculos de flujo, acumulación, histéresis, confirmación, recuperación o
`alert_id` en `traffic_monitoring.py`.

## Auditoría rápida

### Configuración activa

| Concepto | Entrada | Salida |
|---|---:|---:|
| Calentamiento | 10 s válidos y 3 muestras | — |
| Escena MODERATE | 8 vehículos | 5 vehículos |
| Escena HIGH | 16 vehículos | 12 vehículos |
| Flujo MODERATE | 40 veh/min | 30 veh/min |
| Flujo HIGH | 60 veh/min | 45 veh/min |
| Acumulación MODERATE | 2 veh/min | 1 veh/min |
| Acumulación HIGH | 5 veh/min | 2 veh/min |
| Confirmación HIGH | 15 s válidos | — |
| Recuperación desde HIGH | 5 s válidos | — |

La configuración se identifica como demostrativa. El resultado tiene
`origin = OPERATIONAL_ESTIMATE` y `normative = false`; no se presenta como Nivel
de Servicio ni usa velocidad en km/h.

### Estado de sesión y deduplicación

Las claves aisladas son coordinador, snapshot, presentación, error, fuente,
último frame y alertas, todas con prefijo `traffic_congestion_`. La clave de frame
es `(source_id, frame_index, timestamp_seconds, end_of_source)`. Un rerun con la
misma clave reutiliza la presentación y no llama de nuevo al coordinador. Las
alertas se insertan o reemplazan por `alert_id`, por lo que el cierre actualiza la
misma alerta y no crea otra fila.

## Secuencias controladas

Se añadieron siete pruebas en
`tests/integration/test_congestion_dashboard_scenarios.py`. Usan resultados de
frame deterministas y el flujo real de sesión, agregador, motor, coordinador,
snapshot y presentación; no sustituyen umbrales ni componentes de dominio.

| Escenario | Entrada controlada | Resultado demostrado |
|---|---|---|
| A | escena 2 en 0, 5 y 10 s | INSUFFICIENT_DATA en 0/5 s; NORMAL con 10 s y 3 muestras |
| B | NORMAL; escena 8, 7 y 5 en 11/12/13 s | entrada MODERATE, permanencia en histéresis y salida solo en el umbral |
| C | escena 10, 12, 14, 16 y 18 en 0/5/10/20/25 s | candidato HIGH en 10 s; 10 s aún sin alerta; HIGH justo a 15 s y una alerta |
| D | después de HIGH, escena 5 en 27 y 30 s | sigue HIGH con 2 s; recupera a MODERATE a los 5 s; misma alerta cerrada |
| E | candidato en 10 s; pausa; rerun a 20 s; resume y frame a 25 s | pausa no incrementa muestra, observación ni candidato; tras resume el candidato lleva 5 s válidos |
| F | HIGH; reset; fuente nueva en 100 s | IDLE sin snapshot/alertas/clave; primera muestra nueva con duración y flujo cero |
| Final | último frame repetido; `finish` dos veces | 3 muestras, snapshot final conservado, ninguna muestra o alerta duplicada |

Evidencia de alertas: el escenario C crea exactamente una alerta activa y el
frame repetido conserva una sola entrada. El escenario D mantiene el mismo
`alert_id`, cambia su estado a cerrada y conserva una sola entrada. Todos los
snapshots presentados tienen `normative = false`.

## Video real headless

Se inspeccionaron los videos locales. El video demostrativo de la página dura
8,00 s y no alcanza el calentamiento. Existen videos adecuados más largos; se
seleccionó `data/videos/samples/complex_traffic.mp4` por su duración y contenido
de tráfico. La herramienta reproducible es
`scripts/validate_congestion_video.py`.

Comando:

```powershell
.\.venv\Scripts\python.exe scripts/validate_congestion_video.py `
  --video data/videos/samples/complex_traffic.mp4 `
  --model data/models/yolov8n.pt
```

Resultados:

| Evidencia | Resultado |
|---|---:|
| Duración / FPS fuente | 53,917 s / 12,0 FPS |
| Frames válidos / muestras | 647 / 647 |
| Transiciones | 0,000 s INSUFFICIENT_DATA; 10,000 s NORMAL |
| Eventos / eventos únicos | 1 / 1 |
| Alertas / alertas únicas | 0 / 0 |
| Resultado terminal | 1 |
| Claves únicas | 648 (647 frames + terminal) |
| Reruns simulados | 648 |
| Mutaciones causadas por rerun | 0 |
| Fuente cerrada | sí |
| Finalización idempotente / snapshot preservado | sí / sí |
| Tiempo / FPS de procesamiento | 16,608 s / 38,96 FPS |
| Resultado final | NORMAL, no normativo, origen OPERATIONAL_ESTIMATE |

La ausencia de HIGH y de alertas en este video es coherente con sus métricas; no
se alteraron umbrales para forzar estados. HIGH, alerta y recuperación quedan
demostrados de forma determinista en las secuencias controladas.

Como contraste, `car-detection.mp4` (30,160 s, 377 frames) también completó
377 muestras, transición a NORMAL a 10,000 s, un terminal, 378 claves y cero
mutaciones ante 378 reruns.

## Streamlit: AppTest y validación visual

Los AppTest de los tres modos aprobaron:

- imagen demostrativa separada, sin crear coordinador real;
- video pregrabado con snapshot y deduplicación sin excepciones;
- cámara sin abrir el dispositivo durante la prueba ni crear un lote de congestión.

Resultado: **3 aprobadas en 3,27 s**.

Streamlit se inició localmente en un puerto libre y quedó escuchando, pero el
navegador integrado respondió `No browser is available`. Por tanto, la apariencia
visual real **no se declara aprobada** en esta ejecución.

### Checklist manual pendiente

1. Iniciar `streamlit run src/pavement_intelligence/ui/app.py` y abrir el Centro
   de monitoreo.
2. En **Imagen demostrativa**, confirmar la marca visible de simulación y que no
   aparecen coordinador, snapshot ni alertas reales.
3. Cambiar a **Video pregrabado**, iniciar y confirmar inicialmente “Datos
   insuficientes”, tiempo observado creciente, flujo/escena/acumulación y
   “Velocidad: No calibrada”.
4. Confirmar el texto visible “Estimación operativa; no corresponde a un Nivel
   de Servicio normativo”.
5. Pausar antes de finalizar el video y anotar tiempo y métricas; esperar varios
   reruns y comprobar que permanecen iguales y el encabezado indica pausa.
6. Reanudar y comprobar que el tiempo válido continúa sin sumar la pausa.
7. Reiniciar y comprobar que desaparecen snapshot previo y alertas y vuelve el
   calentamiento.
8. Finalizar y revisar: comprobar snapshot final conservado, una sola muestra
   terminal lógica, fuente cerrada y ninguna alerta duplicada.
9. En **Cámara**, no conceder acceso si no se desea; confirmar que cambiar de
   fuente no conserva el estado del video.
10. Para aislamiento de error, usar el AppTest existente: un fallo del coordinador
    conserva la última vista y muestra el error sin descartar el resultado
    vehicular. No provocar manualmente un fallo artificial en producción.

## Pruebas y controles finales

| Control | Resultado |
|---|---|
| Pruebas nuevas | 7 aprobadas en 0,05 s |
| Regresión focalizada de congestión/UI | 167 aprobadas en 3,50 s |
| Suite completa | 742 aprobadas en 11,80 s (base 735 + 7 nuevas) |
| AppTest | 3 aprobadas en 3,27 s |
| Ruff sobre archivos creados/modificados | aprobado |
| `pip check` | aprobado |
| `git diff --check` | aprobado |

## Defectos, limitaciones y riesgos restantes

- Defectos de producción encontrados: ninguno.
- Correcciones necesarias antes de un eventual commit: ninguna en producción.
- Se corrigió durante la preparación una métrica de la herramienta headless que
  comparaba identidad de objetos de presentación en vez de igualdad más identidad
  del snapshot; no afectaba el sistema evaluado.
- Limitación: falta la inspección humana del navegador, indicada en el checklist.
- El video embebido del dashboard dura 8 s; por diseño no puede mostrar NORMAL en
  esa ejecución. La validación de más de 10 s se realizó headless con videos
  locales más largos.
- Un video real no garantiza producir HIGH; la demostración reproducible de HIGH
  debe usar las secuencias controladas o un video validado que sostenga las
  condiciones configuradas.
- No se modificaron motor, agregador, runtime, presentación productiva, sesión
  productiva, página Streamlit, controlador, VisionPipeline, YOLO, ByteTrack,
  OCR, revisión, TPDA, pesaje, ESAL, geotecnia ni pavimentos.
