# Metodología de Tránsito

## 1. Tránsito Observado (Aforos)
El **Tránsito Observado** corresponde a los volúmenes recopilados directamente en el campo a través de estaciones de conteo. Estos aforos pueden ser de diferentes duraciones:
* **Continuos**: Realizados durante 24 horas los 365 días del año.
* **Largos**: Realizados de 12 a 16 horas al día durante periodos de 3 a 10 días.
* **Cortos**: Flujos sin mucha fluctuación que se toman en muestras de 10 a 15 minutos, para luego expandirlos al volumen horario.

Para el diseño del TPDA, se requieren conteos mínimos consecutivos (usualmente 7 días, 24 horas/día) para cubrir un ciclo semanal completo y capturar las variaciones diarias.

## 2. Volumen por Intervalo y Tránsito Horario
* **Volumen por intervalo**: Cantidad de vehículos que cruzan una sección en un periodo específico (ej. 15 minutos).
* **Tránsito Horario**: Volumen expandido o agregado para representar una hora completa de flujo.

## 3. Tránsito Diario y Promedio Diario (TPD)
El **Tránsito Promedio Diario (TPD)** es el volumen medio de 24 horas obtenido durante el número de días aforados ($n$). 
Ecuación:
$$ TPD = \frac{\sum_{1}^{n} Q_i}{n} $$
Donde:
* $Q_i$ = Volumen vehicular durante el día "i"
* $n$ = Número de días aforados

## 4. Tránsito Promedio Diario Anual (TPDA)
Representa el promedio del flujo vehicular de todos los días de un año. 
Ecuación teórica con datos continuos:
$$ TPDA = \frac{\sum_{1}^{365} Q_i}{365} $$

Sin embargo, dado que los aforos suelen ser de menos de 365 días, el TPDA estimado requiere la aplicación de factores de expansión y estacionalidad a un TPD.

## 5. Tipos de TPDA
1. **TPDA calculado con datos continuos**: Promedio exacto sobre 365 días. Nivel de confiabilidad alto.
2. **TPDA estimado con aforos de varios días**: Obtenido de aforos de 7 días, corregido por factores mensuales/estacionales. Confiabilidad media-alta.
3. **TPDA estimado con aforos de 24 o 48 horas**: Uso de factores horarios y diarios para expandir la muestra. Confiabilidad media.
4. **TPDA estimado con aforos cortos**: Aforos de menos de 24 horas, alta dependencia de los factores horarios. Confiabilidad baja.
5. **TPDA importado / oficial**: Datos provenientes de peajes o estudios consolidados de la Administradora Boliviana de Carreteras (ABC).
6. **TPDA introducido manualmente**: Ingreso directo del usuario bajo su criterio.

## 6. Composición Vehicular
El TPDA debe subdividirse porcentualmente según los tipos de vehículos que transitan por la vía (Livianos, Buses, Camiones, etc.).

## 7. Variaciones de Flujo
* **Variaciones diarias y por día de la semana**: Las fluctuaciones entre días laborables y fines de semana.
* **Variaciones mensuales o estacionales**: Los cambios debidos a épocas de siembra, cosecha, lluvias, etc. Estas diferencias se corrigen mediante el Factor de Estacionalidad ($f_e$).
* **Distribución por sentido y por carril**: Por defecto, se asume 50/50 por sentido salvo medición que indique lo contrario. La distribución por carril depende del número de pistas.

## 8. Tránsito Acumulado
Es el número total de vehículos (generalmente expresado en Ejes Equivalentes - ESALs) proyectado para toda la vida útil de diseño de la carretera (Periodo de diseño).
Ecuación general para vehículos proyectados en el tiempo $t$:
$$ V_t = 365 \times P \times V_m $$
(Donde P es periodo de diseño, Vm es el volumen medio durante el proyecto).
