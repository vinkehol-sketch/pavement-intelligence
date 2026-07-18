from dataclasses import replace
from pathlib import Path

import pytest

from pavement_intelligence.esal.workflow import (
    DesignReadiness,
    EQUIVALENCE_METHOD,
    EQUIVALENCE_METHOD_WARNING,
    ESALWorkflowInput,
    ESALWorkflowStatus,
    LoadSource,
    STANDARD_SINGLE_AXLE_KIP,
    STANDARD_SINGLE_AXLE_KN,
    build_esal_input_from_weighing,
    calculate_esal_workflow,
    esal_input_fingerprint,
    esal_result_is_stale,
    store_esal_transfer,
    weighing_transfer_is_current,
)
from pavement_intelligence.traffic.tpda_workflow import (
    ExpansionMethod, FactorTrace, ProjectionMethod, TPDAWorkflowInput,
    TemporalCoverage, calculate_tpda_workflow,
)
from pavement_intelligence.weighing.workflow import (
    AxleGroupLoad, WeighingCondition, WeighingSourceType,
    WeighingWorkflowInput, build_manual_observation,
    build_weighing_input_from_tpda, calculate_weighing_workflow,
)


ROOT = Path(__file__).resolve().parents[2]


def weighing_result(
    *, synthetic=False,
    axles=(("simple_single", 40.0), ("simple_dual", 80.0)), observations=1,
    source_type=WeighingSourceType.STATIC_SCALE,
    condition=None,
):
    tpda = calculate_tpda_workflow(TPDAWorkflowInput(
        batch_id="esal-case", source="manual.csv", data_origin="AFORO_REVISADO",
        automatic_counts={"AUTO": 100, "C2": 10}, corrected_counts={"AUTO": 100, "C2": 10},
        pending_categories={}, temporal_coverage=TemporalCoverage(24, 24, "TIMESTAMPS", False),
        expansion_method=ExpansionMethod.NONE_24H, temporal_factor=None,
        seasonal_factor=FactorTrace("fe", "Identidad", 1.0, "Revisado", "Identidad", "24 h"),
        projection_method=ProjectionMethod.EXPONENTIAL, growth_rate_percent=0.0,
        design_period_years=5, base_year=2026, directional_factor=0.5,
        lane_distribution_factor=1.0, reviewer="Auditor TPDA",
        is_synthetic=synthetic, synthetic_acknowledged=synthetic,
    ))
    transfer = build_weighing_input_from_tpda(tpda, allow_demonstration=synthetic)
    records = tuple(build_manual_observation(
        category="C2", gross_weight=sum(load for _, load in axles), axle_groups=axles,
        unit="kN", source_type=source_type,
        source_reference="balanza-controlada", reviewer="Auditor Pesaje",
        condition=condition or (WeighingCondition.SYNTHETIC if synthetic else WeighingCondition.MEASURED),
        timestamp=f"2026-07-17T20:0{i}:00+00:00",
    ) for i in range(observations))
    return calculate_weighing_workflow(WeighingWorkflowInput(
        tpda_transfer=transfer, observations=records,
        source_type=source_type,
        source_reference="balanza-controlada", source_date="2026-07-17",
        reviewer="Auditor Pesaje", validation_state="REVISADO",
        synthetic_acknowledged=synthetic,
    ))


def esal_input(result=None, **changes):
    result = result or weighing_result()
    transfer = build_esal_input_from_weighing(result, allow_demonstration=result.is_synthetic)
    return ESALWorkflowInput(weighing_transfer=transfer, reviewer="Auditor ESAL", **changes)


def test_accepts_fit_weighing_and_contract_is_complete():
    result = weighing_result()
    contract = build_esal_input_from_weighing(result)
    assert contract.source_weighing_result_id == result.result_id
    assert contract.observation_count == 1
    assert contract.canonical_weight_unit == "kN"
    assert contract.base_tpda_by_category == {"AUTO": 100.0, "C2": 10.0}
    vehicle = contract.vehicles[0]
    assert vehicle.vehicle_id == result.observations[0].record_id
    assert vehicle.approved_category == "C2"
    assert vehicle.canonical_unit == "kN"
    assert vehicle.axle_groups[0].physical_axle_count == 1
    assert vehicle.axle_groups[0].individual_axle_load_kn == 40.0


@pytest.mark.parametrize("change,match", [
    ({"is_stale": True}, "desactualizado"),
    ({"canonical_weight_unit": "t"}, "kN"),
    ({"observations": (), "observation_count": 0}, "vacía"),
])
def test_rejects_invalid_weighing_transfer(change, match):
    with pytest.raises(ValueError, match=match):
        build_esal_input_from_weighing(replace(weighing_result(), **change))


def test_synthetic_transfer_requires_explicit_demonstration():
    result = weighing_result(synthetic=True)
    with pytest.raises(ValueError):
        build_esal_input_from_weighing(result)
    assert build_esal_input_from_weighing(result, allow_demonstration=True).demonstration_mode


