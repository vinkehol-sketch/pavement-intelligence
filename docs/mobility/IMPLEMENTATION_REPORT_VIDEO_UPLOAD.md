# Implementación de carga temporal de video

## Resultado

El Centro de Monitoreo incorpora la opción **Cargar video** dentro de **Video
pregrabado**, junto al catálogo **Video local del proyecto**. El archivo se valida,
se guarda con un nombre interno en el directorio temporal del sistema y solo se
analiza cuando el usuario pulsa **Iniciar análisis**.

No se modificaron el dominio de congestión, TrafficAnalysisController,
VisionPipeline, YOLO, ByteTrack, OCR, revisión, TPDA ni módulos de ingeniería.

## Arquitectura

`ui/utils/uploaded_video.py` contiene el contrato neutral
`UploadedVideoHandle` y toda la validación/persistencia. La página Streamlit solo
coordina widgets, sesión y el ciclo existente:

`st.file_uploader → UploadedVideoHandle → VideoFileSource →
TrafficAnalysisController → TrafficCongestionCoordinator`.

El selector local previo permanece sin cambios. Un `st.segmented_control` separa
el catálogo del uploader y evita mostrar ambos flujos simultáneamente.

## Validaciones

- Extensiones permitidas: `.mp4`, `.avi`, `.mov` y `.mkv`.
- MIME validado cuando está disponible; se aceptan los MIME de video esperados y
  `application/octet-stream` como valor genérico.
- Tamaño máximo demostrativo configurable: **500 MiB**.
- El tamaño declarado se revisa antes de solicitar el contenido completo.
- Se rechazan archivos vacíos, tamaños inconsistentes, extensiones/MIME no
  permitidos y nombres que contienen rutas o traversal.
- El nombre temporal usa UUID y no reutiliza el nombre original.
- La escritura usa modo exclusivo (`xb`) y no sobrescribe temporales.
- El contenido obtiene SHA-256; `source_id` usa
  `uploaded-video:<16 caracteres de la huella>`.
- OpenCV prueba el archivo después de escribirlo y libera siempre el recurso. Un
  archivo corrupto elimina el temporal y no crea controlador ni congestión.
- La ruta temporal nunca se presenta en la interfaz.

El widget también fija `max_upload_size=500`, pero esta comprobación de
Streamlit se considera solo una primera barrera: la utilidad vuelve a validar
tamaño, tipo y contenido.

## Persistencia y deduplicación

Cada upload válido posee su propio `TemporaryDirectory` con prefijo
`pavement-traffic-upload-`. El archivo vive únicamente mientras la fuente pueda
usarlo. No se escribe dentro del repositorio ni de `data/videos`.

Un contenido idéntico se reconoce por SHA-256 y reutiliza el handle mientras el
temporal exista. Un contenido distinto cierra el lote anterior, elimina su
directorio y crea un temporal nuevo. No se crean duplicados por reruns de
Streamlit.

## Limpieza explícita

La limpieza es idempotente y ocurre al:

- reemplazar o quitar el archivo del uploader;
- volver a **Video local del proyecto**;
- cambiar a cámara o imagen demostrativa;
- detectar error de validación o corrupción;
- encontrar que el temporal desapareció antes del inicio;
- finalizar el análisis o finalizar y navegar a revisión;
- abandonar el Centro de Monitoreo mediante la navegación de la aplicación.

Siempre se cierra primero `TrafficAnalysisController`; después se elimina el
temporal. La finalización conserva el snapshot final y marca el upload como
finalizado para impedir que el mismo valor persistente del widget recree el
archivo automáticamente.

`TemporaryDirectory` mantiene además su mecanismo de respaldo al terminar la
sesión o el proceso, pero la operación normal no depende exclusivamente de ese
mecanismo.

## Estado de sesión

- `traffic_video_source_mode`: catálogo local o carga.
- `traffic_uploaded_video_handle`: contrato activo o `None`.
- `traffic_uploaded_video_hash`: SHA-256 del último contenido.
- `traffic_uploaded_video_file_id`: identidad del widget para distinguir una
  carga nueva del mismo contenido.
- `traffic_uploaded_video_error`: error controlado visible.
- `traffic_uploaded_video_cleanup_token`: handle activo, inválido o finalizado.
- `traffic_analysis_active_source_id`: identidad estable usada por congestión.

Cambiar fuente limpia controlador, snapshot, presentación, error, alertas, clave
de frame, resultados, metadatos, lote temporal y revisión pendiente. No aprueba
aforos ni transfiere datos a TPDA.

## Privacidad

La interfaz informa que el archivo se procesa localmente durante la sesión y no
se incorpora al repositorio. También advierte que puede contener matrículas,
personas u otros datos sensibles y que solo debe usarse material autorizado.

No hay red, carga a servicios externos, persistencia permanente ni activación
automática de OCR por usar esta opción.

## Pruebas

Se añadieron 25 casos: 15 en `test_uploaded_video.py` y 10 en los AppTest del
Centro de Monitoreo. Cubren formatos, MIME, límite previo a lectura, vacío,
traversal, UUID, hash, `source_id`, escritura exclusiva, deduplicación,
reemplazo, corrupción, temporal ausente, limpieza idempotente, cambios de modo,
navegación, inicio, calentamiento, pausa, continuación, reset y finalización.

Los AppTest usan el demo local como bytes válidos y dobles de fuente/controlador;
no cargan YOLO ni abren una cámara física.

Resultados finales:

- upload y dashboard: 47 aprobadas;
- upload, catálogo y dashboard: 58 aprobadas;
- regresión focalizada de congestión/UI: 209 aprobadas;
- dashboard/AppTest: 32 aprobadas;
- suite completa: 784 aprobadas.

## Limitaciones y riesgos

- Un archivo cercano a 500 MiB ya reside en memoria por el funcionamiento de
  `UploadedFile`; la utilidad evita leerlo si el tamaño declarado excede el
  límite, pero no controla la recepción previa realizada por Streamlit.
- MIME y extensión no prueban contenido por sí solos; la apertura con OpenCV es
  la validación de contenido disponible en el proyecto.
- Una terminación abrupta del proceso puede impedir callbacks de aplicación; en
  ese caso actúan la limpieza de `TemporaryDirectory` y el sistema operativo.
- La apariencia visual humana permanece pendiente; AppTest valida estructura y
  comportamiento, no percepción visual.

## Checklist manual

1. Abrir `/traffic_monitoring`, seleccionar **Video pregrabado** y luego
   **Cargar video**.
2. Confirmar que el uploader solo ofrece MP4, AVI, MOV y MKV y un solo archivo.
3. Cargar un video autorizado y verificar nombre, tamaño, formato, duración y
   avisos de privacidad/sesión.
4. Confirmar que el análisis no comienza automáticamente.
5. Pulsar **Iniciar análisis** y comprobar Datos insuficientes inicialmente,
   métricas reales y ausencia de métricas sintéticas.
6. Probar pausa, continuar y reiniciar sin mezclar muestras anteriores.
7. Finalizar y comprobar snapshot final conservado y fuente cerrada.
8. Cargar otro archivo y verificar que no sobreviven métricas ni alertas.
9. Cambiar a catálogo, cámara e imagen; confirmar que el temporal previo se
   elimina y el uploader desaparece.
10. Navegar a revisión y confirmar que el flujo existente continúa operativo.
11. Confirmar textos legibles, sin desbordamientos ni errores rojos de Streamlit.
