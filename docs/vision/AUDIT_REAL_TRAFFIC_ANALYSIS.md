# Informe de Auditoría Técnica: Integración de Fuentes Reales

**Proyecto:** Pavement Intelligence
**Módulo UI:** Centro de Monitoreo de Tránsito (`pages/traffic_monitoring.py`)
**Módulo Visión:** `src/pavement_intelligence/vision/` (Captura y Análisis)
**Clasificación Final:** **APROBADA CON CORRECCIONES MENORES**

Este informe presenta la auditoría de solo lectura de los cambios pendientes desarrollados por Codex para conectar el Centro de Monitoreo con el pipeline de visión física (video pregrabado y cámara local).

---

## 1. Verificación de Archivos y Git Status

### A. Archivos Nuevos y Rango de Cambios
Se verificaron los archivos y su estado en el control de cambios de Git:
1. `src/pavement_intelligence/vision/analysis/controller.py`: Implementa el controlador puro `TrafficAnalysisController`. **Correcto.** No tiene acoplamiento con Streamlit ni con librerías de interfaz.
2. `src/pavement_intelligence/vision/capture/camera_source.py`: Implementa `CameraSource` para canales de cámara USB/integrada.
   * *Hallazgo de Rastro*: Aparece como archivo creado nuevo porque no estaba previamente bajo el control de versiones (untracked), a pesar de haber sido planificado/leído en esa ruta.
3. `tests/unit/test_traffic_analysis_controller.py`, `test_traffic_analysis_sources.py`, y `test_traffic_demo_video.py`: Suite de 47 pruebas nuevas unitarias y de simulación aprobadas. **Correcto.**
4. `data/samples/ui/assets/traffic_monitoring_demo.mp4`: Video demostrativo de 1.6 MB. Es un tamaño adecuado para versionar directamente en el repositorio Git del MVP y no contiene datos privados ni matrículas visibles.

---

## 2. Auditoría Detallada por Puntos Críticos

### A. Capa de Captura (`capture/`)
* **Compatibilidad hacia Atrás**: Totalmente mantenida. Se conservan alias de compatibilidad (`AbstractVideoSource = FrameSource` y `FileVideoSource = VideoFileSource`), asegurando que scripts legados como `scripts/run_headless_vision.py` y `scripts/compare_manual_automatic.py` sigan funcionando sin cambios.
* **Firmas y Semántica**: Las firmas públicas de `open()`, `read()`, y `close()` son consistentes y limpias. `read_frame()` y `release()` se redirigen correctamente.
* **Fin de Archivo**: `VideoFileSource.read()` retorna `success=False` y frame `None` de forma correcta.
* **Idempotencia de Cierre**: El método `close()` es idempotente en ambas fuentes; verifica si el puntero `_cap` es nulo, liberándolo de forma segura y reestableciendo el estado a `None`.

### B. Controlador de Análisis (`TrafficAnalysisController`)
* **Máquina de Estados**: La enumeración `AnalysisState` (IDLE, RUNNING, PAUSED, FINISHED, ERROR) y las transiciones de estado en `start()`, `pause()`, `resume()`, `reset()`, y `process_next()` son válidas.
* **Consistencia del Reset**: Al invocar `reset()`, el controlador llama a `source.close()` e invalida la instancia del pipeline (`self.pipeline = None`). Al iniciar de nuevo, se recrea el pipeline a través de la factoría. Esto **garantiza un reinicio real** del contador virtual, los tracks de ByteTrack y la memoria interna de detección, en lugar de solo retroceder el video.
* **Protección del Aforo**: El controlador acumula eventos técnicos de forma inmutable en `pipeline.events`. No tiene capacidades de aprobación automática ni de envío a la base de datos de TPDA, respetando el flujo manual de aforos.

### C. Integración en Streamlit (`traffic_monitoring.py`)
* **Evitación de Bucles Bloqueantes**: La integración utiliza el decorador `@st.fragment(run_every=0.15)` cuando está activo el análisis real. Esto elimina bucles `while` infinitos en la UI y actualiza la imagen y métricas en contenedores `st.empty()` en el lugar (*in-place*), manteniendo la responsividad de Streamlit.
* **Persistencia del Controlador**: Se almacena en `st.session_state["traffic_analysis_controller"]`, permitiendo pausar y reanudar sin perder el descriptor de frames ni la posición actual de reproducción.
* **Aislamiento de Métricas**: El renderizado discrimina estrictamente la fuente: si está activo el análisis real, se leen los conteos y la congestión directamente de `FrameAnalysisResult`, impidiendo la mezcla accidental con cifras sintéticas del lote demostrativo.

