# Contrato de Integración de Datos — MVP Pavement Intelligence
**Proyecto:** Pavement Intelligence (Plataforma de Análisis de Tránsito y Diseño de Pavimentos)  
**Estado:** Documento de Contrato Aprobado  
**Fecha:** 2026-07-17  

Este documento define la estructura de datos, flujo de procesamiento, reglas de validación y claves de `st.session_state` para la integración entre los módulos del sistema Pavement Intelligence:

```
[Visión YOLO] 
     │ (vision_events_raw)
     ▼
[Tabla de Revisión Manual] 
     │ (vision_events_reviewed)
     ▼
[Aforo y TPDA] 
     │ (tpda_result)
     ▼
[Cálculo de ESAL] <─── [Datos de Pesaje WIM] (weighing_records)
     │ (esal_result)
     ▼
[Diseño de Pavimento AASHTO 93] 
     │ (pavement_design_result)
     ▼
[Reportes y Exportación]
```

---

## 1. Contrato de Salida del Contador (`vision_events_raw`)
El módulo de visión por computadora YOLOv8 y ByteTrack produce una lista de eventos de cruce por línea virtual. Cada evento representa un cruce vehicular detectado.

### Esquema de Datos (TrafficEvent)
```json
{
  "event_id": "evt_1712403982000_42",
  "track_id": 42,
  "original_class": "truck",
  "category": "CAMION",
  "confidence": 0.895,
  "frame_number": 725,
  "video_second": 58.2,
  "direction": 1,
  "centroid_x": 120.5,
  "centroid_y": 140.0,
  "source": "car-detection.mp4",
  "processing_date": "2026-07-17T16:00:02.125Z",
  "data_origin": "OBSERVADO_POR_VIDEO"
}
```

### Tabla de Campos Críticos

| Campo | Tipo | Restricción | Descripción |
| :--- | :--- | :--- | :--- |
| `event_id` | str | Obligatorio | Identificador único del evento de cruce. |
| `track_id` | int | $\ge 0$ | Identificador del objeto de tracking. Si es `-1` se rechaza. |
| `original_class` | str | Enum | Clase visual estable consolidada por mayoría (ej: `car`, `truck`, `bus`, `motorcycle`). |
| `category` | str | Enum | Categoría preliminar mapeada por el modelo (ej: `AUTO`, `MOTO`, `BUS`, `CAMION`, `DESCONOCIDO`). |
| `confidence` | float | $0.0 \le c \le 1.0$ | Confianza promedio del track en su trayectoria histórica. |
| `frame_number` | int | $\ge 0$ | Número del fotograma del cruce. |
| `video_second` | float | $\ge 0.0$ | Segundo relativo de reproducción del video. |
| `direction` | int | `1` o `-1` | Sentido de circulación (`1` = ascendente, `-1` = descendente). |
| `centroid_x` | float | Obligatorio | Coordenada X del centroide del vehículo al cruzar. |
| `centroid_y` | float | Obligatorio | Coordenada Y del centroide del vehículo al cruzar. |
| `source` | str | Obligatorio | Nombre del archivo de video origen. |
| `processing_date` | str | ISO 8601 | Fecha y hora del procesamiento de los datos. |
| `data_origin` | str | Obligatorio | Origen del dato, por defecto `"OBSERVADO_POR_VIDEO"`. |

### Niveles de Categorización Vehicular (Crítico)
Para evitar errores de diseño ingenieril, se establecen tres niveles de categorización:
1. **Clase Consolidada (`original_class`):** La clase estable resuelta por votación de mayoría del tracking (`car`, `bus`, `truck`, `motorcycle`).
2. **Categoría Vehicular Preliminar (`category`):** Mapeo automático básico del sistema. Por ejemplo: `car` ➔ `AUTO`, `motorcycle` ➔ `MOTO`, `bus` ➔ `BUS`.  
   * **Regla estricta:** La clase visual `truck` (representada por `original_class` = `truck` y `category` = `CAMION`) **NO** se asocia automáticamente a una categoría vial pesada específica (como `C2`, `C3` o `TRACTOCAMION`). Se mantiene como preliminar y requiere confirmación en la tabla de revisión manual.
