"""Pruebas independientes del flujo temporal ESAL Fase 3B."""
from dataclasses import replace
import math

import pytest

from pavement_intelligence.esal.projection_workflow import (
    PROJECTION_METHOD_LABEL, PROJECTION_WARNING,
    CategoryGrowthRate, ProjectionStatus, ProjectionWorkflowInput,
    TemporalFactorSource, build_projection_transfer, build_temporal_base,
    calculate_projection_workflow, projection_input_fingerprint,
    projection_result_is_stale, projection_transfer_is_current,
    store_projection_transfer,
)
from pavement_intelligence.esal.workflow import calculate_esal_workflow
from test_esal_workflow import esal_input, weighing_result


def source_result(*, vehicles=1):
    return calculate_esal_workflow(esal_input(result=weighing_result(observations=vehicles)))


def temporal(hours=24.0, source=TemporalFactorSource.CALCULATED_DURATION, manual=None):
    return build_temporal_base(
        start_at=None, end_at=None, observed_hours=hours, observed_days=hours / 24 if hours else None,
        factor_source=source, source_reference="registro controlado", responsible="Auditor temporal",
        justification="Cobertura revisada", manual_factor=manual,
    )


def workflow(result=None, **changes):
    transfer = build_projection_transfer(result or source_result(), transferred_at="2026-07-18T00:00:00+00:00")
    rates = tuple(CategoryGrowthRate(c, 0.0, "estudio", "REVISADA") for c in transfer.categories)
    values = dict(transfer=transfer, temporal_base=temporal(), base_year=2026,
                  projection_years=5, directional_distribution_factor=0.5,
                  lane_distribution_factor=1.0, operating_days_per_year=365,
                  growth_rates=rates, reviewer="Auditor 3B")
    values.update(changes)
    return ProjectionWorkflowInput(**values)


def exact_ten_esal_result():
    base = source_result(vehicles=10)
    factors = tuple(replace(x, vehicle_factor=1.0) for x in base.vehicle_factors)
    return replace(base, vehicle_factors=factors, analyzed_batch_esal=10.0,
                   batch_esal_by_category={"C2": 10.0},
                   batch_esal_by_load_source={"MANUAL_VERIFICADO": 10.0})


def test_known_independent_zero_growth_case():
    result = calculate_projection_workflow(workflow(exact_ten_esal_result()))
    assert result.observed_batch_esal == pytest.approx(10)
    assert result.average_esal_per_vehicle == pytest.approx(1)
    assert result.base_daily_esal == pytest.approx(10)
    assert result.distributed_daily_esal == pytest.approx(5)
    assert result.base_annual_esal == pytest.approx(1825)
    assert result.accumulated_esal == pytest.approx(9125)
    assert result.annual_series[0].year_index == 0
    assert result.annual_series[1].calendar_year == 2027
    assert all(row.annual_projected_esal == pytest.approx(1825) for row in result.annual_series)
    assert result.method_label == PROJECTION_METHOD_LABEL
    assert result.method_warning == PROJECTION_WARNING
    assert "esal_design" not in result.as_dict()


@pytest.mark.parametrize("hours,factor", [(24, 1), (12, 2), (48, .5), (72, 1/3)])
def test_temporal_duration_normalizes_partial_and_multiday(hours, factor):
    assert temporal(hours).expansion_factor_to_daily == pytest.approx(factor)


def test_dates_must_be_coherent_and_match_hours():
    with pytest.raises(ValueError, match="posterior"):
        build_temporal_base(start_at="2026-01-02T00:00:00", end_at="2026-01-01T00:00:00",
            observed_hours=None, observed_days=None, factor_source=TemporalFactorSource.CALCULATED_DURATION,
            source_reference="x", responsible="r", justification="j")
    with pytest.raises(ValueError, match="no coinciden"):
        build_temporal_base(start_at="2026-01-01T00:00:00", end_at="2026-01-02T00:00:00",
            observed_hours=12, observed_days=1, factor_source=TemporalFactorSource.CALCULATED_DURATION,
            source_reference="x", responsible="r", justification="j")


def test_unknown_duration_blocks_definitive_daily_result():
    unknown = build_temporal_base(start_at=None, end_at=None, observed_hours=None, observed_days=None,
        factor_source=TemporalFactorSource.DEMONSTRATION, source_reference="sin metadata",
        responsible="Auditor", justification="Explorar sin afirmar duración")
    result = calculate_projection_workflow(workflow(temporal_base=unknown))
    assert result.methodological_status == ProjectionStatus.BLOCKED_UNKNOWN_DURATION.value
    assert result.base_daily_esal == 0
    assert any("no se produce ESAL diario definitivo" in x for x in result.warnings)


