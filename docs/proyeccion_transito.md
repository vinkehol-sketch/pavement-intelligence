# Proyección del Tránsito

El diseño de pavimentos requiere conocer los volúmenes de tránsito no solo en el año de apertura, sino a lo largo de todo el periodo de diseño (usualmente 10 o 20 años). Las proyecciones se basan en modelar el crecimiento del TPDA.

## Métodos de Proyección (Identificados en Bibliografía)

En la documentación revisada ("INGENIERÍA DE TRÁFICO Y TRANSPORTE", Diapositivas 48-52), se identifican y comparan varios modelos matemáticos de proyección basados en el PIB y crecimiento poblacional (INE).

### 1. Crecimiento Lineal
* **Ecuación**: $V_f = V_o \times (1 + r \times n)$
* **Comportamiento**: Añade una cantidad constante de vehículos cada año.
* **Ventajas**: Sencillo, previene sobreestimaciones extremas a largo plazo.
* **Limitaciones**: No captura el interés compuesto; suele subestimar el crecimiento en regiones en desarrollo rápido.

### 2. Crecimiento Exponencial (o Geométrico / Interés Compuesto)
* **Ecuación**: $V_f = V_o \times (1 + r)^n$ 
* **Variables**:
  * $V_f$ = Volumen proyectado al final del periodo (año $n$).
  * $V_o$ = Volumen actual (Año base).
  * $r$ = Tasa de crecimiento anual (ej. 4% = 0.04).
  * $n$ = Número de años del periodo de diseño.
* **Ventajas**: Refleja mejor el comportamiento demográfico y macroeconómico compuesto.
* **Limitaciones**: En periodos muy largos (>20 años) y tasas altas, produce volúmenes logísticamente imposibles para la capacidad de la vía.

### 3. Crecimiento Logarítmico y Potencial
Mencionados en la bibliografía mediante ajuste de curvas estadísticas, aunque rara vez se usan de manera directa en normativa básica sin estudios detallados.

### 4. Tasas Históricas y Oficiales
Según la documentación, la proyección en Bolivia se basa en la asignación de tasas zonales vinculadas al **PIB departamental** y **crecimiento poblacional por municipio del INE**.

## Clasificación del Tránsito Futuro

Para el diseño, el tránsito total ($V_f$) se compone de:
1. **Tráfico Normal (Existente)**: Volumen que utilizaría la carretera aunque no se mejore. Crece a tasas normales vegetativas.
2. **Tráfico Atraído / Desviado**: Tráfico que actualmente usa otra ruta, pero que cambiará a la nueva ruta por mejoras en tiempo/costo.
3. **Tráfico Generado**: Nuevos viajes que ocurren únicamente porque la nueva infraestructura existe (desarrollo económico en la zona).

La suma total define la proyección final. (Ref: Diapositiva 46).

## Método Recomendado para el MVP

Para la versión inicial del software, se recomienda implementar el **Crecimiento Exponencial** debido a que es el método predeterminado en las guías AASHTO 93 para estimar el tránsito de diseño. Además, la interfaz debe permitir al usuario ingresar:
* La tasa de crecimiento ($r$) como porcentaje.
* El Periodo de diseño en años ($n$).

Los tráficos atraídos y generados podrán ser añadidos como un porcentaje extra opcional (Tráfico inducido).
