# Contratos Técnicos de Datos para la Integración de OCR

Este documento detalla las estructuras de datos (contratos técnicos) en Python que rigen el flujo de procesamiento de placas OCR, desde la evaluación de fotogramas del vehículo hasta el volcado final en la capa de presentación.

---

## 1. Contratos del Pipeline de Procesamiento (Inferencia)

Estos contratos se definen utilizando `dataclasses` nativas de Python, asegurando tipado estricto e inmutabilidad durante la ejecución en las capas del motor de visión. No tienen dependencia alguna con Streamlit.

### A. PlateRecognitionConfig
Define los parámetros operativos del motor de detección y lectura de placas.
* **Campos**:
  * `min_confidence` (`float`): Umbral de confianza mínima por carácter para aceptar lectura OCR (ej: `0.60`).
  * `hash_length` (`int`): Longitud del hash de placa para almacenamiento (ej: `8`).
  * `anonymize` (`bool`): Si se activa, las placas en bruto se descartan de la memoria a largo plazo inmediatamente.
  * `lang` (`str`): Idioma del diccionario de caracteres para el OCR (ej: `"es"` o `"en"`).
  * `quality_threshold` (`float`): Puntuación de calidad mínima del fotograma para admitirlo a inferencia (0.0 a 1.0).
  * `max_candidates_per_track` (`int`): Número máximo de fotogramas a procesar con OCR por vehículo (ej: `3`).

### B. PlateCandidate
Representa un fotograma de vehículo que califica para el procesamiento de placa por haber superado el umbral de calidad.
* **Campos**:
  * `track_id` (`int`): ID del vehículo asignado por ByteTrack.
  * `frame_number` (`int`): Número correlativo de fotograma.
  * `quality_score` (`float`): Puntaje de calidad calculado (nitidez, tamaño, contraste).
  * `vehicle_bbox` (`tuple[float, float, float, float]`): Coordenadas de la caja de delimitación del vehículo.
  * `timestamp` (`str`): Timestamp ISO 8601 del fotograma.

### C. PlateCrop
Representa el recorte de imagen de la placa detectada y preprocesada.
* **Campos**:
  * `crop_id` (`str`): Identificador único del recorte (UUID v4).
  * `track_id` (`int`): ID de tracking asociado.
  * `frame_number` (`int`): Número de fotograma de origen.
  * `image_data` (`np.ndarray`): Imagen de la placa recortada y preprocesada en memoria (matriz OpenCV).
  * `bbox_in_vehicle` (`tuple[float, float, float, float]`): Coordenadas de la placa respecto al bounding box del vehículo.
  * `contrast_score` (`float`): Medida de contraste adaptativo calculada en el ROI de la placa.

### D. PlateOcrAttempt
Representa el intento de inferencia OCR crudo ejecutado por el motor (ej. PaddleOCR) sobre un recorte de placa.
* **Campos**:
  * `attempt_id` (`str`): Identificador único de inferencia (UUID v4).
  * `crop_id` (`str`): ID del recorte de origen.
  * `text_raw` (`str`): Texto literal devuelto por el OCR (incluye caracteres especiales y ruido).
  * `confidence` (`float`): Confianza global del texto (0.0 a 1.0).
  * `alternatives` (`list[tuple[str, float]]`): Otras combinaciones de caracteres sugeridas con su probabilidad.
  * `latency_ms` (`float`): Tiempo de procesamiento de la inferencia en milisegundos.

### E. PlateReadingCandidate
Representa el texto de la placa normalizado y verificado contra patrones nacionales antes de la consolidación de consenso.
* **Campos**:
  * `candidate_id` (`str`): UUID v4 del candidato.
  * `track_id` (`int`): ID del vehículo asignado.
  * `text_normalized` (`str`): Texto limpio y en mayúsculas, mapeando ambigüedades (ej. `I` $\rightarrow$ `1` en zona numérica).
  * `confidence` (`float`): Confianza de la lectura.
  * `format_valid` (`bool`): True si cumple con la expresión regular regional de patentes.
  * `ocr_engine_version` (`str`): Identificador del modelo OCR usado.

---

## 2. Contratos de Almacenamiento y Salida

