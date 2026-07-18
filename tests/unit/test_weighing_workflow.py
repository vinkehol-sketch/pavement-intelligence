from dataclasses import replace
from pathlib import Path

import pytest

from pavement_intelligence.traffic.tpda_workflow import (
    ExpansionMethod,
    FactorTrace,
    MethodologicalStatus,
    ProjectionMethod,
    TPDAWorkflowInput,
    TemporalCoverage,
    calculate_tpda_workflow,
)
from pavement_intelligence.weighing.workflow import (
    ESALReadiness,
    WeighingCondition,
    WeighingSourceType,
    WeighingStatus,
    WeighingWorkflowInput,
    build_manual_observation,
    build_weighing_input_from_tpda,
    calculate_weighing_workflow,
    convert_to_kn,
    parse_weighing_csv,
    store_weighing_records,
    store_weighing_transfer,
    tpda_transfer_is_current,
    weighing_input_fingerprint,
    weighing_result_is_stale,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_CSV = PROJECT_ROOT / "data/samples/caso_demostrativo/pesaje_vehicular.csv"


def tpda_result(*, synthetic=False, pending=0):
    data = TPDAWorkflowInput(
        batch_id="batch-weight",
        source="video.mp4",
        data_origin="VIDEO_REVISADO",
        automatic_counts={"AUTO": 100, "C2": 10},
        corrected_counts={"AUTO": 100, "C2": 10},
        pending_categories={"CAMION_NO_CONFIRMADO": pending},
        temporal_coverage=TemporalCoverage(24, 24, "TIMESTAMPS", False),
        expansion_method=ExpansionMethod.NONE_24H,
        temporal_factor=None,
        seasonal_factor=FactorTrace(
            "f_e", "Identidad", 1.0, "Sin corrección", "Identidad 1,0", "24 h"
        ),
        projection_method=ProjectionMethod.EXPONENTIAL,
        growth_rate_percent=4.0,
        design_period_years=20,
        base_year=2026,
        directional_factor=0.5,
        lane_distribution_factor=1.0,
        reviewer="Auditor TPDA",
        is_synthetic=synthetic,
        synthetic_acknowledged=synthetic,
    )
    return calculate_tpda_workflow(data)


def transfer(*, synthetic=False):
    return build_weighing_input_from_tpda(
        tpda_result(synthetic=synthetic),
        allow_demonstration=synthetic,
        transferred_at="2026-07-17T20:00:00+00:00",
    )


def observation(*, condition=WeighingCondition.MEASURED, gross=150.0, axles=None):
    return build_manual_observation(
        category="C2",
        gross_weight=gross,
        axle_groups=axles or (("simple_single", 50.0), ("simple_dual", 100.0)),
        unit="kN",
        source_type=WeighingSourceType.STATIC_SCALE,
        source_reference="balanza-01",
        condition=condition,
        reviewer="Auditor Pesaje",
        timestamp="2026-07-17T20:05:00+00:00",
    )


def workflow_input(*, synthetic=False, observations=None):
    return WeighingWorkflowInput(
        tpda_transfer=transfer(synthetic=synthetic),
        observations=tuple(observations if observations is not None else [observation()]),
        source_type=WeighingSourceType.STATIC_SCALE,
        source_reference="balanza-01",
        source_date="2026-07-17",
        reviewer="Auditor Pesaje",
        validation_state="REVISADO",
        synthetic_acknowledged=synthetic,
    )


def test_accepts_only_valid_tpda_contract() -> None:
    contract = transfer()
    assert contract.tpda_methodological_status == MethodologicalStatus.VALID_TO_CONTINUE.value
    assert contract.source_tpda_result_id
    assert contract.source_tpda_fingerprint


def test_rejects_stale_tpda() -> None:
    stale = replace(tpda_result(), is_stale=True)
    with pytest.raises(ValueError, match="desactualizado"):
        build_weighing_input_from_tpda(stale)


def test_rejects_blocked_tpda() -> None:
    blocked = tpda_result(pending=1)
    assert blocked.methodological_status == MethodologicalStatus.BLOCKED_BY_CLASSIFICATION.value
    with pytest.raises(ValueError, match="no está habilitado"):
        build_weighing_input_from_tpda(blocked)


def test_demo_tpda_requires_explicit_demo_mode() -> None:
    demo = tpda_result(synthetic=True)
    with pytest.raises(ValueError):
        build_weighing_input_from_tpda(demo)
    contract = build_weighing_input_from_tpda(demo, allow_demonstration=True)
    assert contract.demonstration_mode
    assert contract.is_synthetic


def test_transfer_contains_all_categories_not_only_total() -> None:
    contract = transfer()
    assert contract.base_tpda_by_category["AUTO"] == 100
    assert contract.projected_traffic_by_category["C2"] > 10
    c2 = next(item for item in contract.categories if item.category == "C2")
    auto = next(item for item in contract.categories if item.category == "AUTO")
    assert c2.requires_load_configuration
    assert not auto.requires_load_configuration


def test_transfer_is_never_automatic_and_requires_storage_call() -> None:
    session = {"tpda_phase1_result": tpda_result()}
    assert "weighing_input_from_tpda" not in session
    contract = build_weighing_input_from_tpda(session["tpda_phase1_result"])
    assert store_weighing_transfer(session, contract, decision="replace")
    assert session["weighing_input_from_tpda"] == contract


def test_existing_weighing_state_requires_explicit_decision() -> None:
    old = transfer()
    session = {"weighing_input_from_tpda": old}
    with pytest.raises(ValueError, match="decisión explícita"):
        store_weighing_transfer(session, transfer(), decision="")
    assert session["weighing_input_from_tpda"] is old


def test_replace_preserves_previous_weighing_state_in_history() -> None:
    old = transfer()
    session = {
        "weighing_input_from_tpda": old,
        "weighing_records_current": (observation(),),
        "weighing_phase2_result": "resultado-previo",
    }
    new = transfer()
    assert store_weighing_transfer(session, new, decision="replace")
    assert session["weighing_history"][0]["input"] is old
    assert session["weighing_history"][0]["result"] == "resultado-previo"


def test_legacy_pesaje_dataframe_is_not_silently_overwritten() -> None:
    legacy = {"rows": 50}
    session = {"pesaje_df": legacy}
    with pytest.raises(ValueError, match="decisión explícita"):
        store_weighing_transfer(session, transfer(), decision="")
    assert session["pesaje_df"] is legacy
    assert store_weighing_transfer(session, transfer(), decision="replace")
    assert session["weighing_history"][0]["legacy_pesaje_df"] is legacy
    assert session["pesaje_df"] is None


def test_truck_without_structural_category_cannot_be_parsed() -> None:
    csv_text = (
        "timestamp,category_id,gross_weight_kn,axle1_type,axle1_load_kn\n"
        "2026-01-01T00:00:00,CAMION_NO_CONFIRMADO,100,simple_dual,100\n"
    )
    with pytest.raises(ValueError, match="categoría"):
        parse_weighing_csv(
            csv_text, source_reference="real.csv", reviewer="R"
        )


def test_real_csv_loads_with_canonical_kn() -> None:
    csv_text = (
        "timestamp,category_id,gross_weight_kn,axle1_type,axle1_load_kn,"
        "axle2_type,axle2_load_kn\n"
        "2026-01-01T00:00:00,C2,150,simple_single,50,simple_dual,100\n"
    )
    records = parse_weighing_csv(
        csv_text,
        source_reference="medicion.csv",
        condition=WeighingCondition.MEASURED,
        reviewer="R",
    )
    assert len(records) == 1
    assert records[0].gross_weight_kn == 150
    assert records[0].axle_load_sum_kn == 150


def test_demo_csv_is_explicitly_synthetic() -> None:
    records = parse_weighing_csv(
        DEMO_CSV,
        source_reference=str(DEMO_CSV),
        source_type=WeighingSourceType.DEMONSTRATION_LIBRARY,
        condition=WeighingCondition.SYNTHETIC,
        reviewer="R",
    )
    assert len(records) == 50
    assert all(record.condition == WeighingCondition.SYNTHETIC.value for record in records)


def test_axle_sum_mismatch_blocks_loads() -> None:
    bad = observation(gross=200)
    result = calculate_weighing_workflow(workflow_input(observations=[bad]))
    assert result.methodological_status == WeighingStatus.BLOCKED_BY_LOADS.value
    assert result.esal_readiness == ESALReadiness.NOT_FIT.value


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (100, "kN", 100), (1000, "kg", 9.80665), (1000, "kgf", 9.80665),
        (2, "toneladas", 19.6133), (1000, "lb", 4.4482216152605),
        (18, "kip", 80.067989074689),
    ],
)
def test_explicit_unit_conversion(value, unit, expected) -> None:
    assert convert_to_kn(value, unit) == pytest.approx(expected)


