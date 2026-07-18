# Auditoría de migración — Pavement Intelligence

Fecha: 2026-07-17  
Ubicación auditada: `D:\proyecto Vial\pavement_intelligence`

## Actualización de recuperación

Se aplicaron correcciones mínimas de portabilidad después del diagnóstico:

- se añadió `requirements.txt` como entrada compatible con `pyproject.toml`;
- se retiraron del README los comandos hacia API y descargador inexistentes;
- se eliminaron de VS Code las rutas y autorizaciones de la PC anterior;
- se copiaron los pesos existentes a `data/models/`, sin borrar los originales;
- se añadieron excepciones Git para los pesos y videos demostrativos;
- se creó `.venv-new` con Python 3.12, pero la instalación de dependencias quedó
  incompleta por procesos `pip` huérfanos y debe repetirse antes de usarla.

Las 15 pruebas continúan aprobando con el entorno aislado de auditoría. No se
modificó ninguna fórmula ni módulo técnico.

## Resultado ejecutivo

El código fuente compila y las 15 pruebas existentes aprueban, pero la copia migrada no es todavía reproducible como instalación nueva. Los bloqueos principales son el entorno virtual ligado a la PC anterior, la ausencia de Python y Git en `PATH`, metadatos Git vacíos, recursos demostrativos faltantes y rutas por defecto que no coinciden con la ubicación de los modelos YOLO.

No se modificaron fórmulas, lógica técnica ni resultados existentes.

## Evidencias verificadas

- `compileall`: aprobado para `src`, `scripts` y `tests`.
- Suite existente: 15 aprobadas, 0 fallidas.
- Caso mínimo TPDA → proyección → ESAL → AASHTO 93: aprobado.
- Videos:
  - `car-detection.mp4`: 2,811,553 bytes; 377 frames; 12.5 FPS; 768×432; abre correctamente.
  - `complex_traffic.mp4`: 6,031,199 bytes; 647 frames; 12 FPS; 768×432; abre correctamente.
- Modelos:
  - `yolov8n.pt`: 6,549,796 bytes; SHA-256 `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36`.
  - `yolov8s.pt`: 22,588,772 bytes; SHA-256 `1F47A78BF100391C2A140B7AC73A1CAAE18C32779BE7D310658112F7AC9AA78A`.

## Errores y bloqueos encontrados

1. No existe `requirements.txt`. Las dependencias están declaradas solamente en `pyproject.toml`.
2. No hay Python global ni lanzador `py` disponibles en `PATH`.
3. `.venv` no es portable: apunta a `C:\Users\WINDOWS 11\AppData\Local\Python\pythoncore-3.14-64\python.exe`, que no existe en la PC nueva.
4. Git no está disponible en `PATH`.
5. `D:\proyecto Vial\.git` existe, pero está vacío; Git responde que no es un repositorio. No se puede reconstruir estado, historial ni lista real de archivos versionados/ignorados.
6. `.vscode/settings.json` contiene múltiples rutas absolutas a la PC anterior y al usuario `WINDOWS 11`.
7. La UI y configuración usan `data/models/yolov8n.pt`, pero `data/models` está vacío y los pesos están en la raíz del proyecto.
8. Falta `data/samples/caso_demostrativo/pesaje_vehicular.csv`, citado por la UI como archivo demostrativo.
9. El README ordena ejecutar `scripts/download_models.py`, pero ese script no existe.
10. El README ordena iniciar `pavement_intelligence.api.main:app`, pero no existe el paquete `api`.
11. `pyproject.toml` no declara `paddleocr`/`paddlepaddle`, aunque el README anuncia OCR y existe una implementación. Debe definirse explícitamente si OCR es opcional o instalar sus dependencias compatibles.
12. `.gitignore` excluye `data/videos/*`, `data/models/*` y `data/processed/*`. Los videos de muestra son necesarios para la demostración de visión y desaparecerían en un clon limpio salvo Git LFS, excepciones explícitas o un descargador reproducible.
13. No se pudo ejecutar inferencia YOLO real porque no existe un Python funcional del proyecto con `torch`, `ultralytics` y OpenCV instalados. Los pesos y videos sí fueron verificados por separado.

