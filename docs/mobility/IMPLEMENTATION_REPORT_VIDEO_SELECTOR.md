# Implementación del selector controlado de video local

## Resultado

El Centro de Monitoreo permite elegir un video pregrabado desde un catálogo
cerrado. El video demostrativo de 8 segundos sigue siendo el valor inicial y
`data/videos/samples/complex_traffic.mp4` ya está disponible como opción. Cambiar
la selección cierra el análisis anterior, limpia congestión y lote temporal, y no
inicia el nuevo análisis hasta que el usuario pulsa **Iniciar análisis**.

No se modificaron el dominio de congestión, el controlador de análisis,
VisionPipeline, YOLO, ByteTrack, OCR, revisión ni TPDA.

## Catálogo seguro

`ui/utils/video_catalog.py` recorre únicamente estas raíces dinámicas:

- `data/videos/`
- `data/videos/samples/`

La segunda es descendiente de la primera; el catálogo elimina duplicados después
del recorrido y ordena las rutas de forma determinista. Solo admite `.mp4`,
`.avi`, `.mov` y `.mkv` sin distinguir mayúsculas.

El video histórico del dashboard está en
`data/samples/ui/assets/traffic_monitoring_demo.mp4`, fuera de las raíces
dinámicas solicitadas. Para conservar compatibilidad se incluye como un único
activo incorporado, mediante ruta relativa exacta. Esta excepción no habilita el
escaneo de su carpeta ni permite seleccionar otros archivos allí.

Toda selección:

- debe ser relativa al proyecto;
- rechaza componentes `..` y rutas absolutas;
- se resuelve antes de usarse;
- debe permanecer dentro de `data/videos` o ser exactamente el demo incorporado;
- rechaza destinos resueltos fuera de las raíces, incluidos enlaces simbólicos;
- nunca expone una ruta absoluta en el selector.

Los metadatos se leen con OpenCV sin inicializar YOLO. El recurso se libera en un
bloque `finally`. Si FPS o número de frames no están disponibles, la duración se
muestra como no disponible y la opción sigue siendo utilizable.

## Videos encontrados

| Video | Duración aproximada | Ubicación relativa |
|---|---:|---|
| Video demostrativo corto | 8,0 s | `data/samples/ui/assets/traffic_monitoring_demo.mp4` |
| car-detection.mp4 | 30,2 s | `data/videos/samples/car-detection.mp4` |
| complex_traffic.mp4 | 53,9 s | `data/videos/samples/complex_traffic.mp4` |

El selector muestra nombre, duración y ubicación relativa. Para el video corto
advierte que no completa los 10 segundos de calentamiento. Para videos más largos
informa que permiten observar la transición desde Datos insuficientes.

## Ciclo de cambio de video

Cuando cambia la selección:

1. se cierra el `TrafficAnalysisController` y su fuente;
2. se elimina el controlador de la sesión;
3. se resetea y elimina el coordinador de congestión;
4. se limpian snapshot, presentación, error, alertas y clave del último frame;
5. se limpian resultado actual, metadatos de fuente y lote temporal de eventos;
6. se almacena la nueva ruta relativa y duración;
7. el estado queda detenido, sin iniciar YOLO ni consumir frames.

Al pulsar **Iniciar análisis**, la ruta vuelve a validarse contra el catálogo y se
crea `VideoFileSource`. La congestión recibe un `source_id` estable derivado de
una huella SHA-256 de la ruta relativa, sin revelar rutas absolutas. Reiniciar el
mismo video conserva esa identidad. Cámara y modo demostrativo no consumen la
selección de video.

El cambio no aprueba aforos, no transfiere datos a TPDA y no reutiliza estados de
OCR o revisión.

## Estado de sesión

- `traffic_selected_video`: valor del widget, como ruta relativa controlada.
- `traffic_selected_video_path`: ruta relativa validada para el siguiente inicio.
- `traffic_selected_video_duration`: duración opcional en segundos.
- `traffic_video_catalog_signature`: firma determinista de opciones y duraciones.

Las claves se inicializan con `setdefault` o equivalentes compatibles con
sesiones anteriores. El demo incorporado es el valor inicial mientras exista.

## Pruebas

Se añadieron 17 pruebas: 11 en `test_video_catalog.py` y 6 AppTest en
`test_traffic_monitoring_congestion_ui.py`.

Cobertura nueva:

- descubrimiento del demo y `complex_traffic.mp4`;
- extensiones, archivos ignorados, orden y deduplicación;
- traversal, rutas absolutas, archivos externos y destinos resueltos externos;
- duración disponible/no disponible y liberación del recurso;
- `source_id` estable;
- selector visible solo en video y demo como valor inicial;
- selección e inicio controlado de `complex_traffic.mp4` sin cargar YOLO;
- cierre del controlador y limpieza completa de congestión/alertas/lote;
- ausencia de inicio automático, aprobación o transferencia a TPDA.

Resultados de validación:

- catálogo y dashboard: 33 aprobadas;
- regresión focalizada: 184 aprobadas;
- AppTest específicos: 9 aprobadas;
- suite completa: 759 aprobadas.

## Limitaciones

- El catálogo refleja archivos locales existentes; no sube ni descarga videos.
- La duración depende de metadatos legibles por OpenCV.
- El selector no permite entrada libre ni navegación por el sistema de archivos.
- Las pruebas de inicio usan dobles de fuente/controlador para no cargar YOLO.
- La apariencia no se considera validada por una persona en este informe.

## Checklist visual pendiente

1. Abrir `/traffic_monitoring` y cambiar a **Video pregrabado**.
2. Confirmar que el selector muestra demo, `car-detection.mp4` y
   `complex_traffic.mp4`, sin rutas absolutas.
3. Confirmar que el demo está seleccionado inicialmente y muestra advertencia de
   duración menor a 10 segundos.
4. Elegir `complex_traffic.mp4` y comprobar duración aproximada de 53,9 segundos
   y el mensaje sobre calentamiento.
5. Verificar que el análisis no comienza hasta pulsar **Iniciar análisis**.
6. Iniciar y observar Datos insuficientes al comienzo y la transición esperada
   después de 10 segundos válidos.
7. Cambiar de video y comprobar que snapshot, métricas, duración y alertas
   anteriores desaparecen.
8. Cambiar a imagen y cámara; confirmar que el selector no aparece.
9. Confirmar legibilidad, alineación, ausencia de desbordamientos y errores rojos.
10. Finalizar y comprobar que la navegación a revisión permanece operativa.
