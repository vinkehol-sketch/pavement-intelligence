# Integración CBR → módulo resiliente — Fase 4A

## Propósito y alcance

La Fase 4A registra resultados CBR de subrasante, selecciona explícitamente un
CBR representativo y estima un módulo resiliente mediante una correlación
empírica elegida por el usuario. El resultado es independiente de Tránsito,
Pesaje y ESAL, y no escribe parámetros en Diseño de Pavimentos ni ejecuta la
ecuación AASHTO 93.

> La estimación del módulo resiliente mediante CBR depende de una correlación
> empírica. No sustituye un ensayo directo de módulo resiliente ni constituye
> por sí sola un diseño estructural aprobado.

## Contrato CBR

`CBRRecord` es inmutable y serializable. Conserva identificadores de registro y
estudio, tramo, progresiva, profundidad, tipo y condición de muestra, CBR a 2,5
y 5,0 mm cuando existen, CBR reportado, criterio de selección, compactación,
densidad, humedad, saturación, energía de compactación, fecha, laboratorio o
fuente, responsable, procedimiento declarado, origen, observaciones,
advertencias, validez y versión.

Orígenes admitidos:

- `ENSAYO_LABORATORIO`;
- `ENSAYO_CAMPO`;
- `INGRESO_MANUAL_VERIFICADO`;
- `VALOR_ESTIMADO`;
- `DEMOSTRATIVO_SINTETICO`.

El origen se conserva textualmente. Un valor estimado o sintético nunca se
presenta como ensayo de laboratorio. Si solo existe el CBR final, se acepta con
una advertencia de que no se dispone de curva ni valores individuales.

## Validación y clasificación de anomalías

Se bloquean CBR no finitos, iguales o menores que cero y mayores que 150 %;
profundidades negativas; compactaciones fuera de `(0, 100]`; densidades no
positivas; fechas no ISO; orígenes desconocidos; fuentes o procedimientos
vacíos; identificadores duplicados; y falta de responsable para datos manuales,
estimados o sintéticos. Los valores no se recortan.

Se aceptan con observación la compactación menor a 90 %, la condición no
saturada, la falta de CBR individuales y la discrepancia entre el CBR final y
los valores a 2,5/5,0 mm. Los registros marcados como inválidos se conservan,
pero no participan en el agregado.

Los sintéticos no reconocidos se excluyen. Si no queda ningún registro válido,
el flujo se bloquea.

## Selección del CBR de diseño

- `VALOR_UNICO`: exige exactamente una muestra válida.
- `MINIMO_CONSERVADOR`: usa el menor valor e identifica su registro.
- `PROMEDIO`: exige dos o más muestras; su disponibilidad no implica que sea
  automáticamente representativo para ingeniería.
- `PERCENTIL`: exige declarar un percentil entre 0 y 100.
- `SELECCION_MANUAL_JUSTIFICADA`: exige registro válido, responsable y motivo.

El percentil usa interpolación lineal de rango `p/100 × (n−1)` sobre los valores
ordenados. Para los índices inferior y superior se interpola por la fracción del
rango. Esta convención produce mínimo en P0, mediana interpolada en P50 y máximo
en P100, tanto para muestras pares como impares.

## Catálogo de correlaciones

El catálogo central tiene versión `1.0`. La selección siempre es explícita y no
se permite extrapolación silenciosa.

| ID | Ecuación y salida | Intervalo CBR | Fuente disponible | Condición |
|---|---|---:|---|---|
| `LINEAL_1500_PSI` | `MR [psi] = 1500 × CBR` | 0,01–10 % | `cbr_modulo_resiliente.md`, `assumptions.md` | Empírica demostrativa; fuente primaria pendiente |
| `LINEAL_3500_PSI_LOCAL` | `MR [psi] = 3500 × CBR` | 7,2–20 % | Hojas locales citadas en `cbr_modulo_resiliente.md` | Demostrativa, no normativa |
| `LOG_4326_LOCAL` | `MR [psi] = 4326 × ln(CBR) + 241` | 20–150 % | Planilla local citada en `metodos_pendientes_confirmacion_pavimento.md` | Demostrativa, no normativa; discontinuidad advertida |

Los coeficientes se guardan como metadatos. Cualquier sustitución explícita
participa en la huella y debe ser finita. No se unifican expresiones lineales y
logarítmicas bajo un mismo nombre. No se añadió una expresión potencial porque
no existe una fórmula documentada localmente que permita implementarla sin
inventar datos.

## Unidades

La unidad canónica es MPa. Se admiten conversiones explícitas:

```text
1 MPa = 1000 kPa
1 psi = 0,006894757293168361 MPa
1 ksi = 6,894757293168361 MPa
```

El resultado conserva tanto MPa canónico como la unidad solicitada para
visualización. El módulo resiliente no se identifica como CBR, módulo elástico,
módulo de reacción `k`, resistencia a compresión ni capacidad portante.

## Ejemplos numéricos

- Una muestra CBR 5 con correlación 1500: `MR = 7500 psi = 51,7107 MPa`.
- Muestras 4, 6 y 8: mínimo conservador = 4; promedio = 6; P25 = 5.
- Muestras 1, 3, 5 y 7: P50 = 4 mediante interpolación lineal.
- Selección manual de la muestra CBR 6: resultado 6 únicamente con responsable
  y justificación.
- Los límites 7,2 y 20 son admisibles en la correlación lineal local; valores
  externos se bloquean.
- `1000 kPa ↔ 1 MPa` y aproximadamente `145,0377 psi ↔ 1 MPa`.

## Resultado, huella e histórico

`GeotechnicalResult` conserva CBR de diseño, modo y percentil, registros usados
y excluidos, correlación, ecuación, coeficientes, intervalo, referencia, módulo
canónico y visualizado, origen estimado, advertencias, responsable, estado,
huella y versión.

La huella SHA-256 cubre registros completos, humedad, compactación, fuentes,
responsables, criterio, percentil, correlación, coeficientes, versión de
catálogo, unidad y reconocimiento sintético. Cualquier cambio marca el resultado
anterior como desactualizado. Un recálculo conserva el anterior en
`geotechnical_phase4a_history`.

Existe un contrato `GeotechnicalTransfer` para una integración manual futura,
pero la Fase 4A no lo almacena automáticamente ni lo consume desde AASHTO 93.

## Interfaz y limitaciones

La página permite registrar muestras, cargar un caso sintético claramente
marcado, excluir registros, seleccionar criterio, percentil, correlación y
unidad, inspeccionar ecuación, referencia e intervalo, calcular, revisar usados
y excluidos, detectar desactualización y descargar JSON.

Pendientes técnicos:

- confirmar las fuentes primarias, intervalos y condiciones de suelo;
- resolver la discontinuidad de las fórmulas locales;
- disponer de ensayos directos de módulo resiliente cuando sean necesarios;
- definir en una fase separada el contrato aprobado hacia AASHTO 93.