@pytest.mark.parametrize("field,value", [
    ("directional_distribution_factor", 0), ("lane_distribution_factor", 1.1),
    ("operating_days_per_year", 0), ("operating_days_per_year", 367),
    ("operating_days_per_year", 365.5), ("projection_years", 0),
])
def test_invalid_factors_days_and_period_are_rejected(field, value):
    with pytest.raises((TypeError, ValueError)):
        calculate_projection_workflow(workflow(**{field: value}))


@pytest.mark.parametrize("rate", [-99.9, -2, 0, 4.5])
def test_growth_supports_valid_negative_zero_and_positive(rate):
    data = workflow()
    rates = tuple(replace(x, annual_rate_percent=rate) for x in data.growth_rates)
    result = calculate_projection_workflow(replace(data, growth_rates=rates))
    assert result.category_annual_series[1].growth_multiplier == pytest.approx(1 + rate / 100)
    explicit = sum(row.annual_projected_esal for row in result.annual_series)
    assert result.accumulated_esal == pytest.approx(explicit)


@pytest.mark.parametrize("rate", [-100, float("nan"), float("inf")])
def test_invalid_growth_is_rejected(rate):
    data = workflow()
    rates = tuple(replace(x, annual_rate_percent=rate) for x in data.growth_rates)
    with pytest.raises(ValueError, match="Tasa inválida"):
        calculate_projection_workflow(replace(data, growth_rates=rates))


def test_missing_duplicate_and_global_rate_policies_are_not_silent():
    data = workflow()
    with pytest.raises(ValueError, match="Faltan tasas"):
        calculate_projection_workflow(replace(data, growth_rates=()))
    with pytest.raises(ValueError, match="duplicada"):
        calculate_projection_workflow(replace(data, growth_rates=data.growth_rates * 2))
    with pytest.raises(ValueError, match="explícita"):
        calculate_projection_workflow(replace(data, growth_policy="GLOBAL"))


def test_breakdowns_and_percentages_are_consistent():
    result = calculate_projection_workflow(workflow())
    assert sum(x.accumulated_esal for x in result.categories) == pytest.approx(result.accumulated_esal)
    assert sum(x.accumulated_esal for x in result.source_breakdown) == pytest.approx(result.accumulated_esal)
    assert sum(x.total_percent for x in result.categories) == pytest.approx(100)
    assert sum(x.total_percent for x in result.source_breakdown) == pytest.approx(100)
    assert math.isfinite(result.accumulated_esal)


def test_manual_and_tpda_factors_are_explicit_and_fingerprinted():
    manual = temporal(12, TemporalFactorSource.MANUAL, 3.0)
    tpda = temporal(12, TemporalFactorSource.TPDA, 1.75)
    assert manual.expansion_factor_to_daily == 3.0
    assert tpda.expansion_factor_to_daily == 1.75
    base = workflow(temporal_base=manual)
    assert projection_input_fingerprint(base) != projection_input_fingerprint(
        replace(base, temporal_base=tpda)
    )


@pytest.mark.parametrize("manual", [0, -1, float("nan"), float("inf")])
def test_invalid_manual_temporal_factor_is_rejected(manual):
    with pytest.raises(ValueError, match="factor manual"):
        temporal(12, TemporalFactorSource.MANUAL, manual)


def test_transfer_rejects_stale_blocked_empty_rejected_and_pending_sources():
    valid = source_result()
    for changed in (
        replace(valid, is_stale=True),
        replace(valid, analyzed_batch_vehicle_count=0, vehicle_factors=(), analyzed_batch_esal=0),
        replace(valid, rejected_vehicle_ids=("x",)),
        replace(valid, pending_vehicle_ids=("x",)),
    ):
        with pytest.raises(ValueError):
            build_projection_transfer(changed)


def test_transfer_is_manual_current_fingerprinted_and_preserves_history():
    current = source_result()
    data = workflow(current)
    result = calculate_projection_workflow(data)
    assert projection_transfer_is_current(data.transfer, current)
    assert not projection_result_is_stale(result, data, current)
    assert projection_input_fingerprint(data) != projection_input_fingerprint(replace(data, operating_days_per_year=300))
    assert projection_result_is_stale(result, replace(data, operating_days_per_year=300), current)
    session = {"esal_projection_result": result}
    assert not store_projection_transfer(session, data.transfer, decision="keep")
    assert store_projection_transfer(session, data.transfer, decision="replace")
    assert session["esal_projection_history"][0]["result"] == result
