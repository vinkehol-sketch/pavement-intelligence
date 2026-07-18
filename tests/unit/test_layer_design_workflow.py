from dataclasses import replace
import math
from types import SimpleNamespace

import pytest

from pavement_intelligence.aashto93.layer_design_workflow import (
    COEFFICIENT_CATALOG_VERSION,
    ComplianceStatus,
    DesignMode,
    LayerDesignTransfer,
    LayerInput,
    LayerType,
    LayerWorkflowInput,
    SearchRange,
    SearchSettings,
    adjust_layer,
    build_layer_transfer,
    calculate_layer_design,
    coefficient_catalog,
    discrete_search,
    inches_to_thickness,
    input_fingerprint,
    result_is_stale_5b,
    round_up_thickness,
    store_result,
    thickness_to_inches,
    validate_input,
)


def transfer(required=4.0):
    return LayerDesignTransfer(
        "t",
        "2026-07-18",
        "D",
        "5a",
        "fp",
        required,
        5_000_000,
        10_000,
        90,
        4.2,
        2.5,
        1.7,
        True,
        ("demo",),
        "Ing.",
        "5A",
    )


def layer(kind, thickness, unit="in", a=None, m=1.0):
    defaults = {
        LayerType.ASPHALT.value: 0.4,
        LayerType.BASE.value: 0.14,
        LayerType.SUBBASE.value: 0.11,
    }
    return LayerInput(
        kind.lower(),
        kind,
        kind,
        thickness,
        unit,
        a or defaults[kind],
        "Fuente local declarada",
        "CATALOGO",
        m,
        "BUENO" if kind != LayerType.ASPHALT.value else "NO_APLICA",
        5.0 if kind != LayerType.ASPHALT.value else 0.0,
        "Estudio drenaje" if kind != LayerType.ASPHALT.value else "m1=1",
        "Selección explícita",
        None,
        unit,
    )


def layers(d1=5, d2=6, d3=12, unit="in"):
    return (
        layer(LayerType.ASPHALT.value, d1, unit),
        layer(LayerType.BASE.value, d2, unit),
        layer(LayerType.SUBBASE.value, d3, unit),
    )


def data(required=4.0, layer_values=None, mode=DesignMode.MANUAL.value, **changes):
    base = LayerWorkflowInput(
        transfer(required),
        layer_values or layers(),
        mode,
        0.001,
        "Ing.",
        "Evaluación demostrativa revisada",
        created_at="2026-07-18",
    )
    return replace(base, **changes)


@pytest.mark.parametrize("unit,value", [("in", 1), ("cm", 2.54), ("mm", 25.4)])
def test_units_convert_to_exact_inches(unit, value):
    assert thickness_to_inches(value, unit) == pytest.approx(1)
    assert inches_to_thickness(1, unit) == pytest.approx(value)


def test_manual_transfer_preserves_phase5a_traceability(monkeypatch):
    from pavement_intelligence.aashto93 import layer_design_workflow as workflow

    result = SimpleNamespace(
        converged=True,
        required_sn=4.1,
        result_id="r5a",
        input_fingerprint="fp5a",
        w18=5_000_000,
        mr_psi=10_000,
        reliability_percent=90,
        p0=4.2,
        pt=2.5,
        delta_psi=1.7,
        is_demonstrative=True,
        warnings=("demo",),
        methodology_version="5A",
    )
    current = SimpleNamespace(design_id="D", responsible="Ing.")
    monkeypatch.setattr(workflow, "result_is_stale", lambda result, current: False)
    item = build_layer_transfer(result, current, transferred_at="2026-07-18")
    assert item.phase5a_result_id == "r5a" and item.phase5a_fingerprint == "fp5a"
    assert item.required_sn == 4.1 and item.responsible == "Ing."


def test_transfer_blocks_stale_or_invalid_sn(monkeypatch):
    from pavement_intelligence.aashto93 import layer_design_workflow as workflow

    result = SimpleNamespace(converged=True, required_sn=4.1)
    monkeypatch.setattr(workflow, "result_is_stale", lambda result, current: True)
    with pytest.raises(ValueError, match="vigente"):
        build_layer_transfer(result, SimpleNamespace())
    monkeypatch.setattr(workflow, "result_is_stale", lambda result, current: False)
    result.required_sn = 0
    with pytest.raises(ValueError, match="positivo"):
        build_layer_transfer(result, SimpleNamespace())


