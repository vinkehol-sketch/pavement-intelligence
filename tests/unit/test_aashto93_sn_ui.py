from pathlib import Path


SOURCE = Path("src/pavement_intelligence/ui/pages/aashto_sn.py").read_text(
    encoding="utf-8"
)


def test_ui_has_two_manual_import_actions_and_no_layer_design():
    assert "Importar ESAL aprobado desde Fase 3B" in SOURCE
    assert "Importar MR aprobado desde Fase 4B" in SOURCE
    assert "build_esal_5a_transfer" in SOURCE and "build_mr_5a_transfer" in SOURCE
    for forbidden in ("D1", "D2", "D3", "thickness", "layers_config", "LAYER_A_COEFF"):
        assert forbidden not in SOURCE


def test_ui_exposes_solver_traceability_warning_and_json():
    for expected in (
        "SN mínimo",
        "SN máximo",
        "Tolerancia de residuo",
        "Iteraciones máximas",
        "Margen relativo para advertir proximidad a límites",
        "residuo",
        "iteraciones",
        "MANDATORY_WARNING",
        "Descargar resultado JSON",
        "DESACTUALIZADO",
        "Cálculo bloqueado",
        "SN_CERCANO_LIMITE_",
    ):
        assert expected in SOURCE


def test_ui_does_not_write_legacy_design_keys():
    for forbidden in (
        'session_state["mr_psi"]',
        'session_state["cbr_diseno"]',
        'session_state["pavement_design_result"]',
    ):
        assert forbidden not in SOURCE
