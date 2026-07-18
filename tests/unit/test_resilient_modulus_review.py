from dataclasses import FrozenInstanceError, replace
import math

import pytest

from pavement_intelligence.geotechnics.cbr_workflow import calculate_cbr_workflow
from pavement_intelligence.geotechnics.resilient_modulus_review import (
    AdoptionMode, DirectTestEvidence, ReviewInput,
    SensitivityBands, analyze_discontinuity, build_future_transfer,
    calculate_review, compare_correlations, review_input_fingerprint,
    review_is_stale, store_review_result,
)
from test_cbr_workflow import record, workflow


def source(cbr=8.0, *, synthetic=False):
    item = record(cbr=cbr)
    kwargs = {}
    if synthetic:
        item = replace(item, data_origin="DEMOSTRATIVO_SINTETICO")
        kwargs["synthetic_acknowledged"] = True
    correlation = "LINEAL_1500_PSI" if cbr <= 10 else (
        "LINEAL_3500_PSI_LOCAL" if cbr <= 20 else "LOG_4326_LOCAL"
    )
    return calculate_cbr_workflow(workflow((item,), correlation_id=correlation, **kwargs))


def review_input(cbr=8.0, **changes):
    values = dict(
        source_result=source(cbr), sensitivity_bands=SensitivityBands(),
        adoption_mode=AdoptionMode.CORRELATION_SELECTION.value,
        selected_correlation_id="LINEAL_1500_PSI", responsible="Auditor 4B",
        justification="Selección revisada entre alternativas",
        source_demonstrative_acknowledged=True,
    )
    values.update(changes)
    return ReviewInput(**values)


def test_cbr8_comparison_exact_values_and_high_sensitivity():
    comparison = compare_correlations(8)
    values = {x.correlation_id: x.resilient_modulus_mpa / 0.006894757293168361
              for x in comparison.alternatives}
    assert values == {"LINEAL_1500_PSI": pytest.approx(12000),
                      "LINEAL_3500_PSI_LOCAL": pytest.approx(28000)}
    assert comparison.absolute_difference_mpa / 0.006894757293168361 == pytest.approx(16000)
    assert comparison.relative_difference_percent == pytest.approx(133.3333333333)
    assert comparison.sensitivity_level == "ALTA"


def test_cbr10_has_two_correlations_and_high_divergence():
    comparison = compare_correlations(10)
    assert len(comparison.alternatives) == 2
    assert comparison.relative_difference_percent == pytest.approx(133.3333333333)
    assert comparison.sensitivity_level == "ALTA"


def test_cbr20_linear_and_log_values_are_compared():
    comparison = compare_correlations(20)
    psi = {x.correlation_id: x.resilient_modulus_mpa / 0.006894757293168361
           for x in comparison.alternatives}
    assert psi["LINEAL_3500_PSI_LOCAL"] == pytest.approx(70000)
    assert psi["LOG_4326_LOCAL"] == pytest.approx(4326 * math.log(20) + 241)
    assert comparison.sensitivity_level == "ALTA"


def test_one_and_no_applicable_correlation():
    assert len(compare_correlations(5).alternatives) == 1
    none = compare_correlations(151)
    assert none.alternatives == () and none.sensitivity_level == "SIN_CORRELACION_APLICABLE"


@pytest.mark.parametrize("low,moderate,expected", [
    (200, 250, "BAJA"), (100, 200, "MODERADA"), (5, 20, "ALTA"),
])
def test_configurable_sensitivity_bands(low, moderate, expected):
    bands = SensitivityBands(low, moderate)
    assert compare_correlations(8, bands).sensitivity_level == expected


def test_invalid_bands_and_nonpositive_cbr_are_blocked():
    with pytest.raises(ValueError):
        compare_correlations(8, SensitivityBands(30, 10))
    with pytest.raises(ValueError):
        compare_correlations(0)


def test_discontinuity_around_20_is_explicit():
    result = analyze_discontinuity(20, .01)
    assert result.immediately_before.cbr_percent == 19.99
    assert result.at_boundary.cbr_percent == 20
    assert result.immediately_after.cbr_percent == 20.01
    assert result.cross_boundary_difference_percent > 300
    assert "salto metodológico" in result.warning


def test_correlation_selection_is_explicit_and_preserves_alternatives():
    result = calculate_review(review_input())
    assert result.selected_correlation_id == "LINEAL_1500_PSI"
    assert len(result.alternatives) == 2 and result.approved
    with pytest.raises(ValueError, match="seleccionar"):
        calculate_review(review_input(selected_correlation_id=None))


