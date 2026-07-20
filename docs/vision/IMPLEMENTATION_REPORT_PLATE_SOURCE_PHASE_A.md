# Implementación de fuente OCR independiente — Fase A

## Resultado

Se incorporó una fuente visual cercana para lecturas OCR de placas, separada del
pipeline panorámico. El incremento no modifica ni reutiliza
`TrafficAnalysisController`, `VisionPipeline`, YOLO, ByteTrack, la revisión del
aforo ni las transferencias hacia TPDA. Tampoco implementa asociación
placa–vehículo.

La ruta nueva es:

`FrameSource → PlateAnalysisController → ROI configurable → PlateReader →`
`PlateFrameResult / PlateBatchResult → revisión OCR`.

Los resultados son auxiliares, no normativos y no aprueban ni alimentan cálculos
oficiales.

## Estrategia de extracción

No existe actualmente un detector de placas dedicado en el repositorio. Esta
fase utiliza `NormalizedRoiExtractor`, una región rectangular normalizada y
configurable sobre el video cercano. La configuración predeterminada cubre la
zona central inferior del frame (`x=0.10..0.90`, `y=0.25..0.90`).

La interfaz muestra tanto el frame como la región seleccionada y la etiqueta
explícitamente como **ROI, no detector**. No se afirma detección automática de
placas.

## Contratos neutrales

`ocr_models.py` define contratos congelados, sin estado de interfaz:

- `PlateAnalysisState`: `IDLE`, `RUNNING`, `PAUSED`, `FINISHED` y `ERROR`;
- `PlateReadingCandidate`: evidencia, texto, confianza, origen y revisión;
- `PlateFrameResult`: resultado del frame, ROI, advertencias y terminalidad;
- `PlateBatchResult`: lote independiente con `normative = false`.

Cada lote recibe un `plate_batch_id` nuevo. La fuente puede recibir un
`source_id` estable distinto de la ruta física o del nombre temporal.

## Ciclo de vida

`PlateAnalysisController` implementa inicio, procesamiento, pausa, continuación,
finalización idempotente, reset completo, cambio de fuente, error y cierre
explícito. La pausa devuelve el último resultado sin leer otro frame. Un error
cierra la fuente y requiere `reset()` para volver a `IDLE`.

El controlador recibe por inyección:

- `FrameSource`;
- `AbstractPlateReader`;
- `PlateCandidateExtractor`;
- `PlateAnalysisConfig`.

No importa Streamlit, no escribe archivos, no usa reloj real y no conoce claves
del aforo.

## Frecuencia y deduplicación

La evaluación OCR usa `every_n_frames`, configurable y determinista. El valor
predeterminado es 5, por lo que no se ejecuta OCR sobre todos los frames.

La deduplicación combina:

- `source_id`;
- texto normalizado;
- referencia de ROI;
- ventana temporal configurable.

Una lectura equivalente dentro de la ventana no se duplica. Si una repetición
tiene mayor confianza, reemplaza la evidencia conservando el mismo
`reading_id`. El índice LRU de deduplicación y el número de lecturas del lote
tienen límites configurables, por lo que la memoria queda acotada. No se usa
`track_id`.

## Privacidad y revisión

Las placas se muestran enmascaradas de forma predeterminada. Revelarlas requiere
una acción explícita y genera un registro en `plate_session_reveal_audit`. Las
correcciones y rechazos son registros manuales separados: no mutan la lectura
original.

Los frames y ROI solo viven en memoria. Los uploads usan `TemporaryDirectory` y
se eliminan al reemplazar o retirar el archivo, cambiar fuente o modo, finalizar
el lote y abandonar la página. No se guardan recortes de placa permanentemente.

La página muestra el aviso: **“Las lecturas OCR son auxiliares y requieren
revisión humana.”**

## Integración de interfaz

La página existente **Lecturas de placas** conserva dos modos excluyentes:

- **Demostración sintética**, predeterminada y con sus contratos existentes;
- **Análisis OCR real**, con video local, upload temporal y cámara opcional.

El modo real ofrece iniciar, procesar el siguiente frame, pausar, continuar,
finalizar y reiniciar. Usa exclusivamente claves `plate_session_*`. Cambiar de
fuente cierra el controlador, limpia lote, lecturas, deduplicación, revisiones,
auditoría y temporales sin tocar claves `traffic_*`.

La navegación principal cierra los recursos OCR cuando el usuario abandona la
página.

## Estado real de PaddleOCR

PaddleOCR **no está instalado** en el entorno validado. No se instaló ninguna
dependencia ni se descargaron modelos. La interfaz detecta esta ausencia y
muestra un error opcional controlado al intentar iniciar el análisis real.

Por ello no se afirma que OCR real haya sido validado. Las pruebas funcionales
del controlador usan un reader falso inyectado únicamente desde pruebas. La
prueba con una imagen individual autorizada, el texto/confianza/duración y la
versión del backend quedan pendientes hasta que el usuario autorice la
instalación y disponibilidad del modelo.

## Pruebas

Se añadieron pruebas unitarias y AppTest para contratos, lifecycle, frecuencia,
normalización, deduplicación, límites de memoria, errores, privacidad,
corrección, rechazo, separación sintético/real, fuentes locales, upload temporal,
ausencia opcional de PaddleOCR y limpieza al navegar.

Resultados finales:

- pruebas nuevas: **78 aprobadas**;
- regresión OCR existente: **57 aprobadas**;
- AppTest de Lecturas de placas: **18 aprobadas**;
- regresión focalizada: **217 aprobadas**;
- suite completa: **862 aprobadas**.

## Limitaciones y siguiente fase

- La ROI presupone una cámara cercana y encuadre estable; no localiza placas.
- PaddleOCR y sus modelos siguen siendo opcionales y no están instalados.
- No se ejecutan dos cámaras simultáneamente.
- No existe asociación entre lectura OCR y evento vehicular.
- No hay persistencia de imágenes, aprobación automática ni transferencia a
  TPDA, ESAL o diseño de pavimentos.
- La calibración de ROI, rendimiento y exactitud deberá validarse con material
  autorizado cuando el backend real esté disponible.

La siguiente fase puede evaluar un detector de placas dedicado y una política de
evidencia, manteniendo la asociación opcional, reversible y manualmente
confirmada definida en la arquitectura documental.
