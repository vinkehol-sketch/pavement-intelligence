# Validación controlada de PaddleOCR real

Fecha de ejecución: 2026-07-20
Estado: **aprobada para una imagen ficticia individual; no validada sobre video ni placas reales**

## Alcance y aislamiento

La validación se realizó exclusivamente sobre la fuente OCR independiente. No se
modificaron el flujo panorámico, el conteo vehicular, TPDA, pesaje, ESAL, geotecnia
ni diseño de pavimentos. No se descargaron imágenes ni se usaron matrículas reales.

El entorno principal del proyecto permaneció en Python 3.14.6 y sin PaddleOCR. El
backend se instaló fuera del repositorio en:

`C:\Users\Pc\AppData\Local\pavement-intelligence\ocr-venv-py313`

## Entorno auditado

| Elemento | Entorno principal | Entorno OCR aislado |
|---|---:|---:|
| Sistema | Windows 11, 64 bits, AMD64 | Igual |
| Python | 3.14.6 | 3.13.14 |
| pip | 26.1.2 | 26.1.2 |
| NumPy | 2.5.1 | 2.3.5 |
| OpenCV | 5.0.0.93 | opencv-contrib-python 4.10.0.84 |
| Pillow | 12.3.0 | 12.3.0 |
| torch | 2.13.0 | No instalado |
| PaddlePaddle | No instalado | 3.3.1 CPU |
| PaddleOCR | No instalado | 3.7.0 |

El disco `C:` tenía aproximadamente 155,19 GiB libres antes de la instalación.
`pip check` no informó dependencias rotas en ninguno de los dos entornos.

PaddlePaddle publica wheels de Windows para Python 3.9 a 3.13, incluida la rama
3.12, pero no para Python 3.14. PaddleOCR 3.7.0 declara compatibilidad hasta Python
3.13. Por ello no se forzó la instalación en el entorno principal.

Referencias oficiales:

- <https://www.paddlepaddle.org.cn/documentation/docs/en/install/pip/windows-pip_en.html>
- <https://pypi.org/project/paddlepaddle/3.3.1/>
- <https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/installation.en.md>
- <https://pypi.org/project/paddleocr/3.7.0/>

## Instalación reproducible

Desde PowerShell:

```powershell
$ocrEnv = 'C:\Users\Pc\AppData\Local\pavement-intelligence\ocr-venv-py313'
py -3.13 -m venv $ocrEnv
& "$ocrEnv\Scripts\python.exe" -m pip install --upgrade pip
& "$ocrEnv\Scripts\python.exe" -m pip install --only-binary=:all: `
  'paddlepaddle==3.3.1' 'paddleocr==3.7.0' 'pytest>=8.2'
