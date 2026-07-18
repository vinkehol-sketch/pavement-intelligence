# Integración controlada Pesaje → ESAL

Fecha de cierre: 17 de julio de 2026  
Alcance: Fase 2 de Pesaje → transferencia manual → cálculo formal de ESAL.  
No incluye integración con Suelos, Diseño AASHTO 93 ni Reportes.

## 1. Auditoría inicial

Antes de esta integración, la pantalla `esal_calculator.py` reconstruía el cálculo desde claves heredadas de tránsito y aplicaba factores equivalentes por categoría definidos en la interfaz. El dominio existente `traffic/esal_calculator.py` calculaba `TPDA × 365 × FDD × FDC × FEC × GF`; `traffic/factors.py` ya contenía las funciones de cuarta potencia para grupos simple, tándem y trídem. La pantalla, por tanto, mezclaba captura, supuestos y cálculo, y no era compatible con el contrato formal `weighing_phase2_result`.

Las claves antiguas identificadas fueron `tpda_result`, `traffic_counts_corrected` y `esal_result`. `pavement_design.py` y `reports.py` todavía consumen exclusivamente `esal_result`. No se modificaron: el resultado nuevo se publica solamente en `esal_phase3_result`, por lo cual no existe conexión prematura con Diseño.

## 2. Contrato Pesaje → ESAL

La transferencia se inicia exclusivamente desde un `weighing_phase2_result` vigente. La interfaz de Pesaje muestra el origen, categorías, configuraciones, observaciones, cargas, unidad, condición sintética, advertencias y aptitud. Solo después de confirmación y pulsación de **Usar pesaje validado en ESAL** crea el contrato inmutable `ESALInputFromWeighing`.

El contrato conserva identificadores y huellas de Pesaje y TPDA, periodo, crecimiento, método de proyección, año base, FDD, FDC, tránsito base y proyectado por categoría, tránsito de carril, observaciones completas, configuraciones y cargas en kN, fuente, atípicos, tolerancia, supuestos, advertencias, revisor y marca sintética. No transfiere un factor camión agregado.

Se rechazan resultados de Pesaje bloqueados, desactualizados, con muestra vacía, unidad distinta de kN o trazabilidad incompleta. Un resultado sintético requiere selección explícita del modo demostrativo.

## 3. Claves de sesión y protección

| Clave | Uso |
|---|---|
| `esal_input_from_weighing` | Contrato manual e inmutable de entrada |
| `esal_phase3_input` | Configuración exacta del cálculo ejecutado |
| `esal_phase3_result` | Resultado formal nuevo |
| `esal_history` | Estado previo conservado al reemplazar una transferencia |
| `esal_result_history` | Resultados formales anteriores conservados al recalcular |

Si existe estado ESAL, el operador debe conservar, reemplazar preservando histórico o cancelar. No hay sobrescritura silenciosa. La clave heredada `esal_result` no recibe el resultado nuevo, se archiva como evidencia y permanece intacta para que esta implementación no altere el estado que aún observa Diseño.

## 4. Método de equivalencia

Se reutilizan sin duplicarlas en Streamlit las funciones existentes:

- simple/simple dual: `(carga / 80 kN)^4`;
- tándem: `(carga / 142 kN)^4`;
- trídem: `(carga / 213 kN)^4`.

La convención interna del método es un eje simple de ruedas duales de **80 kN**, presentado como aproximadamente **18 kip**. No se intercambian durante el cálculo 80 kN, 80,07 kN, 8,16 t ni 18.000 lb. Los factores son adimensionales y las cargas llegan normalizadas en kN desde Pesaje.

Cada factor registra observación, categoría, posición y tipo de grupo, carga aplicada, carga de referencia, método, versión, tipo de pavimento, procedencia, inclusión y motivo de exclusión. El factor por vehículo es la suma de sus factores de grupo.

## 5. Factor camión y ESAL

El factor camión de una categoría es la media reproducible de los factores por vehículo incluidos de esa categoría. Se registran cantidad observada, ESAL observado total, media, desviación estándar poblacional, mínimo, máximo, fuente, tratamiento de atípicos y condición sintética. No se utilizan tablas ocultas por categoría ni clases inferidas desde YOLO.

Para cada categoría y año:

`ESAL anual = TPDA base × multiplicador de crecimiento × 365 × FDD × FDC × factor camión observado`

