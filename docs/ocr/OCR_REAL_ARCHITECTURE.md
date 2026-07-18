# Arquitectura Técnica para la Integración de OCR Real de Placas

Este documento define la arquitectura técnica para la futura integración del sistema de Reconocimiento Automático de Placas (LPR/OCR) en el proyecto Pavement Intelligence. La arquitectura es estrictamente **de solo lectura para el pipeline de visión, experimental y desacoplada** de la lógica de aforo y diseño estructural.

---

## 1. Diseño del Flujo de Procesamiento Desacoplado

Para evitar cualquier acoplamiento con Streamlit o con los procesos de conteo y seguimiento, la arquitectura de procesamiento OCR opera de manera neutral y unidireccional. **Ningún componente bajo la carpeta `vision/` ni el propio `VisionPipeline` interactúan o conocen la existencia de `st.session_state` o de la interfaz de Streamlit.**

```
+-----------------------------------------------------------------------------------+
|                            PIPELINE DE VISIÓN PRINCIPAL                           |
|  [Video / Cámara] --> [Detección YOLOv8] --> [Seguimiento ByteTrack]              |
+-----------------------------------------------------------------------------------+
                                         |
                                         | (Salida neutral y tipada: bounding boxes,
                                         |  track_id, frames del video)
                                         v
+-----------------------------------------------------------------------------------+
|                         SERVICIO / ORQUESTRADOR OCR NEUTRAL                       |
|                                                                                   |
|  1. Evaluación de Calidad de Fotogramas (Nitidez, tamaño de bbox, IoU simple)      |
|                                        |                                          |
|  2. Selección del Mejor Fotograma (Buffer de 1-3 fotogramas por track_id)          |
|                                        |                                          |
|  3. Detector de Región de Placa (Crop secundario dentro de la caja del vehículo)   |
|                                        |                                          |
|  4. Preprocesamiento del Recorte (OpenCV: contraste, re-escalado)                  |
|                                        |                                          |
|  5. Inferencia OCR (Llamada al motor abstracto AbstractPlateReader)                |
|                                        |                                          |
|  6. Consenso de Lecturas (Consolidación de texto por track_id)                     |
|                                        |                                          |
|  7. Emisión de Resultados Tipados (Instancia de PlateReadingResult)                |
+-----------------------------------------------------------------------------------+
                                         |
                                         | (Resultado neutral y tipado)
                                         v
+-----------------------------------------------------------------------------------+
|                       CAPA DE INTEGRACIÓN / ADAPTACIÓN DE UI                      |
|                                                                                   |
|  1. Adaptador de Presentación (Conversión de PlateReadingResult a UI Model)        |
|                                        |                                          |
|  2. Controlador / Página Streamlit (st.session_state["ocr_readings_raw"])          |
+-----------------------------------------------------------------------------------+
```

---

## 2. Componentes del Flujo OCR

### A. Detección y Seguimiento (Existente e Inmutable)
El pipeline de visión principal (`VisionPipeline`) detecta y realiza el seguimiento de los vehículos, asignando un `track_id` inmutable. Este flujo produce la información espacial y temporal del vehículo sin verse afectado por la lógica de placas.

`src/pavement_intelligence/vision/pipeline.py` permanece protegido durante las fases iniciales. La primera validación del OCR procesa imágenes individuales fuera del video; cualquier hook con el pipeline se posterga hasta la fase final de integración y requiere autorización independiente.

