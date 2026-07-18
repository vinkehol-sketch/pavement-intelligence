# Cierre metodológico de la Fase 1: Aforo y TPDA

**Fecha:** 2026-07-17  
**Versión del contrato:** 1.0  
**Decisión:** **APROBADO PARA CONTINUAR CON PESAJE Y ESAL**

La decisión significa que el módulo puede avanzar a una futura fase de integración controlada. En esta tarea no se implementó ni habilitó ninguna transferencia a Pesaje o ESAL. Cada resultado conserva su propio estado metodológico y solo el estado VALIDO_PARA_CONTINUAR declara aptitud.

## 1. Problemas corregidos

1. Se eliminó de la UI la fórmula duplicada (24/duración) × f_n × f_e.
2. La UI dejó de calcular TPDA, proyecciones, FDD o FDC localmente.
3. CAMION y TRUCK ya no se convierten automáticamente en C2.
4. f_n y f_e se presentan como factores configurables, no como oficiales ABC.
5. Lineal A dejó de ser seleccionable en el flujo normal.
6. Un CSV agregado sin columnas temporales no se presenta como 24 horas verificadas.
7. Los datos sintéticos se propagan y no habilitan la siguiente fase.
8. El resultado anterior se conserva y queda marcado como desactualizado si cambian entradas.
9. El resultado formal contiene lote, origen, cobertura, factores, conteos, proyección, distribución, advertencias y versión.
10. La salida se guarda como tpda_phase1_result, no como tpda_result; no existe consumo por Pesaje o ESAL en este cierre.

## 2. Fuente única de verdad

La pantalla survey_tpda.py solo:

- recopila y presenta entradas;
- valida campos básicos;
- invoca calculate_tpda_workflow;
- conserva el resultado y su huella;
- muestra y exporta la trazabilidad.

El dominio se distribuye así:

- traffic/tpda.py: expansión temporal única, TPDA por categoría y separación de FDD/FDC;
- traffic/projection.py: proyección exponencial y variantes históricas;
- traffic/tpda_workflow.py: contrato formal, clasificación, selección del método, proyección, distribución, estados e invalidación.

Se verificó por búsqueda y prueba estructural que survey_tpda.py no contiene llamadas a calculate_tpda, project_traffic_exponential o project_traffic_linear, ni la operación 24/duración.

## 3. Flujo definitivo de expansión temporal

### Aforo menor a 24 horas

El operador elige exactamente uno:

1. Uniforme: F_t = 24 / duración.
2. Factor temporal documentado: F_t = f_n = Q24h / Qnh.

El segundo sustituye al primero; nunca se multiplican.

### Aforo de 24 horas

Se usa SIN_EXPANSION_24H. No admite factor horario adicional.

### Aforo de más de 24 horas

Se calcula el promedio diario mediante 24/duración, sin factor horario adicional.

### Cobertura no verificable

Las columnas category_id,count no prueban duración. La UI muestra:

> El archivo o registro fue declarado como aforo de 24 horas, pero su cobertura temporal no puede verificarse automáticamente.

El operador debe confirmarla explícitamente. Se guardan duración declarada, duración verificable, origen de duración, método y factor final.

## 4. Tratamiento definitivo de camiones

- Clase visual inicial: CAMION_NO_CONFIRMADO.
- No se asigna C2 ni ningún número de ejes.
- El conteo general puede calcularse, pero el estado queda BLOQUEADO_POR_CLASIFICACION.
- La reclasificación exige categoría final del catálogo, motivo, revisor, fecha y origen.
- Al reclasificar todos los pendientes y recalcular, el resultado puede alcanzar VALIDO_PARA_CONTINUAR.
- El contrato preserva categoría original y corregida mediante TruckReclassification.

Categorías finales disponibles: MOTO, AUTO, CAMIONETA, MINIBUS, BUS, C2, C3, TRACTOCAMION, ARTICULADO y OTRO_PESADO. El catálogo sigue siendo una simplificación operativa configurable; no se infieren ejes desde YOLO.

## 5. Presentación de f_n y f_e

| Símbolo | Nombre en UI | Función | Fuente/estado |
|---|---|---|---|
| f_n | Factor de expansión temporal | Sustituye 24/duración en aforos parciales | Definido por usuario; exige fuente para aprobar; no oficial Bolivia |
| f_e | Factor de corrección del periodo observado | Convierte TPD del periodo en TPDA | Configurable; 1,0 es identidad; valores distintos exigen fuente |

Cada FactorTrace registra símbolo, nombre, valor, función, fuente, aplicabilidad y estado. Un factor documentado sin fuente bloquea por expansión.

## 6. Proyección y distribución

- Exponencial/compuesta: método principal educativo.
- Lineal B: alternativa académica no oficial.
- Lineal A: código histórico conservado, visible solo como explicación experimental y no seleccionable.

El orden presentado e implementado es:

    Aforo observado
    → expansión temporal
    → TPDA base
    → proyección
    → distribución direccional
    → distribución por carril

