# Metodología de Cálculo de ESAL

El módulo ESAL de `pavement_intelligence` es el encargado de convertir los datos de cargas vehiculares en Ejes Equivalentes (EE o ESAL) acumulados.

## Objetivo
Determinar el daño relativo al pavimento provocado por el tránsito de distintos vehículos durante el periodo de diseño, unificándolos bajo la métrica del Eje Simple Equivalente (ESAL).

## Flujo de Procesamiento
1. **Adquisición de Cargas**: Obtención de pesos (Bruto y por Eje) de fuentes WIM, estáticas o normativas.
2. **Clasificación y Configuración**: Determinación de la configuración de ejes (Simple, Tándem, Trídem) asociada a la clasificación ABC.
3. **Cálculo de Factores de Equivalencia**: Transformación de las cargas por eje a Ejes Equivalentes mediante factores de equivalencia.
4. **Acumulación por Vehículo**: Suma de los EE de todos los ejes para obtener el ESAL total (Factor Camión) del vehículo.
5. **Acumulación para Periodo de Diseño**: Integración con el TPDA, tasas de crecimiento y factores direccionales para determinar los ESALs totales de diseño.