3. **Categoría Vial Confirmada (`corrected_category`):** La categoría de tránsito oficial de la ABC asignada manualmente tras la auditoría visual en la tabla de revisión (`AUTO`, `CAMIONETA`, `MINIBUS`, `BUS`, `C2`, `C3`, `TRACTOCAMION`, `ARTICULADO`, `OTRO_PESADO`, `MOTO`).


---

## 2. Contrato de la Tabla de Revisión Manual (`vision_events_reviewed`)
Permite registrar la auditoría humana y correcciones sobre los conteos brutos automáticos de visión antes de transferirlos a los cálculos de TPDA y ESAL.

### Estructura de Datos (Tabla Editable)
Cada fila de la tabla de revisión representa un resumen de conteos o un registro detallado de evento corregido:

```json
{
  "event_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "automatic_category": "CAMION_NO_CONFIRMADO",
  "corrected_category": "C3",
  "automatic_value": 1,
  "corrected_value": 1,
  "correction_reason": "Identificación visual de eje trasero tándem",
  "reviewed": true,
  "reviewed_by": "Ing. Andrés Barrientos",
  "reviewed_at": "2026-07-17T16:15:30.000Z"
}
```

### Tabla de Campos

| Campo | Tipo | Restricción | Descripción |
| :--- | :--- | :--- | :--- |
| `automatic_category` | str | Obligatorio | Categoría preliminar asignada por el sistema. |
| `corrected_category` | str | ABC Enum | Categoría oficial confirmada (debe estar en `CATEGORIAS_ABC`). |
| `automatic_value` | int | $\ge 0$ | Cantidad de vehículos contados automáticamente por la IA. |
| `corrected_value` | int | $\ge 0$ | Cantidad de vehículos corregidos manualmente. |
| `correction_reason` | str | Opcional | Justificación del cambio de clase o eliminación del registro. |
| `reviewed` | bool | Obligatorio | `True` si el registro fue auditado por el usuario. |
| `reviewed_by` | str | Obligatorio | Identificador/nombre del usuario que audita. |
| `reviewed_at` | str | ISO 8601 | Fecha y hora de la auditoría. |

---

## 3. Contrato de Aforo y TPDA (`tpda_result`)
El módulo de Aforo y TPDA procesa los conteos consolidados de la tabla de revisión, aplica factores temporales de la ABC y proyecta el volumen futuro de diseño.

### Entradas del Módulo
* **`counts_by_category`:** `dict[str, int]` - Diccionario con el conteo corregido por categoría de la ABC (ej. `{"AUTO": 650, "C2": 55}`).
* **`survey_duration_hours`:** `float` - Duración total del aforo ($0.1 \le H \le 168.0$).
* **`nocturnity_factor`:** `float` - Factor $f_n \ge 1.0$ (obligatorio para aforos $H < 24.0$).
* **`seasonal_factor`:** `float` - Factor estacional mensual $f_e$ ($0.5 \le f_e \le 3.0$).
* **`directional_factor`:** `float` - FDD/D para el carril de diseño ($0.3 \le D \le 1.0$).
* **`lane_distribution_factor`:** `float` - FDC/L para el carril de diseño ($0.5 \le L \le 1.0$).
* **`base_year`:** `int` - Año de partida de los datos viales.
* **`growth_rate_percent`:** `float` - Tasa de crecimiento anual $r \ge 0.0$.
* **`design_period_years`:** `int` - Años de vida útil del pavimento ($5 \le P \le 40$).
* **`projection_method`:** `str` - Método seleccionado (`exponential`, `linear_base_homogenea`, `linear_academic_documental`).
* **`data_provenance`:** `str` - Origen de datos (`vision`, `csv`, `manual`).
* **`is_synthetic`:** `bool` - `True` si los datos provienen del caso demostrativo.

