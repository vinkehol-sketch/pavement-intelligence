# Auditoría metodológica de la Fase 1: Aforo y TPDA

**Fecha:** 2026-07-17  
**Alcance:** revisión estática, comprobaciones aritméticas y pruebas locales; no se consultaron fuentes de Internet.  
**Decisión:** **NO APROBADO PARA CONECTAR CON ESAL** hasta eliminar la doble expansión potencial de la UI, unificar el cálculo con el dominio y validar documentalmente los factores locales.

## 1. Archivos revisados

- src/pavement_intelligence/ui/pages/survey_tpda.py (solo lectura; reservado a Antigravity).
- src/pavement_intelligence/traffic/tpda.py.
- src/pavement_intelligence/traffic/projection.py.
- src/pavement_intelligence/traffic/factors.py (solo contexto; no se modificó ESAL).
- src/pavement_intelligence/utils/validators.py.
- src/pavement_intelligence/domain/traffic/models.py.
- src/pavement_intelligence/config/vehicle_catalog.yaml.
- src/pavement_intelligence/integration/traffic_event_adapter.py.
- tests/unit/test_tpda.py.
- Documentos de metodología, factores, proyección, casos, especificación y arquitectura indicados en la solicitud.
- data/samples/caso_demostrativo/aforo_24h.csv y pesaje_vehicular.csv.

No se modificaron Streamlit, traffic_review.py, session_state, visión, ByteTrack, YOLO, línea de conteo, ESAL ni AASHTO.

## 2. Metodología realmente implementada

### 2.1 Definiciones y orden correcto en el dominio

La función corregida interpreta la entrada como conteo bruto N_i por categoría durante h horas:

1. Conteo observado: N_i vehículos en el periodo aforado.
2. TPD estimado: TPD_i = N_i × F_t.
3. TPDA base: TPDA_i = TPD_i × f_e.
4. Total: TPDA = suma de TPDA_i.
5. Carril de diseño: TPDA_diseño = TPDA × FDD × FDC.

La expansión temporal tiene dos alternativas mutuamente excluyentes:

- sin estudio horario: F_t = 24 / h, hipótesis uniforme;
- con factor documentado: F_t = f_n = Q_24h / Q_nh.

No se multiplican 24/h y f_n, porque ambos llevan el conteo parcial a 24 horas. Para 24 horas F_t=1; para varios días se obtiene el promedio diario 24/h. FDD y FDC no alteran el TPDA base.

V0 debe significar el **TPDA base del año base**, en veh/día, después de expansión temporal y estacional y antes de proyección, FDD y FDC. No debe denominarse V0 al conteo bruto.

No hay redondeo interno por categoría en el dominio. Esto conserva exactamente la suma de categorías; el redondeo pertenece a presentación/exportación. Las categorías ausentes se omiten y equivalen a cero.

### 2.2 Defecto crítico todavía presente en la UI

survey_tpda.py calcula localmente:

    factor_total = (24 / duración) × f_n × f_e

Para aforo parcial contradice la definición documental f_n = Q24h/Qnh y puede aplicar dos expansiones horarias. Además, la UI importa calculate_tpda pero no lo usa para el resultado: mantiene una segunda fórmula. No se corrigió allí por la exclusión expresa del trabajo de Antigravity.

Consecuencia: el dominio puede recibir conteos revisados de forma segura, pero la pantalla aún no debe afirmar que su resultado parcial es metodológicamente consolidado ni transferirlo a ESAL.

FHP aparece solo como información y no entra en la ecuación TPDA. Este punto es correcto.

## 3. Factores f_n y f_e

| Factor | Definición interna | Aplicación | Unidad/rango | Fuente interna | Bolivia/La Paz | Estado |
|---|---|---|---|---|---|---|
| f_n | Nocturnidad/expansión horaria, Q24h/Qnh | Sustituye 24/h; solo en aforo menor a 24 h | Adimensional, positivo. El rango UI 1–3 no está respaldado | Presentación “Ingeniería de Tráfico y Transporte”, diap. 62, citada en docs | No confirmado | Entrada manual; sin valor oficial por defecto |
| f_e | Estacionalidad mensual, TPDA/TPD_m | Una vez sobre TPD; si la entrada ya es TPDA vale 1 | Adimensional, positivo. El rango UI 0,5–3 no está respaldado | Misma presentación, diap. 60, citada en docs | No confirmado | Entrada manual; 1,0 es identidad, no calibración local |

Los documentos no prueban que sean “factores de la ABC”. La frase UI “parámetros técnicos de la ABC” no está sustentada por las fuentes internas. f_e=1 es neutro, pero supone que el TPD representa el promedio anual. f_n=1,5 no tiene respaldo y no conviene precargarlo.

Texto recomendado para la UI, no aplicado:

