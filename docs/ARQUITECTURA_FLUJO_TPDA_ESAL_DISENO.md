# Arquitectura de Integración Funcional del Flujo de Tránsito y Diseño
**Proyecto:** Pavement Intelligence (Plataforma de Análisis de Tránsito y Diseño de Pavimentos)  
**Estado:** Propuesta Arquitectónica y Diseño de Contratos  
**Fecha:** 2026-07-17  

---

## 1. Estado Actual del Sistema

El MVP cuenta con páginas de Streamlit para cada una de las fases del flujo:
1. **Inicio (`home.py`):** Muestra tarjetas de estado y la secuencia del flujo de trabajo.
2. **Análisis de Video (`video_analysis.py`):** Ejecuta la detección YOLO y el tracking de ByteTrack.
3. **Revisión del Aforo (`traffic_review.py`):** Permite la auditoría manual del aforo y la clasificación de vehículos.
4. **Aforo y TPDA (`survey_tpda.py`):** Permite cargar la auditoría y proyectar el tránsito futuro.
5. **Pesaje (`weighing.py`):** Permite cargar los registros de cargas por eje de básculas WIM.
6. **ESAL (`esal_calculator.py`):** Realiza el cálculo de ejes acumulados equivalentes de diseño ($W_{18}$).
7. **Estudio de Suelo (`soil_study.py`):** Permite registrar muestras de CBR y calcula el percentil de diseño.
8. **Diseño de Pavimento (`pavement_design.py`):** Ejecuta la ecuación AASHTO 93 para calcular el Número Estructural (SN).
9. **Reportes (`reports.py`):** Centraliza la exportación de resultados.

---

## 2. Riesgos Arquitectónicos Identificados

* **Duplicación de Cálculos en la UI:** Múltiples páginas de la UI realizan cálculos directamente en los scripts de presentación (ej. proyecciones de tránsito, conversión de CBR a Módulo Resiliente, promedios de daño por eje). Esto dificulta las pruebas automáticas y rompe el principio de separación de responsabilidades.
* **Dependencias Débiles en `st.session_state`:** El estado de sesión actúa actualmente como un almacén de variables globales dispersas y tipos primitivos (`st.session_state["cbr_diseno"]`, `st.session_state["mr_psi"]`), en lugar de persistir modelos de dominio bien estructurados. Existe riesgo de sobrescritura accidental.
* **Falta de Trazabilidad Cruzada:** Al avanzar de ESAL a Diseño de Pavimentos, se pierden las referencias de origen de los datos. No hay garantía formal de que el CBR utilizado pertenezca al mismo tramo vial que el conteo de tránsito.
* **Propagación del Estado de Datos Sintéticos:** Si el aforo de video es sintético (`is_synthetic = True`), el indicador debe transmitirse sin pérdida a través del ESAL y el diseño del pavimento hasta el reporte técnico final, garantizando que el documento de salida quede sellado con la advertencia de simulación.

---

## 3. Flujo de Datos Arquitectónico

A continuación se define qué datos genera y consume cada etapa del proyecto:

```
[Auditoría de Aforo]
       │ (Genera: Lote de Eventos Auditados + Metadatos de Video)
       ▼
[Aforo y TPDA]
       │ (Genera: TPDA Base + TPDA Proyectado + Huella de Tránsito)
       ▼
[Cálculo de ESAL] <─── [Pesaje WIM / Catálogo] (Genera: Cargas por Eje / Factor Camión)
       │ (Genera: Ejes Equivalentes de Diseño W18 + Huella ESAL)
       ▼
[Diseño de Pavimento] <─── [Estudio de Suelo] (Genera: CBR + Módulo Resiliente MR)
       │ (Genera: Espesores de Capas + SN de Diseño)
       ▼
[Reportes y Exportación]
```

### Tabla de Insumos y Productos por Fase

