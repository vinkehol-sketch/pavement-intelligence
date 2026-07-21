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
3. Recorra las pantallas en el orden del menú. La barra lateral muestra un estado
   discreto mientras el caso está activo.
4. Pulse **Reiniciar demostración** para abandonar el modo y eliminar todos sus
   objetos, resultados, revisiones OCR, PDF en memoria y widgets asociados.

La carga es atómica. Si existe actividad real de video, OCR, aforo, pesaje o
cálculo, se rechaza la carga para impedir que ambos orígenes se mezclen. El
reinicio solo está habilitado cuando el modo demo está activo.

## Arquitectura

- `src/pavement_intelligence/demo/case.py` centraliza la semilla fija
  `20260720`, las entradas declaradas y la construcción del caso. Su función
  `build_demo_tpda_input()` es la fuente oficial del contrato TPDA demostrativo;
  la interfaz no redefine su duración ni sus factores.
- `src/pavement_intelligence/demo/session.py` administra la carga segura, los
  conflictos con datos operacionales y la limpieza completa.
- `src/pavement_intelligence/ui/app.py` expone los dos controles globales, un
  estado lateral discreto y un resumen trazable en todas las pantallas.
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
- Aforo sintético declarado de 2 horas (14:00–16:00); 106 vehículos aprobados.
- Expansión temporal uniforme explícita `24 / 2 = 12` y factor estacional 1.
- Fórmula mostrada y trazada: `106 × 12 × 1 = 1.272 veh/día`.
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

El TPDA demostrativo conserva
`methodologically_fit_for_next_phase = false`: no puede utilizarse como entrada
oficial de Pesaje o ESAL. El adaptador existente permite su continuidad solo si
el llamador activa explícitamente el modo demostración; la interfaz muestra esa
restricción antes de transferirlo.

## Separación del OCR

El OCR experimental usa claves de sesión propias. Sus textos no se incorporan a
`traffic_counts_corrected`, TPDA ni conteos oficiales. La visibilidad comienza
oculta y cualquier revelado se audita. Las matrículas usan palabras reservadas de
prueba para que sean inequívocamente ficticias.

## Formularios prellenados y campos obligatorios

La carga del caso copia una sola vez 177 claves de widget desde
`demo/metadata.py` y `demo/case.py`. Cada widget tiene una clave estable: si el
usuario lo edita, Streamlit conserva la edición durante los reruns. Reiniciar la
demostración elimina exactamente esas claves; una carga posterior restaura la
semilla original. El modo real no consume estos valores.

