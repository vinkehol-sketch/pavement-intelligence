from dataclasses import replace
from pathlib import Path

import pytest

from pavement_intelligence.traffic.tpda_workflow import (
    ExpansionMethod,
    FactorTrace,
    MethodologicalStatus,
    PENDING_TRUCK_CATEGORY,
    ProjectionMethod,
    TPDAWorkflowInput,
    TemporalCoverage,
    calculate_tpda_workflow,
    classify_visual_events,
    inspect_csv_temporal_coverage,
    reclassify_pending_trucks,
    result_is_stale,
)
from pavement_intelligence.ui.pages.survey_tpda import _counts_from_review


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def factor(symbol: str, value: float = 1.0, source: str = "Estudio declarado") -> FactorTrace:
    return FactorTrace(
        symbol=symbol,
        name=f"Factor {symbol}",
        value=value,
        function="Corrección declarada",
        source=source,
        applicability="Según estudio",
    )


def workflow_input(**changes) -> TPDAWorkflowInput:
    base = TPDAWorkflowInput(
        batch_id="batch-test",
        source="conteo_revisado",
        data_origin="VIDEO_REVISADO",
        automatic_counts={"AUTO": 10},
        corrected_counts={"AUTO": 10},
        pending_categories={PENDING_TRUCK_CATEGORY: 0},
        temporal_coverage=TemporalCoverage(
            declared_hours=24,
            verified_hours=24,
            duration_source="TIMESTAMPS",
            operator_confirmed=False,
        ),
        expansion_method=ExpansionMethod.NONE_24H,
        temporal_factor=None,
        seasonal_factor=factor("f_e"),
        projection_method=ProjectionMethod.EXPONENTIAL,
        growth_rate_percent=4.0,
        design_period_years=20,
        base_year=2026,
        directional_factor=0.5,
        lane_distribution_factor=1.0,
        reviewer="Auditor",
    )
    return replace(base, **changes)


def test_partial_survey_uses_one_uniform_expansion() -> None:
    data = workflow_input(
        corrected_counts={"AUTO": 10},
        temporal_coverage=TemporalCoverage(2, None, "OPERADOR", True),
        expansion_method=ExpansionMethod.UNIFORM_24_OVER_HOURS,
    )
    result = calculate_tpda_workflow(data)
    assert result.temporal_expansion_factor == 12
    assert result.final_expansion_factor == 12
    assert result.tpda_base_total == 120


def test_documented_factor_prevents_double_expansion() -> None:
    data = workflow_input(
        corrected_counts={"AUTO": 10},
        temporal_coverage=TemporalCoverage(2, None, "OPERADOR", True),
        expansion_method=ExpansionMethod.DOCUMENTED_TEMPORAL_FACTOR,
        temporal_factor=factor("f_n", 8),
    )
    result = calculate_tpda_workflow(data)
    assert result.temporal_expansion_factor == 8
    assert result.tpda_base_total == 80


def test_24h_has_no_additional_expansion() -> None:
    result = calculate_tpda_workflow(workflow_input())
    assert result.temporal_expansion_factor == 1
    assert result.tpda_base_total == 10


def test_24h_file_without_temporal_evidence_is_blocked() -> None:
    data = workflow_input(
        temporal_coverage=TemporalCoverage(24, None, "CSV_SIN_EVIDENCIA", False)
    )
    result = calculate_tpda_workflow(data)
    assert result.methodological_status == MethodologicalStatus.BLOCKED_BY_EXPANSION.value
    assert any("no puede verificarse" in warning for warning in result.warnings)


def test_manual_duration_confirmation_unblocks_24h() -> None:
    data = workflow_input(
        temporal_coverage=TemporalCoverage(24, None, "CONFIRMADA_POR_OPERADOR", True)
    )
    result = calculate_tpda_workflow(data)
    assert result.temporal_coverage_confirmed
    assert result.methodologically_fit_for_next_phase


def test_csv_temporal_evidence_requires_real_temporal_columns() -> None:
    assert not inspect_csv_temporal_coverage(["category_id", "count"])
    assert inspect_csv_temporal_coverage(["timestamp", "category_id", "count"])


def test_ui_uses_workflow_domain_without_local_formulas() -> None:
    source = (
        PROJECT_ROOT
        / "src/pavement_intelligence/ui/pages/survey_tpda.py"
    ).read_text(encoding="utf-8")
    assert "calculate_tpda_workflow(" in source
    assert "calculate_tpda(" not in source
    assert "project_traffic_exponential(" not in source
    assert "project_traffic_linear(" not in source
    assert "24.0 /" not in source


def test_visual_truck_is_not_automatically_c2() -> None:
    counts, pending = classify_visual_events([{"category": "TRUCK"}])
    assert counts["C2"] == 0
    assert pending[PENDING_TRUCK_CATEGORY] == 1


def test_unconfirmed_truck_blocks_next_phase() -> None:
    data = workflow_input(pending_categories={PENDING_TRUCK_CATEGORY: 1})
    result = calculate_tpda_workflow(data)
    assert result.methodological_status == MethodologicalStatus.BLOCKED_BY_CLASSIFICATION.value
    assert not result.methodologically_fit_for_next_phase