| Módulo | Entradas (Insumos) | Salidas (Productos) | Datos Obligatorios | Datos Opcionales | Bloqueos / Restricciones |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Revisión del Aforo** | `vision_events_raw` (Visión) | `vision_events_reviewed`, `tpda_input_from_review` | `track_id`, `category`, `direction` | `centroid_x`, `centroid_y`, `confidence` | Bloquea si quedan camiones sin clasificar o si faltan justificaciones. |
| **Aforo y TPDA** | `tpda_input_from_review` / Manual / CSV | `tpda_result` | Conteos de entrada, Periodo ($P$), Tasa ($r$), Factores $D$ y $L$ | Fecha de aforo, Ubicación del tramo vial | Bloquea si el conteo total es cero, si $r < 0$ o si $P < 5$ años. |
| **Pesaje** | CSV Báscula WIM | `weighing_records` | Peso bruto, `axles` (lista de ejes con carga y tipo) | ID de báscula, observaciones | Bloquea si la suma de cargas de ejes difiere del peso bruto en $> 5\%$. |
| **ESAL (W18)** | `tpda_result`, `weighing_records` (si modo pesaje) | `esal_result` | Modo cálculo, $TPDA_i$ proyectado, Factores $D$ y $L$, Periodo ($P$) | Datos del catálogo de daño fijos | Bloquea si el TPDA no está definido en la sesión. |
| **Estudio de Suelo**| CBR de muestras | `soil_study_result` | Progresiva, Valor CBR por muestra, Percentil seleccionado | Humedad, Clasificación AASHTO | Bloquea si hay $< 3$ muestras o si CBR de diseño es $\le 0\%$. |
| **Diseño Pavimento**| `esal_result`, `soil_study_result` | `pavement_design_result`| $W_{18}$, Módulo Resiliente ($MR$), Confiabilidad ($R$), Espesores | Coeficientes de drenaje, estructura de capas | Bloquea si $W_{18} \le 0$ o si Confiabilidad $\notin [50, 99.9\%]$. |

---

## 4. Contratos de Datos Propuestos (Modelos de Dominio)

Para asegurar la consistencia del flujo, se propone formalizar los siguientes contratos de intercambio. Estos modelos encapsulan metadatos de trazabilidad e indicadores sintéticos.

### A. Contrato de Auditoría de Visión (`TrafficReviewResult`)
```python
@dataclass(frozen=True)
class TrafficReviewResult:
    review_id: str                      # Identificador único de auditoría
    source_video: str                   # Nombre del video origen
    model_name: str                     # Versión de YOLO utilizada
    line_y: int                         # Posición de la línea de conteo
    events: list[dict[str, Any]]        # Lista de eventos auditados
    counts_corrected: dict[str, int]    # Conteos corregidos agregados
    is_synthetic: bool                  # Indicador de datos demostrativos
    reviewer_name: str                  # Nombre del operador
    review_date: str                    # ISO Timestamp de auditoría
    batch_hash: str                     # Huella digital MD5/SHA256 del lote
```

### B. Contrato de Tránsito y TPDA (`TPDAResult`)
```python
@dataclass(frozen=True)
class TPDAResult:
    tpda_id: str                        # Identificador del cálculo
    source_review_hash: str             # Huella del TrafficReviewResult origen (o vacío si manual)
    tpda_by_category: dict[str, float]  # TPDA base obtenido
    projected_tpda_by_category: dict[str, float] # TPDA proyectado al año de diseño
    tpda_total: float                   # TPDA base total
    total_projected_tpda: float         # TPDA proyectado total
    design_tpda: float                  # Tránsito de diseño (TPDA * D * L)
    design_period_years: int            # Vida útil del pavimento
    growth_rate_percent: float          # Tasa de crecimiento anual
    projection_method: str              # Método (exponencial, lineal A, lineal B)
    applied_factors: dict[str, float]   # fn, fe, fdd, fdc
    is_synthetic: bool                  # Propagación de datos demostrativos
    warnings: list[str]                 # Alertas metodológicas activas
    calculation_date: str               # ISO Timestamp de cálculo
```

### C. Contrato de Pesaje WIM (`WeighingResult`)
```python
@dataclass(frozen=True)
class WeighingResult:
    weighing_id: str                    # Identificador del lote de pesaje
    source_file: str                    # Nombre del archivo CSV
    records: list[dict[str, Any]]       # Lista de registros de pesajes normalizados
    total_vehicles_weighed: int         # Total de vehículos pesados procesados
    average_truck_factor: float         # Factor Camión promedio calculado para la vía
    is_synthetic: bool                  # Indicador de datos de simulación
    import_date: str                    # ISO Timestamp de importación
```

