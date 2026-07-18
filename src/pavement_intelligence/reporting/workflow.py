"""Fase 6A: expediente integrado, continuidad, JSON y PDF demostrativos."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from io import BytesIO
import hashlib
import json
import re
from typing import Any, Mapping, MutableMapping

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)


DOSSIER_VERSION = "6A-1.0"
GENERATOR_VERSION = "MVP-REPORT-GENERATOR-1.0"
MANDATORY_WARNING = (
    "Este expediente integra resultados demostrativos generados por diferentes "
    "módulos del sistema.\n\nLa validez técnica depende de la calidad, "
    "representatividad y aprobación profesional de los datos de tránsito, cargas, "
    "geotecnia, parámetros AASHTO y criterios de capas.\n\nEl documento no "
    "constituye un diseño vial aprobado, una especificación constructiva ni una "
    "autorización para ejecutar obras."
)
PHASES = (
    "FASE_2_REVISION_AFORO",
    "FASE_3A_ESAL_OBSERVADO",
    "FASE_3B_ESAL_PROYECTADO",
    "FASE_4A_CBR_MR",
    "FASE_4B_ADOPCION_MR",
    "FASE_5A_SN_REQUERIDO",
    "FASE_5B_DISENO_CAPAS",
)


class PhaseState(str, Enum):
    NOT_STARTED = "NO_INICIADA"
    PENDING = "PENDIENTE"
    BLOCKED = "BLOQUEADA"
    CURRENT = "VIGENTE"
    STALE = "DESACTUALIZADA"
    DEMO_APPROVED = "APROBADA_PARA_DEMOSTRACION"
    EXCLUDED = "EXCLUIDA"


class ContinuityState(str, Enum):
    CONFIRMED = "CONTINUIDAD_CONFIRMADA"
    FINGERPRINT_MISMATCH = "HUELLA_INCOMPATIBLE"
    STALE_TRANSFER = "TRANSFERENCIA_DESACTUALIZADA"
    IDENTIFIER_MISMATCH = "IDENTIFICADOR_INCOMPATIBLE"
    MISSING_PHASE = "FASE_FALTANTE"


class ReportMode(str, Enum):
    COMPLETE = "REPORTE_COMPLETO"
    PARTIAL = "REPORTE_PARCIAL"
    EXECUTIVE = "RESUMEN_EJECUTIVO"
    TRACEABILITY = "ANEXO_TRAZABILIDAD"


@dataclass(frozen=True)
class AdministrativeData:
    project_name: str
    segment: str
    location: str
    organization: str
    responsible: str
    reviewer: str
    observations: str = ""


@dataclass(frozen=True)
class ReportRequest:
    administrative: AdministrativeData
    mode: str
    included_phases: tuple[str, ...]
    partial_report_acknowledged: bool
    include_last_history: bool = False
    format_version: str = "PDF-A4-1.0"
    generator_version: str = GENERATOR_VERSION


@dataclass(frozen=True)
class WarningRecord:
    phase: str
    category: str
    severity: str
    message: str


@dataclass(frozen=True)
class PhaseRecord:
    phase: str
    identifier: str | None
    input_fingerprint: str | None
    result_fingerprint: str | None
    created_at: str | None
    responsible: str | None
    state: str
    main_result: dict[str, Any] | None
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]
    dependency: str | None
    continuity: str
    is_demonstrative: bool


@dataclass(frozen=True)
class IntegratedDossier:
    dossier_id: str
    generated_at: str
    dossier_version: str
    generator_version: str
    administrative: AdministrativeData
    mode: str
    overall_state: str
    phases: tuple[PhaseRecord, ...]
    current_phases: tuple[str, ...]
    stale_phases: tuple[str, ...]
    missing_phases: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[WarningRecord, ...]
    is_demonstrative: bool
    generation_history: tuple[dict[str, Any], ...]
    request_fingerprint: str
    mandatory_warning: str = MANDATORY_WARNING

    def as_dict(self) -> dict[str, Any]:
        return sanitize_export(asdict(self))


_LOCAL_PATH = re.compile(r"(?i)(?:[a-z]:\\|c:/users/|\\users\\|file://)")


def _plain(value: Any) -> Any:
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(x) for x in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def sanitize_export(value: Any) -> Any:
    """Elimina rutas locales y claves de infraestructura antes de exportar."""
    if isinstance(value, Mapping):
        return {
            str(k): sanitize_export(v)
            for k, v in value.items()
            if str(k).lower()
            not in {"local_path", "temp_path", "file_path", "workspace"}
        }
    if isinstance(value, (tuple, list)):
        return [sanitize_export(x) for x in value]
    if isinstance(value, str) and _LOCAL_PATH.search(value):
        return "[RUTA_LOCAL_OMITIDA]"
    return value


def _fingerprint(value: Any) -> str:
    raw = json.dumps(
        sanitize_export(_plain(value)),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def canonical_administrative_data(data: AdministrativeData) -> dict[str, str]:
    """Representa todos los campos administrativos de forma determinista.

    Los nombres se ordenan y los valores se conservan exactamente como fueron
    ingresados: no se recortan espacios ni se normaliza Unicode. La limpieza de
    rutas locales sigue siendo responsabilidad de ``_fingerprint``.
    """
    values = asdict(data)
    return {key: values[key] for key in sorted(values)}


def _canonical_report_request(request: ReportRequest) -> dict[str, Any]:
    """Construye la solicitud estable sin fechas automáticas ni datos binarios."""
    return {
        "administrative": canonical_administrative_data(request.administrative),
        "format_version": request.format_version,
        "generator_version": request.generator_version,
        "include_last_history": request.include_last_history,
        "included_phases": list(request.included_phases),
        "mode": request.mode,
        "partial_report_acknowledged": request.partial_report_acknowledged,
    }


def _warnings(result: Any) -> tuple[str, ...]:
    values = (
        result.get("warnings", ())
        if isinstance(result, Mapping)
        else getattr(result, "warnings", ())
    )
    return tuple(dict.fromkeys(str(x) for x in values if str(x)))


def _record(
    phase: str,
    result: Any,
    *,
    dependency: str | None,
    state: PhaseState | None = None,
    blockers: tuple[str, ...] = (),
) -> PhaseRecord:
    if result is None:
        return PhaseRecord(
            phase,
            None,
            None,
            None,
            None,
            None,
            (state or PhaseState.NOT_STARTED).value,
            None,
            (),
            blockers,
            dependency,
            ContinuityState.MISSING_PHASE.value,
            False,
        )
    payload = sanitize_export(_plain(result))
    stale = bool(getattr(result, "is_stale", False))
    demo = bool(
        getattr(result, "is_demonstrative", False) or payload.get("is_synthetic", False)
    )
    inferred = state or (
        PhaseState.STALE
        if stale
        else PhaseState.DEMO_APPROVED
        if demo
        else PhaseState.CURRENT
    )
    identifier = next(
        (
            str(payload[k])
            for k in ("result_id", "review_id", "study_id")
            if payload.get(k)
        ),
        None,
    )
    fingerprint = payload.get("input_fingerprint") or payload.get("review_fingerprint")
    created = payload.get("created_at") or payload.get("reviewed_at")
    responsible = payload.get("responsible") or payload.get("reviewer")
    return PhaseRecord(
        phase,
        identifier,
        fingerprint,
        fingerprint,
        created,
        responsible,
        inferred.value,
        payload,
        _warnings(result),
        blockers,
        dependency,
        ContinuityState.CONFIRMED.value,
        demo,
    )


def collect_phase_records(session: Mapping[str, Any]) -> tuple[PhaseRecord, ...]:
    approved = bool(session.get("traffic_review_approved"))
    review_events = session.get("vision_events_reviewed") or ()
    review_payload = (
        {
            "approved": approved,
            "reviewed_event_count": len(review_events),
            "source_fingerprint": session.get("traffic_review_source_fingerprint"),
            "is_synthetic": bool(session.get("is_synthetic_review")),
            "rejected_count": sum(
                1
                for x in review_events
                if _plain(x).get("review_status") == "DESCARTADO"
            ),
        }
        if review_events or approved
        else None
    )
    phase2 = _record(
        PHASES[0],
        review_payload,
        dependency=None,
        state=PhaseState.DEMO_APPROVED
        if approved and review_payload and review_payload["is_synthetic"]
        else PhaseState.CURRENT
        if approved
        else PhaseState.PENDING
        if review_payload
        else PhaseState.NOT_STARTED,
        blockers=()
        if approved
        else ("La revisión de aforo no está aprobada.",)
        if review_payload
        else (),
    )
    records = [
        phase2,
        _record(PHASES[1], session.get("esal_phase3_result"), dependency=PHASES[0]),
        _record(PHASES[2], session.get("esal_projection_result"), dependency=PHASES[1]),
        _record(PHASES[3], session.get("geotechnical_phase4a_result"), dependency=None),
        _record(
            PHASES[4], session.get("geotechnical_phase4b_result"), dependency=PHASES[3]
        ),
        _record(
            PHASES[5],
            session.get("aashto93_phase5a_result"),
            dependency=f"{PHASES[2]} + {PHASES[4]}",
        ),
        _record(
            PHASES[6], session.get("aashto93_phase5b_result"), dependency=PHASES[5]
        ),
    ]
    return validate_continuity(tuple(records))


def validate_continuity(records: tuple[PhaseRecord, ...]) -> tuple[PhaseRecord, ...]:
    by_phase = {x.phase: x for x in records}
    output = list(records)

    def mismatch(phase: str, expected: Any, actual: Any) -> None:
        if expected is None or actual is None:
            continuity = ContinuityState.MISSING_PHASE
        elif expected != actual:
            continuity = ContinuityState.FINGERPRINT_MISMATCH
        else:
            return
        index = next(i for i, x in enumerate(output) if x.phase == phase)
        old = output[index]
        output[index] = PhaseRecord(
            **{
                **asdict(old),
                "continuity": continuity.value,
                "state": PhaseState.BLOCKED.value,
                "blockers": old.blockers
                + (f"Continuidad inválida: {continuity.value}.",),
            }
        )

    p3a, p3b = by_phase[PHASES[1]], by_phase[PHASES[2]]
    p4a, p4b = by_phase[PHASES[3]], by_phase[PHASES[4]]
    p5a, p5b = by_phase[PHASES[5]], by_phase[PHASES[6]]
    mismatch(
        PHASES[2],
        p3a.result_fingerprint,
        (p3b.main_result or {}).get("source_esal_fingerprint"),
    )
    mismatch(
        PHASES[4],
        p4a.result_fingerprint,
        (p4b.main_result or {}).get("source_phase4a_fingerprint"),
    )
    if p5a.main_result:
        mismatch(
            PHASES[5],
            p3b.result_fingerprint,
            ((p5a.main_result.get("esal_transfer") or {}).get("phase3b_fingerprint")),
        )
        mismatch(
            PHASES[5],
            p4b.result_fingerprint,
            ((p5a.main_result.get("mr_transfer") or {}).get("phase4b_fingerprint")),
        )
    mismatch(
        PHASES[6],
        p5a.result_fingerprint,
        ((p5b.main_result or {}).get("transfer") or {}).get("phase5a_fingerprint"),
    )
    return tuple(output)


def _warning_category(phase: str, message: str) -> str:
    normalized = message.lower()
    if "huella" in normalized or "transferencia" in normalized:
        return "TRAZABILIDAD"
    if "normativ" in normalized or "oficial" in normalized:
        return "NORMATIVA"
    if "construct" in normalized or "espesor mínimo" in normalized:
        return "CONSTRUCTIBILIDAD"
    if "dato" in normalized or "sintét" in normalized:
        return "DATOS"
    if "5B" in phase:
        return "CAPAS"
    if "5A" in phase:
        return "AASHTO"
    if "4" in phase:
        return "GEOTECNIA"
    if "3" in phase or "AFORO" in phase:
        return "TRANSITO"
    return "METODOLOGIA"


def build_dossier(
    session: Mapping[str, Any],
    request: ReportRequest,
    *,
    generated_at: str | None = None,
) -> IntegratedDossier:
    if request.mode not in {x.value for x in ReportMode}:
        raise ValueError("Modo de reporte desconocido.")
    if not all(
        (
            request.administrative.project_name.strip(),
            request.administrative.segment.strip(),
            request.administrative.responsible.strip(),
        )
    ):
        raise ValueError("Proyecto, tramo y responsable son obligatorios.")
    unknown = set(request.included_phases) - set(PHASES)
    if unknown:
        raise ValueError("Se solicitaron fases desconocidas.")
    records = collect_phase_records(session)
    selected = tuple(x for x in records if x.phase in request.included_phases)
    missing = tuple(
        x.phase for x in selected if x.state == PhaseState.NOT_STARTED.value
    )
    blocked = tuple(f"{x.phase}: {b}" for x in selected for b in x.blockers)
    incomplete = bool(missing or blocked or len(selected) < len(PHASES))
    if request.mode == ReportMode.COMPLETE.value and incomplete:
        raise ValueError(
            "El reporte completo exige todas las fases vigentes y continuas."
        )
    if (
        request.mode == ReportMode.PARTIAL.value
        and not request.partial_report_acknowledged
    ):
        raise ValueError("El reporte parcial exige aceptación explícita.")
    warnings = tuple(
        WarningRecord(
            x.phase,
            _warning_category(x.phase, w),
            "BLOQUEO" if x.blockers else "PRECAUCION",
            w,
        )
        for x in selected
        for w in x.warnings
    )
    warnings += tuple(
        WarningRecord("EXPEDIENTE", "TRAZABILIDAD", "BLOQUEO", x) for x in blocked
    )
    history = ()
    if request.include_last_history:
        history = tuple(
            {"phase": phase, "last_previous": sanitize_export(_plain(values[-1]))}
            for phase, key in (
                (PHASES[1], "esal_result_history"),
                (PHASES[2], "esal_projection_history"),
                (PHASES[3], "geotechnical_phase4a_history"),
                (PHASES[4], "geotechnical_phase4b_history"),
                (PHASES[5], "aashto93_phase5a_history"),
                (PHASES[6], "aashto93_phase5b_history"),
            )
            if (values := session.get(key) or ())
        )
    at = generated_at or datetime.now(timezone.utc).isoformat()
    fp = _fingerprint(
        (
            _canonical_report_request(request),
            selected,
            warnings,
            history,
            GENERATOR_VERSION,
        )
    )
    state = "COMPLETO_DEMOSTRATIVO" if not incomplete else "PARCIAL_DEMOSTRATIVO"
    return IntegratedDossier(
        "dossier-" + _fingerprint((fp, at))[:16],
        at,
        DOSSIER_VERSION,
        GENERATOR_VERSION,
        request.administrative,
        request.mode,
        state,
        selected,
        tuple(
            x.phase
            for x in selected
            if x.state in {PhaseState.CURRENT.value, PhaseState.DEMO_APPROVED.value}
        ),
        tuple(x.phase for x in selected if x.state == PhaseState.STALE.value),
        missing,
        blocked,
        warnings,
        True,
        history,
        fp,
    )


def dossier_is_stale(
    dossier: IntegratedDossier, session: Mapping[str, Any], request: ReportRequest
) -> bool:
    try:
        current = build_dossier(session, request, generated_at=dossier.generated_at)
    except ValueError:
        return True
    return current.request_fingerprint != dossier.request_fingerprint


def dossier_json_bytes(dossier: IntegratedDossier) -> bytes:
    return json.dumps(dossier.as_dict(), ensure_ascii=False, indent=2).encode("utf-8")


def _safe_text(value: Any) -> str:
    text = str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return text.replace("\n", "<br/>")


def dossier_pdf_bytes(dossier: IntegratedDossier) -> bytes:
    """Genera PDF en memoria; no contiene rutas locales ni firma profesional."""
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "TitleMVP",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#17365D"),
        spaceAfter=12,
    )
    h1 = ParagraphStyle(
        "H1MVP",
        parent=styles["Heading1"],
        textColor=colors.HexColor("#17365D"),
        spaceBefore=8,
    )
    body = ParagraphStyle("BodyMVP", parent=styles["BodyText"], leading=14)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Expediente técnico demostrativo Pavement Intelligence",
    )
    story: list[Any] = [
        Spacer(1, 25 * mm),
        Paragraph("EXPEDIENTE TÉCNICO DEMOSTRATIVO", title),
        Paragraph(_safe_text(dossier.administrative.project_name), title),
        Spacer(1, 8 * mm),
        Paragraph(f"Tramo: {_safe_text(dossier.administrative.segment)}", body),
        Paragraph(
            f"Ubicación: {_safe_text(dossier.administrative.location or 'No declarada')}",
            body,
        ),
        Paragraph(
            f"Responsable: {_safe_text(dossier.administrative.responsible)}", body
        ),
        Paragraph(
            f"Versión: {dossier.dossier_version} | Fecha: {_safe_text(dossier.generated_at)}",
            body,
        ),
        Spacer(1, 10 * mm),
        Paragraph(_safe_text(MANDATORY_WARNING), body),
        PageBreak(),
    ]
    story += [
        Paragraph("1. Resumen ejecutivo", h1),
        Paragraph(
            f"Estado general: {dossier.overall_state}. Modo: {dossier.mode}.", body
        ),
        Paragraph(
            f"Fases incluidas: {len(dossier.phases)}. Faltantes: {len(dossier.missing_phases)}. Bloqueos: {len(dossier.blockers)}.",
            body,
        ),
        Spacer(1, 6 * mm),
        Paragraph(
            "Este resumen distingue resultados demostrativos y no verificados; consulte la trazabilidad.",
            body,
        ),
        PageBreak(),
        Paragraph("2. Estado de fases y continuidad", h1),
    ]
    phase_rows = [["Fase", "Estado", "Continuidad", "Huella"]] + [
        [x.phase, x.state, x.continuity, (x.result_fingerprint or "-")[:16]]
        for x in dossier.phases
    ]
    table = LongTable(
        phase_rows, repeatRows=1, colWidths=[58 * mm, 40 * mm, 47 * mm, 28 * mm]
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9EAF7")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story += [table, PageBreak()]
    section_no = 3
    for phase in dossier.phases:
        if dossier.mode == ReportMode.EXECUTIVE.value:
            break
        story += [
            Paragraph(f"{section_no}. {phase.phase}", h1),
            Paragraph(f"Estado: {phase.state} | Continuidad: {phase.continuity}", body),
        ]
        payload = phase.main_result or {}
        summary = [["Campo", "Valor"]]
        for key, value in list(payload.items())[:35]:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)[:500]
            summary.append([_safe_text(key), Paragraph(_safe_text(value), body)])
        t = LongTable(summary, repeatRows=1, colWidths=[52 * mm, 118 * mm])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF2F8")),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story += [t, PageBreak()]
        section_no += 1
    story += [
        Paragraph(f"{section_no}. Matriz de trazabilidad", h1),
        table,
        PageBreak(),
        Paragraph(f"{section_no + 1}. Advertencias y limitaciones", h1),
    ]
    for warning in dossier.warnings:
        story.append(
            Paragraph(
                f"[{warning.category} / {warning.severity}] {warning.phase}: {_safe_text(warning.message)}",
                body,
            )
        )
    story += [
        Spacer(1, 5 * mm),
        Paragraph(_safe_text(MANDATORY_WARNING), body),
        PageBreak(),
        Paragraph(f"{section_no + 2}. Anexo metodológico", h1),
        Paragraph(
            "El expediente integra contratos existentes sin recalcular fórmulas. Las huellas permiten detectar cambios y transferencias incompatibles. No incluye costos, firma, aprobación normativa ni pavimento rígido.",
            body,
        ),
    ]

    def footer(canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(
            18 * mm, 10 * mm, f"Pavement Intelligence - {dossier.dossier_version}"
        )
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Página {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def store_dossier(
    session: MutableMapping[str, Any],
    dossier: IntegratedDossier,
    request: ReportRequest,
    pdf_bytes: bytes,
) -> None:
    previous = session.get("integrated_dossier")
    if isinstance(previous, IntegratedDossier):
        session.setdefault("integrated_dossier_history", []).append(
            {
                "dossier_id": previous.dossier_id,
                "generated_at": previous.generated_at,
                "request_fingerprint": previous.request_fingerprint,
            }
        )
    session["integrated_report_request"] = request
    session["integrated_dossier"] = dossier
    session["integrated_dossier_pdf"] = pdf_bytes