### B. Evaluador de Calidad de Fotogramas (`FrameQualityEvaluator`)
Este componente analiza los fotogramas del vehículo basándose en criterios geométricos y de nitidez:
1. **Tamaño del Bounding Box**: Filtra vehículos lejanos (cajas menores a `120x120` píxeles).
2. **Nitidez**: Evalúa el desenfoque mediante la varianza del operador Laplaciano de OpenCV en la región del vehículo.
3. **Intersección sobre Unión (IoU) Simple**: Para evitar oclusiones por otros vehículos, se implementa una función de IoU nativa en NumPy/Python sin recurrir a la librería `shapely`:
   ```python
   def calculate_iou_simple(box_a: tuple, box_b: tuple) -> float:
       xa1, ya1, xa2, ya2 = box_a
       xb1, yb1, xb2, yb2 = box_b

       xi1 = max(xa1, xb1)
       yi1 = max(ya1, yb1)
       xi2 = min(xa2, xb2)
       yi2 = min(ya2, yb2)

       inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
       area_a = (xa2 - xa1) * (ya2 - ya1)
       area_b = (xb2 - xb1) * (yb2 - yb1)
       union_area = area_a + area_b - inter_area

       return inter_area / union_area if union_area > 0 else 0.0
   ```
   Si el IoU con cualquier otro vehículo en escena supera el `0.15` (15% de solapamiento), se considera una oclusión potencial y el fotograma se descarta.

### C. Selector de Mejor Fotograma (`BestFrameSelector`)
Mantiene un buffer de hasta 3 fotogramas por `track_id`. Cuando el vehículo sale de la escena o finaliza su seguimiento, se seleccionan únicamente las imágenes con mayor puntuación de calidad para ser enviadas al motor OCR.

### D. Detector de Región de Placa (`PlateDetector`)
Utiliza técnicas de contornos o un detector YOLO secundario para extraer las coordenadas de la placa dentro del bounding box del vehículo. Se aplica un recorte y preprocesamiento de OpenCV (binarización, normalización de brillo).

### E. Motor OCR y Algoritmo de Consenso (`OcrConsensusManager`)
* Ejecuta la lectura mediante el motor que implemente `AbstractPlateReader`.
* Procesa los textos resultantes calculando la distancia de Levenshtein y consolidando una única lectura candidata con confianza ponderada.

---

## 3. Arquitectura del Trabajo Asíncrono y Concurrencia

Para no ralentizar el bucle principal de tracking de video, la ejecución de la detección y lectura OCR debe ser asíncrona, gestionada fuera del pipeline de visión por un servicio de encolamiento.

### A. Cola de Trabajos y Límites
* El servicio OCR asume un modelo de **Productor-Consumidor** con una cola acotada en memoria (`queue.Queue(maxsize=50)`).
* El productor (captura/tracking de video) coloca recortes de placas en la cola. Si la cola se llena (ej. tráfico extremadamente alto), los nuevos elementos se descartan automáticamente para proteger el rendimiento de la aplicación principal, registrando la omisión como una alerta de capacidad en el log.

### B. Gestión de Excepciones y Aislamiento de Errores
* El hilo de ejecución del OCR opera dentro de un bloque `try-except` generalizado.
* Si el motor OCR arroja una excepción (falla de memoria CUDA, error de biblioteca interna), la excepción es capturada, se registra en los logs del sistema, y el elemento de la cola se marca como `status = OCR_fallido`, liberando el recurso de manera inmediata para evitar bloqueos del sistema.

### C. Cancelación y Cierre Limpio (Shutdown)
* Se implementa un mecanismo de bandera de parada (`threading.Event`).
* Durante el cierre de la aplicación o cuando el usuario detiene el video, se activa la bandera. El hilo consumidor de la cola termina de procesar los elementos actualmente activos, vacía la cola descartando elementos pendientes no iniciados y libera de forma segura los recursos del modelo (cerrando el motor OCR y liberando memoria VRAM/RAM).

---

## 4. Flujo de Datos Hacia la UI (Streamlit)

La separación se mantiene a nivel de controladores:

1. **Visión / OCR**: Genera un objeto `PlateReadingResult` (neutro, sin saber de Streamlit).
2. **Controlador de la UI (Streamlit)**: Recibe el `PlateReadingResult` mediante un límite explícito, lo pasa por el `OcrPresentationAdapter` para transformarlo al formato de presentación (aplicando el enmascaramiento por defecto como `***-4A7` y registrando el log de auditoría del revisor), y escribe el resultado en `st.session_state["ocr_readings_raw"]` y `st.session_state["ocr_review_records"]`. Esta escritura ocurre exclusivamente en la página/controlador Streamlit; nunca dentro de `VisionPipeline` ni de módulos bajo `vision/`.