def test_unknown_unit_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unidad"):
        convert_to_kn(10, "oz")


@pytest.mark.parametrize("invalid", [0, -1])
def test_nonpositive_load_is_rejected(invalid) -> None:
    with pytest.raises(ValueError):
        convert_to_kn(invalid, "kN")


def test_empty_sample_is_blocked() -> None:
    result = calculate_weighing_workflow(workflow_input(observations=[]))
    assert result.methodological_status == WeighingStatus.BLOCKED_BY_EMPTY_SAMPLE.value


def test_synthetic_chain_propagates_to_demo_state() -> None:
    synthetic_record = observation(condition=WeighingCondition.SYNTHETIC)
    data = workflow_input(synthetic=True, observations=[synthetic_record])
    result = calculate_weighing_workflow(data)
    assert result.is_synthetic
    assert result.methodological_status == WeighingStatus.VALID_FOR_DEMONSTRATION.value
    assert result.esal_readiness == ESALReadiness.DEMONSTRATION_ONLY.value


def test_real_valid_chain_is_fit_but_not_connected_to_esal() -> None:
    result = calculate_weighing_workflow(workflow_input())
    assert result.methodological_status == WeighingStatus.VALID_TO_CONTINUE.value
    assert result.esal_readiness == ESALReadiness.FIT.value
    assert "esal_result" not in result.as_dict()