> **Factor manual no verificado:** este valor no está confirmado como oficial de la ABC ni calibrado para Bolivia o La Paz. Debe provenir de un estudio horario/estacional del punto de aforo. f_n sustituye la expansión 24/duración; no se multiplica por ella. Sin respaldo, no use el resultado para diseño.

## 4. Proyección exponencial

Implementa:

- V0c = V0 × factor_expansión.
- Vf = V0c × (1 + r/100)^n.
- Para r distinto de cero: VT = 365 × V0c × ((1+r/100)^n - 1)/(r/100).
- Para r=0: VT = 365 × V0c × n.

growth_rate se interpreta como porcentaje anual: 4 significa 4 %, mientras 0,04 significa 0,04 %. El periodo es entero en años. La UI deriva año_diseño = año_base + periodo; el motor recibe el periodo, por lo que la coherencia entre fechas debe validarse antes.

Se comprobaron tasa cero, periodo cero, valores no finitos, base negativa, años negativos y overflow. El MVP rechaza tasa negativa; es una decisión conservadora, aunque una disminución podría ser físicamente posible con respaldo. La proyección por categoría conserva aditividad con una tasa común.

La matemática compuesta queda **aprobada para el MVP educativo**, no como atribución “AASHTO oficial” basada solo en documentos internos.

## 5. Variantes lineales

### Variante A — reproducción académica documental

- Vf = [V0 × (1+n×r)] × fe.
- Vm = (Vf + V0)/2.
- VT = 365 × n × Vm.

Mezcla Vf expandido y V0 no expandido. Sus unidades coinciden pero sus bases no son homogéneas; subestima el acumulado si fe no vale 1. Solo reproduce el ejercicio interno. **Recomendación: ocultarla de la UI productiva y conservarla solo como opción experimental/académica.**

### Variante B — base homogénea

- V0c = V0 × fe.
- Vf = V0c × (1+n×r).
- Vm = (Vf + V0c)/2.
- VT = 365 × n × Vm.

Es matemáticamente coherente para crecimiento lineal constante y no duplica la exponencial. No se encontró fuente normativa primaria ni rango de uso en el repositorio. Con V0, r y n no negativos no genera tránsito negativo. **Recomendación: método académico/alternativo, no oficial; el exponencial debe ser principal.**

## 6. Separación de magnitudes

| Magnitud | Definición recomendada |
|---|---|
| Conteo observado | Vehículos contados durante h horas |
| TPD estimado | Promedio o volumen equivalente de 24 horas |
| TPDA base / V0 | Promedio diario anual del año base, antes de distribución y crecimiento |
| TPDA proyectado / Vf | TPDA del año de diseño |
| Tránsito direccional | TPDA × FDD |
| Tránsito por carril | TPDA × FDD × FDC |
| Tránsito de diseño | Debe indicar año y si es diario o acumulado |

La UI aplica FDD/FDC antes de guardar design_tpda, mientras proyecta el TPDA base sin distribución. Con factores constantes las operaciones conmutan, pero deben permanecer separadas y aplicarse después de proyectar o documentarse junto al resultado. “TPDA diseño” puede confundirse con el TPDA proyectado.

## 7. Categorías vehiculares

El catálogo central tiene 10 categorías: MOTO, AUTO, CAMIONETA, MINIBUS, BUS, C2, C3, TRACTOCAMION, ARTICULADO y OTRO_PESADO. La UI y ambos CSV usan esas diez.

clasificacion_vehicular_bolivia.md describe 13 grupos ABC, pero el catálogo agrega varios grupos. Es una simplificación configurable, no reproducción certificada. No hay IDs duplicados, pero sí pérdida de detalle relevante para ejes y ESAL.

El adaptador admite preliminarmente AUTO, MOTO, BUS, CAMION y DESCONOCIDO. CAMION o “Camión no confirmado” no pertenece al catálogo final: debe revisarse hacia C2, C3, TRACTOCAMION, ARTICULADO u OTRO_PESADO. La UI aún mapea automáticamente CAMION/TRUCK a C2; esto es inseguro para ejes y ESAL. Ninguna clase YOLO debe determinar configuración de ejes.

## 8. CSV sintéticos

### aforo_24h.csv

- Columnas category_id,count; 10 filas; enteros no negativos; sin nulos.
- Total estable: **1.273 vehículos**.
- Compatible con UI y catálogo operativo.
- No contiene hora, fecha, sentido, duración ni data_origin. Por ello **no demuestra por sí solo 24 horas**, pese al nombre; es un agregado interpretado mediante el control externo.
- La carpeta caso_demostrativo y la UI lo identifican como sintético, pero la trazabilidad no viaja dentro del archivo.
- Recomendación: añadir manifiesto o metadatos de duración, fecha sintética, fuente, origen y versión. No se alteraron datos.

