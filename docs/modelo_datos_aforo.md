# Modelo de Datos del Aforo

Para procesar e incorporar datos de aforo en el sistema, es necesario establecer un modelo de datos unificado que pueda representar cualquier intervalo medido (manual o automático).

## Registro de Aforo (Estructura Mínima)

Cada registro individual (una fila en base de datos o dataframe) debe representar el volumen de una categoría específica en un intervalo de tiempo y espacio determinado.

| Campo | Tipo | Descripción | Obligatorio |
|---|---|---|---|
| `record_id` | UUID/String | Identificador único del registro. | Sí |
| `date` | Date (YYYY-MM-DD) | Fecha en la que se realizó el aforo. | Sí |
| `start_time` | Time (HH:MM) | Hora de inicio del intervalo. | Sí |
| `end_time` | Time (HH:MM) | Hora de finalización del intervalo. | Sí |
| `interval_minutes` | Integer | Duración del intervalo en minutos (ej. 15, 60). | Sí |
| `road_section` | String | Tramo vial o proyecto (ej. "CHIMATE - MAPIRI"). | Sí |
| `station_id` | String | Código o nombre del punto de aforo. | Sí |
| `direction` | String | Sentido de circulación (ej. "Ida", "Vuelta"). | Sí |
| `lane` | Integer | Número de carril (1, 2). Por defecto 1 si no hay desglose. | No |
| `vehicle_category` | String | Categoría según clasificación (ej. "AUTO", "BUS"). | Sí |
| `volume` | Integer | Cantidad de vehículos contados. No admite negativos. | Sí |
| `data_source` | Enum | Origen del dato. | Sí |
| `review_status` | Enum | Estado de revisión y auditoría del dato. | Sí |
| `confidence` | Float (0-1) | Nivel de confianza si es automático (opcional). | No |
| `notes` | Text | Observaciones cualitativas (clima, oclusiones, etc). | No |

## Enums y Dominios

### Estados de Origen (`data_source`)
* `AUTOMATICO`: Generado por el módulo de visión artificial.
* `CORREGIDO_MANUALMENTE`: Generado por IA pero editado por el usuario.
* `MANUAL`: Registrado en planillas de campo y digitado.
* `IMPORTADO`: Cargado masivamente vía Excel/CSV.
* `OFICIAL`: Proporcionado por un peaje o informe de la ABC.
* `SIMULADO`: Datos sintéticos generados para pruebas o hackatón.

### Estados de Revisión (`review_status`)
* `NO_REVISADO`: Recién ingresado al sistema, pendiente de aprobación.
* `REVISADO`: Revisión rápida preliminar.
* `VALIDADO`: Datos consistentes y aprobados para cálculos de TPDA/ESAL.
* `RECHAZADO`: Intervalo inválido (ej. cámara tapada, conteo atípico erróneo).
