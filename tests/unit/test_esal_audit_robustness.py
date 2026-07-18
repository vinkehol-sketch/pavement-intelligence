"""Regresiones de la auditoría posterior a Fase 3A."""
from dataclasses import replace
import math

import pytest

from pavement_intelligence.esal.axle_configuration_catalog import (
    AXLE_CONFIGURATION_CATALOG_VERSION,
    validate_category_axle_configuration,
)
from pavement_intelligence.esal.workflow import (
    EQUIVALENCE_METHOD_LABEL,
    ESALWorkflowStatus,
    calculate_esal_workflow,
    esal_input_fingerprint,
    esal_result_is_stale,
)
from pavement_intelligence.weighing.workflow import AxleGroupLoad
from test_esal_workflow import esal_input, weighing_result


def groups(*types):
    return tuple(AxleGroupLoad(i, axle_type, 10.0, "test") for i, axle_type in enumerate(types, 1))


@pytest.mark.parametrize("category,configuration", [
    ("C2", ("simple_single", "simple_dual")),
    ("C3", ("simple_single", "tandem")),
    ("TRACTOCAMION", ("simple_single", "tandem")),
    ("ARTICULADO", ("simple_single", "tandem", "tridem")),
])
def test_confirmed_category_configurations_are_valid(category, configuration):
    result = validate_category_axle_configuration(category, groups(*configuration))
    assert result.is_valid
    assert result.catalog_version == AXLE_CONFIGURATION_CATALOG_VERSION


def test_c2_rejects_tandem_and_distinguishes_groups_from_physical_axles():
    result = validate_category_axle_configuration("C2", groups("simple_single", "tandem"))
    assert not result.is_valid
    assert "CONFIGURACION_INCOMPATIBLE" in result.error_codes
    assert sum(group.physical_axle_count for group in groups("simple_single", "tandem")) == 3
    assert len(result.received_configuration) == 2


@pytest.mark.parametrize("category,code", [
    ("CAMION", "CAMION_NO_RECLASIFICADO"),
    ("AUTO", "CATEGORIA_NO_ESTRUCTURAL"),
    ("DESCONOCIDA", "CATEGORIA_DESCONOCIDA"),
    ("BUS", "CONFIGURACION_NO_CONFIRMADA"),
])
def test_blocked_or_unconfirmed_categories(category, code):
    result = validate_category_axle_configuration(category, groups("simple_single", "simple_dual"))
    assert not result.is_valid
    assert code in result.error_codes


def test_duplicate_and_nonconsecutive_positions_are_rejected():
    duplicated = (
        AxleGroupLoad(1, "simple_single", 40, "test"),
        AxleGroupLoad(1, "simple_dual", 80, "test"),
    )
    result = validate_category_axle_configuration("C2", duplicated)
    assert not result.is_valid
    assert "ORDEN_DE_GRUPOS_INVALIDO" in result.error_codes


def test_catalog_version_participates_in_fingerprint_and_staleness_contract():
    weighing = weighing_result()
    data = esal_input(weighing)
    result = calculate_esal_workflow(data)
    changed = replace(data, axle_configuration_catalog_version="future-2.0")
    assert esal_input_fingerprint(data) != esal_input_fingerprint(changed)
    assert esal_result_is_stale(result, changed, weighing)
    with pytest.raises(ValueError, match="catálogo"):
        calculate_esal_workflow(changed)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_group_load_is_controlled_and_not_aggregated(invalid):
    data = esal_input()
    observation = data.weighing_transfer.observations[0]
    bad_groups = (
        replace(observation.axle_groups[0], load_kn=invalid),
        observation.axle_groups[1],
    )
    transfer = replace(data.weighing_transfer, observations=(replace(observation, axle_groups=bad_groups),))
    result = calculate_esal_workflow(replace(data, weighing_transfer=transfer))
    assert result.design_readiness == "NO_APTO_PARA_CONSOLIDACION_DEMOSTRATIVA"
    assert result.analyzed_batch_esal == 0
    assert result.rejected_vehicle_ids == (observation.record_id,)
    assert all(math.isfinite(item.equivalent_factor) for item in result.axle_factors)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_gross_weight_is_controlled(invalid):
    data = esal_input()
    observation = data.weighing_transfer.observations[0]
    transfer = replace(data.weighing_transfer, observations=(replace(observation, gross_weight_kn=invalid),))
    result = calculate_esal_workflow(replace(data, weighing_transfer=transfer))
    assert result.methodological_status == ESALWorkflowStatus.BLOCKED_BY_LOADS.value
    assert result.analyzed_batch_esal == 0


