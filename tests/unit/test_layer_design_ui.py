from pathlib import Path

SOURCE = Path("src/pavement_intelligence/ui/pages/layer_design.py").read_text(
    encoding="utf-8"
)


def test_ui_requires_manual_transfer_and_exposes_all_modes():
    assert "Importar manualmente SN vigente desde Fase 5A" in SOURCE
    for text in ("DesignMode.MANUAL", "DesignMode.ADJUST_ONE", "DesignMode.DISCRETE"):
        assert text in SOURCE


def test_ui_exposes_layers_results_rounding_warnings_and_json():
    for text in (
        "Carpeta asfáltica",
        "Base",
        "Subbase",
        "SN provisto",
        "Déficit",
        "Excedente",
        "Estado textual",
        "redondeo",
        "MANDATORY_WARNING",
        "Descargar resultado 5B JSON",
        "DESACTUALIZADO",
    ):
        assert text in SOURCE


def test_ui_does_not_claim_official_design_or_write_legacy_state():
    for forbidden in (
        'session_state["pavement_design_result"]',
        'session_state["diseno_result"]',
        "aprobado para construcción",
        "espesor recomendado oficial",
    ):
        assert forbidden not in SOURCE
