# Auditoría documental ESAL - material académico UCB

Fecha de revisión: 17 de julio de 2026  
Carpeta auditada: `docs/Nueva carpeta`  
Alcance: revisión documental y comparación diagnóstica. No se modificó el motor matemático, TPDA, Pesaje, ESAL ni sus pruebas.

## 1. Dictamen ejecutivo

Las hojas `EE` y `EE1` contienen cuatro familias de expresiones de potencia compatibles con un ejercicio de ejes equivalentes para pavimento flexible. Sin embargo:

- las expresiones generalizadas con una variable `W` no aparecen literalmente en los libros; las celdas sustituyen `W` por cargas fijas;
- ninguna celda, comentario, propiedad o texto visible de las hojas examinadas identifica una fuente bibliográfica para los denominadores o exponentes;
- no aparecen `SN = 3` ni `pt = 2.5` en las planillas;
- existen distintas cargas para una misma familia, referencias externas rotas, fórmulas de rango dudosas y errores de clasificación/porcentaje;
- los resultados difieren materialmente del motor vigente de cuarta potencia.

Por ello, las cuatro fórmulas quedan clasificadas como **`REQUIERE_FUENTE_PRIMARIA`** para uso de dominio. Sus casos concretos sí son útiles como **`APTO_SOLO_COMO_CASO_DE_PRUEBA`**. No existe evidencia suficiente para sustituir el método implementado.

## 2. Archivos examinados

Se inspeccionaron siete libros `.xlsx` y el enunciado `SEGUNDO PARCIAL TRAFICO 2026.docx`. Como control de identidad se calcularon sus SHA-256; los archivos clave son:

| Archivo | SHA-256 |
|---|---|
| `CALCULO TRAFICO  22-4-26.xlsx` | `F3E9000CAEF48E3DED939D58057624100E74606D4176E03E3A066A1B29341679` |
| `CALCULO DE TRAFICO EXAMEN FINAL UCB 251.xlsx` | `71A53CC884BC7008340E7BBE704FDAFF0F9DF601A3F000C29FC498526A5BFB42` |
| `trafico cato total 2025.xlsx` | `0384FC1C7172460163DDD3B5F2083E278D19536505FE36A0203FCE3CB91A4C32` |
| `trafico cato total 2025-2.xlsx` | `4E541361D9D276BF803EF5D98983F472DCAEC19750E68EE86B9D1F55402D402E` |
| `SEGUNDO PARCIAL TRAFICO 2026.docx` | `5B5372C8A56B00402491EA94DA9CB0D98F66CD67A1772FD6039280573E03A555` |

Los tres libros `CALCULO DE TRAFICO EXAMEN FINAL UCB 25.xlsx`, `CALCULO DE TRAFICO ejemplo UCB 2026.xlsx` y `CALCULO DE TRAFICO EXAMEN FINAL UCB 251.xlsx` repiten la misma estructura central de `EE1`.

## 3. Celdas y fórmulas originales

### 3.1 Hoja `EE`

| Libro | Eje interpretado | Celda | Fórmula original |
|---|---|---:|---|
| `trafico cato total 2025.xlsx` | sencillo, 2 ruedas | `I4` | `=(7/7.77)^4.32` |
| mismo | sencillo, 4 ruedas | `I9` | `=(11/8.17)^4.32` |
| mismo | tándem | `I13` | `=(17/15.08)^4.14` |
| mismo | trídem, interpretado por el denominador | `I16` | `=(22/22.98)^4.22` |
| `trafico cato total 2025-2.xlsx` | mismos cuatro casos | `I4`, `I9`, `I13`, `I16` | idénticas a las anteriores |
| `CALCULO TRAFICO  22-4-26.xlsx` | mismos cuatro casos | `AA4`, `AA9`, `AA14`, `AA18` | idénticas, respectivamente |

Advertencia: en `trafico cato total 2025[-2].xlsx`, `M15:N16` etiqueta 17 t como “tándem de 6 llantas” y 22 t como “tándem de 10 llantas…”, aunque la fórmula de 22,98 corresponde en la interpretación académica suministrada a un trídem. Esta contradicción impide usar la etiqueta como definición de dominio.

### 3.2 Hoja `EE1`

En los cuatro libros que contienen `EE1` se repite:

| Libros | Eje interpretado | Celda | Fórmula original |
|---|---|---:|---|
| `CALCULO TRAFICO  22-4-26.xlsx` y los tres `CALCULO DE TRAFICO...` | sencillo, 2 ruedas | `AL4` | `=(7.7/7.77)^4.32` |
| mismos | sencillo, 4 ruedas | `AL9` | `=(16/8.17)^4.32` |
| mismos | tándem | `AL14` | `=(18/15.08)^4.14` |
| mismos | trídem | `AL18` | `=(25/22.98)^4.22` |