def test_conservative_means_minimum_and_requires_acceptance():
    data = review_input(adoption_mode=AdoptionMode.CONSERVATIVE_VALUE.value,
                        selected_correlation_id=None, conservative_rule_accepted=True)
    result = calculate_review(data)
    assert result.selected_correlation_id == "LINEAL_1500_PSI"
    assert result.adopted_resilient_modulus_mpa == pytest.approx(12000 * 0.006894757293168361)
    with pytest.raises(ValueError, match="aceptar"):
        calculate_review(replace(data, conservative_rule_accepted=False))


def direct_evidence(**changes):
    values = dict(value=50, unit="MPa", laboratory="Laboratorio MR",
                  procedure="AASHTO T 307 declarada", test_date="2026-07-18",
                  responsible="Especialista", document_reference="Informe MR-001")
    values.update(changes)
    return DirectTestEvidence(**values)


def test_direct_test_is_distinct_high_confidence_source():
    result = calculate_review(review_input(
        adoption_mode=AdoptionMode.DIRECT_TEST.value, selected_correlation_id=None,
        direct_test=direct_evidence()))
    assert result.condition == "ENSAYO_DIRECTO"
    assert result.source == "ENSAYO_DIRECTO" and result.confidence_level == "ALTA"
    assert not result.is_demonstrative and result.adopted_resilient_modulus_mpa == 50


@pytest.mark.parametrize("change", [
    {"laboratory": ""}, {"procedure": ""}, {"responsible": ""},
    {"document_reference": ""}, {"test_date": "18/07/2026"}, {"value": 0},
])
def test_direct_test_requires_complete_evidence(change):
    with pytest.raises(ValueError):
        calculate_review(review_input(adoption_mode=AdoptionMode.DIRECT_TEST.value,
                                      direct_test=direct_evidence(**change)))


def test_manual_value_is_not_presented_as_direct_test():
    result = calculate_review(review_input(
        adoption_mode=AdoptionMode.JUSTIFIED_MANUAL.value, selected_correlation_id=None,
        manual_value=10000, manual_unit="psi", manual_source="Informe histórico verificado"))
    assert result.condition == "ESTIMADO"
    assert result.source == "VALOR_MANUAL_VERIFICADO"
    assert any("no corresponde a un ensayo directo" in x for x in result.warnings)


@pytest.mark.parametrize("field", ["responsible", "justification"])
def test_every_adoption_requires_responsible_and_justification(field):
    with pytest.raises(ValueError):
        calculate_review(review_input(**{field: ""}))


def test_synthetic_source_requires_explicit_acknowledgement_for_correlation_adoption():
    data = review_input(source_result=source(8, synthetic=True), source_demonstrative_acknowledged=False)
    with pytest.raises(ValueError, match="demostrativo"):
        calculate_review(data)


def test_fingerprint_staleness_and_history_cover_all_review_inputs():
    data = review_input()
    result = calculate_review(data)
    assert not review_is_stale(result, data)
    variants = (
        replace(data, responsible="Otro"), replace(data, justification="Otra"),
        replace(data, sensitivity_bands=SensitivityBands(5, 25)),
        replace(data, selected_correlation_id="LINEAL_3500_PSI_LOCAL"),
        replace(data, catalog_version="2.0"),
    )
    assert all(review_input_fingerprint(data) != review_input_fingerprint(item) for item in variants)
    assert all(review_is_stale(result, item) for item in variants)
    session = {}
    store_review_result(session, data, result)
    second_data = variants[0]
    second = calculate_review(second_data)
    store_review_result(session, second_data, second)
    assert session["geotechnical_phase4b_history"] == [result]
    assert session["geotechnical_future_transfer"] is None


def test_manual_future_transfer_is_frozen_serializable_and_writes_no_design_state():
    data = review_input()
    result = calculate_review(data)
    transfer = build_future_transfer(result, data, transferred_at="2026-07-18T00:00:00+00:00")
    assert transfer.as_dict()["unit"] == "MPa"
    with pytest.raises(FrozenInstanceError):
        transfer.unit = "psi"
    session = {"geotechnical_future_transfer": transfer}
    assert "pavement_design_result" not in session and "aashto_result" not in session


def test_transfer_blocks_pending_or_stale_review():
    data = review_input()
    result = calculate_review(data)
    with pytest.raises(ValueError, match="aprobada"):
        build_future_transfer(replace(result, approved=False), data)
    with pytest.raises(ValueError, match="desactualizada"):
        build_future_transfer(result, replace(data, responsible="Otro"))


def test_source_priority_is_visible_but_does_not_auto_select():
    from pavement_intelligence.geotechnics.resilient_modulus_review import SOURCE_PRIORITY
    assert SOURCE_PRIORITY == ("ENSAYO_DIRECTO", "VALOR_MANUAL_VERIFICADO",
                               "CORRELACION_EMPIRICA", "DEMOSTRATIVO_SINTETICO")
    assert not hasattr(compare_correlations(8), "selected_correlation_id")