def test_unknown_and_invalid_units_or_values_block():
    with pytest.raises(ValueError, match="Unidad"):
        thickness_to_inches(1, "m")
    for value in (-1, math.nan, math.inf):
        with pytest.raises(ValueError):
            thickness_to_inches(value, "in")


def test_three_layer_reference_case_and_contributions():
    result = calculate_layer_design(data(required=4.0))
    assert [x.sn_contribution for x in result.contributions] == pytest.approx(
        [2.0, 0.84, 1.32]
    )
    assert result.provided_sn == pytest.approx(4.16)
    assert result.excess == pytest.approx(0.16) and result.deficit == 0
    assert result.status == ComplianceStatus.COMPLIANT_EXCESS.value


def test_one_two_and_three_layer_contribution_effects():
    one = calculate_layer_design(data(layer_values=layers(5, 0, 0)))
    two = calculate_layer_design(data(layer_values=layers(5, 6, 0)))
    three = calculate_layer_design(data(layer_values=layers(5, 6, 12)))
    assert one.provided_sn < two.provided_sn < three.provided_sn


def test_deficit_and_equality_with_tolerance_are_exclusive():
    fail = calculate_layer_design(data(required=5))
    assert (
        fail.status == ComplianceStatus.NOT_COMPLIANT.value
        and fail.deficit > 0
        and fail.excess == 0
    )
    equal = calculate_layer_design(data(required=4.1605))
    assert equal.status == ComplianceStatus.COMPLIANT.value
    assert not (equal.deficit > 0 and equal.excess > 0)


def test_cm_mm_and_inches_designs_are_equivalent():
    a = calculate_layer_design(data(layer_values=layers()))
    b = calculate_layer_design(data(layer_values=layers(12.7, 15.24, 30.48, "cm")))
    c = calculate_layer_design(data(layer_values=layers(127, 152.4, 304.8, "mm")))
    assert a.provided_sn == pytest.approx(b.provided_sn) == pytest.approx(c.provided_sn)


@pytest.mark.parametrize("target", [x.value for x in LayerType])
def test_adjust_each_layer_exactly_satisfies_required_sn(target):
    adjusted = adjust_layer(layers(2, 2, 2), 4.0, target)
    result = calculate_layer_design(
        data(
            required=4,
            layer_values=adjusted,
            mode=DesignMode.ADJUST_ONE.value,
            adjusted_layer=target,
        )
    )
    assert result.provided_sn == pytest.approx(4.0)
    assert result.status == ComplianceStatus.COMPLIANT.value


def test_adjustment_never_returns_negative_and_invalid_target_blocks():
    adjusted = adjust_layer(layers(20, 20, 20), 1, LayerType.ASPHALT.value)
    assert adjusted[0].thickness == 0
    with pytest.raises(ValueError, match="no existe"):
        adjust_layer(layers(), 4, "OTRA")


@pytest.mark.parametrize(
    "field,value",
    [
        ("structural_coefficient", 0),
        ("structural_coefficient", math.nan),
        ("drainage_coefficient", 0),
        ("drainage_coefficient", math.inf),
    ],
)
def test_invalid_coefficients_and_drainage_block(field, value):
    items = list(layers())
    items[1] = replace(items[1], **{field: value})
    with pytest.raises(ValueError):
        validate_input(data(layer_values=tuple(items)))


def test_asphalt_m1_is_fixed_and_drainage_range_is_controlled():
    items = list(layers())
    items[0] = replace(items[0], drainage_coefficient=0.9)
    with pytest.raises(ValueError, match="m1=1"):
        validate_input(data(layer_values=tuple(items)))
    items = list(layers())
    items[2] = replace(items[2], drainage_coefficient=1.5)
    with pytest.raises(ValueError, match="rango"):
        validate_input(data(layer_values=tuple(items)))


