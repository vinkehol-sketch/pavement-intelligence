# Formato de Importación de Datos WIM

Para importar datos históricos o en lote, se utilizará un formato tabular (CSV o Excel) con las siguientes columnas mínimas y sus respectivas validaciones.

## Columnas Mínimas
1. `record_id`: Identificador único de pesaje.
2. `timestamp`: Fecha y hora exacta (ISO 8601).
3. `station_id`: Código de la estación WIM.
4. `road_segment`: Tramo carretero.
5. `lane`: Carril de circulación.
6. `direction`: Dirección de flujo.
7. `vehicle_category`: Categoría (1 a 13 ABC).
8. `axle_count`: Cantidad total de ejes.
9. `axle_number`: Índice del eje (1, 2, ... N).
10. `axle_type`: Tipo de eje (Simple, Tándem, Trídem).
11. `axle_load_kN`: Carga por eje en KiloNewtons.
12. `gross_weight_kN`: Peso Bruto Total.
13. `speed_kmh`: Velocidad registrada.
14. `plate_hash`: Hash anonimizado de la placa.
15. `data_source`: Origen del dato.
16. `confidence`: Nivel de confianza del hardware WIM (0.0 - 1.0).
17. `review_status`: Estado de validación.

## Validaciones Requeridas
- Ninguna carga (`axle_load_kN`, `gross_weight_kN`) puede ser negativa.
- La sumatoria de las cargas de los ejes debe ser igual al Peso Bruto Total (con tolerancia configurable por errores de redondeo).
- Los índices de `axle_number` deben estar en orden secuencial sin duplicados por vehículo.
- Velocidades `speed_kmh` deben estar en rangos realistas (0 a 160 km/h).
- Excluir o alertar sobre registros incompletos o ejes faltantes.