### F. PlateReadingResult (Consolidado por Track)
Este contrato representa el resultado final unificado del OCR para un vehículo individual. Es el elemento de salida del orquestador OCR.
* **Campos**:
  * `track_id` (`int`): ID único de seguimiento.
  * `event_id` (`Optional[str]`): ID del evento de cruce de línea asociado (si cruzó la línea virtual).
  * `text_best_candidate` (`str`): Texto óptimo final obtenido por el algoritmo de consenso.
  * `text_hash` (`str`): Hash SHA-256 truncado del texto (para almacenamiento en base de datos sin consentimiento).
  * `confidence_weighted` (`float`): Confianza del consenso ponderada por el número de fotogramas analizados.
  * `status` (`str`): Estado de validación del resultado. Valores:
    * `sin_placa_detectada`: No se localizó ninguna placa en el vehículo.
    * `recorte_insuficiente`: El ROI es muy pequeño o desenfocado.
    * `placa_ilegible`: Ninguna inferencia superó la confianza mínima o falló la decodificación.
    * `confianza_baja`: Inferencia completada pero la confianza ponderada está por debajo del umbral mínimo.
    * `multiples_alternativas`: La diferencia de confianza entre los dos candidatos más votados es menor al 10%.
    * `lectura_duplicada`: Se detectó la misma placa en una ventana de tiempo muy corta.
    * `ok`: Lectura completada satisfactoriamente con alta confianza.
  * `candidates_count` (`int`): Cantidad de fotogramas con inferencia OCR que formaron el consenso.
  * `alternatives` (`list[str]`): Lista de textos alternativos detectados para el mismo track.

### G. PlateEvidence
Define los metadatos y rutas de almacenamiento para la evidencia gráfica que usará el auditor en la pantalla de revisión.
* **Campos**:
  * `evidence_id` (`str`): Identificador único de la evidencia (UUID).
  * `track_id` (`int`): ID de tracking asociado.
  * `best_frame_number` (`int`): Fotograma representativo para mostrar en la UI.
  * `best_crop_path` (`str`): Ruta del archivo del recorte de placa.
  * `original_frame_path` (`str`): Ruta del fotograma original del video.
  * `is_anonymized` (`bool`): Define si los archivos de imagen han sido difuminados antes de guardarse en disco.

---

## 3. Adaptador para el Modelo de Presentación de la UI (Streamlit Wrapper)

Para conectar la salida física neutral del OCR con la interfaz Streamlit, se diseña un adaptador en la capa de presentación que se encarga de estructurar el diccionario de visualización y gestionar la anonimización:

```python
class OcrPresentationAdapter:
    """ Convierte el PlateReadingResult real al formato consumido por la UI de Streamlit. """

    @staticmethod
    def to_presentation_model(
        result: PlateReadingResult,
        evidence: PlateEvidence,
        timestamp: str,
        traffic_reference: Mapping[str, str]
    ) -> dict[str, Any]:
        # Enmascaramiento por defecto a nivel de adaptador (servidor)
        raw_text = result.text_best_candidate or "ILEGIBLE"
        masked_text = f"***-{raw_text[-3:]}" if len(raw_text) >= 4 else "ILEGIBLE"

        return {
            "event_id": result.event_id or f"ocr:{result.track_id}",
            "track_id": result.track_id,
            "timestamp": timestamp,
            "crop_thumbnail_path": evidence.best_crop_path,
            "original_frame_path": evidence.original_frame_path,
            "ocr_reading_original": raw_text,
            "ocr_reading_masked": masked_text,
            "confidence": f"{int(result.confidence_weighted * 100)}%",
            # Referencias inmutables, recibidas del contrato oficial; el OCR no las infiere ni modifica.
            "vehicle_category": traffic_reference["vehicle_category"],
            "direction": traffic_reference["direction"],
            "validation_status": "pendiente" if result.status == "ok" else "dudosa",
            "correction_reason": "",
            "reviewed": False,
            "reviewed_by": "",
            "reviewed_at": None,
            "is_unmasked": False,
            "audit_trail": []
}
```

El adaptador no escribe en `st.session_state`, no recalcula conteos y no ofrece campos editables para categoría o sentido. La página Streamlit es responsable de almacenar su propio estado OCR aislado; los contratos permanecen neutrales respecto a la interfaz y al aforo oficial.
