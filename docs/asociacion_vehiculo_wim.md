# Asociación Vehículo (Visión) - Registro WIM

Para enriquecer los conteos visuales del módulo de aforo con pesos, se establece un algoritmo de cruce:

## Criterios de Emparejamiento
1. Ventana Temporal (Timestamp ± tolerancia en segundos).
2. Carril y Dirección.
3. Clase Visual vs Categoría de Pesaje.
4. Placa (mediante ALPR) si está disponible (Hash coincidente).

## Estados de Asociación
- `ASOCIACION_CONFIRMADA`: Empate perfecto por placa o tiempo/carril único en la ventana.
- `ASOCIACION_PROBABLE`: Empate temporal sin confirmación de placa.
- `ASOCIACION_MANUAL`: Resuelta por intervención de un operador.
- `SIN_ASOCIACION`: Datos huérfanos.
- `CONFLICTO`: Varios candidatos visuales posibles para un registro WIM en el mismo segundo.

> [!IMPORTANT]
> El sistema no realizará asociaciones automáticas en caso de `CONFLICTO`. Se conservará el registro WIM de manera estadística agregada, pero no enlazada al track visual.
