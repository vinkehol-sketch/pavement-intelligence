# Diseño demostrativo de capas AASHTO 93 — Fase 5B

## Propósito y alcance

La Fase 5B evalúa propuestas de tres capas a partir de un SN requerido vigente de
Fase 5A. Calcula aportes estructurales y cumplimiento; no selecciona materiales
automáticamente ni constituye diseño normativo, económico o constructivo.

> El diseño por capas presentado es una evaluación demostrativa basada en el número estructural AASHTO 93 y en parámetros seleccionados por el usuario.
>
> Los coeficientes estructurales, drenaje, materiales, espesores mínimos y criterios de redondeo requieren validación técnica, normativa, constructiva y económica.
>
> El resultado no constituye una especificación de construcción ni un diseño vial aprobado.

## Transferencia desde Fase 5A

La transferencia es manual y conserva diseño, resultado y huella 5A, SN requerido,
W18, MR, confiabilidad, serviciabilidad, advertencias, responsable, fecha y versión.
Se bloquean resultados desactualizados, no convergidos o SN no positivo. No se
escriben claves del diseño heredado.

## Capas, fórmula y unidades

El modelo contiene `CARPETA_ASFALTICA`, `BASE` y `SUBBASE`:

```text
SN1 = a1 × D1
SN2 = a2 × m2 × D2
SN3 = a3 × m3 × D3
SN_provisto = SN1 + SN2 + SN3
```

La unidad canónica es la pulgada. La entrada admite `in`, `cm` y `mm`, usando
exactamente 1 in = 2,54 cm = 25,4 mm. La conversión ocurre antes del cálculo sin
redondeo interno. Para la carpeta `m1=1` y no es editable.

## Coeficientes estructurales y drenaje

El catálogo `LOCAL-AASHTO93-DEMO-1.0` consolida únicamente valores ya documentados
en los archivos locales: concreto asfáltico 0,35–0,44, base 0,10–0,14 y subbase
0,08–0,11. Cada entrada señala que requiere validación de fuente primaria. La
selección es explícita; también se admite valor manual con fuente, responsable y
justificación. El nombre del material nunca selecciona el coeficiente.

Para m2 y m3 se admite el rango local documentado 0,40–1,40. Se exigen calidad de
drenaje, tiempo próximo a saturación, fuente y decisión responsable. No existe un
valor normativo automático.

## Espesores mínimos

No se encontró una tabla ABC suficientemente confirmada y universal para fijar
mínimos por W18. Por ello no se inventó un catálogo normativo. El usuario puede
declarar un mínimo manual con unidad y el resultado advierte su incumplimiento.
Debe distinguirse este dato de mínimos metodológicos, constructivos o normativos.

## Modos de diseño

- `EVALUAR_PROPUESTA_MANUAL`: evalúa D1, D2 y D3 explícitos.
- `AJUSTAR_UNA_CAPA`: fija dos capas y obtiene el espesor matemático exacto no
  negativo de la tercera; exige denominador positivo y no redondea.
- `BUSQUEDA_DISCRETA_DEMOSTRATIVA`: recorre límites e incrementos explícitos para
  las tres capas, con máximo de 10.000 combinaciones. Es determinista, no económico
  y no selecciona una solución final.

Las alternativas pueden ordenarse por menor excedente SN, menor espesor total o
menor espesor asfáltico. Son criterios demostrativos, no una definición de “mejor”.

## Redondeo y cumplimiento

El espesor matemático se conserva separado del adoptado. El redondeo hacia arriba
usa un incremento explícito y exige responsable y justificación; después se
recalcula SN. No hay redondeo silencioso.

Con tolerancia configurable `ε`:

- `|SN_provisto − SN_requerido| ≤ ε`: `CUMPLE`;
- diferencia mayor que ε: `CUMPLE_CON_EXCEDENTE`;
- déficit mayor que ε: `NO_CUMPLE`.

El déficit es `max(0, SN_requerido − SN_provisto)` y el excedente es
`max(0, SN_provisto − SN_requerido)`; nunca son positivos simultáneamente.

## Ejemplos independientes

Con a1=0,40, D1=5 in; a2=0,14, m2=1, D2=6 in; a3=0,11, m3=1,
D3=12 in: SN1=2,00, SN2=0,84, SN3=1,32 y SN=4,16. Cumple un requerido
4,00 con excedente 0,16; no cumple un requerido 5,00 con déficit 0,84. Frente a
4,1605 y tolerancia 0,001 se clasifica `CUMPLE`.

Los casos automatizados ajustan exactamente D1, D2 y D3. La misma propuesta
expresada como 5/6/12 in, 12,7/15,24/30,48 cm o 127/152,4/304,8 mm produce el
mismo SN dentro de tolerancia numérica.

## Huellas, históricos y limitaciones

La huella cubre transferencia, capas, espesores/unidades, coeficientes, drenaje,
catálogo, mínimos, tolerancia, modo, capa ajustada, búsqueda, redondeo, responsable,
justificación y versiones. Un cambio deja el resultado desactualizado. Al recalcular
se conserva el anterior en `aashto93_phase5b_history`.

Quedan pendientes la validación normativa de coeficientes y mínimos, calibración
local, constructibilidad, drenaje de proyecto, costos y auditoría profesional. La
fase no cubre pavimento rígido, diseño mecanicista, dosificación ni reportes globales.
