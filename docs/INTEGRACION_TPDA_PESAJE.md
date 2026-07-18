# Integración controlada TPDA → Pesaje

**Fecha:** 2026-07-17  
**Contratos:** TPDA 1.0 / Pesaje 1.0  
**Decisión:** **APROBADO PARA AUDITAR FASE 2 DE PESAJE**

Esta decisión habilita una auditoría independiente de Pesaje. No declara la Fase 2 lista para ESAL y no crea consumo desde ESAL.

## 1. Auditoría inicial de Pesaje

### Estado encontrado

- weighing.py solo aceptaba un CSV, lo cargaba con pandas y lo guardaba directamente en st.session_state["pesaje_df"].
- La UI calculaba número de registros, categorías, media de peso y rango de fechas.
- No existía contrato de entrada desde TPDA, transferencia manual, firma, histórico ni estado metodológico.
- No existía resultado formal de Pesaje.
- Cada archivo cargado podía reemplazar pesaje_df durante la interacción sin decisión ni histórico.
- El CSV demostrativo contiene 50 registros y notes=simulado, pero la interfaz dependía del texto y la ruta para advertir su condición.
- Categorías del archivo: BUS, C2, C3, TRACTOCAMION y ARTICULADO.
- El dominio previo incluye WIMRecord y AxleLoad en kN, pero permite carga cero y el importador histórico omite silenciosamente filas inválidas. El nuevo flujo no usa esa conducta permisiva.
- El catálogo admite simple_single, simple_dual, tandem, tridem y unknown. El flujo auditado rechaza unknown para una configuración estructural confirmada.
- ESAL conserva una integración histórica separada con tpda_result. No consume weighing_phase2_result ni weighing_input_from_tpda.

### Riesgos corregidos

- sobrescritura silenciosa;
- filas inválidas descartadas sin explicación;
- ausencia de unidad y fuente formal;
- falta de comparación entre peso bruto y suma de ejes;
- posible uso ambiguo del CSV sintético;
- ausencia de invalidación por cambio de TPDA o cargas;
- falta de separación entre tránsito liviano y categorías que requieren cargas.

## 2. Flujo implementado

    tpda_phase1_result
    → revisión visible
    → confirmación del operador
    → botón “Usar TPDA validado en Pesaje”
    → weighing_input_from_tpda
    → adopción explícita de muestra de cargas
    → validación del dominio
    → weighing_phase2_result

No existe transferencia automática al calcular TPDA. No se escribe pesaje_df, tpda_result ni esal_result.

## 3. Contrato TPDA → Pesaje

WeighingInputFromTPDA contiene:

- versión, ID y fecha de transferencia;
- ID y huella del resultado TPDA;
- estado metodológico;
- TPDA base y tránsito proyectado por categoría;
- periodo, tasa, FDD, FDC y tránsito proyectado por carril;
- categorías con necesidad de configuración de carga;
- marca sintética, advertencias y supuestos;
- revisor y modo demostrativo.

Solo build_weighing_input_from_tpda crea el contrato. Valida:

- VALIDO_PARA_CONTINUAR para producción;
- VALIDO_PARA_DEMOSTRACION con aceptación explícita para demo;
- resultado vigente;
- duración confirmada;
- proyección exponencial o Lineal B;
- conteos no vacíos;
- ausencia de pendientes;
- ausencia de CAMION_NO_CONFIRMADO;
- identidad, huella y revisor.

Pesaje consume únicamente st.session_state["tpda_phase1_result"] para comprobar vigencia y st.session_state["weighing_input_from_tpda"] como entrada transferida. No consume conteos YOLO, traffic_counts_corrected, corrected_records, events ni tpda_result.

## 4. Transferencia y sobrescritura

La sección “Transferir resultado a Pesaje” muestra resumen, exige casilla y botón.

Si existen weighing_input_from_tpda, weighing_records_current, weighing_phase2_result o el legado pesaje_df, el operador debe elegir:

- conservar;
- reemplazar y conservar histórico;
- cancelar.

Los históricos se guardan en:

- weighing_history;
- weighing_records_history;
- weighing_result_history.

Al reemplazar una sesión antigua, pesaje_df se archiva como legacy_pesaje_df antes de quedar inactivo. Nada se borra ni reemplaza sin la decisión explícita.

