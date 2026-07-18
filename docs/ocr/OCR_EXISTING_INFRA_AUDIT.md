# Auditoría de la infraestructura OCR existente

## Alcance

Esta auditoría cubre exclusivamente `vision/plates/base.py` y `vision/plates/paddleocr_reader.py`. Se realizó con imágenes NumPy sintéticas y un motor simulado, sin PaddleOCR instalado, red, video, Streamlit, YOLO, ByteTrack ni cambios en `vision/pipeline.py`.

## Interfaz pública actual

`base.py` define:

- `PlateResult`, dataclass con `text_raw`, `text_hash`, `confidence`, `bbox` e `is_anonymized`.
- `AbstractPlateReader.detect_and_read(frame, vehicle_bbox) -> Optional[PlateResult]`.

`PaddleOCRPlateReader` conserva esa interfaz. Su constructor acepta `min_confidence`, `hash_length`, `anonymize` y `lang`. `detect_and_read` recibe un `np.ndarray` y un bounding box `(x1, y1, x2, y2)`, recorta el ROI y devuelve el candidato válido de mayor confianza o `None`.

## Dependencia opcional

PaddleOCR se importa de forma diferida dentro de `_load_model`; importar el módulo e instanciar el lector no requiere la biblioteca. Tras la corrección, la ausencia de la dependencia opcional durante la primera lectura produce `None` en vez de propagar `ModuleNotFoundError`.

## Comportamiento auditado

- Los límites del bounding box se convierten a enteros y se acotan al fotograma.
- Imágenes nulas, vacías, unidimensionales y ROI vacíos devuelven `None`.
- El motor se invoca con el ROI y `cls=True`.
- Resultados vacíos, estructuras inesperadas, textos nulos y confianzas inválidas se ignoran.
- Los textos se normalizan a caracteres ASCII `A-Z0-9`, eliminando espacios, minúsculas, guiones, separadores y símbolos no admitidos.
- Entre múltiples candidatos válidos se selecciona la mayor confianza.
- Las confianzas `0.0` y `1.0` son válidas si el umbral configurado las admite; valores no finitos o fuera de rango se descartan.
- Excepciones del motor producen `None` y no alteran estado global.
- El identificador es SHA-256 del texto normalizado, truncado a ocho caracteres con la configuración predeterminada. Es estable para entradas equivalentes.
- Con `anonymize=True`, `text_raw` es `None` y la representación pública de `PlateResult` no contiene la lectura original. Con `anonymize=False`, el resultado expone únicamente el texto normalizado por decisión explícita del consumidor.
- No existe dependencia de Streamlit, estado global mutable, escritura de archivos ni persistencia en disco.

## Defectos demostrados y correcciones mínimas

La primera ejecución de la nueva suite produjo 17 fallos y 17 aprobaciones. Se corrigieron únicamente los defectos demostrados:

1. La ausencia de PaddleOCR propagaba `ModuleNotFoundError`.
2. Imágenes nulas o inválidas fallaban antes del manejo de errores.
3. Estructuras OCR inesperadas, texto nulo y confianza no numérica podían producir excepciones o hashes inválidos.
4. Confianza `0.0` no podía seleccionarse con umbral cero.
5. Confianzas mayores que uno o no finitas podían aceptarse.
6. Hash y texto público no compartían una normalización consistente.

La corrección se limitó a `paddleocr_reader.py`; no cambió la firma pública, `PlateResult` ni `AbstractPlateReader`.

## Casos cubiertos

Se añadieron 34 pruebas para importación segura, motor simulado, recorte de imagen, entradas inválidas, resultados vacíos o mal formados, normalización, selección de candidatos, límites y errores de confianza, excepción del motor, estabilidad y separación de hashes, anonimización, ausencia de Streamlit, ausencia de escritura y ausencia de mutación global.

## Resultados

- Pruebas OCR nuevas: 34 aprobadas en 0.10 s.
- Suite completa: 520 aprobadas en 7.77 s.
- PaddleOCR/PaddlePaddle: no instalados ni ejecutados.
- Red/modelos/video: no utilizados.

## Limitaciones

- No se valida todavía la calidad óptica ni se localiza una placa dentro del ROI del vehículo.
- `bbox` del resultado permanece `None` porque el lector procesa el ROI completo.
- No hay consenso multiimagen ni persistencia.
- El constructor conserva su comportamiento previo y no rechaza anticipadamente configuraciones incoherentes de umbral o longitud de hash.
- La captura genérica de excepciones devuelve `None` sin diagnóstico estructurado, adecuada para la interfaz actual pero limitada para observabilidad futura.

## Siguiente tarea pequeña recomendada

Crear una prueba aislada opcional sobre un pequeño conjunto de imágenes sintéticas individuales almacenadas dentro del repositorio, manteniendo un mock de PaddleOCR por defecto y habilitando el motor real solo mediante un extra explícito. No integrar todavía con video ni modificar `vision/pipeline.py`.