## Dependencias

Declaradas: ultralytics, OpenCV, FastAPI, Uvicorn, SQLAlchemy, Alembic, Streamlit, Pandas, NumPy, Plotly, Matplotlib, Pydantic, pydantic-settings, python-dotenv, PyYAML, openpyxl y Jinja2; desarrollo: pytest, Ruff y mypy.

Faltante respecto de funcionalidad anunciada: PaddleOCR y su backend PaddlePaddle, si el reconocimiento de placas debe estar habilitado.

Recomendación: usar `pyproject.toml` como fuente autoritativa y, si se exige `requirements.txt`, generar uno reproducible después de instalar y validar una versión de Python soportada. No copiar `.venv` entre PCs.

## Pruebas ejecutadas

- `test_tpda.py`: 1 aprobada.
- `test_vision_counting.py`: 14 aprobadas.
- Total: 15 aprobadas, 0 fallidas.
- Compilación sintáctica: aprobada.
- Caso mínimo numérico:
  - TPDA total: 120.0.
  - TPDA de diseño: 60.0.
  - Proyección a 20 años al 4%: 131.46738858200524.
  - FEC para 80 kN: 1.0.
  - ESAL: 326070.0; factor de crecimiento: 29.7781.
  - SN requerido: 2.756655421736931; SN provisto: 2.856655421736931; convergencia: verdadera.

## Archivos indispensables faltantes o mal ubicados

- Falta: `data/samples/caso_demostrativo/pesaje_vehicular.csv`.
- Falta: `scripts/download_models.py` citado por README, o debe eliminarse/corregirse esa instrucción.
- Falta: `src/pavement_intelligence/api/main.py` citado por README, o debe eliminarse/corregirse esa instrucción.
- Mal ubicados para la configuración actual: `yolov8n.pt` y `yolov8s.pt`; están en la raíz, no en `data/models/`.
- No se encontraron imágenes de demostración; `data/images` contiene solo `.gitkeep`.

## Comandos para reconstruir y ejecutar en esta PC

Ejecutar desde PowerShell, después de instalar Python 3.12 o 3.13 de 64 bits y Git, ambos agregados a `PATH`:

```powershell
cd 'D:\proyecto Vial\pavement_intelligence'
python -m venv .venv-new
& '.\.venv-new\Scripts\Activate.ps1'
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
Copy-Item '.env.example' '.env'
$env:PYTHONPATH = (Resolve-Path '.\src')
python -m compileall src scripts tests
python -m pytest -v
python -m streamlit run src\pavement_intelligence\ui\app.py
```

Para visión, primero colocar los modelos en la ruta que espera la configuración:

```powershell
New-Item -ItemType Directory -Force 'data\models'
Copy-Item 'yolov8n.pt' 'data\models\yolov8n.pt'
Copy-Item 'yolov8s.pt' 'data\models\yolov8s.pt'
python scripts\run_headless_vision.py --video data\videos\samples\car-detection.mp4 --prefix migracion_smoke
```

Para iniciar la interfaz sin activar el entorno:

```powershell
& '.\.venv-new\Scripts\python.exe' -m streamlit run src\pavement_intelligence\ui\app.py
```

No ejecutar el comando Uvicorn del README hasta que exista y se pruebe `pavement_intelligence.api.main`.

## Correcciones mínimas recomendadas, en orden

1. Instalar Python y Git; recrear el entorno virtual desde cero.
2. Restaurar `.git` desde el repositorio remoto mediante un clon limpio, no copiando una carpeta `.git` vacía.
3. Colocar los pesos en `data/models/` o unificar las tres rutas por defecto hacia la ubicación real.
4. Recuperar el CSV del caso demostrativo.
5. Corregir README: retirar comandos de API/descarga inexistentes o agregar esos componentes si pertenecen al proyecto original.
6. Decidir y documentar OCR como dependencia opcional o requerida.
7. Versionar recursos pequeños de demostración, usar Git LFS o proporcionar un script de descarga con hashes.
8. Eliminar las rutas absolutas migradas de `.vscode/settings.json` y regenerar esa configuración localmente.
