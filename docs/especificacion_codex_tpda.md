# Especificación para Implementación de TPDA (Módulo Tránsito)

Este documento es la especificación técnica entregable para "Codex" u otro desarrollador encargado de implementar el módulo de cálculo de TPDA y proyecciones de tránsito en Python. Ha sido auditado para asegurar la correspondencia estricta con las fórmulas de los manuales.

## 1. Alcance Exacto
Desarrollar el backend (clases de dominio, lógica de negocio y validación) para la ingesta de aforos vehiculares, la aplicación de factores de corrección temporal, el cálculo del Tránsito Promedio Diario Anual (TPDA) y la proyección del Tránsito Acumulado a lo largo del periodo de diseño. **No** incluye cálculos de ESAL, factores de equivalencia de carga ni diseño de pavimentos.

## 2. Funciones a Implementar
* `TrafficDataImporter`: Carga de archivos CSV/Excel, validación y conversión al modelo de dominio.
* `TpdCalculator`: Cálculo del TPD base y aplicación de factor de nocturnidad ($f_n$) y factor estacional ($f_e$).
* `LinearTrafficProjector`: Proyección de tránsito mediante modelo lineal (como se usa en ejercicios académicos).
* `ExponentialTrafficProjector`: Proyección de tránsito mediante modelo exponencial / compuesto (estándar AASHTO).

## 3. Modelos de Datos
Las clases usarán `pydantic.BaseModel`:
* `SurveyRecord`: Registro de aforo por intervalo.
* `AbcVehicleCategory`: Enum estricto de las 13 categorías de la ABC para preservar configuración de ejes (LIVIANOS, CAMIONETAS, MINIBUSES, MICROBUSES, BUS_MEDIANO, BUS_GRANDE, CAMION_MEDIANO, CAMION_GRANDE_2E, CAMION_GRANDE_3E, SEMIREMOLQUE, REMOLQUE, MOTOCICLETAS, OTROS).
* `TrafficProjectionResult`: Objeto que retorna $V_f$, $V_m$ y $V_T$.

## 4. Ecuaciones Aprobadas e Implementables

### 4.1. Factor de Nocturnidad ($f_n$)
Expande un aforo de 1 hora a 24 horas (Diapositiva 62).
* **Ecuación**: $f_n = \frac{Q_{24h}}{Q_{nh}}$
* **Condición de aplicación**: **SOLO** debe aplicarse si el aforo no cubre 24 horas continuas. Nunca aplicarlo si el volumen ya es de 24 horas, para evitar duplicación.

### 4.2. Tránsito Promedio Diario Anual (TPDA)
Expande un TPD (promedio de días aforados) a TPDA anual (Diapositiva 60).
* **Ecuación**: $TPDA = TPD_m \times f_e$
* **Condición de aplicación**: El factor $f_e$ (estacionalidad mensual) **SOLO** debe aplicarse cuando el tránsito aforado todavía no represente el promedio anual (ej. aforo de una semana en época lluviosa). Si el dato de entrada ya es TPDA, $f_e$ debe forzarse a 1.0.

### 4.3. Proyección de Tránsito (Modelos Lineales)
Basado en Diapositivas 64 y 65. El sistema deberá soportar dos variantes debido a inconsistencias metodológicas detectadas en la bibliografía.

**Variante A: METODO_REPRODUCCION_DOCUMENTAL**
Aplica el factor de expansión al volumen final, pero calcula el promedio mezclando datos expandidos ($V_f$) y no expandidos ($V_0$). Únicamente sirve para reproducir ejercicios académicos.
* **Tráfico Medio Diario Final ($V_f$)**: $V_f = [V_0 \times (1 + P \times t)] \times f_e$
* **Tráfico Medio Diario ($V_m$)**: $V_m = \frac{V_f + V_0}{2}$
* **Volumen Total Acumulado ($V_T$)**: $V_T = 365 \times P \times V_m$

**Variante B: METODO_BASE_HOMOGENEA (Recomendado)**
Homogeneiza la base calculando un TPDA inicial antes de proyectar.
* **Tráfico Inicial Corregido ($V_{0c}$)**: $V_{0c} = V_0 \times f_e$
* **Tráfico Medio Diario Final ($V_f$)**: $V_f = V_{0c} \times (1 + P \times t)$
* **Tráfico Medio Diario ($V_m$)**: $V_m = \frac{V_f + V_{0c}}{2}$
* **Volumen Total Acumulado ($V_T$)**: $V_T = 365 \times P \times V_m$

> **ADVERTENCIA DE INCONSISTENCIA METODOLÓGICA:** Las Diapositivas 64 y 65 instruyen promediar un $V_f$ expandido con un $V_0$ bruto. Esto subestima el tráfico real ($V_m$ y $V_T$) en casi 2 millones de vehículos en el ejercicio de 20 años. Para fines de pavimentación reales, el sistema debe alertar al usuario si escoge el método documental.

### 4.4. Proyección de Tránsito (Modelo Exponencial / Compuesto)
Basado en Diapositiva 48. Utiliza siempre la base homogénea ($V_{0c}$).
* **Tráfico Medio Diario Final ($V_f$)**: $V_f = V_{0c} \times (1 + r)^P$
* **Volumen Total Acumulado ($V_T$)**: $V_T = 365 \times V_{0c} \times \frac{(1 + r)^P - 1}{r}$

## 5. Pruebas Unitarias Exigidas

**Test 1: Proyección Lineal (Caso Diapositiva 65)**
* **Entradas**: $V_0 = 1100$ veh/día (TPD no expandido), $p = 20$ años, $t = 14.1\%$ ($0.141$), $f_e = 1.5$.
* **Fórmula aplicada**: $V_f = \{1100 \times (1 + 20 \times 0.141)\} \times 1.5$
* **Resultados Esperados**:
  * $V_f = 6303$ veh/día
  * $V_m = 3701.5$ (Tolerancia: $\pm 1$)
  * $V_T = 27,020,950$ (Tolerancia: verificar redondeo a $27,024,600$ si se usa $V_m=3702$).

## 6. Funciones y Ecuaciones Excluidas del MVP
* **Factor de Hora Pico (FHP)**: Se excluye del cálculo de TPDA. Su uso es estrictamente operacional (nivel de servicio y capacidad vial), no es un factor de expansión volumétrica.
* **Ejes Equivalentes (EE) y ESALs**: Todo cálculo de cargas, factor camión y distribución por carril queda pospuesto hasta que se implemente el módulo de Pavimentos.
* **Asignación estocástica de tráfico urbano**: Limitación asumida.