from dataclasses import FrozenInstanceError, replace
import math

import pytest

from pavement_intelligence.geotechnics.cbr_workflow import (
    CATALOG_VERSION, CBRRecord, CBRWorkflowInput, DataOrigin, DesignCBRMode,
    build_geotechnical_transfer, calculate_cbr_workflow, convert_resilient_modulus,
    correlation_catalog, input_fingerprint, percentile_linear, result_is_stale,
    store_geotechnical_result, validate_cbr_record,
)


def record(record_id="r1", cbr=5.0, **changes):
    values = dict(
        record_id=record_id, study_id="EST-1", project_segment="Tramo A", location="km 0+000",
        depth_m=1.5, sample_type="Alterada", sample_condition="Preparada",
        cbr_2_5_mm_percent=cbr, cbr_5_0_mm_percent=None, reported_cbr_percent=cbr,
        selection_criterion="CBR reportado", compaction_percent=95.0,
        dry_density_kn_m3=18.0, moisture_condition="Saturada", saturated=True,
        compaction_energy="Proctor modificado", test_date="2026-07-18",
        laboratory_or_source="Laboratorio X", responsible="Ing. Geotécnico",
        declared_standard="ASTM D1883 declarada", data_origin=DataOrigin.LABORATORY_TEST.value,
    )
    values.update(changes)
    return CBRRecord(**values)


def workflow(records=None, **changes):
    values = dict(study_id="EST-1", project_segment="Tramo A",
                  records=tuple(records or (record(),)), design_mode=DesignCBRMode.SINGLE_VALUE.value,
                  correlation_id="LINEAL_1500_PSI", reviewer="Auditor 4A")
    values.update(changes)
    return CBRWorkflowInput(**values)


def test_contract_is_frozen_serializable_and_fingerprinted():
    item = record()
    with pytest.raises(FrozenInstanceError):
        item.depth_m = 2
    assert item.as_dict()["reported_cbr_percent"] == 5
    data = workflow()
    assert input_fingerprint(data) == input_fingerprint(data)
    assert input_fingerprint(data) != input_fingerprint(replace(data, output_unit="psi"))


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), 151])
def test_invalid_cbr_values_are_blocked(value):
    with pytest.raises(ValueError):
        validate_cbr_record(record(cbr=value))


def test_final_only_cbr_is_accepted_with_warning():
    warnings = validate_cbr_record(record(cbr_2_5_mm_percent=None, cbr_5_0_mm_percent=None))
    assert any("Solo existe CBR final" in item for item in warnings)


@pytest.mark.parametrize("field,value", [
    ("depth_m", -0.1), ("compaction_percent", 0), ("compaction_percent", 101),
    ("dry_density_kn_m3", 0), ("test_date", "18/07/2026"),
])
def test_physical_and_documentary_validation(field, value):
    with pytest.raises(ValueError):
        validate_cbr_record(record(**{field: value}))


@pytest.mark.parametrize("origin", [DataOrigin.VERIFIED_MANUAL, DataOrigin.ESTIMATED, DataOrigin.SYNTHETIC])
def test_manual_estimated_and_synthetic_require_responsible(origin):
    with pytest.raises(ValueError, match="responsable"):
        validate_cbr_record(record(data_origin=origin.value, responsible=""))


def test_percentile_linear_even_odd_and_boundaries():
    assert percentile_linear((1, 3, 5), 50) == 3
    assert percentile_linear((1, 3, 5, 7), 50) == 4
    assert percentile_linear((1, 3, 5), 0) == 1
    assert percentile_linear((1, 3, 5), 100) == 5
    with pytest.raises(ValueError):
        percentile_linear((1,), 101)
    with pytest.raises(ValueError):
        percentile_linear((), 50)


def test_single_minimum_average_and_percentile_modes():
    records = (record("a", 4), record("b", 6), record("c", 8))
    minimum = calculate_cbr_workflow(workflow(records, design_mode=DesignCBRMode.CONSERVATIVE_MINIMUM.value))
    assert minimum.design_cbr_percent == 4 and minimum.used_record_ids == ("a",)
    average = calculate_cbr_workflow(workflow(records, design_mode=DesignCBRMode.AVERAGE.value))
    assert average.design_cbr_percent == 6
    percentile = calculate_cbr_workflow(workflow(
        records, design_mode=DesignCBRMode.PERCENTILE.value, percentile=25))
    assert percentile.design_cbr_percent == 5
    with pytest.raises(ValueError, match="PROMEDIO"):
        calculate_cbr_workflow(workflow(design_mode=DesignCBRMode.AVERAGE.value))


