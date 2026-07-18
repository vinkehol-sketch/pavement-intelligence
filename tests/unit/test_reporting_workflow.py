from dataclasses import replace
import json
import pdfplumber
import pytest
from pypdf import PdfReader

from pavement_intelligence.reporting.workflow import (
    GENERATOR_VERSION,
    MANDATORY_WARNING,
    PHASES,
    AdministrativeData,
    ContinuityState,
    IntegratedDossier,
    PhaseState,
    ReportMode,
    ReportRequest,
    build_dossier,
    canonical_administrative_data,
    collect_phase_records,
    dossier_is_stale,
    dossier_json_bytes,
    dossier_pdf_bytes,
    sanitize_export,
    store_dossier,
)


def complete_session():
    return {
        "traffic_review_approved": True,
        "vision_events_reviewed": ({"review_status": "APROBADO"},),
        "traffic_review_source_fingerprint": "fp-review",
        "is_synthetic_review": True,
        "esal_phase3_result": {
            "result_id": "3a",
            "input_fingerprint": "fp3a",
            "created_at": "2026",
            "accumulated_esal": 100,
            "warnings": ["demo 3a"],
        },
        "esal_projection_result": {
            "result_id": "3b",
            "input_fingerprint": "fp3b",
            "source_esal_fingerprint": "fp3a",
            "accumulated_esal": 5_000_000,
            "base_year": 2026,
            "projection_years": 20,
            "warnings": ["demo 3b"],
        },
        "geotechnical_phase4a_result": {
            "result_id": "4a",
            "study_id": "GEO",
            "input_fingerprint": "fp4a",
            "design_cbr_percent": 8,
            "warnings": ["demo 4a"],
        },
        "geotechnical_phase4b_result": {
            "review_id": "4b",
            "input_fingerprint": "fp4b",
            "source_phase4a_fingerprint": "fp4a",
            "adopted_resilient_modulus_mpa": 55,
            "source": "CORRELACION_EMPIRICA",
            "warnings": ["demo 4b"],
        },
        "aashto93_phase5a_result": {
            "result_id": "5a",
            "input_fingerprint": "fp5a",
            "required_sn": 4.04,
            "w18": 5_000_000,
            "mr_psi": 10_000,
            "reliability_percent": 90,
            "zr": -1.282,
            "s0": 0.45,
            "p0": 4.2,
            "pt": 2.5,
            "delta_psi": 1.7,
            "equation": "AASHTO 93",
            "iterations": 29,
            "residual": 4e-9,
            "esal_transfer": {"phase3b_fingerprint": "fp3b"},
            "mr_transfer": {"phase4b_fingerprint": "fp4b"},
            "warnings": ["demo 5a"],
        },
        "aashto93_phase5b_result": {
            "result_id": "5b",
            "input_fingerprint": "fp5b",
            "required_sn": 4.04,
            "provided_sn": 4.16,
            "status": "CUMPLE_CON_EXCEDENTE",
            "deficit": 0,
            "excess": 0.12,
            "contributions": [
                {
                    "layer_type": "BASE",
                    "thickness_in": 6,
                    "structural_coefficient": 0.14,
                    "drainage_coefficient": 1,
                }
            ],
            "transfer": {"phase5a_fingerprint": "fp5a"},
            "warnings": ["demo 5b"],
        },
    }


def admin(**changes):
    return replace(
        AdministrativeData(
            "Proyecto vial",
            "Tramo A",
            "La Paz",
            "Entidad",
            "Ing. Responsable",
            "Ing. Revisor",
            "Demostración",
        ),
        **changes,
    )


def request(mode=ReportMode.COMPLETE.value, phases=PHASES, ack=False, **changes):
    return replace(ReportRequest(admin(), mode, tuple(phases), ack), **changes)


def test_complete_contract_is_frozen_serializable_versioned_and_fingerprinted():
    dossier = build_dossier(complete_session(), request(), generated_at="2026-07-18")
    assert (
        isinstance(dossier, IntegratedDossier) and dossier.dossier_version == "6A-1.0"
    )
    assert (
        dossier.generator_version == GENERATOR_VERSION
        and len(dossier.request_fingerprint) == 64
    )
    json.dumps(dossier.as_dict(), ensure_ascii=False)
    with pytest.raises(Exception):
        dossier.mode = "OTRO"


def test_all_required_phases_are_present_current_and_continuous():
    records = collect_phase_records(complete_session())
    assert tuple(x.phase for x in records) == PHASES
    assert all(x.continuity == ContinuityState.CONFIRMED.value for x in records)
    assert all(
        x.state in {PhaseState.CURRENT.value, PhaseState.DEMO_APPROVED.value}
        for x in records
    )


@pytest.mark.parametrize(
    "phase,key,nested",
    [
        (PHASES[2], "esal_projection_result", "source_esal_fingerprint"),
        (PHASES[4], "geotechnical_phase4b_result", "source_phase4a_fingerprint"),
    ],
)
def test_upstream_fingerprint_mismatch_blocks(phase, key, nested):
    session = complete_session()
    session[key][nested] = "wrong"
    record = next(x for x in collect_phase_records(session) if x.phase == phase)
    assert record.state == PhaseState.BLOCKED.value
    assert record.continuity == ContinuityState.FINGERPRINT_MISMATCH.value