& "$ocrEnv\Scripts\python.exe" -m pip check
```

La instalación es CPU: no incluye CUDA ni paquetes GPU. PaddleOCR instaló sus
dependencias transitivas normales y descargó, al construir el motor por primera
vez, `PP-OCRv6_medium_det` y `PP-OCRv6_medium_rec` al caché externo
`C:\Users\Pc\.paddlex\official_models`. Ningún modelo se añadió al repositorio.

## Compatibilidad del reader

La primera construcción real reveló dos defectos reproducibles del adaptador:

1. PaddleOCR 3.7.0 rechazó el argumento heredado `show_log` con
   `ValueError: Unknown argument: show_log`.
2. La primera inferencia con oneDNN habilitado falló en Windows con
   `NotImplementedError: ConvertPirAttribute2RuntimeAttribute ... DoubleAttribute`.

La corrección se limitó a `PaddleOCRPlateReader`: selección explícita de la API
2.x/3.x, parser defensivo del resultado 3.x y `enable_mkldnn=False` para el motor
CPU 3.x. No se modificó `PlateAnalysisController`. Después de la corrección,
`import paddle`, `import paddleocr`, la importación del reader, su construcción y
la inferencia finalizaron sin crashes.

## Imagen y resultados

Se generó durante la prueba una imagen PNG ficticia de 1280 × 720 píxeles con la
placa visible `ABC-123`. El archivo vivió únicamente en el directorio temporal de
pytest y fue eliminado por un finalizer. No contenía datos personales ni se
versionó.

| Caso | ROI `(x1, y1, x2, y2)` | Texto bruto | Normalizado | Confianza | Tiempo |
|---|---|---|---|---:|---:|
| Imagen completa | `(0, 0, 1280, 720)` | `ABC-123` | `ABC123` | 0,999993 | 7,726120 s |
| Recorte manual | `(390, 320, 890, 480)` | `ABC-123` | `ABC123` | 0,999990 | 1,195426 s |
| ROI ajustada | `(366, 300, 914, 500)` | `ABC-123` | `ABC123` | 0,999992 | 1,581568 s |

El texto esperado era `ABC-123` y la coincidencia normalizada esperada era
`ABC123`. PaddleOCR entregó el texto bruto correcto y el reader devolvió la forma
normalizada correcta. La inferencia directa adicional sobre el recorte manual,
usada para registrar el payload bruto, tomó 0,954381 s. Los tiempos
son una observación local única, no un benchmark.

## Prueba opcional

`tests/integration/test_paddleocr_real_reader.py`:

- se omite si `RUN_PADDLEOCR_REAL` no vale `1`;
- usa `pytest.importorskip("paddleocr")`;
- acepta una imagen autorizada mediante `PADDLEOCR_TEST_IMAGE`;
- puede generar la placa ficticia temporal mediante `PADDLEOCR_SYNTHETIC_TEXT`;
- compara opcionalmente con `PADDLEOCR_EXPECTED_TEXT`;
- verifica confianza acotada, repetición razonablemente determinista, imagen
  vacía y ROI vacía;
- elimina la imagen ficticia incluso si la prueba falla.

Ejecución reproducible desde la raíz:

```powershell
$ocrPy = 'C:\Users\Pc\AppData\Local\pavement-intelligence\ocr-venv-py313\Scripts\python.exe'
$env:PYTHONPATH = "$PWD\src"
$env:RUN_PADDLEOCR_REAL = '1'
$env:PADDLEOCR_SYNTHETIC_TEXT = 'ABC-123'
$env:PADDLEOCR_EXPECTED_TEXT = 'ABC123'
$env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = 'True'
& $ocrPy -m pytest -q -s tests/integration/test_paddleocr_real_reader.py
```

En otra PC debe instalarse Python 3.13 de 64 bits, crear el entorno aislado,
ejecutar los comandos anteriores y permitir la descarga inicial de los modelos
oficiales. Para una imagen propia debe omitirse `PADDLEOCR_SYNTHETIC_TEXT` y
definirse `PADDLEOCR_TEST_IMAGE` con una ruta local autorizada.

## Warnings, seguridad y limitaciones

- Paddle emitió un warning informativo por ausencia de `ccache`; no afectó la
  inferencia y no se instaló porque no se compilaron extensiones.
- El mensaje de consola sobre patrones no encontrados procede de la detección de
  herramientas del backend en Windows y no afectó el resultado.
- El reader devuelve `None` ante imagen inválida, vacía, ROI vacía, cero
  resultados o excepción del motor; las pruebas unitarias con fakes permanecen.
- No hubo escritura permanente de imágenes ni resultados. Solo persisten el
  entorno OCR y el caché oficial de modelos, ambos fuera del repositorio.
- Una placa sintética nítida no demuestra precisión ante perspectiva, movimiento,
  iluminación, suciedad, tipografías locales ni matrículas reales.
- No se validaron procesamiento continuo, uso de memoria, latencia sostenida,
  saltos cada N frames ni recuperación de una fuente de video.

## Recomendación

El backend queda apto para continuar con más imágenes individuales autorizadas y
variadas. **No se recomienda avanzar todavía a OCR sobre video completo**: antes
debe validarse un conjunto pequeño y autorizado de imágenes reales, acordar
métricas de precisión/privacidad y medir rendimiento sostenido en CPU. Esta prueba
no aprueba asociación con el conteo panorámico ni transferencia a TPDA o módulos
de ingeniería.