### D. Contrato de Ejes Equivalentes (`ESALResult`)
```python
@dataclass(frozen=True)
class ESALResult:
    esal_id: str                        # Identificador de ESAL
    source_tpda_id: str                 # ID del TPDAResult utilizado
    source_weighing_id: str             # ID del WeighingResult utilizado (o vacío si catálogo)
    calculation_mode: str               # "catalogo" o "pesaje"
    total_esal_w18: float               # Tránsito acumulado de diseño (W18)
    esal_by_category: dict[str, float]  # ESAL aportado por categoría
    applied_truck_factors: dict[str, float] # FEC/FC por categoría vehicular
    growth_factor_accumulated: float    # FCA de diseño
    is_synthetic: bool                  # Propagación de indicador sintético
    warnings: list[str]                 # Alertas activas
    calculation_date: str               # ISO Timestamp
```

### E. Contrato de Estudio de Suelos (`SoilStudyResult`)
```python
@dataclass(frozen=True)
class SoilStudyResult:
    soil_study_id: str                  # Identificador del estudio
    samples: list[dict[str, Any]]       # CBR y progresivas de las muestras
    percentil_selected: int             # Percentil de diseño (ej. percentil 75)
    cbr_design_percent: float           # CBR de diseño representativo
    mr_design_psi: float                # Módulo Resiliente correlacionado
    is_synthetic: bool                  # Indicador de datos sintéticos
    calculation_date: str               # ISO Timestamp
    operator_name: str                  # Ingeniero responsable
```

### F. Contrato de Diseño Estructural (`PavementDesignResult`)
```python
@dataclass(frozen=True)
class PavementDesignResult:
    design_id: str                      # Identificador de diseño estructural
    source_esal_id: str                 # ID del ESALResult utilizado
    source_soil_id: str                 # ID del SoilStudyResult utilizado
    required_sn: float                  # Número Estructural requerido por AASHTO
    provided_sn: float                  # Número Estructural provisto por la sección
    layers: list[dict[str, Any]]        # Espesores y coeficientes (capa, espesor, a, m)
    reliability_percent: float          # Confiabilidad (R)
    overall_standard_deviation: float   # Desviación estándar (S0)
    initial_serviceability: float       # Serviciabilidad inicial (pi)
    terminal_serviceability: float      # Serviciabilidad terminal (pt)
    is_synthetic: bool                  # Propagación final del indicador sintético
    calculation_date: str               # ISO Timestamp
```

---

## 5. Mapa de Claves del Estado de Sesión (`st.session_state`)

Para evitar la redundancia y desorganización de variables, se establece el siguiente diccionario jerárquico de claves estables de sesión:

```python
st.session_state = {
    # 🎥 Módulo de Visión (YOLO + ByteTrack)
    "vision_events_raw": list[dict],            # Salida cruda de pipeline.py
    
    # 🔍 Módulo de Auditoría Manual
    "vision_events_reviewed": list[dict],       # Eventos en proceso de edición
    "traffic_review_approved": bool,            # Aprobación del aforo
    "traffic_counts_corrected": dict[str, int],  # Resultados consolidados corregidos
    "tpda_input_from_review": dict,             # Contrato de traspaso manual aprobado
    
    # 📊 Módulo de Aforo y TPDA
    "tpda_result": TPDAResult,                  # Objeto inmutable con los resultados del TPDA
    
    # ⚖️ Módulo de Pesaje WIM
    "weighing_records": WeighingResult,         # Objeto inmutable con registros y Factor Camión WIM
    
    # 🔢 Módulo de ESAL
    "esal_result": ESALResult,                  # Objeto inmutable con el cálculo de W18
    
    # 🌍 Módulo de Geotecnia / Suelos
    "soil_study_result": SoilStudyResult,        # Objeto inmutable con CBR y Módulo Resiliente
    
    # 🛣️ Módulo de Diseño Estructural
    "pavement_design_result": PavementDesignResult, # Objeto inmutable con espesores de capas
    
    # 📢 Registro de Alertas Generales
    "validation_warnings": list[str]            # Alertas técnicas transversales del MVP
}
```

---

## 6. Matriz de Invalidación y Estados de Resultados

Cuando un ingeniero modifica un valor de entrada en fases tempranas, los cálculos de las fases posteriores quedan automáticamente desactualizados. El sistema mantendrá los resultados anteriores intactos (sin borrados automáticos ni silenciosos) y gestionará su estado para evitar inconsistencias técnicas:

