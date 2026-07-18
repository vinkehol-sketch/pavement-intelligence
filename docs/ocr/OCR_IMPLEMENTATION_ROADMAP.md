# Hoja de Ruta de Implementación de OCR Real (LPR)

Este documento detalla el plan de implementación progresiva, la estrategia de prevención de duplicados, la política de almacenamiento seguro de evidencia y el análisis de dependencias de software para la integración del módulo OCR.

---

## 1. Auditoría de la Funcionalidad OCR Existente y Faltante

Antes de integrar hardware u algoritmos de producción, se realiza un análisis del código actual en el repositorio:

### A. Funcionalidad Ya Existente
* **`src/pavement_intelligence/vision/plates/base.py`**: Define la dataclass `PlateResult` y la clase abstracta `AbstractPlateReader`.
* **`src/pavement_intelligence/vision/plates/paddleocr_reader.py`**: Implementa `PaddleOCRPlateReader` utilizando la biblioteca PaddleOCR. Incluye la binarización de coordenadas de bounding box y la generación de un hash SHA-256 truncado de 8 caracteres para la anonimización de la placa.

### B. Funcionalidad Faltante
* **Detector/Localizador de Placa**: Falta el modelo o técnica (YOLO de placas o morfología matemática) para recortar específicamente la placa dentro del bounding box del vehículo. Actualmente, `PaddleOCRPlateReader` ejecuta OCR en todo el ROI del vehículo, lo cual es ineficiente y propenso a errores al leer textos publicitarios o de carrocería.
* **Evaluador de Calidad y Selector de Fotogramas**: Falta el algoritmo de descarte de imágenes borrosas o con oclusión (IoU) y el buffer por `track_id`.
* **Consolidador de Consenso**: Falta el gestor de votaciones y ponderación por confianza.
* **Adaptador de Presentación**: Falta conectar el flujo neutral con las páginas Streamlit de Codex.
* **Gestor Asíncrono de Trabajos**: Falta la cola de procesamiento concurrente.

---

## 2. Hoja de Ruta Progresiva (7 Fases)

Para mitigar riesgos y asegurar la estabilidad del proyecto, el desarrollo de la integración OCR se propone en siete fases consecutivas:

```
+------------------------------------------------------------------------+
| FASE 1: Prueba Aislada sobre Imágenes Individuales                    |
| -> Probar base.py y paddleocr_reader.py fuera del video.               |
| -> Usar imágenes sintéticas individuales y un mock de PaddleOCR.       |
| -> Validar inicialización, salida neutral, hashing y anonimización.     |
+------------------------------------------------------------------------+
                                   |
                                   v
+------------------------------------------------------------------------+
| FASE 2: OCR Opcional sobre un Conjunto Local de Recortes               |
| -> Procesar fixtures estáticos ubicados dentro del repositorio.        |
| -> Evaluar tiempos y precisión del motor en CPU de forma aislada.      |
+------------------------------------------------------------------------+
                                   |
                                   v
+------------------------------------------------------------------------+
| FASE 3: Detector o Recortador de la Región de Placa                    |
| -> Implementar el localizador fino de la placa dentro del ROI.         |
| -> Reducir la imagen a la zona exacta de los caracteres.               |
+------------------------------------------------------------------------+
                                   |
                                   v
+------------------------------------------------------------------------+
| FASE 4: Evaluador de Calidad y Selector de Fotogramas por Track ID     |
| -> Implementar FrameQualityEvaluator (filtros de nitidez y tamaño).     |
| -> Implementar BestFrameSelector para aislar 1-3 fotogramas por track.  |
+------------------------------------------------------------------------+
                                   |
                                   v
+------------------------------------------------------------------------+
| FASE 5: Consenso de Varias Lecturas                                    |
| -> Implementar OcrConsensusManager para votación y Levenshtein.        |
| -> Ponderar confianza de lecturas acumuladas por track_id.             |
+------------------------------------------------------------------------+
                                   |
                                   v
+------------------------------------------------------------------------+
| FASE 6: Adaptador Hacia la Pantalla Streamlit                          |
| -> Implementar OcrPresentationAdapter.                                 |
| -> Escribir las lecturas neutrales en st.session_state de la página.    |
+------------------------------------------------------------------------+
                                   |
                                   v
+------------------------------------------------------------------------+
| FASE 7: Hook Opcional y Desacoplado con el Pipeline de Video           |
| -> Integración asíncrona no invasiva como tarea final autorizada.      |
| -> pipeline.py permanece protegido e inmutable hasta esta fase.        |
+------------------------------------------------------------------------+
```

---

## 3. Estrategia de Concurrencia y Cola de Trabajos

Para evitar bloquear la interfaz y el tracking en tiempo real, se implementará un servicio de procesamiento en segundo plano con límites estrictos antes de introducir hilos en el pipeline principal:

1. **Cola Acotada**: Se utiliza `queue.Queue(maxsize=50)` en memoria. Si el buffer de mejores fotogramas rebasa este límite, los recortes excedentes se descartan para proteger el tracking en vivo.
2. **Ciclo de Vida y Cierre Limpio**:
   * El hilo de ejecución lee de la cola continuamente.
   * Se define un evento `stop_event = threading.Event()`.
   * Al detener el procesamiento, se activa el evento, el hilo descarta las tareas pendientes en la cola, ejecuta un cierre ordenado del modelo OCR y libera la memoria RAM/VRAM.
3. **Manejo de Excepciones**: Cada tarea en el hilo corre bajo protección de errores (`try-except`). Si ocurre un fallo crítico de CUDA o de asignación de memoria, se registra el log y el track afectado se marca como `status = OCR_fallido`, previniendo que el proceso caiga.

---

## 4. Análisis de Dependencias y Justificación

Al revisar `pyproject.toml` y `requirements.txt`, se constata que las librerías de OCR no forman parte del núcleo obligatorio. Se establece la siguiente política:

* **Dependencias Opcionales**: Las librerías `paddleocr` y `paddlepaddle` (o `paddlepaddle-gpu`) se declaran como dependencias opcionales de desarrollo, requeridas únicamente si el usuario habilita el OCR en el archivo de configuración.
* **Eliminación de Librerías Complejas (`shapely`)**: Se descarta el uso de `shapely` para el cálculo de intersecciones de bounding boxes (IoU). Su funcionalidad geométrica se reemplaza con una función simple en Python puro/NumPy, lo que evita dependencias nativas complejas y facilita la portabilidad de la instalación en entornos Windows.

---

## 5. Primera Tarea Pequeña Recomendada para Codex

* **Tarea 1.1**: Escribir una prueba unitaria en `tests/unit/test_ocr_existing_infra.py` para procesar una imagen sintética individual, fuera de cualquier video y sin modificar `vision/pipeline.py`. La prueba usa un mock de la biblioteca opcional `paddleocr` y valida el contrato neutral, el hashing SHA-256 truncado y la anonimización.

### Salvaguarda del pipeline oficial

Las fases 1 a 6 no autorizan cambios en `src/pavement_intelligence/vision/pipeline.py`. Ningún componente de `vision/` escribe en `st.session_state`; la escritura de estado pertenece exclusivamente al controlador Streamlit de la fase 6. Cualquier hook de video se evalúa recién en la fase 7 mediante una tarea separada, con pruebas de regresión del aforo oficial.
