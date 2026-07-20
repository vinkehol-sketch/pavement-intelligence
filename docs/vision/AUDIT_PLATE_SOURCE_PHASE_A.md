# Informe de Auditoría Técnica — Integración de Fuente OCR Independiente (Fase A)

Este informe presenta la auditoría técnica neutral e independiente de la implementación de la Fase A para la fuente OCR independiente de matrículas.

---

## 1. Veredicto

El veredicto para los cambios propuestos en la Fase A es:

### **APROBADA**

Todos los criterios de aceptación técnicos y de diseño han sido plenamente satisfechos. La suite completa de pruebas unitarias (**862 pruebas aprobadas al 100 %**) y el análisis estático mediante Ruff verifican la estabilidad, seguridad y el estricto aislamiento de los módulos del aforo y del diseño estructural.

---

## 2. Resultados de las Validaciones y Pruebas Ejecutadas

Para autorizar esta integración se ejecutaron y verificaron las siguientes actividades de diagnóstico:

1. **Pruebas Unitarias e Integración**:
   * **Comando**: `pytest`
   * **Resultado**: **862 aprobadas** de 862 coleccionadas.
   * **Nuevas pruebas**: 78 pruebas aprobadas (cubriendo controladores, ciclo de vida, deduplicación, ROI, privacidad, sesión Streamlit y manejo de excepciones).
   * **Regresión OCR existente**: 57 pruebas aprobadas.
   * **AppTest de placas**: 18 pruebas aprobadas (evaluando de forma simulada flujos de rerun de Streamlit y rendering de la UI).
   * **Regresión general**: 784 pruebas históricas aprobadas sin degradación de código.
2. **Análisis Estático (Ruff)**:
   * **Comando**: `ruff check` sobre todos los archivos creados y modificados.
   * **Resultado**: **Check exitoso** (0 infracciones de estilo o código).
3. **Análisis de Requerimientos y Dependencias (Pip)**:
   * **Comando**: `pip check`
   * **Resultado**: Exitoso (ningún conflicto en el entorno virtual).
4. **Verificación de Formato y Estilo de Git**:
   * **Comando**: `git diff --check`
   * **Resultado**: Exitoso (sin espacios en blanco al final de línea o anomalías de formato).

---

## 3. Hallazgos Auditados

### A. Aislamiento e Inmutabilidad de Datos
* **Claves de Sesión Aisladas**: Se verifica que la página `ocr_plate_review.py` opera en el modo real empleando de manera exclusiva claves con el prefijo `plate_session_*` (definidas y centralizadas en `plate_session.py`).
* **Protección del Aforo y Diseño**: Bajo ninguna circunstancia se modifican claves del aforo como `traffic_analysis_controller`, `traffic_review_approved` o transferencias a TPDA/ESAL. Tampoco se inyectan variables en `st.session_state` desde los hilos de adquisición de visión.
* **Inmutabilidad**: Todos los contratos de `ocr_models.py` (`PlateReadingCandidate`, `PlateFrameResult`, `PlateBatchResult`) están codificados como `@dataclass(frozen=True)` con validaciones defensivas en su inicializador y con `normative=False` inalterable.

### B. Ciclo de Vida del Controlador (`PlateAnalysisController`)
* El controlador maneja estados seguros (`IDLE`, `RUNNING`, `PAUSED`, `FINISHED`, `ERROR`).
* **Pausa**: Devuelve el último `PlateFrameResult` obtenido sin avanzar la lectura física ni acumular latencia en el backend.
* **Cierre**: Las llamadas a `close()` liberan explícitamente los descriptores de `FrameSource`, previniendo retenciones físicas de dispositivos en el servidor.
* **Excepciones**: Si el extractor de frames o el reader de placas arrojan un error, el controlador captura la excepción localmente, pasa al estado `ERROR` y cierra la cámara para evitar fugas de descriptores de video.