@pytest.mark.parametrize("field", ["growth_rate_percent", "directional_factor", "lane_distribution_factor"])
@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_projection_factors_raise_controlled_error(field, invalid):
    data = esal_input()
    transfer = replace(data.weighing_transfer, **{field: invalid})
    with pytest.raises(ValueError, match="Periodo o crecimiento"):
        calculate_esal_workflow(replace(data, weighing_transfer=transfer))


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_exponent_and_tolerance_raise_controlled_error(invalid):
    data = esal_input()
    with pytest.raises(ValueError, match="exponente"):
        calculate_esal_workflow(replace(data, equivalence_exponent=invalid))
    transfer = replace(data.weighing_transfer, gross_axle_tolerance_percent=invalid)
    with pytest.raises(ValueError, match="tolerancia"):
        calculate_esal_workflow(replace(data, weighing_transfer=transfer))


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_standard_load_raises_controlled_error(invalid):
    with pytest.raises(ValueError, match="80 kN"):
        calculate_esal_workflow(replace(esal_input(), standard_single_axle_kn=invalid))


def _with_gross_and_tolerance(gross, tolerance):
    data = esal_input()
    observation = data.weighing_transfer.observations[0]
    transfer = replace(
        data.weighing_transfer,
        observations=(replace(observation, gross_weight_kn=gross),),
        gross_axle_tolerance_percent=tolerance,
    )
    return calculate_esal_workflow(replace(data, weighing_transfer=transfer))


def test_tolerance_boundary_is_inclusive_and_zero_is_supported():
    axle_sum = 120.0
    exact_five_percent = axle_sum / 0.95
    assert _with_gross_and_tolerance(exact_five_percent, 5.0).rejected_vehicle_ids == ()
    assert _with_gross_and_tolerance(axle_sum / 0.950001, 5.0).rejected_vehicle_ids == ()
    assert _with_gross_and_tolerance(axle_sum / 0.949999, 5.0).rejected_vehicle_ids
    assert _with_gross_and_tolerance(axle_sum, 0.0).rejected_vehicle_ids == ()


def test_negative_tolerance_is_rejected():
    data = esal_input()
    transfer = replace(data.weighing_transfer, gross_axle_tolerance_percent=-0.1)
    with pytest.raises(ValueError, match="tolerancia"):
        calculate_esal_workflow(replace(data, weighing_transfer=transfer))


@pytest.mark.parametrize("load", [1e-12, 1e308])
def test_extreme_loads_do_not_produce_nonfinite_aggregates(load):
    data = esal_input()
    observation = data.weighing_transfer.observations[0]
    bad_groups = (
        replace(observation.axle_groups[0], load_kn=load),
        replace(observation.axle_groups[1], load_kn=load),
    )
    transfer = replace(
        data.weighing_transfer,
        observations=(replace(observation, gross_weight_kn=load * 2, axle_groups=bad_groups),),
    )
    result = calculate_esal_workflow(replace(data, weighing_transfer=transfer))
    assert math.isfinite(result.analyzed_batch_esal)


def test_demonstrative_method_name_and_warning_are_serialized():
    result = calculate_esal_workflow(esal_input())
    assert result.equivalence_method_label == EQUIVALENCE_METHOD_LABEL
    assert "demostrativo/académico" in result.equivalence_method_label
    assert "No sustituye" in result.equivalence_method_warning
    assert "esal_result" not in result.as_dict()