def test_tpda_change_invalidates_weighing_result_without_deleting_it() -> None:
    data = workflow_input()
    result = calculate_weighing_workflow(data)
    changed_tpda = replace(tpda_result(), calculation_id="tpda-new-source")
    assert weighing_result_is_stale(result, data, changed_tpda)
    assert result.observation_count == 1


def test_load_change_invalidates_weighing_result() -> None:
    data = workflow_input()
    result = calculate_weighing_workflow(data)
    changed = replace(data, observations=(observation(gross=151, axles=(("simple_single", 51), ("simple_dual", 100))),))
    assert weighing_result_is_stale(result, changed, tpda_result())


def test_input_fingerprints_are_reproducible() -> None:
    data = workflow_input()
    assert weighing_input_fingerprint(data) == weighing_input_fingerprint(data)
    changed = replace(data, gross_axle_tolerance_percent=6)
    assert weighing_input_fingerprint(data) != weighing_input_fingerprint(changed)


def test_existing_records_are_preserved_or_archived() -> None:
    first = (observation(),)
    second = (observation(gross=151, axles=(("simple_single", 51), ("simple_dual", 100))),)
    session = {"weighing_records_current": first}
    assert not store_weighing_records(session, second, decision="keep")
    assert session["weighing_records_current"] == first
    assert store_weighing_records(session, second, decision="replace")
    assert session["weighing_records_history"] == [first]


def test_transfer_current_signature_must_match_tpda() -> None:
    current = tpda_result()
    contract = build_weighing_input_from_tpda(current)
    assert tpda_transfer_is_current(contract, current)
    changed = replace(current, calculation_id="tpda-changed")
    assert not tpda_transfer_is_current(contract, changed)


def test_esal_ui_consumes_only_formal_weighing_contract() -> None:
    source = (
        PROJECT_ROOT / "src/pavement_intelligence/ui/pages/esal_calculator.py"
    ).read_text(encoding="utf-8")
    assert "weighing_phase2_result" in source
    assert "esal_input_from_weighing" in source
    assert "weighing_input_from_tpda" not in source
    assert "traffic_counts_corrected" not in source
    assert 'st.session_state["esal_result"]' not in source
