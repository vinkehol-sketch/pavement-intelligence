# Factores de Expansión para TPDA

El cálculo del Tránsito Promedio Diario Anual (TPDA) a partir de aforos muestrales requiere la aplicación de factores para compensar las variaciones temporales. En base a la bibliografía revisada, se identifican los siguientes factores:

## 1. Factor de Estacionalidad / Mensual ($f_e$)
Permite ajustar un volumen aforado en un mes específico al promedio anual.
* **Símbolo**: $f_e$
* **Ecuación**: $f_e = \frac{TPDA}{TPD_m}$
* **Aplicación**: Multiplica al TPD del mes aforado para obtener el TPDA.
* **Fuente**: Presentación "INGENIERÍA DE TRÁFICO Y TRANSPORTE" (Diapositiva 60).
* **Valores de Referencia**: 
  * Varían típicamente entre 0.69 (meses de mucho tráfico) y 1.58 (meses de poco tráfico).
  * *Estos valores no deben predeterminarse sin una justificación de la estación de peaje más cercana.*
* **Configurable manualmente**: SÍ (Obligatorio si no es 1.0).

## 2. Factor de Nocturnidad / Horario ($f_n$)
Permite expandir un aforo corto o de horas específicas a un volumen de 24 horas.
* **Símbolo**: $f_n$
* **Ecuación**: $f_n = \frac{Q_{24h}}{Q_{nh}}$
* **Unidad**: Adimensional.
* **Aplicación**: Multiplica el conteo horario por el factor para llegar al volumen diario estimado.
* **Fuente**: Presentación "INGENIERÍA DE TRÁFICO Y TRANSPORTE" (Diapositiva 62).
* **Configurable manualmente**: SÍ. Opcional.

## 3. Factor de Hora Pico (FHP)
Relaciona el volumen de la hora de máxima demanda con el flujo máximo dentro de esa hora (intervalos de 15 min).
* **Símbolo**: FHP
* **Ecuación**: $FHP = \frac{VHP}{4 \times I_{max(15min)}}$
* **Rango**: $0.25 \leq FHP \leq 1.0$ (Típicamente $> 0.5$).
* **Fuente**: Presentación "INGENIERÍA DE TRÁFICO Y TRANSPORTE" (Diapositiva 137).

## 4. Factores Pendientes de Confirmación Oficial
Los siguientes factores no tienen valores tabulados universales en la documentación revisada y dependen del manual específico o estudios de tráfico previos:
* **Factor Diario (Día de la semana)**: Convierte aforos de un día laboral al promedio de la semana.
* **Factor Direccional**: Suele asumirse 0.5 (50%), pero debe confirmarse.
* **Factor de Distribución por Carril**: Depende del número de carriles (ej. 1.0 para 1 carril, 0.8 a 1.0 para 2 carriles por sentido).

**Nota para el MVP**: Los factores se tratarán como variables configurables por el usuario. El sistema proveerá $f_e = 1.0$ por defecto (lo que asume que el TPD aforado es representativo del TPDA) emitiendo una advertencia.
