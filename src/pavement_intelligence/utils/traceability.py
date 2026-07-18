"""
Utilidades de trazabilidad y auditoría de cálculos.

Proporciona un registro de auditoría (``AuditLog``) para almacenar el historial
de cálculos realizados en el sistema, con referencias completas a entradas,
salidas, fórmulas y referencias normativas.

Esto es especialmente importante para resultados de ingeniería que serán
usados en decisiones de diseño y documentos técnicos oficiales.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class CalculationStep:
    """
    Paso individual de un cálculo trazado.

    Attributes:
        step_name: Nombre del paso (ej: "Estimar MR desde CBR").
        formula: Fórmula aplicada (ej: "MR = 1500 × CBR").
        inputs: Diccionario de valores de entrada {nombre: valor}.
        outputs: Diccionario de valores de salida {nombre: valor}.
        reference: Referencia normativa del paso.
        notes: Observaciones adicionales.
    """

    step_name: str
    formula: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    reference: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        """Serializa el paso a diccionario."""
        return {
            "paso": self.step_name,
            "formula": self.formula,
            "entradas": self.inputs,
            "salidas": self.outputs,
            "referencia": self.reference,
            "notas": self.notes,
        }


@dataclass
class AuditLog:
    """
    Registro de auditoría de un cálculo completo.

    Almacena el historial completo de un cálculo de ingeniería, incluyendo
    todos los pasos intermedios, para garantizar la trazabilidad completa.

    Attributes:
        id: Identificador único del registro (UUID v4).
        calculation_name: Nombre del cálculo (ej: "Diseño AASHTO 93 - Tramo Norte").
        entity_id: ID de la entidad principal del cálculo (ej: ID del diseño).
        entity_type: Tipo de entidad (ej: "FlexiblePavementDesign").
        method: Método de cálculo (ej: "AASHTO_93").
        steps: Lista ordenada de pasos del cálculo.
        summary_inputs: Resumen de entradas principales.
        summary_outputs: Resumen de salidas principales.
        warnings: Advertencias generadas durante el cálculo.
        performed_by: Usuario o proceso que realizó el cálculo.
        performed_at: Fecha y hora del cálculo.
        software_version: Versión del sistema al momento del cálculo.
        notes: Observaciones generales.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    calculation_name: str = ""
    entity_id: Optional[str] = None
    entity_type: str = ""
    method: str = ""
    steps: list[CalculationStep] = field(default_factory=list)
    summary_inputs: dict[str, Any] = field(default_factory=dict)
    summary_outputs: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    performed_by: str = "sistema"
    performed_at: datetime = field(default_factory=datetime.now)
    software_version: str = "0.1.0"
    notes: str = ""

    def add_step(
        self,
        step_name: str,
        formula: str = "",
        inputs: Optional[dict[str, Any]] = None,
        outputs: Optional[dict[str, Any]] = None,
        reference: str = "",
        notes: str = "",
    ) -> CalculationStep:
        """
        Agrega un paso de cálculo al registro.

        Args:
            step_name: Nombre descriptivo del paso.
            formula: Fórmula matemática aplicada.
            inputs: Valores de entrada del paso.
            outputs: Valores de salida del paso.
            reference: Referencia normativa.
            notes: Observaciones.

        Returns:
            El ``CalculationStep`` creado y agregado.
        """
        step = CalculationStep(
            step_name=step_name,
            formula=formula,
            inputs=inputs or {},
            outputs=outputs or {},
            reference=reference,
            notes=notes,
        )
        self.steps.append(step)
        return step

    def add_warning(self, message: str) -> None:
        """Agrega una advertencia al registro."""
        if message not in self.warnings:
            self.warnings.append(message)

    def to_dict(self) -> dict:
        """Serializa el registro de auditoría a diccionario."""
        return {
            "id": self.id,
            "calculo": self.calculation_name,
            "entidad_id": self.entity_id,
            "entidad_tipo": self.entity_type,
            "metodo": self.method,
            "pasos": [s.to_dict() for s in self.steps],
            "entradas_resumen": self.summary_inputs,
            "salidas_resumen": self.summary_outputs,
            "advertencias": self.warnings,
            "realizado_por": self.performed_by,
            "fecha_hora": self.performed_at.isoformat(),
            "version_software": self.software_version,
            "notas": self.notes,
        }

    def __repr__(self) -> str:
        return (
            f"AuditLog('{self.calculation_name}', "
            f"pasos={len(self.steps)}, "
            f"fecha={self.performed_at.strftime('%Y-%m-%d %H:%M')})"
        )


def log_calculation(
    calculation_name: str,
    entity_id: Optional[str] = None,
    entity_type: str = "",
    method: str = "",
    summary_inputs: Optional[dict[str, Any]] = None,
    summary_outputs: Optional[dict[str, Any]] = None,
    performed_by: str = "sistema",
) -> AuditLog:
    """
    Crea y retorna un nuevo ``AuditLog`` para registrar un cálculo.

    Función de conveniencia para inicializar el registro de auditoría
    al comienzo de cualquier cálculo de ingeniería trazado.

    Args:
        calculation_name: Nombre descriptivo del cálculo.
        entity_id: ID de la entidad principal.
        entity_type: Tipo de entidad (clase).
        method: Método o estándar aplicado.
        summary_inputs: Entradas principales del cálculo.
        summary_outputs: Salidas principales del cálculo.
        performed_by: Usuario o proceso que inicia el cálculo.

    Returns:
        Un nuevo ``AuditLog`` inicializado y listo para agregar pasos.

    Example:
        >>> log = log_calculation(
        ...     calculation_name="Diseño AASHTO 93 - Av. Montes",
        ...     entity_id="design-uuid-123",
        ...     entity_type="FlexiblePavementDesign",
        ...     method="AASHTO_93",
        ...     summary_inputs={"ESAL_W18": 1_500_000, "CBR": 6.5},
        ... )
        >>> log.add_step("Estimar MR", formula="MR = 1500 × CBR", ...)
    """
    return AuditLog(
        calculation_name=calculation_name,
        entity_id=entity_id,
        entity_type=entity_type,
        method=method,
        summary_inputs=summary_inputs or {},
        summary_outputs=summary_outputs or {},
        performed_by=performed_by,
    )
