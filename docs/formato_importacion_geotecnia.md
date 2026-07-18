# Formato de Importación Geotécnica

El sistema debe permitir la carga masiva de ensayos y perfiles geotécnicos mediante archivos CSV o Excel (.xlsx).

## Especificación de Columnas

Las columnas obligatorias para la subrasante se marcan con un asterisco (*).

| Columna en CSV | Tipo de Dato | Obligatorio | Descripción |
|----------------|--------------|-------------|-------------|
| `sample_id` | String | Sí (*) | Identificador único de la muestra. |
| `road_segment` | String | Sí (*) | Tramo vial asociado. |
| `station` | String | Opcional | Progresiva en formato texto (ej. "12+500"). |
| `chainage` | Float | Sí (*) | Progresiva numérica (ej. 12500). |
| `latitude` | Float | Opcional | Latitud (grados decimales). |
| `longitude` | Float | Opcional | Longitud (grados decimales). |
| `depth_from_m` | Float | Sí (*) | Profundidad superior de la muestra (m). |
| `depth_to_m` | Float | Sí (*) | Profundidad inferior de la muestra (m). |
| `soil_description`| String | Sí (*) | Descripción de campo o laboratorio. |
| `natural_moisture_percent`| Float | Sí (*) | Humedad natural (%). |
| `liquid_limit` | Float | Sí (*) | Límite Líquido (%). |
| `plastic_limit`| Float | Sí (*) | Límite Plástico (%). |
| `plasticity_index`| Float | Sí (*) | Índice de Plasticidad (%). |
| `uscs_class` | String | Sí (*) | Clasificación SUCS. |
| `aashto_class` | String | Sí (*) | Clasificación AASHTO (ej. A-2-4). |
| `group_index` | Float | Sí (*) | Índice de Grupo. |
| `proctor_type` | Enum | Sí (*) | `ESTANDAR` o `MODIFICADO`. |
| `max_dry_density`| Float | Sí (*) | Densidad seca máxima. |
| `optimum_moisture_percent`| Float | Sí (*) | Humedad óptima (%). |
| `cbr_percent` | Float | Sí (*) | Valor de CBR de diseño (%). |
| `cbr_condition`| Enum | Sí (*) | `SATURADO` o `NO_SATURADO`. |
| `compaction_percent`| Float | Sí (*) | Porcentaje de compactación asociado al CBR (ej. 95). |
| `expansion_percent`| Float | Sí (*) | Expansión en CBR (%). |
| `resilient_modulus_mpa`| Float | Opcional | Mr medido en MPa (si existe, sobreescribe CBR). |
| `water_table_depth_m`| Float | Opcional | Nivel freático detectado (m). |
| `drainage_condition`| Enum | Opcional | `EXCELENTE`, `BUENO`, `REGULAR`, `POBRE`, `MUY_POBRE`. |
| `data_source` | String | Sí (*) | Laboratorio o fuente de datos. |
| `review_status`| Enum | Opcional | Estado: `APROBADO`, `REVISADO`. |
| `observations` | String | Opcional | Notas adicionales. |

## Validaciones durante la importación
1. `cbr_percent` debe ser $>0$.
2. Si `cbr_condition` es `NO_SATURADO`, el sistema levantará una advertencia de que la condición no es la crítica.
3. El `plasticity_index` debe coincidir aproximadamente con `liquid_limit - plastic_limit`.
4. Todos los datos importados por defecto iniciarán con la etiqueta `review_status` en blanco, y requerirán aprobación en la plataforma para ser utilizados en el diseño.