### Salidas del Módulo (`tpda_result` en sesión)
```json
{
  "tpda_by_category": {
    "MOTO": 85.0,
    "AUTO": 650.0,
    "C2": 55.0
  },
  "tpda_total": 790.0,
  "projected_tpda_by_category": {
    "MOTO": 186.2,
    "AUTO": 1424.2,
    "C2": 120.5
  },
  "total_projected_tpda": 1730.9,
  "design_tpda": 865.45,
  "applied_factors": {
    "expansion_factor": 1.0,
    "nocturnity_factor": 1.0,
    "seasonal_factor": 1.0,
    "directional_factor": 0.5,
    "lane_distribution_factor": 1.0
  },
  "warnings": [
    "Uso de factor estacional manual pendiente de validación",
    "Uso de datos sintéticos del caso demostrativo"
  ],
  "correction_traceability": {
    "original_vehicles": 780,
    "corrected_vehicles": 790,
    "auditor": "Ing. Andrés Barrientos",
    "date": "2026-07-17T16:15:30Z"
  },
  "methodology_version": "ABC Bolivia - Manual de Tránsito 2021 / AASHTO 93"
}
```

---

## 4. Contrato de Pesaje (`weighing_records`)
Define el esquema para la caracterización de cargas de vehículos pesados (importadas desde CSV o básculas WIM virtuales).

### Esquema Normalizado de Ejes (AxleRecord)
Representar los pesos como columnas planas (`axle1_load`, `axle2_load`...) no es robusto porque la cantidad de ejes es altamente variable (desde 2 ejes en un auto hasta 6 o más en camiones articulados). Se define la estructura normalizada de lista de ejes:

```json
{
  "weighing_id": "c39d892d-944a-4e20-80d5-e2f4ea7c89f5",
  "vehicle_id": "WIM-2026-0717-004",
  "timestamp": "2026-07-17T16:05:00.000Z",
  "vehicle_category": "C3",
  "source": "Báscula Chimate km 10+200",
  "gross_weight": 260.0,
  "gross_weight_unit": "kN",
  "axle_count": 2,
  "axles": [
    {
      "axle_index": 1,
      "axle_type": "simple_single",
      "load": 60.0,
      "load_unit": "kN"
    },
    {
      "axle_index": 2,
      "axle_type": "tandem",
      "load": 200.0,
      "load_unit": "kN"
    }
  ],
  "synthetic_data": true,
  "validation_status": "VALIDADO",
  "observations": "SIMULADO - Caso Demostrativo"
}
```

### Mapeo de Casos Especiales en Pesaje

1. **Tipos de Eje (Axle Types):**
   - `simple_single`: Eje simple de rueda simple (direccional - carga estándar 6.6 t / 65 kN).
   - `simple_dual`: Eje simple de rueda doble (estándar de daño - carga estándar 8.2 t / 80 kN).
   - `tandem`: Eje doble (carga estándar 15.1 t / 148 kN).
   - `tridem`: Eje triple (carga estándar 21.8 t / 214 kN).
2. **Vehículos con Número Variable de Ejes:** La longitud de la lista de objetos `axles` será estrictamente igual a `axle_count`.
3. **Pesos o Datos Faltantes:** Si un sensor WIM falla en registrar el peso de un eje, el campo `load` se define como `null`. El registro se marcará con `validation_status = "INCOMPLETO"`. Los registros incompletos se excluyen del cálculo del Factor Camión para evitar subestimar el daño.
4. **Unidades Inconsistentes:** Se define **kilonewtons (kN)** como la unidad de cálculo interna estándar. Si los datos se importan en toneladas viales (t), se aplica la conversión estándar de ingeniería: $1.0\text{ t} = 9.80665\text{ kN}$ (o $10.0\text{ kN}$ si la especificación del proyecto lo requiere para simplificación).