| Acción del Usuario | Componente Modificado | Estados Afectados y Acción Requerida |
| :--- | :--- | :--- |
| **Editar Tabla de Revisión de Aforo** | `vision_events_reviewed` | - `tpda_input_from_review` ➔ **Desactualizado / Requiere Re-aprobación**.<br>- `traffic_review_approved` ➔ **False**.<br>- `tpda_result` ➔ **Desactualizado** (se conserva pero con advertencia visual).<br>- `esal_result` ➔ **Desactualizado**.<br>- `pavement_design_result` ➔ **Desactualizado**. |
| **Guardar y Actualizar Tránsito** | `tpda_result` | - `esal_result` ➔ **Desactualizado**.<br>- `pavement_design_result` ➔ **Desactualizado**. |
| **Cargar nuevo CSV de Pesaje WIM** | `weighing_records` | - `esal_result` (si modo pesaje) ➔ **Desactualizado**.<br>- `pavement_design_result` ➔ **Desactualizado**. |
| **Cambiar Modo de ESAL (Catálogo/Pesaje)** | `calculation_mode` | - `esal_result` ➔ **Desactualizado**.<br>- `pavement_design_result` ➔ **Desactualizado**. |
| **Editar muestras de CBR / Percentil** | `soil_study_result` | - `pavement_design_result` ➔ **Desactualizado**. |
| **Recalcular ESAL W18** | `esal_result` | - `pavement_design_result` ➔ **Desactualizado**. |

### Definición de Estados del Flujo
1. **Vigente:** El objeto en sesión es completamente consistente y sincronizado con sus insumos predecesores (las firmas/huellas coinciden y están aprobadas).
2. **Desactualizado:** El objeto en sesión existe y se conserva (no se elimina silenciosamente), pero su huella de origen (`source_id`) difiere del identificador actual del componente predecesor. Se muestra una advertencia destacada: *"Los datos de origen de esta etapa cambiaron. Vuelva a procesar el cálculo para sincronizar."*
3. **Bloqueado:** El módulo no permite realizar nuevos cálculos ni guardar resultados porque no se cumplen los requisitos mínimos del contrato predecesor (ej. intentar calcular ESAL sin un TPDA de diseño configurado).
4. **Histórico:** Resultados previos de sesiones guardados o almacenados para trazabilidad del proyecto, conservando sus firmas originales.

### Regla de Eliminación y Borrado
* **Acción Explícita:** La eliminación o limpieza completa de cualquier cálculo o resultado de diseño anterior solo debe ocurrir mediante acción explícita e intencional del usuario (ej. un botón de 'Limpiar datos del proyecto' o 'Reiniciar flujo'), y **nunca de forma automática o silenciosa** por parte del sistema al modificar celdas en pantallas anteriores.


---

## 7. Estrategia de Trazabilidad y Datos Sintéticos

Cada objeto de cálculo en la sesión y el reporte consolidado (`reports.py`) implementarán los siguientes mecanismos de auditoría técnica:

* **Huella Digital del Lote (`batch_hash`):** Generada mediante un hash de los eventos auditados y la fecha. El módulo TPDA guarda esta huella; si la huella cambia, el cálculo se marca como desactualizado.
* **Propagación del Indicador Sintético (`is_synthetic`):** Si `is_synthetic` es `True` en el aforo, este booleano se copia al `TPDAResult`, luego al `ESALResult` y finalmente al `PavementDesignResult`.
* **Sello de Advertencia Visual:** Si el indicador es sintético, la UI y el PDF del reporte final dibujarán una franja roja diagonal en el fondo de las páginas con el texto: **"DATOS SINTÉTICOS - DEMOSTRACIÓN MVP"**.
* **Trazabilidad de Metodologías:** Cada resultado almacenará el nombre del responsable y la versión exacta de la norma aplicada (ej. `AASHTO 93 Flexible - v1.0`, `ABC Bolivia Tránsito - v2.1`).

---

## 8. Secuencia de Integración Recomendada

Para implementar las conexiones de forma segura y sin dependencias circulares, se propone la siguiente secuencia de desarrollo, priorizando la clasificación y procedencia del pesaje antes de definir factores de equivalencia de carga (Factor Camión):