FDD y FDC no modifican TPDA base. Se aplican sobre el tránsito proyectado y quedan expuestos separadamente.

## 7. Resultado formal

TPDAWorkflowResult contiene:

- schema_version, calculation_id, batch_id, calculated_at e input_fingerprint;
- source, data_origin, conteos automáticos y corregidos;
- categorías pendientes y reclasificaciones;
- duración declarada/verificada, origen y confirmación;
- método y factor temporal, factor estacional y factor final;
- TPDA base total y por categoría;
- método, tasa, periodo, años base/diseño y proyección;
- FDD, FDC, tránsito direccional y de carril;
- advertencias, supuestos y condición sintética;
- estado metodológico, aptitud y desactualización.

No contiene campos ni transferencias de Pesaje o ESAL.

## 8. Estados y reglas de aprobación

Estados implementados:

- VALIDO_PARA_DEMOSTRACION;
- VALIDO_PARA_CONTINUAR;
- BLOQUEADO_POR_CLASIFICACION;
- BLOQUEADO_POR_EXPANSION;
- BLOQUEADO_POR_DATOS_SINTETICOS;
- BLOQUEADO_POR_CONTEOS;
- DESACTUALIZADO_REQUIERE_RECALCULO.

VALIDO_PARA_CONTINUAR exige:

- conteos no vacíos, finitos y no negativos;
- duración confirmada;
- un único método temporal;
- factores identificados y, cuando no son identidad, con fuente;
- ausencia de camiones pendientes;
- proyección exponencial o Lineal B;
- datos no sintéticos;
- huella vigente.

Los datos sintéticos reconocidos solo alcanzan VALIDO_PARA_DEMOSTRACION.

## 9. Invalidación

La huella incluye conteos, pendientes, cobertura, expansión, factores, clasificación, proyección, tasa, periodo, FDD, FDC, origen y condición sintética. Si cambia cualquiera, result_is_stale devuelve verdadero.

La UI:

- conserva el resultado y su calculation_id;
- muestra DESACTUALIZADO;
- exige pulsar nuevamente “Calcular y evaluar Fase 1”;
- no borra ni reemplaza silenciosamente la trazabilidad anterior.

## 10. Pruebas añadidas

Se añadieron 22 pruebas puras del flujo y 5 pruebas funcionales de Streamlit. Cubren:

- expansión única uniforme y documentada;
- 24 horas sin expansión;
- CSV sin evidencia temporal y confirmación manual;
- UI sin fórmulas locales;
- CAMION pendiente y reclasificación trazable;
- FDD/FDC separados;
- exponencial, Lineal B y exclusión de Lineal A;
- factores sin fuente;
- invalidación;
- datos sintéticos;
- aptitud/no aptitud;
- compatibilidad con conteos revisados;
- contrato completo de trazabilidad.

## 11. Escenarios funcionales de Streamlit

Los cinco escenarios se ejecutaron con streamlit.testing.v1.AppTest:

| Escenario | Resultado |
|---|---|
| 2 h, expansión uniforme | Factor único 12; TPDA de 10 autos = 120 |
| 24 h sin evidencia | Advertencia visible y BLOQUEADO_POR_EXPANSION sin confirmación |
| CAMION | Conservado como pendiente; C2=0; BLOQUEADO_POR_CLASIFICACION |
| Reclasificación completa | Traza registrada; apto después de recalcular |
| Cambio de duración | Resultado anterior conservado y marcado DESACTUALIZADO |

La aplicación inició correctamente en http://localhost:8502 y AppTest no reportó excepciones. El entorno de ejecución no ofreció un navegador gráfico conectado, por lo que no se afirma una inspección visual manual. Esta limitación no se ocultó ni se sustituyó por una afirmación de revisión humana.

## 12. Verificación final

- Pruebas específicas TPDA y flujo: 52 aprobadas, 0 fallidas.
- Escenarios funcionales Streamlit: 5 aprobados, 0 fallidos.
- Suite completa: **120 aprobadas, 0 fallidas** en 14,21 s.
- pip check: **No broken requirements found**.

## 13. Archivos

### Creados

- src/pavement_intelligence/traffic/tpda_workflow.py
- tests/unit/test_tpda_workflow.py
- tests/unit/test_survey_tpda_ui.py
- docs/CIERRE_FASE1_AFORO_TPDA.md

### Modificados

- src/pavement_intelligence/ui/pages/survey_tpda.py

Se conservan las correcciones previas en traffic/tpda.py, traffic/projection.py y tests/unit/test_tpda.py.

## Conclusión

Los bloqueos metodológicos identificados fueron corregidos en dominio, UI y pruebas. El flujo Aforo–TPDA queda auditable, trazable y preparado para diseñar una integración posterior controlada.

**APROBADO PARA CONTINUAR CON PESAJE Y ESAL**

Esta aprobación no constituye una conexión automática ni valida factores locales como oficiales. Pesaje y ESAL deberán respetar en una tarea futura el indicador methodologically_fit_for_next_phase y rechazar cualquier otro estado.
