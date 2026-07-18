import csv
import math
from pathlib import Path

import pytest

from pavement_intelligence.domain.traffic.models import HourlyCount
from pavement_intelligence.traffic.projection import (
    project_traffic,
    project_traffic_exponential,
    project_traffic_linear,
)
from pavement_intelligence.traffic.tpda import TPDAResult, calculate_tpda
from pavement_intelligence.utils.validators import (
    validate_design_period,
    validate_growth_rate,
    validate_survey_duration,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_tpda_24h_has_no_temporal_expansion() -> None:
    result = calculate_tpda({"AUTO": 100, "BUS": 20}, 24.0, 0.5)

    assert result.tpda_by_category == {"AUTO": 100.0, "BUS": 20.0}
    assert result.tpda_total == 120.0
    assert result.temporal_expansion_factor == 1.0
    assert result.design_tpda == 60.0


def test_partial_survey_uses_one_uniform_expansion() -> None:
    result = calculate_tpda({"AUTO": 100}, 12.0, 0.5, seasonal_factor=1.2)

    assert result.temporal_expansion_factor == 2.0
    assert result.tpda_total == pytest.approx(240.0)


def test_nocturnity_factor_replaces_uniform_expansion() -> None:
    result = calculate_tpda(
        {"AUTO": 100}, 12.0, 0.5, nocturnity_factor=1.5, seasonal_factor=1.2
    )

    # 100 * fn(1.5) * fe(1.2), no 24/12 factor applied a second time.
    assert result.tpda_total == pytest.approx(180.0)
    assert result.temporal_expansion_factor == 1.5


def test_nocturnity_cannot_expand_24h_survey() -> None:
    with pytest.raises(ValueError, match="24 horas"):
        calculate_tpda({"AUTO": 100}, 24.0, nocturnity_factor=1.5)


def test_multiday_survey_is_averaged_per_day() -> None:
    result = calculate_tpda({"AUTO": 700}, 168.0)

    assert result.tpda_total == pytest.approx(100.0)
    assert result.temporal_expansion_factor == pytest.approx(1 / 7)


def test_direction_and_lane_are_separate_from_base_tpda() -> None:
    result = calculate_tpda(
        {"AUTO": 100}, 24.0, 0.6, lane_distribution_factor=0.8
    )

    assert result.tpda_total == 100.0
    assert result.design_tpda == pytest.approx(48.0)
    assert result.directional_factor == 0.6
    assert result.lane_distribution_factor == 0.8


def test_missing_categories_preserve_totals() -> None:
    result = calculate_tpda({"AUTO": 10, "C2": 2}, 12.0)

    assert set(result.tpda_by_category) == {"AUTO", "C2"}
    assert sum(result.tpda_by_category.values()) == result.tpda_total


def test_empty_counts_are_valid_zero_observation() -> None:
    result = calculate_tpda({}, 24.0)

    assert result == TPDAResult(tpda_total=0.0, design_tpda=0.0)


@pytest.mark.parametrize("invalid", [-1, math.nan, math.inf, -math.inf])
def test_invalid_counts_are_rejected(invalid: float) -> None:
    with pytest.raises(ValueError):
        calculate_tpda({"AUTO": invalid}, 24.0)


@pytest.mark.parametrize("invalid", [math.nan, math.inf, -math.inf])
def test_nonfinite_tpda_parameters_are_rejected(invalid: float) -> None:
    with pytest.raises(ValueError):
        calculate_tpda({"AUTO": 1}, invalid)
    with pytest.raises(ValueError):
        calculate_tpda({"AUTO": 1}, 24.0, seasonal_factor=invalid)


def test_hourly_count_rejects_negative_count() -> None:
    with pytest.raises(ValueError):
        HourlyCount(hour=10, category_id="AUTO", direction="ascendente", count=-5)


def test_exponential_reference_case_is_independently_calculated() -> None:
    result = project_traffic_exponential(1000, 4.0, 20, expansion_factor=1.5)

    # Independent spreadsheet/reference arithmetic retained as fixed regression values.
    assert result["v_f"] == pytest.approx(3286.6846, abs=1e-4)
    assert result["v_t"] == pytest.approx(16303498.0203, abs=1e-4)


def test_exponential_zero_rate_and_zero_period() -> None:
    zero_rate = project_traffic_exponential(1000, 0.0, 20)
    zero_period = project_traffic_exponential(1000, 4.0, 0)

    assert zero_rate == {"v_f": 1000.0, "v_m": 1000.0, "v_t": 7_300_000.0}
    assert zero_period == {"v_f": 1000.0, "v_m": 1000.0, "v_t": 0.0}


def test_growth_rate_contract_is_percentage_not_decimal_fraction() -> None:
    percent = project_traffic(1000, 4.0, 1)
    decimal_like_input = project_traffic(1000, 0.04, 1)

    assert percent == pytest.approx(1040.0)
    assert decimal_like_input == pytest.approx(1000.4)


@pytest.mark.parametrize("fn", [project_traffic_linear, project_traffic_exponential])
def test_projection_rejects_negative_rate_and_years(fn) -> None:
    with pytest.raises(ValueError):
        fn(1000, -2.0, 20)
    with pytest.raises(ValueError):
        fn(1000, 4.0, -1)


@pytest.mark.parametrize("invalid", [math.nan, math.inf, -math.inf])
def test_projection_rejects_nonfinite_values(invalid: float) -> None:
    with pytest.raises(ValueError):
        project_traffic_exponential(invalid, 4.0, 20)
    with pytest.raises(ValueError):
        project_traffic_exponential(1000, invalid, 20)


def test_projection_rejects_overflow() -> None:
    with pytest.raises(OverflowError):
        project_traffic_exponential(1e308, 25.0, 1000)


def test_linear_variants_have_explicit_regression_results() -> None:
    variant_b = project_traffic_linear(1000, 4.0, 20, 1.5, "B")
    variant_a = project_traffic_linear(1000, 4.0, 20, 1.5, "A")

    assert variant_b == {"v_f": 2700.0, "v_m": 2100.0, "v_t": 15_330_000.0}
    assert variant_a == {"v_f": 2700.0, "v_m": 1850.0, "v_t": 13_505_000.0}
    assert variant_a["v_t"] < variant_b["v_t"]


def test_invalid_linear_variant_is_rejected() -> None:
    with pytest.raises(ValueError, match="variant"):
        project_traffic_linear(1000, 4.0, 20, variant="C")


def test_validators_reject_inconsistent_temporal_inputs() -> None:
    assert not validate_survey_duration(-5.0).is_valid
    assert not validate_growth_rate(-1.0).is_valid
    assert not validate_design_period(2).is_valid


def test_demo_csvs_retain_synthetic_traceability() -> None:
    survey_path = PROJECT_ROOT / "data/samples/caso_demostrativo/aforo_24h.csv"
    weighing_path = PROJECT_ROOT / "data/samples/caso_demostrativo/pesaje_vehicular.csv"
    with survey_path.open(encoding="utf-8-sig", newline="") as stream:
        survey_rows = list(csv.DictReader(stream))
    with weighing_path.open(encoding="utf-8-sig", newline="") as stream:
        weighing_rows = list(csv.DictReader(stream))

    assert survey_path.parent.name == "caso_demostrativo"
    assert len(survey_rows) == 10
    assert all(row["notes"].lower() == "simulado" for row in weighing_rows)


def test_demo_survey_totals_are_stable() -> None:
    path = PROJECT_ROOT / "data/samples/caso_demostrativo/aforo_24h.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    counts = {row["category_id"]: int(row["count"]) for row in rows}
    result = calculate_tpda(counts, 24.0)
    assert len(counts) == 10
    assert result.tpda_total == 1273.0
    assert sum(result.tpda_by_category.values()) == 1273.0