## 5. Categorías

Las categorías transferidas incluyen:

- categoría de tránsito;
- TPDA base;
- cantidad proyectada;
- requiere o no configuración de carga;
- clasificación confirmada;
- procedencia.

Categorías estructurales pesadas: BUS, C2, C3, TRACTOCAMION, ARTICULADO y OTRO_PESADO.

MOTO, AUTO, CAMIONETA y MINIBUS permanecen para estadística de tránsito, sin asignarles cargas automáticamente. CAMION_NO_CONFIRMADO no se admite. No se infieren ejes, pesos ni factores camión desde YOLO.

## 6. Fuentes admitidas

- exportación WIM mediante CSV;
- pesaje estático mediante CSV;
- archivo CSV general;
- ingreso manual;
- biblioteca demostrativa.

Cada WeighingObservation registra:

- ID reproducible;
- fecha;
- categoría;
- peso bruto;
- grupos de ejes;
- tipo de fuente y referencia;
- condición medida, importada, asumida o sintética;
- revisor y observaciones.

La biblioteca pesaje_vehicular.csv se importa siempre como SINTETICO_DEMOSTRATIVO y exige reconocimiento.

## 7. Unidades

Unidad interna única: **kN**.

Conversiones explícitas:

- kN → kN: factor 1;
- kg → kN: factor 0,00980665;
- tonelada métrica → kN: factor 9,80665.

Unidades desconocidas, valores cero, negativos, NaN o infinito se rechazan. La UI muestra “Unidad interna canónica: kN”.

## 8. Ejes y cargas

Tipos confirmados:

- simple_single: un eje físico;
- simple_dual: un eje físico;
- tandem: dos ejes físicos;
- tridem: tres ejes físicos.

Cada grupo exige tipo, carga positiva, posición y origen. No se admite unknown. La suma de cargas se compara con el peso bruto; la tolerancia predeterminada es 5 % y puede configurarse de forma trazable.

Se validan:

- muestra no vacía;
- categorías transferidas;
- configuraciones completas;
- número físico de ejes coherente;
- cargas y peso bruto positivos;
- discrepancia dentro de tolerancia;
- IDs no duplicados;
- unidad reconocida;
- trazabilidad de fuente y revisor.

Los valores atípicos se detectan por IQR dentro de cada categoría cuando hay muestra suficiente. Por defecto se marcan sin excluir.

## 9. Modelo formal de Pesaje

WeighingWorkflowResult es inmutable e incluye:

- result_id, version, created_at;
- ID y huella TPDA;
- input_fingerprint;
- fuente y referencia;
- categorías y configuraciones;
- número de observaciones;
- cargas de eje y pesos brutos en kN;
- estadísticas por categoría;
- IDs atípicos;
- supuestos y advertencias;
- condición sintética;
- estado metodológico;
- indicador ESAL;
- revisor, validación y vigencia.

No calcula FEC, factor camión ni ESAL.

## 10. Estados

- VALIDO_PARA_CONTINUAR;
- VALIDO_PARA_DEMOSTRACION;
- BLOQUEADO_POR_TPDA;
- BLOQUEADO_POR_CLASIFICACION;
- BLOQUEADO_POR_CONFIGURACION_DE_EJES;
- BLOQUEADO_POR_CARGAS;
- BLOQUEADO_POR_UNIDADES;
- BLOQUEADO_POR_DATOS_SINTETICOS;
- BLOQUEADO_POR_MUESTRA_VACIA;
- DESACTUALIZADO_REQUIERE_RECALCULO.

Indicadores preparados:

- APTO_PARA_ESAL;
- APTO_SOLO_DEMOSTRACION;
- NO_APTO_PARA_ESAL.

Estos son indicadores, no una transferencia.

## 11. Datos sintéticos

Si TPDA o cualquier observación es sintética:

- is_synthetic se propaga;
- sin reconocimiento queda BLOQUEADO_POR_DATOS_SINTETICOS;
- con reconocimiento solo alcanza VALIDO_PARA_DEMOSTRACION;
- el indicador máximo es APTO_SOLO_DEMOSTRACION;
- nunca se presenta como medición real.