El multiplicador respeta el método validado en TPDA: exponencial `(1 + r)^año` o lineal B `1 + r × año`. Se suman los años del periodo para obtener el ESAL acumulado. Se conservan las categorías livianas con factor estructural cero y una advertencia; no se eliminan de las estadísticas.

Caso numérico independiente de prueba: C2 = 10 veh/día, factor camión = 1, FDD = 0,5, FDC = 1, crecimiento = 0 % y periodo = 5 años. Resultado: 1.825 ESAL iniciales/año y 9.125 ESAL acumulados.

## 6. Atípicos, sintéticos e invalidación

Los atípicos permanecen incluidos por defecto. Solo pueden excluirse identificadores previamente marcados por Pesaje, mediante selección y motivo explícitos; el detalle original permanece en el resultado. La selección, tratamiento y motivo participan en la huella.

La condición sintética se hereda desde la cadena validada. Sin reconocimiento, el cálculo queda `BLOQUEADO_POR_DATOS_SINTETICOS`; reconocido, solo puede producir `VALIDO_PARA_DEMOSTRACION` y `APTO_SOLO_DEMOSTRACION`. Una cadena real completa puede producir `VALIDO_PARA_CONTINUAR` y el indicador preparatorio `APTO_PARA_DISENO`.

El resultado se considera desactualizado si cambia la huella o el identificador de Pesaje, la selección de observaciones, atípicos, supuestos, reconocimiento sintético, método, tipo de pavimento o eje estándar. El anterior se conserva y no se publica hacia Diseño.

## 7. Modelo formal de resultado

`ESALWorkflowResult` es inmutable, serializable e independiente de Streamlit. Incluye identificadores y huellas de origen, método y eje estándar, factores por eje y vehículo, factores camión, tránsito y ESAL por categoría, progresión anual, ESAL acumulado/W18, atípicos, supuestos, advertencias, condición sintética, estado metodológico, aptitud futura, revisor y vigencia.

Estados implementados: válido para continuar, válido para demostración, bloqueado por Pesaje, configuración de ejes, factores equivalentes, tránsito, unidades, datos sintéticos o muestra vacía, y desactualizado con recálculo requerido. Indicadores preparados: `APTO_PARA_DISENO`, `APTO_SOLO_DEMOSTRACION` y `NO_APTO_PARA_DISENO`.

## 8. Verificación

Se cubrieron mediante pruebas unitarias, de integración y AppTest: fuente exclusiva formal, transferencia manual/no automática, rechazos y aceptación productiva/demostrativa, protección e históricos, kN, referencias simple/tándem/trídem, factores por vehículo y categoría, ausencia de YOLO, FDD/FDC, periodo, crecimiento, acumulación, livianos, muestra/cargas/configuraciones inválidas, atípicos, propagación sintética, flujo real, huellas e invalidación, almacenamiento formal, aislamiento de Diseño y navegación Streamlit.

Escenarios AppTest ejecutados:

1. Pesaje real válido: transferencia manual y resultado `APTO_PARA_DISENO`.
2. Sintético reconocido/no reconocido: reglas verificadas en dominio.
3. Pesaje desactualizado y firma distinta: transferencia bloqueada.
4. Resultado existente: conservación o archivo antes de reemplazar.
5. Cambio de Pesaje/método/eje: huella distinta y recálculo obligatorio.
6. Caso numérico pequeño: 1.825/año y 9.125 acumulados.

Resultado de la suite completa:

```text
174 passed in 23.30s
```

Resultado de dependencias:

```text
No broken requirements found.
```

## 9. Archivos modificados

- `src/pavement_intelligence/weighing/workflow.py`
- `src/pavement_intelligence/esal/workflow.py`
- `src/pavement_intelligence/ui/pages/weighing.py`
- `src/pavement_intelligence/ui/pages/esal_calculator.py`
- `tests/unit/test_weighing_workflow.py`
- `tests/unit/test_weighing_ui.py`
- `tests/unit/test_esal_workflow.py`
- `docs/INTEGRACION_PESAJE_ESAL.md`

## 10. Conclusión

**APROBADO PARA AUDITAR FASE 3 DE ESAL**

Esta conclusión habilita una auditoría independiente del cálculo formal. No declara la Fase 3 lista para Diseño ni autoriza publicar W18 en Suelos, Diseño AASHTO 93 o Reportes.
