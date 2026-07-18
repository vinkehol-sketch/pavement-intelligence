from dataclasses import replace
import math

import pytest

from pavement_intelligence.aashto93.sn_workflow import (
    AASHTO93Input,
    ESAL5ATransfer,
    EQUATION,
    MANDATORY_WARNING,
    MPA_TO_PSI,
    MR5ATransfer,
    METHODOLOGY_VERSION,
    SolverSettings,
    ZR_CATALOG,
    ZR_CATALOG_VERSION,
    aashto_log10_w18,
    calculate_required_sn,
    convert_mr_to_psi,
    residual,
    result_is_stale,
    store_result,
    validate_input,
    zr_from_catalog,
)


def esal_transfer(w18=5_000_000.0, demo=False):
    return ESAL5ATransfer(
        "e",
        "2026-07-18",
        "traffic",
        "3b",
        "fp3b",
        w18,
        20,
        2026,
        2045,
        "PROYECCION_GEOMETRICA_POR_CATEGORIA_V1",
        "VALIDO_PARA_DEMOSTRACION" if demo else "VALIDO_PARA_CONTINUAR",
        demo,
        24.0,
        "CALCULADO_DESDE_DURACION",
        0.5,
        1.0,
        365,
        (
            {
                "category": "BUS",
                "annual_rate_percent": 3.0,
                "source": "estudio",
                "condition": "revisada",
            },
        ),
        ("advertencia ESAL",),
    )


def mr_transfer(value=10_000.0, unit="psi", demo=False):
    return MR5ATransfer(
        "m",
        "2026-07-18",
        "geo",
        "4b",
        "fp4b",
        value,
        unit,
        "ENSAYO_DIRECTO",
        "ENSAYO_DIRECTO",
        "Ing. Responsable",
        "Adopción revisada",
        "Informe LAB-1",
        demo,
        ("advertencia MR",),
    )


def valid_input(**changes):
    e = changes.pop("esal_transfer", esal_transfer())
    m = changes.pop("mr_transfer", mr_transfer())
    data = AASHTO93Input(
        "D-5A",
        "Tramo Norte",
        e,
        m,
        e.accumulated_esal,
        m.adopted_mr,
        m.unit,
        90.0,
        -1.282,
        "CATALOGO",
        ZR_CATALOG_VERSION,
        0.45,
        "Estudio local",
        "MANUAL",
        4.2,
        2.5,
        1.7,
        "2026–2045",
        (("W18", "3B"), ("MR", "4B"), ("R_ZR", "CATALOGO")),
        "Ing. Responsable",
        "Parámetros revisados para demostración",
        ("heredada",),
        SolverSettings(0.01, 15.0, 1e-8, 100),
        False,
        created_at="2026-07-18T00:00:00Z",
    )
    return replace(data, **changes)


def test_reference_case_substitutes_back_into_equation():
    result = calculate_required_sn(valid_input())
    assert result.required_sn == pytest.approx(4.0421, abs=0.005)
    assert abs(result.residual) <= 1e-8
    assert aashto_log10_w18(
        result.required_sn,
        zr=result.zr,
        s0=result.s0,
        delta_psi=result.delta_psi,
        mr_psi=result.mr_psi,
    ) == pytest.approx(math.log10(result.w18), abs=1e-8)
    assert result.converged and result.iterations > 0
    assert result.equation == EQUATION and MANDATORY_WARNING in result.warnings


def test_catalog_is_explicit_versioned_and_has_expected_signs():
    assert set(ZR_CATALOG) == {50.0, 75.0, 80.0, 85.0, 90.0, 95.0, 99.0}
    assert zr_from_catalog(50.0) == 0
    assert all(zr_from_catalog(r) < 0 for r in ZR_CATALOG if r > 50)
    with pytest.raises(ValueError, match="catálogo"):
        zr_from_catalog(92.0)


def test_mpa_conversion_is_explicit_and_unknown_unit_blocks():
    assert convert_mr_to_psi(1, "MPa") == pytest.approx(MPA_TO_PSI)
    assert convert_mr_to_psi(7500, "psi") == 7500
    with pytest.raises(ValueError, match="Unidad"):
        convert_mr_to_psi(1, "kPa")


@pytest.mark.parametrize("value", [0, -1, math.nan, math.inf, -math.inf])
def test_invalid_w18_blocks(value):
    with pytest.raises(ValueError, match="W18"):
        validate_input(valid_input(w18=value))


@pytest.mark.parametrize("value", [0, -1, math.nan, math.inf, -math.inf])
def test_invalid_mr_blocks(value):
    m = mr_transfer(value=value)
    with pytest.raises(ValueError, match="MR"):
        validate_input(valid_input(mr_transfer=m))


@pytest.mark.parametrize(
    "p0,pt", [(2.5, 2.5), (2.0, 2.5), (math.nan, 2.0), (4.2, math.inf)]
)
def test_invalid_serviceability_blocks(p0, pt):
    with pytest.raises(ValueError, match="Serviciabilidad"):
        validate_input(valid_input(p0=p0, pt=pt, delta_psi=p0 - pt))