def test_phase5a_and_phase5b_stale_transfers_block():
    session = complete_session()
    session["aashto93_phase5a_result"]["esal_transfer"]["phase3b_fingerprint"] = "old"
    assert (
        next(x for x in collect_phase_records(session) if x.phase == PHASES[5]).state
        == PhaseState.BLOCKED.value
    )
    session = complete_session()
    session["aashto93_phase5b_result"]["transfer"]["phase5a_fingerprint"] = "old"
    assert (
        next(x for x in collect_phase_records(session) if x.phase == PHASES[6]).state
        == PhaseState.BLOCKED.value
    )


def test_missing_phase_is_explicit_and_complete_report_blocks():
    session = complete_session()
    del session["geotechnical_phase4a_result"]
    record = next(x for x in collect_phase_records(session) if x.phase == PHASES[3])
    assert record.state == PhaseState.NOT_STARTED.value
    with pytest.raises(ValueError, match="completo"):
        build_dossier(session, request())


def test_partial_requires_acknowledgement_then_lists_missing():
    session = {}
    with pytest.raises(ValueError, match="aceptación"):
        build_dossier(session, request(ReportMode.PARTIAL.value, ack=False))
    dossier = build_dossier(session, request(ReportMode.PARTIAL.value, ack=True))
    assert dossier.missing_phases and dossier.overall_state == "PARCIAL_DEMOSTRATIVO"


@pytest.mark.parametrize(
    "mode", [ReportMode.EXECUTIVE.value, ReportMode.TRACEABILITY.value]
)
def test_summary_and_traceability_modes(mode):
    dossier = build_dossier(complete_session(), request(mode))
    assert dossier.mode == mode and dossier.phases


def test_unknown_mode_phase_and_missing_admin_block():
    with pytest.raises(ValueError, match="Modo"):
        build_dossier({}, request("OTRO"))
    with pytest.raises(ValueError, match="desconocidas"):
        build_dossier({}, request(ReportMode.PARTIAL.value, ("X",), True))
    with pytest.raises(ValueError, match="obligatorios"):
        build_dossier(
            {},
            replace(
                request(ReportMode.PARTIAL.value, ack=True),
                administrative=admin(project_name=""),
            ),
        )


def test_warnings_are_grouped_by_phase_without_within_phase_duplicates():
    session = complete_session()
    session["esal_phase3_result"]["warnings"] = ["igual", "igual"]
    dossier = build_dossier(session, request())
    same = [
        x for x in dossier.warnings if x.phase == PHASES[1] and x.message == "igual"
    ]
    assert len(same) == 1 and same[0].category == "TRANSITO"


def test_json_has_units_warnings_missing_phases_and_no_local_paths():
    session = complete_session()
    session["aashto93_phase5b_result"]["local_path"] = r"C:\Users\Pc\secret.tmp"
    dossier = build_dossier(session, request())
    raw = dossier_json_bytes(dossier)
    text = raw.decode("utf-8")
    assert "thickness_in" in text and MANDATORY_WARNING.split("\n")[0] in text
    assert "C:\\Users" not in text and "secret.tmp" not in text


@pytest.mark.parametrize(
    "value", [r"C:\Users\Pc\x", "file://secret", {"file_path": "x"}]
)
def test_privacy_sanitizer_omits_sensitive_paths(value):
    cleaned = sanitize_export(value)
    assert "C:\\Users" not in json.dumps(cleaned) and "file://" not in json.dumps(
        cleaned
    )


def test_pdf_is_valid_multipage_legible_spanish_and_private():
    dossier = build_dossier(complete_session(), request(), generated_at="2026-07-18")
    pdf = dossier_pdf_bytes(dossier)
    assert pdf.startswith(b"%PDF") and len(pdf) > 5_000
    reader = PdfReader(__import__("io").BytesIO(pdf))
    assert len(reader.pages) >= 10
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    normalized = " ".join(text.split())
    assert "EXPEDIENTE TÉCNICO DEMOSTRATIVO" in text
    assert "autorización para ejecutar obras" in normalized
    assert "C:\\Users" not in text and "Página" in text
    with pdfplumber.open(__import__("io").BytesIO(pdf)) as document:
        assert len(document.pages) == len(reader.pages)


def test_partial_and_executive_pdf_are_created_with_controlled_pages():
    partial = build_dossier({}, request(ReportMode.PARTIAL.value, PHASES[:2], True))
    executive = build_dossier(complete_session(), request(ReportMode.EXECUTIVE.value))
    assert (
        len(PdfReader(__import__("io").BytesIO(dossier_pdf_bytes(partial))).pages) >= 5
    )
    assert (
        len(PdfReader(__import__("io").BytesIO(dossier_pdf_bytes(executive))).pages)
        >= 5
    )


