# Fuentes de Datos de Carga

El sistema está diseñado para procesar datos provenientes de múltiples canales, manteniendo una rigurosa trazabilidad de su origen mediante los siguientes estados:

- `MEDIDO_WIM`: Datos provenientes de sensores Weigh-In-Motion.
- `MEDIDO_ESTATICO`: Datos provenientes de balanzas estáticas.
- `IMPORTADO`: Cargas importadas desde archivos (CSV/Excel).
- `MANUAL`: Cargas ingresadas por un operador a través de la interfaz.
- `NORMATIVO`: Cargas teóricas máximas aplicadas según el DS 24327.
- `ESTIMADO`: Cargas imputadas utilizando promedios de la misma categoría o factores camión académicos.
- `SIMULADO`: Cargas generadas sintéticamente para pruebas o proyecciones teóricas.

> [!WARNING]
> **Riesgo Metodológico**: Es estrictamente prohibido que el sistema presente una carga `ESTIMADO` o `NORMATIVO` como si fuera peso real (`MEDIDO`). La interfaz y los reportes siempre deben resaltar la confiabilidad de la fuente.