@pytest.mark.parametrize("s0", [0, -1, math.nan, math.inf, 0.2, 0.7])
def test_invalid_s0_blocks(s0):
    with pytest.raises(ValueError, match="S0"):
        validate_input(valid_input(s0=s0))


@pytest.mark.parametrize(
    "settings",
    [
        SolverSettings(0, 15, 1e-4, 100),
        SolverSettings(2, 1, 1e-4, 100),
        SolverSettings(0.01, 15, 0, 100),
        SolverSettings(0.01, 15, 1e-4, 0),
        SolverSettings(math.nan, 15, 1e-4, 100),
    ],
)
def test_invalid_solver_settings_block(settings):
    with pytest.raises(ValueError):
        validate_input(valid_input(solver=settings))


def test_interval_without_root_and_insufficient_iterations_block():
    with pytest.raises(ValueError, match="no encierra"):
        calculate_required_sn(valid_input(solver=SolverSettings(0.01, 0.02, 1e-8, 100)))
    with pytest.raises(ValueError, match="no convergió"):
        calculate_required_sn(valid_input(solver=SolverSettings(0.01, 15, 1e-15, 1)))


def test_manual_zr_requires_correct_sign_and_declared_source():
    calculate_required_sn(valid_input(zr_source="MANUAL_JUSTIFICADO", zr=-1.3))
    with pytest.raises(ValueError, match="negativo"):
        validate_input(valid_input(zr_source="MANUAL_JUSTIFICADO", zr=0.1))
    with pytest.raises(ValueError, match="Fuente ZR"):
        validate_input(valid_input(zr_source="OTRA"))


def test_catalog_zr_must_match_reliability_and_version():
    with pytest.raises(ValueError, match="inconsistentes"):
        validate_input(valid_input(zr=-1.645))
    with pytest.raises(ValueError, match="inconsistentes"):
        validate_input(valid_input(zr_catalog_version="old"))


def test_demonstrative_input_requires_acknowledgement():
    with pytest.raises(ValueError, match="reconocimiento"):
        calculate_required_sn(valid_input(esal_transfer=esal_transfer(demo=True)))
    result = calculate_required_sn(
        valid_input(esal_transfer=esal_transfer(demo=True), synthetic_acknowledged=True)
    )
    assert result.is_demonstrative


def test_sensitivities_are_directionally_consistent():
    base = calculate_required_sn(valid_input())
    e2 = esal_transfer(10_000_000)
    assert (
        calculate_required_sn(valid_input(esal_transfer=e2)).required_sn
        > base.required_sn
    )
    m2 = mr_transfer(20_000)
    assert (
        calculate_required_sn(valid_input(mr_transfer=m2)).required_sn
        < base.required_sn
    )
    assert (
        calculate_required_sn(
            valid_input(reliability_percent=95, zr=-1.645)
        ).required_sn
        > base.required_sn
    )
    lower_delta = calculate_required_sn(valid_input(p0=4.2, pt=3.0, delta_psi=1.2))
    assert base.required_sn < lower_delta.required_sn


def test_w18_one_and_extreme_finite_values_are_controlled():
    e = esal_transfer(1)
    with pytest.raises(ValueError, match="no encierra"):
        calculate_required_sn(
            valid_input(esal_transfer=e, solver=SolverSettings(0.000001, 15, 1e-8, 100))
        )
    huge = esal_transfer(1e12)
    assert math.isfinite(
        calculate_required_sn(
            valid_input(esal_transfer=huge, solver=SolverSettings(0.01, 30, 1e-8, 200))
        ).required_sn
    )


def test_fingerprint_staleness_covers_parameters_and_methodology():
    data = valid_input()
    result = calculate_required_sn(data)
    assert not result_is_stale(result, data)
    variants = [
        replace(data, w18=data.w18 + 1),
        replace(data, reliability_percent=95, zr=-1.645),
        replace(data, s0=0.46),
        replace(data, p0=4.3, delta_psi=1.8),
        replace(data, pt=2.4, delta_psi=1.8),
        replace(data, solver=replace(data.solver, tolerance=1e-6)),
        replace(data, methodology_version=METHODOLOGY_VERSION + "-NEW"),
        replace(data, responsible="Otro"),
    ]
    assert all(result_is_stale(result, item) for item in variants)


def test_history_preserves_previous_result_without_automatic_writes():
    session = {}
    first = calculate_required_sn(valid_input())
    store_result(session, valid_input(), first)
    second_data = valid_input(s0=0.46)
    second = calculate_required_sn(second_data)
    store_result(session, second_data, second)
    assert session["aashto93_phase5a_history"] == [first]
    assert "pavement_design_result" not in session and "mr_psi" not in session


def test_residual_is_reproducible_and_nonfinite_equation_inputs_block():
    data = valid_input()
    result = calculate_required_sn(data)
    assert residual(result.required_sn, data) == pytest.approx(result.residual)
    with pytest.raises(ValueError):
        aashto_log10_w18(math.nan, zr=-1.282, s0=0.45, delta_psi=1.7, mr_psi=10000)


def test_contracts_are_frozen_and_serializable():
    data = valid_input()
    json_text = __import__("json").dumps(data.as_dict())
    assert "D-5A" in json_text
    with pytest.raises(Exception):
        data.w18 = 1