def test_justified_manual_selection():
    records = (record("a", 4), record("b", 6))
    result = calculate_cbr_workflow(workflow(
        records, design_mode=DesignCBRMode.JUSTIFIED_MANUAL.value,
        manual_record_id="b", manual_justification="Unidad representativa revisada"))
    assert result.design_cbr_percent == 6 and result.used_record_ids == ("b",)
    with pytest.raises(ValueError, match="selección manual"):
        calculate_cbr_workflow(workflow(records, design_mode=DesignCBRMode.JUSTIFIED_MANUAL.value))


def test_rejected_and_unselected_records_are_traceable():
    records = (record("ok", 5), replace(record("bad", 1), is_valid=False, rejection_reason="alterada"))
    result = calculate_cbr_workflow(workflow(records))
    assert result.used_record_ids == ("ok",)
    assert result.excluded_record_ids == ("bad",)


def test_synthetic_requires_acknowledgement_and_remains_demonstrative():
    synthetic = record(data_origin=DataOrigin.SYNTHETIC.value)
    with pytest.raises(ValueError, match="No existen"):
        calculate_cbr_workflow(workflow((synthetic,)))
    result = calculate_cbr_workflow(workflow((synthetic,), synthetic_acknowledged=True))
    assert result.is_demonstrative
    assert result.methodological_status == "VALIDO_PARA_DEMOSTRACION"


@pytest.mark.parametrize("correlation_id,cbr,expected_psi", [
    ("LINEAL_1500_PSI", 5, 7500),
    ("LINEAL_3500_PSI_LOCAL", 10, 35000),
    ("LOG_4326_LOCAL", 20, 4326 * math.log(20) + 241),
])
def test_known_numeric_case_per_correlation(correlation_id, cbr, expected_psi):
    result = calculate_cbr_workflow(workflow((record(cbr=cbr),), correlation_id=correlation_id, output_unit="psi"))
    assert result.displayed_resilient_modulus == pytest.approx(expected_psi)
    assert result.resilient_modulus_mpa == pytest.approx(expected_psi * 0.006894757293168361)


@pytest.mark.parametrize("correlation_id,cbr", [
    ("LINEAL_1500_PSI", 0.01), ("LINEAL_1500_PSI", 10),
    ("LINEAL_3500_PSI_LOCAL", 7.2), ("LINEAL_3500_PSI_LOCAL", 20),
    ("LOG_4326_LOCAL", 20), ("LOG_4326_LOCAL", 150),
])
def test_correlation_limits_are_inclusive(correlation_id, cbr):
    assert calculate_cbr_workflow(workflow((record(cbr=cbr),), correlation_id=correlation_id))


def test_outside_correlation_range_and_bad_coefficients_are_blocked():
    with pytest.raises(ValueError, match="aplicabilidad"):
        calculate_cbr_workflow(workflow((record(cbr=11),)))
    with pytest.raises(ValueError, match="finito"):
        calculate_cbr_workflow(workflow(coefficient_overrides=(("k", float("nan")),)))
    with pytest.raises(ValueError, match="no positivo"):
        calculate_cbr_workflow(workflow(coefficient_overrides=(("k", -1),)))


def test_catalog_is_explicit_versioned_and_source_pending():
    catalog = correlation_catalog()
    assert len(catalog) == 3
    assert all(item.version == CATALOG_VERSION for item in catalog.values())
    assert all("DEMOSTRATIVA" in item.status for item in catalog.values())


@pytest.mark.parametrize("unit,value", [("MPa", 1), ("kPa", 1000), ("psi", 145.0377377), ("ksi", 0.1450377377)])
def test_units_to_mpa_and_round_trip(unit, value):
    mpa = convert_resilient_modulus(value, unit, "MPa")
    assert mpa == pytest.approx(1, rel=1e-7)
    assert convert_resilient_modulus(mpa, "MPa", unit) == pytest.approx(value)


def test_unknown_unit_and_nonfinite_conversion_are_blocked():
    with pytest.raises(ValueError):
        convert_resilient_modulus(1, "Pa", "MPa")
    with pytest.raises(ValueError):
        convert_resilient_modulus(float("inf"), "MPa", "psi")


def test_staleness_history_and_future_manual_transfer():
    data = workflow()
    result = calculate_cbr_workflow(data)
    assert not result_is_stale(result, data)
    assert result_is_stale(result, replace(data, catalog_version="2.0"))
    assert result_is_stale(result, replace(data, correlation_id="LINEAL_3500_PSI_LOCAL"))
    session = {}
    store_geotechnical_result(session, data, result)
    newer = calculate_cbr_workflow(replace(data, output_unit="psi"))
    store_geotechnical_result(session, replace(data, output_unit="psi"), newer)
    assert session["geotechnical_phase4a_history"] == [result]
    transfer = build_geotechnical_transfer(newer, transferred_at="2026-07-18T00:00:00+00:00")
    assert transfer.source_result_id == newer.result_id
    assert "pavement_design" not in session and "aashto" not in session
