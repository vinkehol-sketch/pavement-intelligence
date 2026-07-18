"""
Página de Reportes y Exportación
===================================
Módulo para la exportación de resultados del análisis y diseño de pavimentos.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st


def _build_report_dict() -> Dict[str, Any]:
    """Construye un diccionario de reporte a partir de los datos de sesión."""
    report: Dict[str, Any] = {
        "sistema": "Pavement Intelligence",
        "version": "0.1.0-beta",
        "advertencia": "DATOS PARCIALMENTE SIMULADOS. Solo para uso demostrativo.",
    }

    tpda = st.session_state.get("tpda_result")
    if tpda is not None:
        report["tpda"] = {
            "tpda_total": round(tpda.tpda_total, 2),
            "design_tpda": round(tpda.design_tpda, 2),
            "expansion_factor": tpda.expansion_factor,
            "directional_factor": tpda.directional_factor,
            "lane_distribution_factor": tpda.lane_distribution_factor,
        }

    esal = st.session_state.get("esal_result")
    if esal is not None:
        report["esal"] = {
            "total_esal_w18": round(esal.total_esal_w18, 0),
            "design_period_years": esal.design_period_years,
            "growth_rate_percent": esal.growth_rate_percent,
        }

    cbr = st.session_state.get("cbr_diseno")
    mr = st.session_state.get("mr_psi")
    if cbr is not None:
        report["subrasante"] = {
            "cbr_diseno_pct": round(cbr, 2),
            "mr_estimado_psi": round(mr or 0, 0),
        }

    diseno = st.session_state.get("diseno_result")
    if diseno is not None:
        report["diseno_pavimento"] = {
            "metodo": "AASHTO 93 Flexible",
            "sn_requerido": round(diseno.required_sn, 3),
            "sn_provisto": round(diseno.provided_sn, 3),
            "confiabilidad_pct": None,
            "capas": [
                {
                    "capa": ld.layer_number,
                    "material": ld.material,
                    "espesor_cm": round(ld.thickness_cm, 1),
                    "coef_a": round(ld.layer_coefficient, 3),
                    "sn_parcial": round(ld.sn_contribution, 3),
                }
                for ld in diseno.layers
            ],
            "advertencias": diseno.warnings,
        }

    return report


def render() -> None:
    """Renderiza la página de reportes y exportación."""
    st.title("📄 Reportes y Exportación")
    st.markdown(
        "Exporte los resultados del análisis de tránsito y diseño de pavimento "
        "en formatos estándar para su documentación."
    )
    st.markdown("---")

    # ── Estado de los módulos ──────────────────────────────────────────────────
    st.subheader("📊 Estado de Módulos Calculados")

    checks = {
        "📊 TPDA": st.session_state.get("tpda_result") is not None,
        "🔢 ESAL (W18)": st.session_state.get("esal_result") is not None,
        "🌍 CBR de Suelo": st.session_state.get("cbr_diseno") is not None,
        "🛣️ Diseño Pavimento": st.session_state.get("diseno_result") is not None,
    }

    col_check = st.columns(len(checks))
    for col, (nombre, estado) in zip(col_check, checks.items()):
        with col:
            st.metric(nombre, "✅ Listo" if estado else "❌ Pendiente")

    completados = sum(checks.values())
    if completados == 0:
        st.warning(
            "⚠️ No hay resultados calculados aún. Complete al menos el módulo de "
            "**TPDA** y **Diseño de Pavimento** para exportar un reporte completo.",
            icon="⚠️",
        )
    else:
        st.success(f"✅ {completados} de {len(checks)} módulos completados.")

    st.markdown("---")

    # ── Exportación JSON ───────────────────────────────────────────────────────
    st.subheader("📥 Exportar Reporte en JSON")
    st.markdown(
        "El reporte JSON consolida todos los parámetros y resultados calculados "
        "en sesión en un único archivo estructurado."
    )

    if st.button("📋 Generar Reporte JSON", type="primary", use_container_width=False):
        report_data = _build_report_dict()
        json_str = json.dumps(report_data, indent=2, ensure_ascii=False)
        st.download_button(
            label="⬇️ Descargar reporte.json",
            data=json_str.encode("utf-8"),
            file_name="pavement_intelligence_reporte.json",
            mime="application/json",
        )
        st.code(json_str, language="json")

    st.markdown("---")

    # ── Exportación CSV de muestras ────────────────────────────────────────────
    st.subheader("📥 Exportar Muestras de Suelo en CSV")

    muestras = st.session_state.get("muestras_list", [])
    if muestras:
        df_muestras = pd.DataFrame(muestras)
        csv_bytes = df_muestras.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Descargar muestras_suelo.csv",
            data=csv_bytes,
            file_name="muestras_suelo.csv",
            mime="text/csv",
        )
        st.dataframe(df_muestras, use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ Sin muestras de suelo registradas en sesión.")

    st.markdown("---")

    # ── Módulos en desarrollo ─────────────────────────────────────────────────
    st.subheader("🔧 Exportaciones en Desarrollo")

    col_exp1, col_exp2, col_exp3 = st.columns(3)
    with col_exp1:
        st.button("📄 Exportar PDF (Próximamente)", disabled=True, use_container_width=True)
        st.caption("Reporte completo en PDF con tablas y gráficos.")
    with col_exp2:
        st.button("📊 Exportar Excel (Próximamente)", disabled=True, use_container_width=True)
        st.caption("Libro de Excel con hojas por módulo.")
    with col_exp3:
        st.button("🖨️ Imprimir / Vista Previa (Próximamente)", disabled=True, use_container_width=True)
        st.caption("Vista de impresión del reporte técnico.")

    st.markdown("---")
    st.caption(
        "⚠️ Todos los reportes generados incluyen la advertencia: "
        "**DATOS PARCIALMENTE SIMULADOS — Solo para uso demostrativo.** "
        "Reemplace con datos reales antes de uso técnico formal."
    )

if __name__ == "__main__":
    render()