### pesaje_vehicular.csv

- 50 registros entre 07:00 y 19:15 del 2026-01-15; 10 por categoría C2, BUS, C3, TRACTOCAMION y ARTICULADO.
- Cargas y peso bruto en kN; velocidad en km/h. Sin negativos ni faltantes esenciales.
- En los 50 registros, la suma de ejes coincide exactamente con el peso bruto.
- notes=simulado marca todos los registros. Faltan lote/equipo, precisión, calibración y data_origin estructurado.
- Sirve para demostración visual. Antes de WIM/ESAL real requiere esquema repetible de ejes, identificador de medición, sensor, calibración, calidad y procedencia. No se calcularon ESAL ni factores camión.

## 9. Auditoría y ampliación de pruebas

Las pruebas originales repetían varias ecuaciones del código; una legitimaba la doble expansión UI. Se sustituyó por regresiones de contrato y referencias numéricas fijas.

Cobertura añadida:

- 24 h sin expansión; parcial con expansión única; varios días como promedio.
- f_n sustituye 24/h y se rechaza como expansión adicional para 24 h.
- FDD/FDC separados; categorías ausentes; conservación de totales.
- NaN, infinito, negativos, tasa cero, periodo cero, años inválidos y overflow.
- Contrato porcentaje frente a decimal.
- Referencias numéricas para exponencial y variantes lineales.
- Rechazo de variante desconocida.
- Totales y trazabilidad disponible de CSV demostrativos.

Las pruebas no convierten datos sintéticos ni ejercicios académicos en normativa oficial.

## 10. Correcciones aplicadas

| Archivo | Antes | Después |
|---|---|---|
| traffic/tpda.py | Solo total, 24/h y FDD; sin categorías, FDC ni finitud | Categorías, factores trazables, FDD/FDC separados, expansión única y validaciones |
| traffic/projection.py | Admitía NaN/infinito/base negativa; variante desconocida caía en B; posible desborde | Valida entradas, variante, periodo y factor; reporta overflow |
| tests/unit/test_tpda.py | 8 pruebas; una replicaba doble expansión | 30 pruebas de contrato, regresión, bordes y trazabilidad |

No se corrigió survey_tpda.py por la prohibición expresa de modificar el trabajo concurrente de Antigravity.

## 11. Estructura recomendada para tpda_input_from_review

El motor debería aceptar un objeto versionado con:

    schema_version: 1.0
    batch_id: identificador no vacío
    counts_by_category: conteos corregidos
    duration_hours: duración positiva
    source: traffic_review
    data_origin: video_reviewed
    reviewer: nombre o ID
    reviewed_at: fecha ISO 8601 con zona
    warnings: lista
    is_synthetic: booleano
    approved: true
    temporal_expansion_method: uniform_24_over_h o documented_fn
    nocturnity_factor: valor o null
    seasonal_factor: valor documentado

Obligatorios antes de calcular: versión, lote, conteos finales no negativos y finitos en categorías oficiales, duración, fuente, origen, revisor, fecha, indicador sintético, aprobación y método de expansión. Si se usa f_n, debe incluir fuente/estudio y no combinarse con 24/h. Las advertencias deben persistir. CAMION, DESCONOCIDO o CAMION_NO_CONFIRMADO bloquean hasta revisión. No se modificó session_state.

## 12. Riesgos y condición de aprobación

1. Corregir en UI la doble expansión y delegar al motor único.
2. Eliminar conversión automática CAMION/TRUCK a C2.
3. Sustituir afirmaciones “ABC” no demostradas por advertencias manuales.
4. Quitar f_n=1,5 por defecto; mantener f_e=1 solo como identidad explícita.
5. Ocultar o etiquetar la lineal A como experimental.
6. Alinear las 10 categorías con la clasificación documental de 13 antes de ESAL.
7. Añadir trazabilidad estructurada al CSV agregado de aforo.
8. Validar factores locales con fuente oficial y profesional responsable.

**Conclusión funcional:** el dominio puede **recibir conteos revisados** si están aprobados, clasificados y trazados. La integración UI todavía no debe transferir automáticamente ni alimentar ESAL. La Fase 1 queda **NO APROBADA PARA CONECTAR CON ESAL**.

## 13. Verificación ejecutada

- Pruebas TPDA, revisión, adaptador y contador: **93 aprobadas, 0 fallidas**.
- Suite completa: **93 aprobadas, 0 fallidas**.
- pip check: **No broken requirements found**.
- La primera ejecución combinada encontró dos errores de acceso a la carpeta temporal global de pytest en Windows; al usar una carpeta temporal exclusiva del proyecto, ambas pruebas pasaron. No fue un defecto funcional ni de dependencias.
