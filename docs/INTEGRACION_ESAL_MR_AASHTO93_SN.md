# Integración ESAL + MR → AASHTO 93 — SN requerido (Fase 5A)

## Propósito y alcance

La Fase 5A obtiene exclusivamente el número estructural requerido `SN` mediante la
ecuación AASHTO 93 para pavimento flexible. Recibe manualmente un W18 vigente de
Fase 3B y un MR adoptado en Fase 4B. No selecciona materiales, no calcula
coeficientes estructurales o de drenaje y no produce espesores, costos ni una
recomendación constructiva.

> Este cálculo implementa la ecuación AASHTO 93 para obtener un número estructural requerido dentro de un flujo demostrativo.
>
> La validez del resultado depende de la calidad y representatividad de W18, MR, confiabilidad, serviciabilidad y demás parámetros ingresados.
>
> No constituye por sí solo un diseño vial aprobado ni una recomendación constructiva.

## Transferencias manuales

`ESAL5ATransfer` sólo se crea mediante el botón de importación de Fase 5A. Conserva
el identificador del estudio y resultado 3B, huella, ESAL acumulado, periodo y años,
método, estado metodológico, condición sintética, expansión temporal, FDD, FDC,
días de operación, tasas por categoría, fuentes, condiciones y advertencias. Se
bloquea si el resultado 3B está desactualizado, no está habilitado o W18 no es
positivo.

`MR5ATransfer` se crea desde el contrato futuro producido manualmente por 4B y se
contrasta con la revisión 4B vigente. Conserva estudio, revisión y huella, MR,
unidad original, fuente, modo de adopción, responsable, justificación, evidencia,
condición demostrativa y advertencias. Ninguna transferencia escribe claves del
diseño heredado ni dispara un cálculo.

## Contrato, unidades y parámetros

`AASHTO93Input` es inmutable y serializable. Incluye diseño, tramo, transferencias,
W18, MR y unidad original, R, ZR, S0, p0, pt, ΔPSI, periodo, fuentes, responsable,
justificación, advertencias, configuración numérica, versiones y fecha. La unidad
canónica de MR dentro de la ecuación es **psi**. MPa se convierte explícitamente con
`1 MPa = 145.03773773020923 psi`; cualquier otra unidad bloquea el flujo.

La confiabilidad usa el catálogo `AASHTO93-TABLE-2.2-1.0`, atribuido a *AASHTO
Guide for Design of Pavement Structures (1993), Tabla 2.2*: R = 50, 75, 80, 85,
90, 95 y 99 %. Para R mayor que 50 %, ZR es negativo. Un ZR manual exige la fuente
`MANUAL_JUSTIFICADO`, responsable, justificación y signo coherente; una pareja R/ZR
inconsistente con el catálogo se bloquea.

S0 se ingresa explícitamente con fuente y condición. El rango admitido y
documentado para este flujo es 0,30–0,60; dentro de él se encuentra el intervalo
típico local documentado 0,40–0,50. Los valores 0,45, p0=4,2 y pt=2,5 que muestra la
interfaz son ejemplos visibles, editables y quedan incluidos en la huella; no son
parámetros oficiales ni valores ocultos. Se exige `0 < pt < p0 ≤ 5` y se calcula
explícitamente `ΔPSI = p0 - pt`.

## Ecuación y solver

La expresión implementada, coincidente con `docs/aashto93_flexible.md`, es:

```text
log10(W18) = ZR*S0 + 9.36*log10(SN+1) - 0.20
             + log10(ΔPSI/(4.2-1.5)) / (0.40 + 1094/(SN+1)^5.19)
             + 2.32*log10(MR_psi) - 8.07
```

Los coeficientes, texto de la ecuación, fuente, unidad y versión metodológica
participan en el contrato y la huella. La raíz se obtiene por bisección acotada.
El usuario declara SN mínimo, SN máximo, tolerancia de residuo e iteraciones
máximas. Se verifica dominio finito, intervalo positivo, cambio de signo, residuo
y convergencia real. El intervalo demostrativo visible es 0,01–15, la tolerancia
visible es `1e-4` y el límite visible es 100 iteraciones; todos son editables y
trazables. No converger o no encerrar una raíz bloquea el resultado.

Como control posterior a la convergencia, el solver calcula un margen relativo
configurable: `(SN_max - SN_min) × porcentaje_margen`. El valor demostrativo visible
es 0,02 (2 %) y el rango admitido es 0–0,25. Si el SN queda dentro del margen se
conserva `SN_CERCANO_LIMITE_INFERIOR` o `SN_CERCANO_LIMITE_SUPERIOR` en el resultado
y JSON, y se recomienda ampliar el intervalo y recalcular. Es únicamente una
advertencia: no altera la raíz, el residuo, las iteraciones ni la convergencia.

## Ejemplo y sensibilidad

Caso documentado: W18=5.000.000, MR=10.000 psi, R=90 %, ZR=-1,282, S0=0,45,
p0=4,2 y pt=2,5. La solución es aproximadamente `SN=4,0421`; al sustituirla, el
lado derecho coincide con `log10(W18)` dentro de la tolerancia.

- Al aumentar W18 y mantener lo demás constante, aumenta SN.
- Al aumentar MR, disminuye SN.
- Al pasar de R=90 % a R=95 % (ZR más negativo), aumenta SN.
- Para este caso, aumentar ΔPSI reduce el SN requerido conforme al término de
  serviciabilidad de la ecuación; disminuir ΔPSI lo aumenta. Esto es una
  sensibilidad matemática, no una recomendación para adoptar valores.

Se prueban además W18=1, valores grandes, MR extremos, R=50/95, valores no finitos,
serviciabilidad inválida, S0 nulo o fuera de rango, intervalos inválidos o sin raíz,
tolerancia cero e iteraciones insuficientes.

## Bloqueos, huellas e históricos

Se bloquea por transferencias ausentes o desactualizadas, W18/MR no positivos o no
finitos, unidad desconocida, R/ZR inconsistente, S0 inválido, p0≤pt, ΔPSI
incoherente, datos demostrativos no reconocidos o solver sin convergencia. Una
entrada inválida nunca produce un resultado aparentemente válido.

La huella cubre transferencias y sus huellas, W18, MR/unidad, R/ZR/catálogo, S0,
p0, pt, ecuación y coeficientes mediante la versión metodológica, solver,
responsable, justificación, advertencias y fecha contractual. Cualquier cambio
marca el resultado como desactualizado. Al recalcular, el resultado anterior se
añade a `aashto93_phase5a_history`; no se sobrescribe silenciosamente.

## Limitaciones y relación futura con Fase 5B

Las fuentes locales confirman la forma de la ecuación y la Tabla 2.2 declarada,
pero la selección normativa de parámetros, calibración local, representatividad
de W18/MR y aprobación profesional siguen pendientes. La futura Fase 5B podrá
consumir un SN vigente mediante otra transferencia explícita para diseñar capas;
esa transferencia, los materiales, drenaje, coeficientes y espesores quedan fuera
de la Fase 5A.
