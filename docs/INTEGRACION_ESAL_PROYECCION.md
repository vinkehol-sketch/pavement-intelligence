# Integración ESAL observado → proyección temporal (Fase 3B)

## Alcance

La Fase 3B convierte un lote ESAL **ya calculado y validado en 3A** en una serie
temporal auditable. Es una herramienta demostrativa/académica separada. No
modifica la equivalencia de ejes de 3A, no recalcula TPDA o Pesaje y no crea ni
transfiere un `esal_design` a Pavimentos, Geotecnia, AASHTO 93 o Reportes.

Método visible: **Proyección temporal de ESAL — uso demostrativo/académico**.

> Los factores temporales, FDD, FDC, días de operación y tasas de crecimiento
> son calculados o ingresados bajo supuestos declarados; este resultado no es un
> ESAL oficial de diseño.

## Contrato manual 3A → 3B

`ESALProjectionTransfer` es inmutable y serializable. Solo se crea por una
acción manual sobre un resultado 3A vigente, válido, no vacío y con identidad y
huella verificables. Conserva:

- identificador, huella, fecha, método y condición metodológica 3A;
- ESAL observado del lote, vehículos válidos y categorías;
- desglose por categoría, fuente de carga y contribución individual;
- rechazados, pendientes, advertencias y referencias temporales de 3A.

Los rechazados y pendientes nunca entran al cálculo. Un resultado bloqueado,
desactualizado o vacío no se puede transferir. Reemplazar una transferencia o
un resultado conserva el anterior en `esal_projection_history`.

## Base temporal

`TemporalObservationBase` registra inicio/fin ISO opcionales, horas y días
observados, factor a día, origen del factor, fuente, responsable, justificación
y notas. Los orígenes permitidos son:

- calculado desde duración: `24 / horas_observadas`;
- ingresado manualmente;
- referencia TPDA;
- demostrativo con duración desconocida.

Así, 24 h produce factor 1; 12 h, factor 2; y 48 h, factor 0,5. Fechas
incoherentes, duración no positiva o discrepancias entre fechas y horas se
bloquean. Una duración desconocida puede conservarse para exploración, pero el
estado queda `BLOQUEADO_POR_DURACION_DESCONOCIDA` y no produce un ESAL diario
definitivo.

## Magnitudes y unidades temporales

Las salidas se mantienen separadas:

1. ESAL del lote observado `[ESAL/lote]`;
2. ESAL medio por vehículo `[ESAL/vehículo]`;
3. ESAL diario base `[ESAL/día]`;
4. ESAL diario distribuido `[ESAL/día de carril]`;
5. ESAL anual base `[ESAL/año]`;
6. ESAL anual proyectado por año `[ESAL/año]`;
7. ESAL acumulado del período `[ESAL/período]`.

El factor direccional (FDD) y el factor de distribución por carril (FDC) deben
estar en `(0, 1]` y se aplican una sola vez. Los días de operación son un entero
entre 1 y 366; el valor inicial visible es 365, pero queda registrado como dato
de entrada y en la huella.

## Crecimiento y convención anual

Cada categoría observada exige una tasa anual explícita, su fuente y condición.
No existe relleno silencioso desde una tasa global. Se aceptan tasas positivas,
cero y negativas mayores que −100 %. Se bloquean −100 %, valores menores y no
finitos.

Para categoría `c`, año índice `n` y tasa decimal `r_c`:

```text
ESAL_anual(c,n) = ESAL_anual_base(c) × (1 + r_c)^n
```

`n=0` es el año base; `n=1`, el segundo año de la serie. El acumulado es la suma
explícita de los años y se contrasta numéricamente con la forma cerrada de la
serie geométrica, incluyendo el caso especial `r=0`.

## Consistencia, vigencia y desgloses

El resultado incluye series global y por categoría, además del acumulado por
fuente de carga. Los totales por año, categoría y fuente deben coincidir dentro
de tolerancia numérica estricta; una discrepancia interrumpe el cálculo. Los
porcentajes se calculan sobre el acumulado total.

La huella SHA-256 cubre el contrato 3A completo y todos los parámetros 3B. El
resultado se marca visualmente como desactualizado si cambia la huella/identidad
3A o cualquier entrada temporal, distributiva, anual o de crecimiento.

## Caso independiente de control

Con 10 vehículos C2 que aportan 1 ESAL cada uno en 24 h, FDD 0,5, FDC 1, 365
días, cinco años y crecimiento cero:

```text
ESAL lote observado     = 10
ESAL diario base        = 10
ESAL diario distribuido = 10 × 0,5 × 1 = 5
ESAL anual base         = 5 × 365 = 1.825
ESAL acumulado          = 1.825 × 5 = 9.125
```

Este caso está automatizado en `tests/unit/test_esal_projection_workflow.py`.