---

## 5. Contrato para ESAL (`esal_result`)
El módulo ESAL calcula el tránsito acumulado equivalente $W_{18}$ en repeticiones de eje estándar de 80 kN.

### Entradas Requeridas
* **`tpda_result`:** Resultados consolidados de tránsito (especialmente `projected_tpda_by_category` y factores de diseño FDD y FDC).
* **`growth_factor`:** Factor de crecimiento acumulado ($GF$) provisto por el módulo de tránsito.
* **`calculation_mode`:** `str` (Enum: `"catalogo"` o `"pesaje"`).
* **`weighing_records`:** Lista de registros de pesaje importados (solo para `"pesaje"`).

### Definición de los Modos de Operación
1. **Modo Catálogo (Estimación Rápida):**
   El sistema calcula el daño utilizando factores de equivalencia de carga (FEC/Factor Camión) fijos extraídos del manual oficial de la ABC en `factors.py` (ej. `C2` = 2.5, `C3` = 4.0).
2. **Modo Pesaje (Integración WIM):**
   El sistema calcula el Factor Camión dinámicamente. Para cada vehículo pesado de los `weighing_records`, se suma el daño de sus ejes individuales calculados con las fórmulas de equivalencia AASHTO (cuarta potencia):
   $$EE_{eje} = \left(\frac{P_{real}}{P_{std}}\right)^4$$
   Luego se promedian los ESALs por categoría vehicular para obtener el Factor Camión real medido de la vía.

---

## 6. Trazabilidad y Calidad de Datos
Para certificar la procedencia de cada resultado geotécnico y estructural, todo reporte y objeto de cálculo del sistema conservará la siguiente sección de metadatos:

```json
{
  "data_provenance": {
    "source_type": "sintetico_demostrativo",
    "source_file": "aforo_24h.csv / pesaje_vehicular.csv",
    "processing_datetime": "2026-07-17T16:30:00Z",
    "operator_name": "Usuario Anónimo (IDE)",
    "yolo_model_version": "YOLOv8n-COCO (v0.1.0)",
    "tpda_method_version": "LinearBaseHomogenea-v1.0",
    "esal_method_version": "AASHTO93-Flexible-v1.0",
    "is_corrected": true,
    "active_warnings": ["DATOS_DEMOSTRATIVOS_SIMULADOS"]
  }
}
```

### Niveles de Madurez de Datos (Calidad)
* `experimental`: Flujo en crudo de visión artificial, sin auditoría del ingeniero. Útil para previsualización.
* `demostrativo`: Uso de archivos sintéticos preestablecidos (`aforos_24h.csv`, `pesaje_vehicular.csv`). Bloqueado para firmas de planos.
* `revisado`: Conteos corregidos y validados visualmente por el usuario en la tabla de revisión manual.
* `validado`: Registros con procedencia de datos reales, básculas calibradas y CBR de laboratorios certificados.

---

## 7. Integración con `session_state`
A continuación se detallan las claves propuestas para compartir información entre las páginas de Streamlit:

