# Informe de implementación — Video demostrativo de tráfico

## Alcance

El Centro de Monitoreo conserva la imagen urbana anotada como modo inicial y fallback, y añade un reproductor de video local controlado desde Streamlit. El reproductor es exclusivamente demostrativo: no importa ni ejecuta YOLO, ByteTrack, OCR, eventos de cruce ni el pipeline oficial de visión.

## Fuente local

- Archivo: `data/samples/ui/assets/traffic_monitoring_demo.mp4`
- Origen: generado localmente a partir de `traffic_monitoring_urban_avenue.png`.
- Formato: MP4 (`mp4v`).
- Duración: 8 segundos.
- Resolución: 1672 × 766 píxeles.
- Frecuencia: 8 FPS.
- Fotogramas: 64.
- Privacidad: usa únicamente el fotograma demostrativo preprocesado existente; no contiene matrículas reales ni datos externos.

Antes de generarlo se revisaron `data/videos/`, `data/samples/` y `data/raw/`. No existía otro video local: `data/videos/` y `data/raw/` solo contenían sus archivos `.gitkeep`.

## Estrategia de reproducción

`demo_video.py` concentra la inspección, lectura, conversión BGR→RGB, límites de índice, progreso, avance temporal, reinicio y métricas sintéticas. Cada lectura crea un `cv2.VideoCapture`, extrae un único fotograma y lo libera mediante `finally`. No hay recursos globales, hilos, colas, escritura en disco ni bucles bloqueantes.

La página usa un fragmento Streamlit con actualización cada 150 ms solo mientras el modo `Video local` está reproduciéndose. El avance se calcula con reloj monotónico y FPS fuente; la UI se actualiza a una frecuencia reducida y estable. Pausar conserva el índice y las métricas. Reiniciar vuelve al fotograma cero, pausa y restablece las métricas iniciales.

El estado usa exclusivamente claves `traffic_demo_*`. No reutiliza estados de aforo, aprobación, OCR ni integración técnica.

## Comportamiento de seguridad

- El modo inicial es `Imagen estática` y no reproduce automáticamente.
- Los controles están deshabilitados en modo imagen.
- Un error de ruta, apertura, metadatos o lectura detiene la reproducción, presenta un mensaje y muestra el fotograma estático.
- Las métricas se derivan de una serie determinista basada solo en el progreso y muestran permanentemente “Métricas demostrativas, no calculadas desde el video”.
- El reproductor no modifica conteo oficial, clasificación oficial, direcciones, revisión, TPDA ni ESAL.

## Pruebas

Se añadieron 26 pruebas en `tests/unit/test_traffic_demo_video.py` para:

- inspección válida, archivo inexistente y archivo corrupto;
- primer y último fotograma, índices negativos y fuera de rango;
- conversión RGB y validación de imágenes;
- progreso, avance, loop y pausa al final;
- métricas deterministas y reinicio;
- aislamiento del estado;
- ausencia de Streamlit, IA y escritura en la utilidad;
- render estático y render de video mediante AppTest;
- visibilidad y estado de controles;
- secuencia Reproducir, Pausar y Reiniciar sin excepciones.

## Limitaciones de Streamlit

Streamlit funciona por reruns y no como un reproductor multimedia de tiempo real. Por ello la reproducción puede saltar fotogramas si un render tarda más que el intervalo visual; se conserva el tiempo lógico y se prioriza la estabilidad. El video no incluye audio ni busca sincronización exacta con la frecuencia original. La barra informa progreso, pero no actúa como editor ni permite carga externa en esta fase.

## Cómo probar

1. Ejecutar `streamlit run src/pavement_intelligence/ui/app.py`.
2. Abrir **Monitoreo de tráfico**.
3. Confirmar que inicia en **Imagen estática** y los controles están deshabilitados.
4. Cambiar **Fuente de demostración** a **Video local**.
5. Usar **Reproducir**, **Pausar** y **Reiniciar** y observar fotograma, progreso, tiempo y métricas simuladas.
6. Ejecutar `pytest -q tests/unit/test_traffic_demo_video.py` para la validación aislada.
