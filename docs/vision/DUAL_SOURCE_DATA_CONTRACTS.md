# Contratos de Datos para Monitoreo con Doble Fuente

Este documento detalla las estructuras de datos (contratos de datos) en Python y los esquemas de sesión requeridos para dar soporte a la adquisición, procesamiento y asociación de tránsito vehicular y lecturas OCR de matrículas.

---

## 1. Identificadores Únicos y Metadatos de Sesión

### A. MonitoringPointId
Identificador unificado de la estación de medición (ej. `"BOL-LPZ-VSEC-04"`). Vincula ambas cámaras en el espacio geográfico.
* **Tipo**: `str` (validación de cadena no vacía).

### B. TrafficBatchId
Identificador único asignado al lote de conteo y clasificación vehicular generado por el pipeline panorámico.
* **Tipo**: `str` (formato `"trf:monitoring_point_id:timestamp_iso"`).

### C. PlateBatchId
Identificador de auditoría asignado al lote de lecturas de placas OCR tomadas por la cámara de primer plano.
* **Tipo**: `str` (formato `"ocr:monitoring_point_id:timestamp_iso"`).

---

## 2. Contratos de Estructura de Sesiones Independientes

### D. TrafficSourceSession (Inmutable)
Define el estado operativo de la adquisición del aforo panorámico.
* **Campos**:
  * `session_id` (`str`): UUID v4 único de la sesión.
  * `source_id` (`str`): Identificador del origen físico (ej: `"car-detection.mp4"` o `"camera:0"`).
  * `monitoring_point_id` (`str`): ID del punto de control físico.
  * `batch_id` (`TrafficBatchId`): ID del lote resultante.
  * `started_at` (`str`): Timestamp de inicio ISO 8601.

### E. PlateSourceSession (Inmutable)
Define el estado de adquisición de la cámara de matrículas.
* **Campos**:
  * `session_id` (`str`): UUID v4 de la sesión de placas.
  * `source_id` (`str`): Identificador de la cámara o video de placas (ej: `"lpr-close-up.mp4"` o `"camera:1"`).
  * `monitoring_point_id` (`str`): ID del punto de control asociado.
  * `batch_id` (`PlateBatchId`): ID del lote OCR resultante.
  * `started_at` (`str`): Timestamp ISO 8601 de inicio.

### F. DualSourceMonitoringSession
Agrupa ambas sesiones activas bajo el mismo punto de monitoreo para supervisión simultánea.
* **Campos**:
  * `monitoring_point_id` (`str`): ID de la estación.
  * `traffic_session` (`Optional[TrafficSourceSession]`): Sesión activa de tránsito vehicular.
  * `plate_session` (`Optional[PlateSourceSession]`): Sesión activa de lectura de placas.

---

## 3. Contrato de Asociación por Evidencia (OptionalSourceAssociation)

Esta estructura representa el emparejamiento heurístico e informativo entre una lectura de placa y un evento de tránsito vehicular sin recurrir al intercambio de identificadores de tracking nativos.

Su creación es opcional y no modifica ninguno de los registros de origen. Los `track_id` permanecen confinados a cada cámara y no forman parte del contrato. Toda asociación debe conservar la evidencia que originó la sugerencia, requiere confirmación manual para pasar a confirmada y puede revocarse posteriormente mediante una transición auditada. Ni una sugerencia ni una confirmación pueden modificar conteo, clasificación, sentido, aprobación, TPDA, ESAL o diseño de pavimentos.

* **Estados de la Asociación**:
  1. `UNASSOCIATED`: Sin emparejamiento.
  2. `CANDIDATE`: Sugerencia automática del sistema por coincidencia espacial-temporal.
  3. `MANUALLY_CONFIRMED`: Verificado y aprobado explícitamente por el auditor manual.
  4. `REJECTED`: Descartado explícitamente por el auditor.
  5. `AMBIGUOUS`: Ventana congestionada con múltiples vehículos y placas en colisión temporal.
  6. `REVOKED`: Confirmación manual revertida, con identidad, fecha y motivo de revocación.

* **Estructura del Contrato**:
```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class AssociationState(str, Enum):
    UNASSOCIATED = "UNASSOCIATED"
    CANDIDATE = "CANDIDATE"
    MANUALLY_CONFIRMED = "MANUALLY_CONFIRMED"
    REJECTED = "REJECTED"
    AMBIGUOUS = "AMBIGUOUS"
    REVOKED = "REVOKED"


@dataclass(frozen=True)
class OptionalSourceAssociation:
    association_id: str                 # UUID v4 de la asociación
    monitoring_point_id: str            # Punto común de control
    traffic_event_id: str               # ID del evento vehicular (de TrafficSourceSession)
    plate_reading_id: str               # ID de la lectura de placa (de PlateSourceSession)

    # Heurísticas de emparejamiento
    time_difference_seconds: float       # t_placa - t_vehiculo
    direction_match: bool               # Coincidencia de sentido (ej: N-S)
    lane_match: Optional[bool]          # Coincidencia de carril de circulación (si se detecta)
    category_match: bool                # Coincidencia de tipo (ej: Auto en tránsito e inferido en OCR)

    # Criterios de confianza y auditoría
    heuristic_score: float              # Confianza de la asociación (0.0 a 1.0)
    state: AssociationState             # Estado de asociación actual
    confirmed_by: Optional[str]         # Identidad del auditor manual
    confirmed_at: Optional[str]         # Timestamp ISO de la confirmación
    revoked_by: Optional[str]           # Identidad de quien revoca la confirmación
    revoked_at: Optional[str]           # Timestamp ISO de la revocación
    revocation_reason: Optional[str]     # Motivo auditable de la reversión
    notes: str                          # Observaciones del auditor
```

---

## 4. Representación Conceptual en Código de Dominio

```python
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class TrafficSourceSession:
    session_id: str
    source_id: str
    monitoring_point_id: str
    batch_id: str
    started_at: str


@dataclass(frozen=True)
class PlateSourceSession:
    session_id: str
    source_id: str
    monitoring_point_id: str
    batch_id: str
    started_at: str


@dataclass(frozen=True)
class DualSourceMonitoringSession:
    monitoring_point_id: str
    traffic_session: TrafficSourceSession | None = None
    plate_session: PlateSourceSession | None = None
```
