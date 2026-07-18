# Formatos de Importación de Aforos

Para alimentar el sistema `pavement_intelligence` a partir de encuestas de origen/destino y conteos físicos de gabinete, se define el siguiente esquema de importación (soportado en formatos CSV y Excel `.xlsx`).

## 1. Esquema de Columnas

| Nombre Columna | Tipo / Formato | Requerido | Descripción |
|---|---|---|---|
| `FECHA` | YYYY-MM-DD | Sí | Fecha del aforo. |
| `HORA_INICIO` | HH:MM | Sí | Hora de inicio del periodo registrado. |
| `HORA_FIN` | HH:MM | Sí | Hora final del periodo registrado. |
| `ESTACION` | Texto | Sí | Punto de control (Ej: "Caihuasi", "Peaje 1"). |
| `SENTIDO` | Texto o 1/-1 | Sí | Dirección de flujo. |
| `LIVIANOS` | Entero | Sí | Sumatoria de Autos, Vagonetas, Camionetas. |
| `BUSES` | Entero | Sí | Sumatoria de Microbuses, Minibuses y Buses. |
| `CAMIONES` | Entero | Sí | Sumatoria de Rígidos, Articulados. |
| `OTROS` | Entero | No | Motos, Triciclos, etc. Default: 0. |

> **Nota:** La agrupación de columnas previene errores comunes de importación causados por los 13 distintos tipos de vehículos de la ABC. Si el usuario requiere granularidad, puede añadir columnas exactas (ej. `BUS_2EJES`, `CAMION_3EJES`), y el importador de Python las asignará a la categoría macro correspondiente si está configurado.

## 2. Tratamiento y Reglas de Negocio en la Importación

1. **Formatos de Fecha y Hora**: Se validará mediante `pd.to_datetime`. Las filas con errores de parseo se registrarán en un log de advertencias.
2. **Validaciones Numéricas**: Ningún valor volumétrico puede ser negativo. Un error generará un rechazo completo de la fila o se tratará como 0 según el parámetro estricto.
3. **Datos Faltantes (NaN)**: 
   - En columnas volumétricas se asume `0`.
   - En columnas requeridas de tiempo o estación, se rechaza la fila.
4. **Intervalos Incompletos**: Si un bloque (ej. de 12:00 a 13:00) falta para un día específico, el sistema lo marcará como "Brecha detectada" en el reporte de validación para prevenir un cálculo de TPDA erróneo sin factores de expansión horaria.
5. **Aforos con Duraciones Mixtas**: El sistema estandarizará todos los conteos agrupándolos internamente a resoluciones de 1 hora. Si un registro dura 2 horas, se asume distribución uniforme para cada hora.
6. **Duplicados**: Si existe el mismo intervalo, estación y sentido, se sobreescribe con el último cargado, previa advertencia.