def test_transfer_is_manual_and_protected_with_history():
    contract = esal_input().weighing_transfer
    session = {"esal_phase3_result": "anterior", "esal_result": "legacy"}
    assert not store_esal_transfer(session, contract, decision="keep")
    assert store_esal_transfer(session, contract, decision="replace")
    assert session["esal_history"][0]["result"] == "anterior"
    assert session["esal_history"][0]["legacy_esal_result"] == "legacy"
    assert session["esal_input_from_weighing"] == contract
    assert session["esal_result"] == "legacy"


@pytest.mark.parametrize("axle,load", [("simple_dual", 80.0), ("tandem", 142.0), ("tridem", 213.0)])
def test_existing_equivalence_functions_give_one_at_reference_load(axle, load):
    weighing = weighing_result(axles=((axle, load),))
    result = calculate_esal_workflow(esal_input(result=weighing))
    factor = next(item for item in result.axle_factors if item.axle_type == axle)
    assert factor.equivalent_factor == pytest.approx(1.0)
    assert factor.reference_load_kn == load


def test_load_sources_are_explicit_and_never_promote_estimated_to_measured():
    wim = build_esal_input_from_weighing(weighing_result(source_type=WeighingSourceType.WIM))
    assert wim.vehicles[0].load_source == LoadSource.WIM_MEASURED.value
    manual = build_esal_input_from_weighing(weighing_result())
    assert manual.vehicles[0].load_source == LoadSource.MANUAL_VERIFIED.value
    estimated_result = weighing_result(condition=WeighingCondition.ASSUMED)
    estimated = build_esal_input_from_weighing(estimated_result)
    assert estimated.vehicles[0].load_source == LoadSource.ESTIMATED_BY_CATEGORY.value
    assert "no corresponde a una medición" in estimated.vehicles[0].quality_warnings[0]
    synthetic = build_esal_input_from_weighing(
        weighing_result(synthetic=True), allow_demonstration=True
    )
    assert synthetic.vehicles[0].load_source == LoadSource.SYNTHETIC_DEMONSTRATION.value


def test_vehicle_and_category_truck_factor_are_reproducible():
    result = calculate_esal_workflow(esal_input(result=weighing_result(
        axles=(("simple_single", 40.0), ("simple_dual", 80.0)), observations=2)))
    expected = (40 / 80) ** 4 + 1
    assert result.vehicle_factors[0].vehicle_factor == pytest.approx(expected)
    assert result.truck_factors_by_category[0].mean_truck_factor == pytest.approx(expected)
    assert result.truck_factors_by_category[0].observed_vehicles == 2
    assert result.analyzed_batch_vehicle_count == 2
    assert result.analyzed_batch_esal == pytest.approx(expected * 2)
    assert result.batch_esal_by_category == {"C2": pytest.approx(expected * 2)}
    assert result.batch_esal_by_load_source == {
        LoadSource.MANUAL_VERIFIED.value: pytest.approx(expected * 2)
    }
    assert result.manual_vehicle_percent == pytest.approx(100.0)


def test_small_independent_numerical_case_fdd_fdc_period_and_light_traffic():
    result = calculate_esal_workflow(esal_input())
    # C2 válido: simple 40 kN + simple dual 80 kN = factor 1,0625.
    assert result.initial_annual_esal == pytest.approx(1825.0 * 1.0625)
    assert result.accumulated_esal == pytest.approx(9125.0 * 1.0625)
    assert len(result.annual_esal) == 5
    auto = next(row for row in result.traffic_by_category if row.category == "AUTO")
    assert auto.truck_factor == 0
    assert auto.accumulated_esal == 0


def test_growth_is_accumulated_annually():
    data = esal_input()
    transfer = replace(data.weighing_transfer, growth_rate_percent=10.0)
    result = calculate_esal_workflow(replace(data, weighing_transfer=transfer))
    assert result.annual_esal[1].annual_esal == pytest.approx(1825 * 1.0625 * 1.1)


def test_outliers_are_included_by_default_and_excluded_only_with_traceability():
    data = esal_input()
    record_id = data.weighing_transfer.observations[0].record_id
    marked = replace(data.weighing_transfer, outlier_record_ids=(record_id,))
    included = calculate_esal_workflow(replace(data, weighing_transfer=marked))
    assert included.vehicle_factors[0].included
    excluded = calculate_esal_workflow(replace(
        data, weighing_transfer=marked, excluded_observation_ids=(record_id,),
        exclusion_reason="Decisión documentada"))
    assert not excluded.vehicle_factors[0].included
    assert excluded.excluded_observation_ids == (record_id,)
    with pytest.raises(ValueError, match="atípicos"):
        calculate_esal_workflow(replace(data, excluded_observation_ids=(record_id,), exclusion_reason="x"))