Una cadena TPDA real + cargas medidas/importadas reales y válidas puede alcanzar VALIDO_PARA_CONTINUAR.

## 12. Firmas e invalidación

La firma de entrada incluye:

- contrato TPDA;
- observaciones y cargas;
- configuraciones;
- unidades ya normalizadas;
- fuente y fecha;
- tolerancia;
- tratamiento de atípicos;
- supuestos, advertencias y revisor.

weighing_result_is_stale marca desactualizado cuando:

- cambia la firma o ID TPDA;
- el TPDA actual falta o está desactualizado;
- cambian cargas, ejes, categorías, fuente, filtros/tolerancia o tratamiento de atípicos.

El resultado se conserva y su transferencia futura debe bloquearse. Recalcular archiva el resultado anterior.

## 13. Claves de sesión

- tpda_phase1_result: única comprobación del TPDA actual;
- weighing_input_from_tpda: contrato manual independiente;
- weighing_records_current: muestra adoptada;
- weighing_phase2_input: entrada firmada del último cálculo;
- weighing_phase2_result: resultado formal;
- weighing_history, weighing_records_history y weighing_result_history: históricos.

No se crean ni actualizan claves ESAL.

## 14. Pruebas

Se añadieron:

- tests/unit/test_weighing_workflow.py;
- tests/unit/test_weighing_ui.py.

Cobertura:

- consumo exclusivo, vigencia y estados TPDA;
- transferencia manual y ausencia de automatismo;
- sobrescritura e históricos, incluido pesaje_df legado;
- categorías y CAMION no confirmado;
- CSV real y sintético;
- suma de ejes/peso bruto;
- kg, toneladas y kN;
- cargas inválidas y muestra vacía;
- cadena sintética/productiva;
- firmas e invalidación;
- almacenamiento en weighing_phase2_result;
- ausencia de consumo por ESAL;
- carga de páginas Streamlit sin excepciones.

Resultado final:

- **153 pruebas aprobadas, 0 fallidas** en 21,76 s.
- pip check: **No broken requirements found**.

## 15. Escenarios funcionales y prueba manual

Los escenarios de dominio/AppTest cubren:

1. TPDA real válido: contrato copiado sin modificar TPDA.
2. TPDA sintético: modo demostrativo.
3. TPDA desactualizado: transferencia bloqueada.
4. Datos existentes: conservar, reemplazar con histórico o cancelar.
5. CSV sintético: advertencia y demostración.
6. Cambio posterior de TPDA: Pesaje desactualizado y conservado.
7. Cambio de carga/eje: firma diferente y recálculo requerido.

Para comprobación visual humana:

1. Abra Aforo y TPDA, calcule un resultado vigente, marque la confirmación y pulse “Usar TPDA validado en Pesaje”.
2. Abra Pesaje y compruebe el bloque “Origen del tránsito”.
3. Pruebe la biblioteca demostrativa y reconozca su carácter sintético.
4. Adopte una muestra; intente cargar otra y verifique las tres decisiones.
5. Calcule, cambie tolerancia o carga y confirme el aviso DESACTUALIZADO.
6. Recalcule TPDA sin transferir y confirme el bloqueo por firma.
7. Verifique que ESAL no ofrece ni consume weighing_phase2_result.

Streamlit inició correctamente en localhost. El entorno automatizado no expuso navegador gráfico, por lo cual no se afirma una inspección visual humana; los escenarios fueron verificados funcionalmente con dominio y AppTest.

## 16. Archivos

### Creados

- src/pavement_intelligence/weighing/workflow.py
- tests/unit/test_weighing_workflow.py
- tests/unit/test_weighing_ui.py
- docs/INTEGRACION_TPDA_PESAJE.md

### Modificados

- src/pavement_intelligence/traffic/tpda_workflow.py: propagación del revisor, sin cambio de fórmulas.
- src/pavement_intelligence/ui/pages/survey_tpda.py: transferencia manual.
- src/pavement_intelligence/ui/pages/weighing.py: flujo de Fase 2.

## 17. Conclusión

La integración TPDA → Pesaje es explícita, reversible, firmada y auditable. La Fase 2 queda preparada para una auditoría independiente, no para consumo directo por ESAL.

**APROBADO PARA AUDITAR FASE 2 DE PESAJE**