```
[Fase 1: Aforo y TPDA (Cerrado)]
               │
               ▼
[Fase 2: Conexión Aforo ➔ Pesaje (Consumo de Categorías)]
               │
               ▼
[Fase 3: Clasificación, Configuraciones de Ejes y Procedencia del Pesaje]
               │
               ▼
[Fase 4: Cierre Metodológico de Pesaje (Factor Camión WIM)]
               │
               ▼
[Fase 5: Integración Pesaje ➔ ESAL (Modo Pesaje Dinámico)]
               │
               ▼
[Fase 6: Cierre Metodológico de ESAL (Ecuación W18)]
               │
               ▼
[Fase 7: Integración ESAL + Suelo ➔ Diseño AASHTO 93]
               │
               ▼
[Fase 8: Consolidación y Generación de Reportes Técnicos]
```

### Hitos de Control Técnico antes de avanzar
* **Hito 1 (Aforo → Pesaje):** La báscula WIM de pesaje requiere que la categoría del camión (`C2`, `C3`, `TRACTOCAMION`) ya esté confirmada en el aforo. No se puede cargar pesaje de vehículos sin categoría asignada.
* **Hito 2 (Clasificación y Ejes WIM):** Antes de calcular el Factor Camión por báscula, se debe normalizar el número de ejes por categoría (ej. 2 ejes para C2, 3 ejes para C3) y verificar la procedencia de la estación de pesaje.
* **Hito 3 (Pesaje → ESAL):** Se requiere que el cálculo de ESAL detecte si `weighing_records` tiene vehículos correspondientes a las categorías de tránsito. Si no hay camiones pesados pesados, se fuerza el modo catálogo.
* **Hito 4 (ESAL + Suelo → Diseño):** El módulo de diseño estructural requiere que existan tanto el CBR representativo de diseño (en `soil_study_result`) como el $W_{18}$ (en `esal_result`).

---

## 9. Alcance Mínimo para la Hackatón (MVP)

Para la presentación del MVP en la hackatón se diferencian los entregables imprescindibles en la ruta crítica de las mejoras de visualización secundarias:

### Imprescindible para la Hackatón (Ruta Crítica):
* **Flujo Estable y Sincronizado:** Carga rápida con un solo clic del caso demostrativo completo (tránsito, pesaje, CBR y diseño estructural) sin fallos ni excepciones del flujo.
* **Exactitud de Fórmulas:** Cálculos matemáticos correctos y alineados a las normativas de AASHTO 93 y ABC Bolivia.
* **Trazabilidad en Pantalla:** Mostrar la huella digital del lote, datos del revisor, procedencia de los datos y fechas de actualización.
* **Sello de Datos Sintéticos:** Advertencia de datos sintéticos de demostración propagada en el flujo hasta los reportes.

### Mejoras Secundarias (Fuera de la Ruta Crítica):
* **Gráficos Dinámicos:** Gráficos Plotly comparativos de incremento de tránsito base vs. diseño.
* **Gráfico de Dispersión WIM:** Gráfico de caja (boxplot) de cargas por eje de camiones WIM para demostrar la variabilidad del daño.

### Fase Futura (Post-Hackatón):
* Integración de lectura de placas vehiculares por OCR de video en tiempo real.
* Conexión con base de datos georreferenciada centralizada de la ABC.
* Exportación de reportes PDF técnicos con diagramas CAD automáticos de espesores de pavimento.


---

## 10. Recomendaciones Específicas para Codex

* **Modelado en el Dominio:** Codex debe implementar las clases inmutables `TrafficReviewResult`, `TPDAResult`, `WeighingResult`, `ESALResult`, `SoilStudyResult` y `PavementDesignResult` como clases Pydantic o Dataclasses congeladas (`frozen=True`) dentro de la carpeta `src/pavement_intelligence/domain/`.
* **Fórmulas de Daño Dinámicas:** Implementar el motor matemático del Factor Camión dinámico basado en la ley de la cuarta potencia en `src/pavement_intelligence/esal/` y no dentro de `esal_calculator.py`.
* **Desacoplamiento de la Sesión:** Toda validación de firmas y detección de invalidaciones debe ser procesada por un servicio dedicado (ej. `src/pavement_intelligence/services/flow_manager.py`) en lugar de escribir lógica condicional compleja de Streamlit en las páginas de la UI.