def test_pdf_handles_long_tables_and_page_breaks():
    session = complete_session()
    session["aashto93_phase5b_result"]["contributions"] *= 80
    pdf = dossier_pdf_bytes(build_dossier(session, request()))
    assert len(PdfReader(__import__("io").BytesIO(pdf)).pages) >= 10


def test_dossier_staleness_covers_admin_phase_mode_and_history():
    session = complete_session()
    original_request = request()
    dossier = build_dossier(session, original_request)
    assert not dossier_is_stale(dossier, session, original_request)
    assert dossier_is_stale(
        dossier,
        session,
        replace(original_request, administrative=admin(location="Otra")),
    )
    changed = complete_session()
    changed["aashto93_phase5b_result"]["provided_sn"] = 9
    assert dossier_is_stale(dossier, changed, original_request)
    assert dossier_is_stale(
        dossier, session, replace(original_request, mode=ReportMode.EXECUTIVE.value)
    )
    assert dossier_is_stale(
        dossier, session, replace(original_request, include_last_history=True)
    )


@pytest.mark.parametrize(
    ("field", "changed_value"),
    [
        ("project_name", "Proyecto vial actualizado"),
        ("segment", "Tramo B"),
        ("location", "Cochabamba"),
        ("organization", "Otra entidad"),
        ("responsible", "Otra responsable"),
        ("reviewer", "Otro revisor"),
        ("observations", "Observación administrativa actualizada"),
    ],
)
def test_every_exported_administrative_field_invalidates_report(field, changed_value):
    session = complete_session()
    original_request = request()
    original = build_dossier(session, original_request)
    changed_request = replace(
        original_request,
        administrative=replace(
            original_request.administrative, **{field: changed_value}
        ),
    )
    changed = build_dossier(session, changed_request)

    assert changed.request_fingerprint != original.request_fingerprint
    assert dossier_is_stale(original, session, changed_request)
    assert [phase.result_fingerprint for phase in changed.phases] == [
        phase.result_fingerprint for phase in original.phases
    ]
    assert [phase.main_result for phase in changed.phases] == [
        phase.main_result for phase in original.phases
    ]


def test_administrative_canonicalization_is_stable_and_preserves_exact_text():
    values = {
        "project_name": "Proyecto Ñ",
        "segment": "Tramo A",
        "location": "La Paz",
        "organization": "Entidad",
        "responsible": "Responsable",
        "reviewer": "Revisor",
        "observations": "Observación",
    }
    reversed_values = dict(reversed(tuple(values.items())))
    first = AdministrativeData(**values)
    second = AdministrativeData(**reversed_values)

    assert canonical_administrative_data(first) == canonical_administrative_data(second)
    assert (
        build_dossier(
            complete_session(), replace(request(), administrative=first)
        ).request_fingerprint
        == build_dossier(
            complete_session(), replace(request(), administrative=second)
        ).request_fingerprint
    )

    spaced = replace(first, project_name=" Proyecto Ñ")
    assert canonical_administrative_data(spaced)["project_name"] == " Proyecto Ñ"
    assert (
        build_dossier(
            complete_session(), replace(request(), administrative=spaced)
        ).request_fingerprint
        != build_dossier(
            complete_session(), replace(request(), administrative=first)
        ).request_fingerprint
    )


def test_automatic_generation_date_does_not_change_request_fingerprint():
    first = build_dossier(complete_session(), request(), generated_at="2026-07-18")
    second = build_dossier(complete_session(), request(), generated_at="2026-07-19")
    assert first.request_fingerprint == second.request_fingerprint


def test_json_and_pdf_reflect_changed_administrative_data_without_local_paths():
    changed_admin = admin(
        project_name="Proyecto Ñ actualizado",
        segment="Tramo B",
        location="Cochabamba",
        organization="Entidad actualizada",
        responsible="Responsable actualizada",
        reviewer="Revisor actualizado",
        observations="Observación actualizada",
    )
    dossier = build_dossier(
        complete_session(), replace(request(), administrative=changed_admin)
    )
    json_text = dossier_json_bytes(dossier).decode("utf-8")
    pdf_text = "\n".join(
        page.extract_text() or ""
        for page in PdfReader(
            __import__("io").BytesIO(dossier_pdf_bytes(dossier))
        ).pages
    )

    for value in canonical_administrative_data(changed_admin).values():
        assert value in json_text
    for value in (
        changed_admin.project_name,
        changed_admin.segment,
        changed_admin.location,
        changed_admin.responsible,
    ):
        assert value in pdf_text
    assert "C:\\Users" not in json_text and "C:\\Users" not in pdf_text


def test_store_preserves_generation_history_without_overwrite():
    session = complete_session()
    req = request()
    first = build_dossier(session, req)
    store_dossier(session, first, req, dossier_pdf_bytes(first))
    second = build_dossier(session, replace(req, administrative=admin(location="Otra")))
    store_dossier(session, second, req, dossier_pdf_bytes(second))
    assert session["integrated_dossier_history"][0]["dossier_id"] == first.dossier_id
    assert session["integrated_dossier"] == second