| Clave de Sesión | Tipo de Dato | Productor | Consumidor | Campos Obligatorios | Comportamiento si falta |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `vision_events_raw` | `list[dict]` | `video_analysis.py` | `survey_tpda.py` | `event_id`, `original_class`, `category`, `direction` | Mostrar advertencia de "No hay video procesado". |
| `vision_events_reviewed`| `list[dict]` | `survey_tpda.py` | `survey_tpda.py` | `event_id`, `corrected_category`, `reviewed` | Inicializar con los datos brutos de `vision_events_raw`. |
| `traffic_counts_corrected`| `dict[str, int]`| `survey_tpda.py` | `survey_tpda.py` | `{"AUTO": count, ...}` (10 categorías ABC) | Bloquear cálculo de TPDA. |
| `tpda_result` | `TPDAPageResult` | `survey_tpda.py` | `esal_calculator.py`, `reports.py` | `tpda_by_category`, `design_tpda`, `expansion_factor` | Mostrar info "Por favor, defina el TPDA primero". |
| `weighing_records` | `list[dict]` | `weighing.py` | `esal_calculator.py` | `gross_weight`, `axles` (con lista de cargas) | ESAL forzará el uso del Modo Catálogo obligatoriamente. |
| `esal_result` | `ESALResult` | `esal_calculator.py`| `pavement_design.py`, `reports.py` | `total_esal_w18`, `esal_by_category` | Pavement Design mostrará advertencia y usará ESAL de demo. |
| `pavement_design_result`| `PavementDesignResult`| `pavement_design.py`| `reports.py` | `required_sn`, `provided_sn`, `layers` | El reporte final marcará el diseño como "Pendiente". |
| `data_provenance` | `dict` | Todos | `reports.py` | `source_type`, `is_corrected` | Definir por defecto como `"experimental"` con alertas. |
| `validation_warnings` | `list[str]` | Todos | Todos | Alertas de integridad y diseño | Inicializar como lista vacía `[]`. |

---

## 8. Reglas de Validación y Manejo de Errores (Bloqueos)
Para garantizar la integridad y calidad del software, se definen las siguientes reglas de parada de ejecución:

1. **Revisión de Categorías YOLO:** Si un registro en `vision_events_raw` contiene la clase `truck` y el usuario intenta avanzar al cálculo de TPDA sin haber auditado el registro para clasificarlo en un camión específico de la ABC (`C2`, `C3`, etc.), el sistema mostrará un bloqueo: *"Existen camiones detectados por la IA pendientes de clasificación vial en la tabla de revisión."*
2. **Conteos Negativos o Vacíos:** La tabla de revisión manual o importación de CSV rechazará el cálculo si existen celdas vacías (`null`) o valores inferiores a `0`.
3. **Cargas de Eje Inconsistentes en Pesaje:** Si la suma de pesos individuales de los ejes de un camión (`axles[].load`) difiere del peso bruto total registrado (`gross_weight`) en más de un 5%, el registro se cataloga como `"ERRONEO"` y se descarta del promedio.
4. **Validación de Unidades en ESAL:** Si los pesos de báscula WIM están en Toneladas (t) pero el módulo de cálculo de ESAL los procesa sin aplicar la conversión estándar a kN, se detiene el cálculo para evitar el colapso del diseño estructural (un error de factor de 10).
5. **Marca de Datos Sintéticos:** Si `is_synthetic == true`, todos los reportes impresos y el encabezado de Streamlit mostrarán un banner rojo parpadeante con el texto: **"COPIA DEMOSTRATIVA - DATOS SINTETICOS"**.

---

## 9. División de Responsabilidades (Roadmap Futuro)

### Codex
- **Validación y Tracking de Visión:** Estabilización del contador, corrección de IDs perdidos, reducción de oscilaciones y duplicados en el cruce de línea.
- **Backend de Ingeniería de Tránsito:** Implementación de clases Pydantic para el cumplimiento estricto del esquema normalizado de pesajes y ejes en `src/pavement_intelligence/domain`.
- **Motor de Inferencia YOLO:** Configuración de procesamiento batch y selección de CUDA en entornos Windows.

### Antigravity (Tuyo)
- **Desarrollo de la UI en Streamlit:** Implementar la tabla de revisión manual editable, conectar las variables de `session_state` entre las pantallas y crear el panel dinámico de visualización de proyecciones.
- **Mapeo de Datos WIM:** Programar la lectura estructurada de la lista de ejes en `weighing.py` para dibujar los boxplots de Plotly.
- **Orquestación de Reportes:** Consolidar el reporte JSON final y diseñar el módulo de exportación.