Además, `I8:I31` usa una expresión particular, por ejemplo `I8`:

`=(POWER((0.2*5.5)/8.17,4.32))*TPDA!F7`

Esta no es una definición general del factor: combina una carga implícita `0.2 × 5.5 = 1.1` con un TPDA anual. No debe confundirse con la ecuación base. Hay también referencias externas como `=[8]CONSOLIDADO!...` y fórmulas matriciales dudosas como `C7 = TPDA!C6*'EE1'!$C$4:$D$4*...`, que reducen su reproducibilidad fuera del equipo de origen.

## 4. Significado de `W`, configuración y unidades

El enunciado académico declara explícitamente pesos en `tn` y la tabla de `EE!M11:N16` titula los valores como toneladas. Por consistencia interna, `W` se interpreta como **toneladas-fuerza del eje o grupo**, no como kN ni como peso bruto vehicular indiscriminado:

- sencillo de 2 ruedas: carga total de un eje individual con dos neumáticos;
- sencillo de 4 ruedas: carga total de un eje individual con ruedas duales;
- tándem: carga total del grupo de dos ejes;
- trídem: carga total del grupo de tres ejes.

Esta interpretación es necesaria para que los denominadores funcionen como cargas de referencia. Aun así, no está formalmente definida en una nota metodológica dentro de las hojas y la etiqueta incorrecta del caso de 22 t introduce ambigüedad. Clasificación: **`REQUIERE_FUENTE_PRIMARIA`**.

## 5. Pavimento, `SN` y `pt`

El párrafo 51 del documento `SEGUNDO PARCIAL TRAFICO 2026.docx` dice que el tramo La Padcaya-La Mamora tendrá “asfaltado de pavimento flexible”. Por lo tanto, el caso académico pretende pavimento flexible. Clasificación del caso: **`APTO_SOLO_COMO_CASO_DE_PRUEBA`**.

No se encontró `SN`, número estructural, serviciabilidad ni `pt` en ninguna celda examinada de `EE`/`EE1`. En consecuencia, **no puede verificarse documentalmente** que los coeficientes se hayan ajustado para `SN = 3` y `pt = 2.5`.

