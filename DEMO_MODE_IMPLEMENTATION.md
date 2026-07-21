# Modo demostración de Pavement Intelligence

## Alcance y advertencia

**DATOS SINTÉTICOS — SOLO DEMOSTRACIÓN**

El caso `DEMO-CORREDOR-ANDINO-01` representa un corredor bidireccional
completamente ficticio. Todo el estado cargado por este modo declara:

```text
data_origin = "synthetic_demo"
is_demo = true
```

No es un estudio vial, un pesaje, un ensayo de laboratorio ni un diseño
aprobado. La demostración vive únicamente en la sesión de Streamlit. No escribe
resultados en las fuentes reales, no crea archivos de datos y no descarga ni
versiona videos, modelos, pesos o cachés.

## Uso

1. Inicie Streamlit con el intérprete del proyecto.
2. Pulse **Cargar caso demostrativo** en la barra lateral.
3. Recorra las pantallas en el orden del menú. La advertencia permanece visible
   mientras el caso está activo.
4. Pulse **Reiniciar demostración** para abandonar el modo y eliminar todos sus
   objetos, resultados, revisiones OCR, PDF en memoria y widgets asociados.

La carga es atómica. Si existe actividad real de video, OCR, aforo, pesaje o
cálculo, se rechaza la carga para impedir que ambos orígenes se mezclen. El
reinicio solo está habilitado cuando el modo demo está activo.

## Arquitectura

- `src/pavement_intelligence/demo/case.py` centraliza la semilla fija
  `20260720`, las entradas declaradas y la construcción del caso.
- `src/pavement_intelligence/demo/session.py` administra la carga segura, los
  conflictos con datos operacionales y la limpieza completa.
- `src/pavement_intelligence/ui/app.py` expone los dos controles globales, la
  advertencia y un resumen trazable en todas las pantallas.
- Los fixtures visuales existentes usan el origen canónico `synthetic_demo` y
  cifras consistentes con el caso central.

No se duplicó lógica de negocio. El constructor llama los flujos existentes de
TPDA, Pesaje, ESAL, proyección, CBR/MR, AASHTO 93, capas y reportes. Los IDs de
eventos, conteos, placas y parámetros de entrada son reproducibles; los motores
conservan sus sellos temporales y huellas propios.

## Caso ficticio y trazabilidad

- 120 cruces visuales distribuidos en dos sentidos.
- 106 cruces aprobados para el aforo; 14 aparecen inicialmente como pendientes
  y terminan resueltos mediante revisión documentada.
- Categorías: automóviles, motocicletas, camionetas, minibuses, buses y cuatro
  configuraciones confirmadas de camiones.
- Cuatro lecturas OCR ficticias (`DEMO-01`, `FICT-?2`, `TEST-X3` y una ilegible),
  enmascaradas por defecto. Dos contienen revisión/corrección demostrativa.
- Ventana observada de 2 horas; expansión uniforme explícita `24 / 2 = 12`.
- Factor estacional neutro 1,0; crecimiento geométrico 4,0 %; periodo 20 años;
  FDD 0,52; FDC 1,00; 365 días/año.
- Ocho observaciones de pesaje sintéticas para C2, C3, tractocamión y articulado,
  con peso bruto igual a la suma visible de grupos de ejes.
- Tres muestras CBR saturadas ficticias: 6,5 %, 7,0 % y 7,5 %.
- Correlación de MR seleccionada del catálogo existente:
  `LINEAL_1500_PSI`.
- AASHTO 93 flexible: confiabilidad 90 %, `S0 = 0,45`, `p0 = 4,2` y `pt = 2,5`.
- Capas seleccionadas mediante la búsqueda discreta existente, con rangos,
  incrementos, coeficientes y drenaje visibles.

Resultados calculados del caso:

| Resultado | Valor aproximado |
|---|---:|
| TPDA base | 1.272 veh/día |
| Tránsito proyectado | 2.787,11 veh/día |
| W18 acumulado de diseño | 1.053.765,77 |
| CBR de diseño | 7,0 % |
| MR adoptado | 72,39 MPa |
| SN requerido | 3,081 |
| Carpeta asfáltica | 5 in |
| Base granular | 4 in |
| Subbase granular | 4 in |
| Expediente | `COMPLETO_DEMOSTRATIVO` |

Los resultados pueden cambiar en los últimos decimales si evoluciona un motor;
las entradas del caso y la semilla no cambian silenciosamente.

## Separación del OCR

El OCR experimental usa claves de sesión propias. Sus textos no se incorporan a
`traffic_counts_corrected`, TPDA ni conteos oficiales. La visibilidad comienza
oculta y cualquier revelado se audita. Las matrículas usan palabras reservadas de
prueba para que sean inequívocamente ficticias.

## Limitación contractual documentada

El catálogo actual marca `BUS` y `OTRO_PESADO` como categorías estructurales sin
configuración de ejes confirmada. El caso muestra buses en monitoreo y revisión,
pero los excluye justificadamente del lote estructural. No se inventaron ejes ni
factores equivalentes para superar esa restricción. La consolidación ESAL emplea
solo C2, C3, `TRACTOCAMION` y `ARTICULADO`, cuyas configuraciones están admitidas
por el catálogo existente.

La demostración tampoco sustituye un video procesado por YOLO ni un ensayo OCR
real: representa sus eventos y revisiones con datos marcados. Los algoritmos
YOLO, ByteTrack y PaddleOCR no se modificaron.

## Validaciones automatizadas

Las pruebas específicas verifican:

- recorrido completo por los motores existentes;
- origen y condición demostrativa en cada fase;
- reproducibilidad de eventos y dos sentidos;
- privacidad y separación del OCR;
- rechazo de una carga sobre sesión real;
- limpieza completa al reiniciar;
- carga y reinicio desde AppTest sin excepciones.

Resultados de validación de esta implementación:

- Pruebas focalizadas del modo demo y presentación: **39 aprobadas**.
- AppTest manual automatizado: carga del caso y navegación por las 13 pantallas,
  **sin excepciones**; reinicio completo verificado.
- Suite completa: **880 aprobadas, 1 omitida y 4 fallos preexistentes**.
- Ruff sobre archivos modificados: aprobado.
- `python -m pip check`: aprobado, sin dependencias rotas.
- `git diff --check`: aprobado.

Los cuatro fallos preexistentes dependen exclusivamente de artefactos no
versionados de `line_y360`:

1. `test_real_line_y360_csv_is_contract_compatible` requiere `events.csv`.
2. `test_real_line_y360_batch_loads_with_metadata` requiere
   `batch_ui_contract_example.json`.
3. `test_real_csv_is_adapted_with_correct_types` requiere `events.csv`.
4. `test_batch_model_and_line_metadata_survive_session_load` requiere
   `batch_ui_contract_example.json`.

No se generaron sustitutos sintéticos para esos archivos reales porque hacerlo
ocultaría la ausencia del artefacto contractual que las pruebas pretenden validar.
