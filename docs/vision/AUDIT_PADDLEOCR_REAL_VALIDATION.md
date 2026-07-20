# Informe de Auditoría Técnica — Validación Real y Compatibilidad de PaddleOCR

Este informe presenta la auditoría técnica neutral e independiente sobre la primera validación real del backend PaddleOCR y las correcciones de compatibilidad incorporadas en el reader.

---

## 1. Veredicto

El veredicto para los cambios propuestos es:

### **APROBADA**

Las correcciones de compatibilidad resuelven fallos específicos del motor en Windows de forma segura. La suite completa de pruebas (**863 pruebas aprobadas, 1 omitida de forma controlada**) y el análisis estático confirman el correcto funcionamiento y el aislamiento respecto de las capas críticas de la aplicación.

---

## 2. Resultados de las Validaciones y Pruebas Ejecutadas

Se ejecutaron y verificaron las siguientes actividades de diagnóstico en el espacio de trabajo:

1. **Pruebas Unitarias e Integración**:
   * **Comando**: `pytest`
   * **Resultado**: **863 aprobadas, 1 omitida** (864 coleccionadas en 30,77 s).
   * **Prueba de integración opcional**: `tests/integration/test_paddleocr_real_reader.py`
     * `test_modern_result_parser_accepts_paddleocr_3_payload`: **Aprobada** (verifica el parseo del payload en formato PaddleOCR 3.7.0).
     * `test_real_paddleocr_reader_on_authorized_local_image`: **Omitida (Skipped)** de manera controlada al no tener la variable de entorno `RUN_PADDLEOCR_REAL=1` activada en el entorno de pruebas principal (evitando fallos por la ausencia de PaddleOCR en el entorno local).
2. **Análisis Estático (Ruff)**:
   * **Comando**: `ruff check` sobre el reader modificado y la prueba de integración.
   * **Resultado**: **Check exitoso** (0 advertencias o errores).
3. **Análisis de Formato de Git**:
   * **Comando**: `git diff --check`
   * **Resultado**: Exitoso (sin trailing whitespaces ni anomalías).

---

## 3. Hallazgos Auditados

### A. Compatibilidad de Backends (PaddleOCR 2.x / 3.x)
* **Detección Dinámica de Versiones**: Se audita que `PaddleOCRPlateReader._load_model()` determina la versión mayor de PaddleOCR en tiempo de ejecución utilizando `importlib.metadata.version`.
* **oneDNN / MKLDNN en Windows**: Para la versión mayor $\ge 3$, se inicializa el motor con `enable_mkldnn=False`, previniendo de forma efectiva el error `NotImplementedError: ConvertPirAttribute2RuntimeAttribute` del backend de oneDNN en sistemas operativos Windows CPU.
* **Argumento show_log**: Se verifica que en PaddleOCR 3.x se omite el argumento `show_log` para evitar la excepción `ValueError: Unknown argument: show_log`, mientras que en PaddleOCR 2.x se conserva para compatibilidad histórica.

### B. Robustez de la API Pública y del Parser
* El contrato público de `AbstractPlateReader.detect_and_read` se mantiene inalterado:
  * Retorno de tipo `Optional[PlateResult]`.
  * Conversión de bounding box (`vehicle_bbox`) a tupla entera segura con control de límites para la región de interés (`roi`).
  * Validación estricta y acotada del nivel de confianza (`0.0 <= confidence <= 1.0`) y eliminación de textos vacíos antes de generar el hash de la matrícula.
* **Parser de Candidatos Modernos**: `_modern_candidates` soporta adecuadamente la estructura devuelta por PaddleOCR 3.7.0, resolviendo de manera segura listas anidadas u objetos de resultados con atributo o método `json`.

### C. Aislamiento y Seguridad en la Prueba de Integración
* La prueba real en `test_paddleocr_real_reader.py` se salta de forma segura en entornos sin PaddleOCR o CI estándar empleando `pytest.importorskip("paddleocr")` y el marcador condicional de la variable de entorno.
* **Privacidad**: No se versionan ni almacenan imágenes con datos reales. La imagen ficticia es generada dinámicamente y se destruye a través de un finalizer de pytest.
* **Modelos**: El caché de modelos descargados por PaddleOCR (`PP-OCRv6_medium`) se almacena en el directorio de usuario (`C:\Users\Pc\.paddlex\official_models`) externo al repositorio de código de producción.

---

## 4. Limitaciones Documentadas de la Validación Real

* **Imagen Ficticia Individual**: Los resultados de latencia y precisión corresponden a una placa sintética ideal generada en memoria de 1280×720 con texto plano (`ABC-123`).
* **Vídeo y Cámara**: No se ha realizado la validación en tiempo real sobre flujos de video continuos o transmisiones de cámaras con ruido, desenfoque de movimiento o variaciones de luz.
* **Asociación**: La coincidencia del hash de la placa con el aforo panorámico sigue sin estar implementada.

---

## 5. Módulos Protegidos (Verificación de Integridad)

Se confirma que ningún archivo crítico de producción ha sido modificado:
* `PlateAnalysisController` (Intacto)
* `ocr_controller.py` (Intacto)
* `traffic_monitoring.py` (Intacto)
* `VisionPipeline` (Intacto)
* `YOLO` / `ByteTrack` (Intacto)
* Aprobación y revisión manual del aforo (Intacto)
* Módulos de ingeniería: TPDA, ESAL, pesaje, geotecnia y pavimentos (Intacto)

---

## 6. Recomendación de Siguientes Pasos

1. **Aprobación de Commit**: Se autoriza la incorporación de `paddleocr_reader.py`, `test_paddleocr_real_reader.py`, `VALIDATION_REPORT_PADDLEOCR_REAL.md` y este informe de auditoría en la rama principal.
2. **Pruebas de Campo Controladas**: Si el usuario instala el entorno aislado en la máquina objetivo, realizar pruebas con un conjunto limitado (5–10) de capturas de vehículos locales autorizados para medir la exactitud de lectura antes de integrarlo en el flujo continuo.