Las fuentes técnicas oficiales sí confirman que los factores AASHTO no son universalmente independientes de la estructura: la guía de datos de tráfico de FHWA indica que las tablas de equivalencia proceden del Apéndice D de AASHTO y que la ecuación considera carga aplicada, pendiente, número estructural y serviciabilidad. FHWA también documenta variaciones de factores con `SN` y distingue pavimento flexible de rígido. Referencias: [FHWA Traffic Data Computation Method Pocket Guide](https://www.fhwa.dot.gov/policyinformation/pubs/pl18027_traffic_data_pocket_guide.pdf), [FHWA Traffic Monitoring Guide - pavement data](https://www.fhwa.dot.gov/policyinformation/tmguide/tmg_2013/traffic-data-pavement.cfm) y [FHWA NHI-05-037, capítulo 3](https://www.fhwa.dot.gov/engineering/geotech/pubs/05037/03b.cfm).

La dependencia específica `SN = 3`, `pt = 2.5` de estas cuatro regresiones queda como **`REQUIERE_FUENTE_PRIMARIA`**. No es metodológicamente correcto reconstruirla por semejanza.

## 6. Naturaleza metodológica de las ecuaciones

La forma `carga/referencia` elevada a exponentes 4,14-4,32 es una aproximación de potencia. Las planillas no contienen las ecuaciones completas de factores AASHTO, tablas de equivalencia, procedimiento de ajuste, residuos, intervalo de validez ni referencia de edición/página. Por ello:

- no se pueden presentar como ecuaciones AASHTO originales;
- es plausible que sean regresiones académicas o aproximaciones de tablas para una combinación fija de parámetros, pero eso es una inferencia, no un hecho probado;
- tampoco puede atribuirse el ajuste al docente sin metadatos o explicación explícita.

Clasificación: **`REQUIERE_FUENTE_PRIMARIA`** para producción y **`APTO_SOLO_COMO_CASO_DE_PRUEBA`** para reproducir los ejercicios.

## 7. Rango de cargas observado

Las planillas no definen un rango de validez continuo; únicamente evalúan puntos discretos:

| Tipo | Valores explícitos observados de `W` |
|---|---|
| sencillo, 2 ruedas | 7 y 7,7 t |
| sencillo, 4 ruedas | 1,1 t en `I8:I31`, 11 y 16 t |
| tándem | 17 y 18 t |
| trídem | 22 y 25 t |

El documento del parcial declara 7 t para livianos, 11 t para medios, 21 t para pesados y 25 t para muy pesados. El valor de 21 t no coincide con los 17/18 t usados en las celdas tándem. No hay base para extrapolar las regresiones fuera de esos puntos: **`REQUIERE_FUENTE_PRIMARIA`**.

## 8. Comparación con el motor vigente

El motor actual recibe kN y usa:

- simple: `(P/80)^4`;
- tándem: `(P/142)^4`;
- trídem: `(P/213)^4`.

Para la comparación se convirtió cada tonelada-fuerza mediante `1 tf = 9,80665 kN`. Los valores siguientes se muestran sin el redondeo interno a cuatro decimales, para exponer la diferencia matemática. `Δ%` es `(académico - actual) / actual`.

### Sencillo de 2 ruedas

| W (t) | Académico | Actual | Δ% |
|---:|---:|---:|---:|
| 5 | 0,148913 | 0,141125 | +5,52 % |
| 7 | 0,637096 | 0,542144 | +17,51 % |
| 7,7 | 0,961659 | 0,793754 | +21,15 % |
| 10 | 2,974276 | 2,257994 | +31,72 % |
| 12 | 6,537989 | 4,682176 | +39,64 % |

### Sencillo de 4 ruedas

| W (t) | Académico | Actual | Δ% |
|---:|---:|---:|---:|
| 5 | 0,119881 | 0,141125 | -15,05 % |
| 8,17 | 1,000000 | 1,006030 | -0,60 % |
| 11 | 3,614241 | 3,305929 | +9,33 % |
| 14 | 10,244100 | 8,674309 | +18,10 % |
| 16 | 18,238917 | 14,797988 | +23,25 % |

### Tándem

| W (t) | Académico | Actual | Δ% |
|---:|---:|---:|---:|
| 10 | 0,182565 | 0,227473 | -19,74 % |
| 14 | 0,735171 | 0,873859 | -15,87 % |
| 15,08 | 1,000000 | 1,176345 | -14,99 % |
| 18 | 2,080878 | 2,387918 | -12,86 % |
| 22 | 4,775824 | 5,328685 | -10,38 % |

### Trídem

| W (t) | Académico | Actual | Δ% |
|---:|---:|---:|---:|
| 15 | 0,165275 | 0,227473 | -27,34 % |
| 20 | 0,556480 | 0,718926 | -22,60 % |
| 22,98 | 1,000000 | 1,253038 | -20,19 % |
| 25 | 1,426953 | 1,755191 | -18,70 % |
| 30 | 3,080027 | 3,639564 | -15,37 % |

Conclusión: **no coinciden**. La diferencia no es solo conversión de unidades: cambian exponentes, denominadores y la distinción entre eje sencillo de dos y cuatro ruedas. Esto es una discrepancia metodológica documentada, no un error demostrado del motor vigente. No se recomienda cambiarlo sin la fuente primaria y una decisión explícita sobre `SN`, `pt`, pavimento y rango: **`NO_RECOMENDADO`** cambiar ahora.

## 9. Clasificación T1-T12

La referencia común de `EE1!A37:Q40` define:

- T1 automóviles/vagonetas/jeep; T2 camionetas hasta 2 t; T3 minibuses;
- T4 microbuses de dos ejes; T5 buses medianos de dos ejes; T6 buses grandes;
- T7 camiones medianos de dos ejes; T8 camiones grandes de dos ejes;
- T9 camiones grandes de tres ejes; T10 semirremolques; T11 remolques; T12 otros.

En `EE!A34:J37` aparece un error: T10 se repite para “Camiones Remolque”, omitiendo T11. También varía T9 entre “hasta 10 Ton” y “hasta 15 Ton”. `EE1` asigna un único factor de grupo a categorías completas, sin demostrar la configuración y carga de cada vehículo. Esto contradice el enfoque trazable de Pesaje, que calcula desde ejes medidos.

Clasificación: **`APTO_SOLO_PARA_DEMOSTRACION`** como catálogo visual y **`NO_RECOMENDADO`** como sustituto de configuraciones/cargas medidas. Requiere una fuente primaria si se desea institucionalizar.

## 10. Cargas 7, 11, 18 y 25 toneladas y caso La Padcaya-La Mamora

El parcial declara 7, 11, 21 y 25 t como pesos fijados después de pesajes para “livianos, medios, pesados y muy pesados”. La hoja `EE1` usa 7,7, 16, 18 y 25 t; por tanto, solo 25 t coincide y 18 t no es el valor “pesados” del enunciado. Las planillas no aportan registros de balanza, identificadores, muestra, estadística ni relación vehículo-ejes.

El caso La Padcaya-La Mamora es un enunciado docente para pavimento flexible y añade tráfico de desarrollo de 8,5 % e inducido de 3,5 %. No contiene referencia de estación oficial, fecha de aforo verificable, fuente normativa o datos primarios de pesaje. Clasificación completa: **`APTO_SOLO_COMO_CASO_DE_PRUEBA`**. Los pesos no deben tratarse como límites oficiales ni como factores de Bolivia.

## 11. Nocturnidad, estacionalidad y crecimiento

### Nocturnidad

`trafico cato total 2025[-2].xlsx`, hoja `Factor nocturnidad`, calcula en `C2:C25` la fracción horaria `Bfila/$B$26`, con total en `B26 = SUM(B2:B25)`. Eso describe una distribución horaria completa de 24 horas; no define por sí solo un factor para expandir un aforo parcial. `FACTOR NOCTURNIDAD.xlsx` presenta dos series horarias sin fórmulas ni fuente.

Clasificación: **`APTO_SOLO_COMO_CASO_DE_PRUEBA`** para comprobar porcentajes horarios; **`NO_RECOMENDADO`** como factor productivo sin ventana observada, periodo base y fuente.

### Estacionalidad

Las hojas calculan `fe = promedio mensual / volumen del mes`; por ejemplo, `trafico cato total 2025-2.xlsx!C9 = $B$15/B9`, con `B15 = B14/12`. En `CALCULO DE TRAFICO EXAMEN FINAL UCB 251.xlsx`, `factor estacional!E5:E6` afirma que, al no indicarse el mes, se usa diciembre y `fe = 0,90`. Esa selección no es reproducible a partir del enunciado y los volúmenes no tienen fuente.

Clasificación de la relación media/mes: **`APTO_SOLO_COMO_CASO_DE_PRUEBA`**. Clasificación de `0,90` y de la selección de diciembre: **`APTO_SOLO_PARA_DEMOSTRACION`** y **`REQUIERE_FUENTE_PRIMARIA`** para producción.

### Tasa histórica

`CALCULO DE TRAFICO EXAMEN FINAL UCB 251.xlsx!historicos!F10` usa `=(((B11/B2)^(1/9)-1))` para 550 (2015) y 1220 (2024), es decir, una CAGR aproximada de 9,25 %. Luego `G15` suma 3,2 % de desarrollo y 5,2 % inducido, alcanzando aproximadamente 17,65 %. En `trafico cato total 2025.xlsx!tasa de crecimiento!H5` se repite CAGR con 150 y 570, y `K11` suma además 3,5 %, 5,9 % y 2,5 %.

La CAGR entre extremos es matemáticamente reproducible, pero las series fluctúan y la suma directa de tasas de naturalezas distintas no viene acompañada de metodología ni fuente. Clasificación: CAGR **`APTO_SOLO_COMO_CASO_DE_PRUEBA`**; tasas adicionales y tasa total **`REQUIERE_FUENTE_PRIMARIA`**.

## 12. Matriz final de decisiones

| Hallazgo | Clasificación |
|---|---|
| Fórmula respaldada para incorporación inmediata al dominio | Ninguna (`APTO_COMO_FORMULA_DE_DOMINIO` no asignado) |
| Cuatro expresiones de potencia como método productivo | `REQUIERE_FUENTE_PRIMARIA` |
| Celdas concretas de `EE`/`EE1` | `APTO_SOLO_COMO_CASO_DE_PRUEBA` |
| Cambio inmediato del motor actual | `NO_RECOMENDADO` |
| Catálogo T1-T12 como apoyo visual | `APTO_SOLO_PARA_DEMOSTRACION` |
| T1-T12 como fuente de ejes/factores | `NO_RECOMENDADO` |
| Pesos 7/11/18/25 como límites oficiales | `REQUIERE_FUENTE_PRIMARIA` |
| Caso La Padcaya-La Mamora | `APTO_SOLO_COMO_CASO_DE_PRUEBA` |
| Distribuciones horarias y estacionales | `APTO_SOLO_COMO_CASO_DE_PRUEBA` |
| Factor estacional 0,90 asumido | `APTO_SOLO_PARA_DEMOSTRACION` |
| CAGR entre extremos | `APTO_SOLO_COMO_CASO_DE_PRUEBA` |
| Adición directa de tasas históricas/desarrollo/inducido | `REQUIERE_FUENTE_PRIMARIA` |

## 13. Recomendación

Mantener sin cambios el motor vigente durante el cierre Pesaje → ESAL. Antes de evaluar una variante metodológica se requiere, como mínimo:

1. referencia primaria con edición, sección, tabla o ecuación;
2. confirmación de unidad y definición de carga por eje/grupo;
3. pavimento aplicable y valores explícitos de `SN` y `pt`;
4. rango de calibración y error de la regresión;
5. pruebas independientes frente a las tablas originales;
6. decisión arquitectónica para versionar métodos sin reemplazar resultados previos.

No se presenta ningún dato de estas planillas como oficial de Bolivia.