def test_manual_truck_reclassification_is_traceable() -> None:
    counts, pending, trace = reclassify_pending_trucks(
        {"AUTO": 10}, 2, "C3", "Se observaron tres ejes", "Revisor 1",
        corrected_at="2026-07-17T20:00:00+00:00",
    )
    assert counts["C3"] == 2
    assert pending[PENDING_TRUCK_CATEGORY] == 0
    assert trace.original_category == PENDING_TRUCK_CATEGORY
    assert trace.corrected_category == "C3"
    assert trace.reason == "Se observaron tres ejes"
    assert trace.reviewer == "Revisor 1"


def test_fdd_is_separate_from_tpda_base() -> None:
    a = calculate_tpda_workflow(workflow_input(directional_factor=0.5))
    b = calculate_tpda_workflow(workflow_input(directional_factor=0.7))
    assert a.tpda_base_total == b.tpda_base_total
    assert a.projected_directional_traffic != b.projected_directional_traffic


def test_fdc_is_separate_from_tpda_base() -> None:
    a = calculate_tpda_workflow(workflow_input(lane_distribution_factor=1.0))
    b = calculate_tpda_workflow(workflow_input(lane_distribution_factor=0.8))
    assert a.tpda_base_total == b.tpda_base_total
    assert a.projected_design_lane_traffic != b.projected_design_lane_traffic


def test_exponential_projection_reference() -> None:
    result = calculate_tpda_workflow(workflow_input())
    assert result.projected_traffic_total == pytest.approx(21.9112, abs=1e-4)
    assert result.projection_method == ProjectionMethod.EXPONENTIAL.value


def test_linear_b_is_marked_academic() -> None:
    result = calculate_tpda_workflow(
        workflow_input(projection_method=ProjectionMethod.LINEAR_B_ACADEMIC)
    )
    assert result.projection_method == "LINEAL_B_ACADEMICA"


def test_linear_a_is_not_a_productive_workflow_option() -> None:
    assert "LINEAR_A" not in ProjectionMethod.__members__
    ui = (
        PROJECT_ROOT / "src/pavement_intelligence/ui/pages/survey_tpda.py"
    ).read_text(encoding="utf-8")
    assert "Lineal A — experimental, no seleccionable" in ui


def test_unsourced_configurable_factor_blocks_approval() -> None:
    data = workflow_input(
        temporal_coverage=TemporalCoverage(2, None, "OPERADOR", True),
        expansion_method=ExpansionMethod.DOCUMENTED_TEMPORAL_FACTOR,
        temporal_factor=factor("f_n", 8, "SIN_FUENTE_DECLARADA"),
    )
    result = calculate_tpda_workflow(data)
    assert result.methodological_status == MethodologicalStatus.BLOCKED_BY_EXPANSION.value
    assert result.factor_traces[0].status == "DEFINIDO_POR_USUARIO_NO_OFICIAL"


def test_changed_input_marks_previous_result_stale_without_deleting_it() -> None:
    original = workflow_input()
    result = calculate_tpda_workflow(original)
    changed = replace(original, corrected_counts={"AUTO": 11})
    assert result_is_stale(result, changed)
    assert result.tpda_base_total == 10


def test_synthetic_data_propagates_and_only_allows_demo() -> None:
    result = calculate_tpda_workflow(
        workflow_input(is_synthetic=True, synthetic_acknowledged=True)
    )
    assert result.is_synthetic
    assert result.methodological_status == MethodologicalStatus.VALID_FOR_DEMONSTRATION.value
    assert not result.methodologically_fit_for_next_phase


def test_synthetic_data_without_acknowledgement_is_blocked() -> None:
    result = calculate_tpda_workflow(workflow_input(is_synthetic=True))
    assert result.methodological_status == MethodologicalStatus.BLOCKED_BY_SYNTHETIC_DATA.value


def test_valid_result_is_fit_for_next_phase_but_does_not_transfer() -> None:
    result = calculate_tpda_workflow(workflow_input())
    assert result.methodological_status == MethodologicalStatus.VALID_TO_CONTINUE.value
    assert result.methodologically_fit_for_next_phase
    assert "esal" not in result.as_dict()
    assert "weighing" not in result.as_dict()


def test_reviewed_counts_are_compatible_and_pending_trucks_preserved() -> None:
    counts, pending = _counts_from_review(
        {"counts_by_category": {"AUTO": 5, "C3": 2, "CAMION": 1}}
    )
    assert counts["AUTO"] == 5
    assert counts["C3"] == 2
    assert counts["C2"] == 0
    assert pending[PENDING_TRUCK_CATEGORY] == 1


def test_result_contains_required_traceability() -> None:
    result = calculate_tpda_workflow(workflow_input())
    payload = result.as_dict()
    required = {
        "calculation_id", "batch_id", "source", "automatic_counts",
        "corrected_counts", "pending_categories", "declared_duration_hours",
        "verified_duration_hours", "duration_source", "expansion_method",
        "final_expansion_factor", "tpda_base_total", "tpda_by_category",
        "projection_method", "growth_rate_percent", "design_period_years",
        "projected_traffic_total", "directional_factor",
        "lane_distribution_factor", "warnings", "assumptions",
        "is_synthetic", "calculated_at", "schema_version",
    }
    assert required <= payload.keys()
