# Caso de Prueba de Validación (TPDA y Tránsito Acumulado)

Se ha identificado un ejercicio completo en el documento base de la asignatura (Presentación "INGENIERÍA DE TRÁFICO Y TRANSPORTE", Diapositiva 65). Este caso se utilizará para desarrollar las pruebas unitarias que garanticen la fiabilidad del algoritmo matemático.

## Descripción del Ejercicio

Determinar el número total de vehículos que circularán en un tramo de carretera al cabo de 20 años, tomando en cuenta un volumen inicial de tráfico de 1100 vehículos/día. 

### Entradas del Caso

* **Tráfico Promedio Diario Inicial ($V_o$)**: 1100 veh/día
* **Vida Útil / Periodo de Diseño ($P$)**: 20 años
* **Factor de expansión ($f_e$)**: 1.5 (Afecta de forma global, al parecer se utiliza de manera multiplicativa al final de la proyección lineal en el ejemplo académico).
* **Tasas de crecimiento / Tráfico Combinado ($r$ o $t$)**: 
  * Crecimiento normal: 5.3%
  * Tráfico de desarrollo: 3.2%
  * Tráfico inducido: 5.6%
  * **Suma de Tasas ($t$)**: 5.3% + 3.2% + 5.6% = 14.1%
* **Clasificación vehicular y EE (Opcional en esta fase, pero parte del problema)**:
  * Livianos: 27.9%, Peso = 7.7 Tn
  * Medianos: 56.5%, Peso = 11.0 Tn
  * Pesados: 15.6%, Peso = 22.0 Tn

### Procedimiento Analítico (Crecimiento Lineal Aplicado)

El ejemplo académico utiliza el modelo de crecimiento **Lineal** y aplica el factor $f_e$ al final de la ecuación del Tráfico Final:

1. **Cálculo del Tráfico Final ($V_f$)**
   $$ V_f = V_o \times (1 + P \times t) \times f_e $$
   $$ V_f = 1100 \times \left(1 + 20 \times \frac{14.1}{100}\right) \times 1.5 $$
   $$ V_f = 1100 \times (1 + 2.82) \times 1.5 = 1100 \times 3.82 \times 1.5 $$
   $$ V_f = 6303 \text{ veh/día} $$

2. **Cálculo del Tráfico Medio Diario durante el periodo ($V_m$)**
   $$ V_m = \frac{V_f + V_o}{2} $$
   $$ V_m = \frac{6303 + 1100}{2} = \frac{7403}{2} $$
   $$ V_m = 3701.5 \approx 3702 \text{ veh/día} $$

3. **Cálculo del Tráfico Total Acumulado ($V_T$)**
   $$ V_T = 365 \times P \times V_m $$
   $$ V_T = 365 \times 20 \times 3701.5 = 27,020,950 \text{ vehículos} $$
   *(Nota: La diapositiva redondea $V_m$ a 3702, por lo que $365 \times 20 \times 3702 = 27,024,600$)*.

### Resultado Esperado (Test Case Assertion)
El algoritmo deberá, dadas las mismas variables de entrada, arrojar un $V_f$ de 6303, un $V_m$ de 3702 y un $V_T$ de 27,024,600 utilizando el modelo lineal.

*(Nota: En la implementación real, deberemos soportar también el modelo exponencial que es el estándar de AASHTO).*