def test_catalog_is_versioned_explicit_and_not_auto_selected():
    catalog = coefficient_catalog()
    assert len(catalog) == 6 and all(
        x.version == COEFFICIENT_CATALOG_VERSION for x in catalog.values()
    )
    with pytest.raises(ValueError, match="desactualizado"):
        validate_input(data(coefficient_catalog_version="OLD"))


def test_manual_coefficient_requires_source():
    items = list(layers())
    items[0] = replace(
        items[0], coefficient_condition="MANUAL_JUSTIFICADO", coefficient_source=""
    )
    with pytest.raises(ValueError, match="fuentes|fuente"):
        validate_input(data(layer_values=tuple(items)))


def search_data(order="MENOR_EXCEDENTE_SN", max_combinations=1000):
    ranges = tuple(SearchRange(kind.value, 2, 8, 2) for kind in LayerType)
    return data(
        mode=DesignMode.DISCRETE.value,
        search=SearchSettings(ranges, max_combinations, order),
    )


def test_discrete_search_is_deterministic_has_multiple_and_ordered_results():
    first = discrete_search(search_data())
    second = discrete_search(search_data())
    assert first == second and len(first) > 1
    assert [x.excess_sn for x in first] == sorted(x.excess_sn for x in first)


def test_discrete_search_none_increment_and_limit_cases():
    none = discrete_search(replace(search_data(), transfer=transfer(100)))
    assert none == ()
    bad = replace(
        search_data(),
        search=SearchSettings((SearchRange(LayerType.ASPHALT.value, 1, 2, 0),), 100),
    )
    with pytest.raises(ValueError):
        discrete_search(bad)
    with pytest.raises(ValueError, match="límite"):
        discrete_search(search_data(max_combinations=1))


def test_discrete_result_preserves_alternatives_without_auto_selection():
    result = calculate_layer_design(search_data())
    assert result.alternatives and result.mode == DesignMode.DISCRETE.value


def test_rounding_up_is_explicit_and_recalculates_sn():
    record = round_up_thickness(
        4.1,
        0.5,
        layer_type=LayerType.ASPHALT.value,
        responsible="Ing.",
        justification="Constructibilidad",
    )
    assert record.before_in == 4.1 and record.after_in == 4.5
    before = calculate_layer_design(data(layer_values=layers(4.1, 6, 12)))
    after = calculate_layer_design(
        data(layer_values=layers(4.1, 6, 12), rounding=(record,))
    )
    assert after.provided_sn > before.provided_sn


@pytest.mark.parametrize("value,increment", [(-1, 0.5), (1, 0), (math.nan, 0.5)])
def test_invalid_rounding_blocks(value, increment):
    with pytest.raises(ValueError):
        round_up_thickness(
            value,
            increment,
            layer_type=LayerType.BASE.value,
            responsible="Ing.",
            justification="J",
        )


def test_fingerprint_staleness_covers_design_inputs():
    original = data()
    result = calculate_layer_design(original)
    variants = [
        replace(original, layers=layers(6, 6, 12)),
        replace(original, compliance_tolerance=0.002),
        replace(
            original,
            mode=DesignMode.ADJUST_ONE.value,
            adjusted_layer=LayerType.BASE.value,
        ),
        replace(original, responsible="Otro"),
        replace(original, coefficient_catalog_version="NEW"),
    ]
    assert all(result_is_stale_5b(result, x) for x in variants)
    assert input_fingerprint(original) == input_fingerprint(original)


def test_history_and_no_automatic_legacy_write():
    session = {}
    first_data = data()
    first = calculate_layer_design(first_data)
    store_result(session, first_data, first)
    second_data = replace(first_data, layers=layers(6, 6, 12))
    second = calculate_layer_design(second_data)
    store_result(session, second_data, second)
    assert session["aashto93_phase5b_history"] == [first]
    assert "pavement_design_result" not in session and "diseno_result" not in session


def test_contracts_are_serializable_and_frozen():
    result = calculate_layer_design(data())
    assert "provided_sn" in result.as_dict()
    with pytest.raises(Exception):
        result.provided_sn = 0
