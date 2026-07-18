from pathlib import Path

SOURCE = Path("src/pavement_intelligence/ui/pages/reports.py").read_text(
    encoding="utf-8"
)


def test_ui_uses_formal_integrated_contract_not_legacy_keys():
    for expected in (
        "collect_phase_records",
        "build_dossier",
        "dossier_json_bytes",
        "dossier_pdf_bytes",
        "store_dossier",
    ):
        assert expected in SOURCE
    for forbidden in (
        "tpda_result",
        "esal_result",
        "cbr_diseno",
        "mr_psi",
        "diseno_result",
    ):
        assert forbidden not in SOURCE


def test_ui_exposes_admin_states_modes_preview_and_downloads():
    for expected in (
        "Nombre del proyecto",
        "Tramo",
        "Ubicación",
        "Entidad u organización",
        "Responsable",
        "Revisor",
        "Estado de fases y continuidad",
        "Modo de reporte",
        "Fases incluidas",
        "Vista previa",
        "Generar expediente demostrativo",
        "Descargar expediente JSON",
        "Descargar reporte PDF",
        "DESACTUALIZADO",
    ):
        assert expected in SOURCE


def test_ui_has_mandatory_warning_and_textual_states():
    assert "MANDATORY_WARNING" in SOURCE
    assert "Bloqueo:" in SOURCE and "Fases faltantes:" in SOURCE
    assert "No exporta el estado completo de Streamlit" in SOURCE
