# Integración TPDA y ESAL

Existen tres abstracciones conceptuales distintas que no deben mezclarse:

1. **Factor de Equivalencia de un Eje**: El daño de un grupo de ejes individual (ej. Eje Tándem con 14 tn = 0.73 ESAL).
2. **Factor Camión (ESAL por Vehículo)**: La sumatoria de todos los ejes de un vehículo específico.
3. **Factor Promedio de una Categoría**: El promedio estadístico de los Factores Camión de todos los vehículos que pertenecen a una misma categoría (ej. Categoría 7).

## Cálculo por Vehículo (Procedimiento Correcto)
Cuando se dispone de pesajes reales o normativos:
1. Identificar cada grupo de ejes del vehículo (ej. Eje Direccional Simple, Eje Trasero Tándem).
2. Asignar o leer la carga individual de cada grupo.
3. Aplicar la ecuación por grupo: `EE = (Carga / Carga_Estandar)^n`.
4. Sumar los EE de todos los grupos para obtener el Factor Camión del vehículo.

## Acumulación en el Periodo de Diseño
El cálculo del ESAL de diseño finaliza con la proyección a futuro:
`ESAL_Diseño = TPDA_Anual * Factor_Camion_Promedio * Crecimiento * Direccionalidad * Carril * 365`

> [!WARNING]
> No aplicar fórmulas simplificadas diseñadas para Ejes a Pesos Brutos Totales.