---

## 3. Hallazgos Técnicos y Correcciones Sugeridas (No Bloqueantes)

A pesar de que las pruebas aprueban plenamente, se recomiendan las siguientes mejoras arquitectónicas:

### Hallazgo 1: Carga Repetitiva de YOLOv8 en CPU
* **Severidad**: Menor
* **Ubicación**: `src/pavement_intelligence/ui/pages/traffic_monitoring.py:L98-L102` (`_pipeline_factory`)
* **Evidencia**: Se crea una nueva instancia de `YOLODetectorTracker` en cada llamada a la factoría de pipeline (lo que ocurre al iniciar y en cada llamada a `reset()`). Esto provoca que los pesos del modelo `.pt` se carguen de disco a memoria en cada reinicio, causando un retraso de calentamiento de 0.5s.
* **Impacto**: Experiencia de usuario degradada por congelamientos temporales de 500ms al reiniciar.
* **Corrección sugerida**: Cachear o persistir la instancia de `YOLODetectorTracker` (ej: `@st.cache_resource`) y pasar el detector ya inicializado a la factoría en lugar de instanciarlo dentro.
* **Bloquea Commit**: No.

### Hallazgo 2: Falta de Liberación de Recursos en Desconexión (Sesión Huérfana)
* **Severidad**: Menor
* **Ubicación**: `src/pavement_intelligence/vision/capture/camera_source.py` y `file_source.py`
* **Evidencia**: Si la sesión de Streamlit expira por inactividad o el navegador se cierra abruptamente, el objeto `CameraSource` se destruye por el Garbage Collector de Python, pero no existe un método de destrucción `__del__` que llame explícitamente a `self.close()`.
* **Impacto**: Riesgo de recursos de cámara ocupados en el servidor, bloqueando el dispositivo a otros usuarios.
* **Corrección sugerida**: Añadir un destructor básico en las fuentes de captura:
  ```python
  def __del__(self):
      self.close()
  ```
* **Bloquea Commit**: No.

### Hallazgo 3: Limpieza Tardía de Datos Sintéticos
* **Severidad**: Menor
* **Ubicación**: `src/pavement_intelligence/ui/pages/traffic_monitoring.py`
* **Evidencia**: Las variables del aforo anterior en el lote sintético se limpian solo al presionar "Finalizar y revisar". Si el usuario inicia un análisis real, las métricas del aforo del lote anterior aún residen en `st.session_state["vision_events_reviewed"]` hasta que se finaliza la ejecución real.
* **Impacto**: Confusión en el flujo si el usuario navega a "Revisión" a la mitad de un análisis de video real.
* **Corrección sugerida**: Limpiar las claves de aforo sintéticas (`vision_events_reviewed`, `traffic_review_approved`) de manera inmediata al invocar `_start_real_analysis()`.
* **Bloquea Commit**: No.

---

## 4. Cobertura de Pruebas
Las 47 pruebas nuevas proporcionan una cobertura robusta de los siguientes aspectos:
* Ciclos de vida del controlador (Start, Process, Pause, Resume, Reset, Finish).
* Casos extremos de archivos de video corruptos y dispositivos de cámara no disponibles.
* Pruebas del adaptador de presentación inmutable.
* Comprobación en Streamlit mediante `AppTest` para renderizados de interfaces estáticas, video y cámara.

* **Vacío Menor**: No se prueban fugas de descriptores de archivos concurrentes cuando dos clientes solicitan el mismo canal de cámara, aunque el control de excepciones de inicialización mitiga este riesgo a nivel de hardware.

---

## 5. Correcciones menores aplicadas

Los tres hallazgos quedaron atendidos y validados:

1. La transición a análisis real limpia inmediatamente cualquier lote sintético y temporales demostrativos, sin eliminar un lote real finalizado.
2. Se auditó el cache del detector y se descartó de forma deliberada: `YOLODetectorTracker` une el modelo con ByteTrack persistente, por lo que reutilizarlo compartiría estado mutable entre lotes. Detector, tracker, contador y pipeline se recrean en cada lote y reset.
3. Las fuentes mantienen cierre idempotente. El controlador cierra en finalización, cambio de fuente, reset, error de lectura, excepción de pipeline y fallo de la fábrica; pausa conserva la fuente abierta y continuar mantiene la posición.
4. Git confirma que `camera_source.py` es un archivo nuevo no rastreado y no reemplaza una implementación versionada anterior.

La validación añadida cubre separación de lotes, ausencia de eventos duplicados, limpieza sintética, preservación del modo demostrativo, cierre repetido, cierre por error y cambio de fuente mediante AppTest.
