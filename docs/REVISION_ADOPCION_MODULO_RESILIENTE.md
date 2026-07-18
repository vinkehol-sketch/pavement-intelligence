# Revisión y adopción controlada del módulo resiliente — Fase 4B

## Propósito y alcance

La Fase 4B consume un resultado vigente de Fase 4A, compara todas las
correlaciones cuyo intervalo contiene el CBR de diseño, cuantifica la
sensibilidad metodológica y exige una adopción humana documentada. No modifica
las correlaciones de 4A, no ejecuta AASHTO 93 y no calcula número estructural ni
espesores.

El resultado se denomina **MR adoptado para revisión o demostración**, nunca
“módulo resiliente oficial de diseño”.

## Dependencia de Fase 4A

`ReviewInput` conserva el resultado 4A completo y su huella. Un resultado 4A
desactualizado bloquea la revisión. El CBR, criterio de selección, condición
demostrativa, advertencias y versión del catálogo se propagan sin recalcular el
CBR. Las fórmulas se evalúan mediante el catálogo central de 4A.

## Comparación de correlaciones

Para cada correlación aplicable se conserva identificador, nombre, ecuación,
intervalo, MR canónico en MPa, referencia, carácter y advertencias. No se elige
automáticamente el mayor, menor, promedio ni primera coincidencia.

```text
diferencia absoluta = MR_max − MR_min
diferencia relativa = |MR_max − MR_min| / MR_min × 100
```

Un MR mínimo igual o menor que cero bloquea el indicador.

## Sensibilidad

Bandas iniciales, explícitamente demostrativas y configurables:

- `≤ 10 %`: `BAJA`;
- `> 10 %` y `≤ 30 %`: `MODERADA`;
- `> 30 %`: `ALTA`.

Sensibilidad alta produce una advertencia textual y no habilita ninguna
transferencia sin adopción, responsable y justificación.

## Solapamientos y discontinuidades

Entre CBR 7,2 y 10 coinciden las dos correlaciones lineales. En CBR 20 coinciden
la lineal local y la logarítmica. `analyze_discontinuity()` evalúa 19,99; 20,00
y 20,01, conservando todas las alternativas del límite y comparando los valores
a ambos lados.

Una pequeña variación de CBR puede producir un salto grande por cambiar de
metodología; esto no implica necesariamente una variación física equivalente
del suelo.

## Modos de adopción

### Selección de correlación

Exige una correlación aplicable, responsable, justificación y reconocimiento de
una fuente 4A demostrativa. Conserva todas las alternativas.

### Valor conservador

Se define como el menor MR entre correlaciones aplicables. Es una regla
demostrativa, no normativa, y exige aceptación expresa, responsable y motivo.

### Ensayo directo

Registra valor y unidad, laboratorio, procedimiento, fecha, responsable,
documento y observaciones. Se convierte a MPa canónico y se identifica como
`ENSAYO_DIRECTO`, con confianza metodológica alta, sin presentarlo como
correlación CBR.

### Valor manual justificado

Exige valor positivo, unidad, fuente, responsable y justificación. Se identifica
como `VALOR_MANUAL_VERIFICADO`, condición `ESTIMADO`, y muestra que no corresponde
a un ensayo directo.

## Jerarquía visible de fuentes

```text
ENSAYO_DIRECTO
> VALOR_MANUAL_VERIFICADO
> CORRELACION_EMPIRICA
> DEMOSTRATIVO_SINTETICO
```

La jerarquía orienta la lectura de confianza y evidencia, pero nunca reemplaza
la decisión humana.

## Ejemplos

### CBR 8

```text
Lineal 1500 = 12.000 psi
Lineal 3500 = 28.000 psi
Diferencia = 16.000 psi
Diferencia relativa = 133,333 %
Sensibilidad = ALTA
```

### CBR 10

```text
Lineal 1500 = 15.000 psi
Lineal 3500 = 35.000 psi
Diferencia relativa = 133,333 %
Sensibilidad = ALTA
```

### CBR 20

```text
Lineal 3500 = 70.000 psi
Logarítmica = 4326 × ln(20) + 241 ≈ 13.200,54 psi
Sensibilidad = ALTA
```

En 19,99 domina la correlación lineal local; en 20 aparecen ambas alternativas;
en 20,01 queda la logarítmica. El salto relativo entre ambos lados supera 400 %
con las ecuaciones locales vigentes.

## Contrato, huella e histórico

`ResilientModulusReviewResult` es inmutable y serializable. Conserva estudio y
huella 4A, CBR y criterio, alternativas, diferencias, bandas, sensibilidad,
modo, correlación seleccionada, MR adoptado, fuente, confianza, evidencia,
limitaciones, advertencias, catálogo, responsable, fecha y aprobación.

La huella cambia con el resultado 4A, CBR, catálogo, bandas, modo, selección,
valor manual, ensayo directo, responsable, justificación, unidad y fuente. Un
recálculo archiva el resultado anterior en `geotechnical_phase4b_history` e
invalida `geotechnical_future_transfer`.

## Transferencia futura

`FutureAASHTOTransfer` solo se crea mediante un botón después de una revisión
aprobada y vigente. Conserva MR en MPa, fuente, responsable, justificación,
correlación o ensayo, condición demostrativa, advertencias, fecha, huella y
versión. No se escribe en Diseño, no se calcula SN y no se marca como normativo.

## Limitaciones y pendientes

- Las correlaciones siguen siendo demostrativas y sus fuentes primarias están
  pendientes de confirmación.
- La clasificación de sensibilidad requiere calibración y aprobación regional.
- Un ensayo directo requiere revisión de representatividad y documentación.
- La transferencia hacia AASHTO 93 pertenece a una fase futura independiente.