def test_synthetic_state_is_blocked_until_acknowledged_then_demo_only():
    data = esal_input(weighing_result(synthetic=True))
    blocked = calculate_esal_workflow(data)
    assert blocked.methodological_status == ESALWorkflowStatus.BLOCKED_BY_SYNTHETIC_DATA.value
    demo = calculate_esal_workflow(replace(data, synthetic_acknowledged=True))
    assert demo.design_readiness == DesignReadiness.DEMONSTRATION_ONLY.value
    assert demo.is_synthetic


def test_estimated_state_is_blocked_until_visibly_acknowledged():
    data = esal_input(weighing_result(condition=WeighingCondition.ASSUMED))
    blocked = calculate_esal_workflow(data)
    assert blocked.methodological_status == ESALWorkflowStatus.BLOCKED_BY_ESTIMATED_DATA.value
    acknowledged = calculate_esal_workflow(replace(data, estimated_data_acknowledged=True))
    assert acknowledged.methodological_status == ESALWorkflowStatus.VALID_TO_CONTINUE.value
    assert acknowledged.estimated_vehicle_percent == pytest.approx(100.0)


def test_real_result_is_fit_for_future_audit_and_uses_declared_standard():
    result = calculate_esal_workflow(esal_input())
    assert result.methodological_status == ESALWorkflowStatus.VALID_TO_CONTINUE.value
    assert result.design_readiness == DesignReadiness.FIT.value
    assert result.equivalence_method == EQUIVALENCE_METHOD
    assert result.standard_single_axle_kn == STANDARD_SINGLE_AXLE_KN
    assert result.standard_single_axle_kip == STANDARD_SINGLE_AXLE_KIP
    assert result.equivalence_method_warning == EQUIVALENCE_METHOD_WARNING
    assert "no es un resultado oficial" in result.equivalence_method_warning
    assert "DISENO" not in result.design_readiness


def test_invalid_load_and_incomplete_configuration_are_blocked():
    data = esal_input()
    obs = data.weighing_transfer.observations[0]
    bad_group = AxleGroupLoad(1, "simple_dual", 0.0, "test")
    bad_obs = replace(obs, axle_groups=(bad_group,))
    bad_transfer = replace(data.weighing_transfer, observations=(bad_obs,))
    result = calculate_esal_workflow(replace(data, weighing_transfer=bad_transfer))
    assert result.methodological_status == ESALWorkflowStatus.BLOCKED_BY_EQUIVALENCE_FACTORS.value
    empty_obs = replace(obs, axle_groups=())
    empty_transfer = replace(data.weighing_transfer, observations=(empty_obs,))
    result = calculate_esal_workflow(replace(data, weighing_transfer=empty_transfer))
    assert result.methodological_status == ESALWorkflowStatus.BLOCKED_BY_AXLE_CONFIGURATION.value


def test_gross_weight_mismatch_and_unconfirmed_truck_are_blocked():
    data = esal_input()
    obs = data.weighing_transfer.observations[0]
    mismatch = replace(obs, gross_weight_kn=160.0)
    transfer = replace(data.weighing_transfer, observations=(mismatch,))
    result = calculate_esal_workflow(replace(data, weighing_transfer=transfer))
    assert result.methodological_status == ESALWorkflowStatus.BLOCKED_BY_LOADS.value
    assert result.rejected_vehicle_ids == (obs.record_id,)
    assert result.analyzed_batch_vehicle_count == 0
    assert result.analyzed_batch_esal == 0
    assert not result.vehicle_factors[0].included

    truck = replace(obs, category="CAMION")
    transfer = replace(data.weighing_transfer, observations=(truck,))
    result = calculate_esal_workflow(replace(data, weighing_transfer=transfer))
    assert result.methodological_status == ESALWorkflowStatus.BLOCKED_BY_CLASSIFICATION.value
    assert result.pending_vehicle_ids == (obs.record_id,)


def test_fingerprints_and_staleness_cover_input_weighing_method_and_standard():
    current_weighing = weighing_result()
    data = esal_input(current_weighing)
    result = calculate_esal_workflow(data)
    assert esal_input_fingerprint(data) == esal_input_fingerprint(data)
    assert not esal_result_is_stale(result, data, current_weighing)
    assert esal_input_fingerprint(data) != esal_input_fingerprint(replace(data, pavement_type="OTRO"))
    assert esal_input_fingerprint(data) != esal_input_fingerprint(replace(data, standard_single_axle_kn=80.07))
    changed_weighing = replace(weighing_result(), result_id="otro")
    assert not weighing_transfer_is_current(data.weighing_transfer, changed_weighing)


def test_esal_ui_excludes_raw_sources_and_design_does_not_consume_new_result():
    esal_source = (ROOT / "src/pavement_intelligence/ui/pages/esal_calculator.py").read_text("utf-8")
    assert "traffic_counts_corrected" not in esal_source
    assert "tpda_phase1_result" not in esal_source
    assert "YOLO" not in esal_source
    assert 'st.session_state["esal_phase3_result"]' in esal_source
    design_sources = "\n".join(p.read_text("utf-8") for p in (ROOT / "src/pavement_intelligence/ui/pages").glob("*design*.py"))
    assert "esal_phase3_result" not in design_sources