### C. Configuración y Validación de la ROI
* La región de interés es estática y parametrizada con coordenadas relativas normalizadas (`x1`, `y1`, `x2`, `y2`) limitadas a `[0,1]` y con validación estricta de área no nula.
* **No Detector**: La UI advierte explícitamente al usuario que no es un localizador automático de placas, sino una región fija configurada.

### D. Frecuencia y Deduplicación Operativa
* Se ejecuta la inferencia de manera determinista cada $N$ frames (evaluando únicamente cuando `(frame_index - 1) % every_n_frames == 0`).
* **Deduplicación**: Se combinan `source_id`, texto normalizado y ROI dentro de una ventana temporal ajustable (`dedup_window_seconds`).
* Si se encuentra una lectura idéntica de mayor confianza dentro de la ventana, se actualiza el registro conservando el `reading_id` para evitar duplicaciones innecesarias en la bitácora. La memoria de deduplicación se acota usando un `OrderedDict` con un límite máximo configurable (por defecto 256).

### E. Privacidad y Seguridad
* **Enmascaramiento**: Las matrículas en la UI se muestran por defecto como `***-123` empleando el formateador `mask_plate_text`.
* **Auditoría de Desvelado**: Mostrar la matrícula legible requiere una acción explícita del auditor, la cual se registra de forma obligatoria en la bitácora de auditoría en memoria `plate_session_reveal_audit` (capturando revisor, acción y timestamp ISO).
* **Eliminación de Temporales**: Los archivos temporales creados por el widget de subida de archivos se limpian de manera inmediata al finalizar el lote o al navegar hacia cualquier otra página de Streamlit en `app.py`.

---

## 4. Limitaciones del MVP a Considerar en Demostraciones

* **Backend Opcional**: PaddleOCR no está instalado por defecto en el entorno del servidor del MVP. En la interfaz se presenta una advertencia clara cuando no está disponible y las pruebas unitarias emplean `FakeReader` inyectado para simular lecturas sin fallos de ejecución.
* **Extracción Estática**: Al no contar con un localizador automático (YOLOv8 de placas), la lectura requiere que el video mantenga un encuadre centrado y estable sobre la placa.
* **No Asociación**: No existe correlación espacial ni emparejamiento con el flujo panorámico de conteo de vehículos en esta fase.

---

## 5. Módulos Protegidos (Verificación de Integridad)

Se confirma mediante Git que los siguientes archivos clave del proyecto **no sufrieron ninguna modificación ni edición**:
* `src/pavement_intelligence/ui/pages/traffic_monitoring.py` (Intacto)
* `src/pavement_intelligence/vision/analysis/controller.py` (Intacto)
* `src/pavement_intelligence/vision/pipeline.py` (Intacto)
* `src/pavement_intelligence/domain/traffic/congestion.py` (Intacto)
* `src/pavement_intelligence/domain/traffic/congestion_aggregation.py` (Intacto)
* `src/pavement_intelligence/domain/traffic/congestion_runtime.py` (Intacto)
* `src/pavement_intelligence/ui/pages/traffic_review.py` (Intacto)
* `src/pavement_intelligence/ui/pages/survey_tpda.py` (Intacto)
* `src/pavement_intelligence/ui/pages/weighing.py` (Intacto)

---

## 6. Recomendación de Siguientes Pasos

1. **Aprobación de Commit**: Se autoriza la incorporación de los 3 archivos modificados y los 8 archivos creados al repositorio de producción.
2. **Fase B - Integración de Asociación por Evidencia**: Implementar el motor de coincidencia temporal en segundo plano empleando la heurística temporal de $3$ segundos definida en el documento de arquitectura para asociar las lecturas enmascaradas con los eventos de tránsito panorámico.
3. **Instalación de Dependencias**: Si se desea validar OCR físico durante la hackatón, coordinar la instalación controlada de `paddleocr` y sus respectivos pesos ligeros (`ch_PP-OCRv4_rec`) en el servidor local.