| Pantalla | Campos o contrato inspeccionado | Claves o modelo | Validación/bloqueo | Valor demo visible |
|---|---|---|---|---|
| Inicio | Proyecto, código, tipo, ubicación, tramo, entidad, fecha y responsables | `demo_project_metadata`, `demo_responsible_parties` | Identificación y trazabilidad | Evaluación demostrativa del Corredor Andino; responsables ficticios |
| Monitoreo de tráfico | Fuente, dos sentidos, estación, fecha, operador | `demo_traffic_inputs`, `vision_batch_metadata` | Lote visual disponible | `demo://corredor-andino/video-ficticio`; `DEMO-LINE-01`; 14:00–16:00 |
| Lecturas de placas | Revisor, privacidad, corrección, motivo y observaciones | `ocr_reviewer`, `ocr_corrected_*`, `ocr_reason_*`, `ocr_notes_*` | Una corrección exige texto, motivo y revisor | Auditor Vial Demo; placas ficticias enmascaradas; motivos trazables |
| Análisis de video | Fuente y eventos procesados | `vision_events_raw`, `processing_done` | Evita requerir un video real para presentar el caso | Fuente sintética; 120 eventos reproducibles |
| Revisión del aforo | Aceptación sintética, totales, correcciones y transferencia | `traffic_review_synthetic_ack`, `traffic_review_totals_ack`, `traffic_review_transfer_ack` | Sin pendientes; reconocimientos obligatorios | Aprobados; motivo: clasificación visual supervisada |
| Aforo y TPDA | Duración, cobertura, expansión, estacionalidad, crecimiento, periodo, FDD/FDC y revisor | `demo_tpda_authoritative_input` y widgets `demo_tpda_*` | Cobertura confirmada; revisor y reconocimiento obligatorios | 2 h; `24/2=12`; FE=1; 4 %; 20 años; 0,52/1,00; Auditor Vial Demo |
| Pesaje | Fuente, fecha, revisor, ejes, cargas, tolerancia y reconocimiento | `demo_weighing_inputs`, `weighing_*` | Pesos/ejes coherentes y aceptación sintética | Biblioteca demo; 8 observaciones en kN; tolerancia 5 % |
| ESAL | Método, revisor, supuestos, reconocimientos y proyección temporal | `demo_esal_inputs`, `esal_*`, `esal3b_*` | Transferencia vigente y aceptación de aproximación académica | Ley de cuarta potencia visible; 2 h; 4 %; 20 años; 365 días |
| Estudio de suelo | Muestra, ubicación, profundidad, CBR, humedad, fuente, responsable, correlación y adopción MR | `demo_geotechnical_inputs`, `geotech_*` | Fuente/revisor/reconocimiento; adopción justificada | Tres CBR sintéticos; promedio 7 %; `LINEAL_1500_PSI`; DEMO-LAB ficticio |
| AASHTO 93 — SN | Diseño, tramo, R/ZR, S0, p0, pt, responsable, justificación y confirmación | `demo_pavement_inputs.phase_5a`, `aashto5a_*` | Transferencias 3B/4B vigentes y campos trazables | R=90 %; S0=0,45; p0=4,2; pt=2,5; Especialista Demo en Pavimentos |
| AASHTO 93 — Capas | Modo, materiales, espesores, coeficientes, drenaje, mínimos, rangos y responsable | `demo_pavement_inputs.phase_5b`, `5b_*` | Propuesta completa y búsqueda discreta acotada | Capas sintéticas; rangos, incrementos, aᵢ y mᵢ visibles |
| Diseño de pavimento | Tipo, método, W18, CBR, responsables y criterio | `esal_projection_result`, `geotechnical_phase4a_result`, `pavement_*` | Entradas positivas y serviciabilidad consistente | Pavimento flexible AASHTO 93; entradas tomadas de motores previos |
| Reportes | Título, código, entidad, ubicación, elaboró/revisó/aprobó, fecha, versión y descargo | `demo_report_metadata`, `report_*`, `integrated_report_request` | Datos administrativos y fases obligatorias | `DEMO-1.0`; expediente completo; descargo sintético visible |

El inventario ejecutable `DEMO_REQUIRED_FIELDS` registra para cada campo la
pantalla, nombre, clave o modelo, tipo de dato, validación y valor propuesto. No
se eliminaron validaciones: los bloqueos se satisfacen mediante entradas válidas,
reconocimientos explícitos y transferencias ya construidas por los adaptadores.

## Recorrido exacto de demostración

1. Cargar el caso desde la barra lateral y revisar la ficha sintética en Inicio.
2. Abrir Monitoreo, Lecturas de placas y Análisis de video para presentar eventos,
   privacidad OCR y separación del conteo oficial.
3. Abrir Revisión del aforo y comprobar que no quedan categorías pendientes.
4. En Aforo y TPDA verificar `106 × 12 × 1 = 1.272 veh/día` y la proyección.
5. Recorrer Pesaje y ESAL; mostrar ejes/cargas, ley de cuarta potencia y proyección.
6. En Estudio de suelo revisar CBR, correlación y adopción explícita de MR.
7. Recorrer SN requerido, Capas demostrativas y Diseño de pavimento.
8. Abrir Reportes, revisar la identificación ficticia y descargar el expediente.
9. Pulsar **Reiniciar demostración** para eliminar metadatos, responsables,
   widgets y resultados sintéticos.

Limitaciones: Monitoreo, Video y OCR representan datos sintéticos ya preparados;
no ejecutan YOLO ni PaddleOCR al cargar el caso. La pantalla histórica Diseño de
pavimento consume W18 y CBR calculados por las fases formales, pero su bloque de
responsables es solo identificación visible porque ese motor legado no posee un
contrato administrativo propio.

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

- Pruebas específicas del modo demo: **22 aprobadas**.
- AppTest parametrizado: las 13 pantallas cargan prellenadas **sin excepciones**;
  las acciones principales no quedan deshabilitadas por datos faltantes y el
  reinicio completo está verificado.
- Suite completa: **898 aprobadas, 1 omitida y 4 fallos preexistentes**.
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
