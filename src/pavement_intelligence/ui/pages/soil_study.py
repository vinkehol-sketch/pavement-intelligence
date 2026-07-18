"""
Página de Estudio de Suelo y Subrasante
=========================================
Permite registrar muestras de suelo, calcular el CBR de diseño
representativo y estimar el módulo resiliente de la subrasante.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# ── Clasificaciones ──────────────────────────────────────────────────────────

CLASIFICACIONES_SUCS = [
    "GW", "GP", "GM", "GC", "SW", "SP", "SM", "SC",
    "ML", "CL", "OL", "MH", "CH", "OH", "Pt",
]

CLASIFICACIONES_AASHTO = [
    "A-1-a", "A-1-b", "A-2-4", "A-2-5", "A-2-6", "A-2-7",
    "A-3", "A-4", "A-5", "A-6", "A-7-5", "A-7-6",
]

CONDICIONES_CBR = ["saturado", "no saturado", "sumergido"]

TIPOS_DRENAJE = ["bueno", "regular", "pobre", "muy pobre"]

PERCENTILES_DISENO = [60, 75, 80, 85, 90, 95]


def _mr_from_cbr(cbr: float) -> float:
    """
    Estima el Módulo Resiliente (MR) en psi a partir del CBR.
    Correlación: MR [psi] = 1500 * CBR  (AASHTO 93, Heukelom & Klomp).
    """
    return 1500.0 * cbr


def _design_cbr(cbr_values: List[float], percentile: int = 75) -> float:
    """Calcula el CBR de diseño como percentil de la distribución."""
    if not cbr_values:
        return 0.0
    sorted_vals = sorted(cbr_values)
    n = len(sorted_vals)
    # Método de posición percentílica
    rank = percentile / 100.0 * (n - 1)
    lower = int(rank)
    upper = min(lower + 1, n - 1)
    frac = rank - lower
    return sorted_vals[lower] + frac * (sorted_vals[upper] - sorted_vals[lower])


# ── Datos de ejemplo SIMULADOS ────────────────────────────────────────────────

MUESTRAS_DEMO = [
    {
        "Descripción": "Calzada principal km 0+000",
        "Progresiva (km)": 0.0,
        "Profundidad (m)": 1.5,
        "SUCS": "CL",
        "AASHTO": "A-6",
        "Índice de Grupo": 8,
        "CBR (%)": 4.8,
        "Condición CBR": "saturado",
        "Expansión (%)": 1.2,
        "Dens. Máx. Proctor (kN/m³)": 17.8,
        "Humedad Óptima (%)": 14.5,
        "Observaciones": "Arcilla de mediana plasticidad. SIMULADO",
    },
    {
        "Descripción": "Cuneta derecha km 0+500",
        "Progresiva (km)": 0.5,
        "Profundidad (m)": 1.5,
        "SUCS": "ML",
        "AASHTO": "A-4",
        "Índice de Grupo": 5,
        "CBR (%)": 6.2,
        "Condición CBR": "saturado",
        "Expansión (%)": 0.8,
        "Dens. Máx. Proctor (kN/m³)": 18.5,
        "Humedad Óptima (%)": 12.0,
        "Observaciones": "Limo de baja plasticidad. SIMULADO",
    },
    {
        "Descripción": "Calzada km 1+000",
        "Progresiva (km)": 1.0,
        "Profundidad (m)": 1.5,
        "SUCS": "CL",
        "AASHTO": "A-6",
        "Índice de Grupo": 9,
        "CBR (%)": 3.5,
        "Condición CBR": "saturado",
        "Expansión (%)": 1.5,
        "Dens. Máx. Proctor (kN/m³)": 17.2,
        "Humedad Óptima (%)": 15.8,
        "Observaciones": "Arcilla de alta plasticidad. CBR crítico. SIMULADO",
    },
    {
        "Descripción": "Calzada km 1+500",
        "Progresiva (km)": 1.5,
        "Profundidad (m)": 1.5,
        "SUCS": "SC",
        "AASHTO": "A-2-6",
        "Índice de Grupo": 3,
        "CBR (%)": 7.2,
        "Condición CBR": "saturado",
        "Expansión (%)": 0.5,
        "Dens. Máx. Proctor (kN/m³)": 19.2,
        "Humedad Óptima (%)": 10.5,
        "Observaciones": "Arena arcillosa, mejor capacidad. SIMULADO",
    },
    {
        "Descripción": "Calzada km 2+000",
        "Progresiva (km)": 2.0,
        "Profundidad (m)": 1.5,
        "SUCS": "GM",
        "AASHTO": "A-2-4",
        "Índice de Grupo": 1,
        "CBR (%)": 5.8,
        "Condición CBR": "saturado",
        "Expansión (%)": 0.3,
        "Dens. Máx. Proctor (kN/m³)": 20.1,
        "Humedad Óptima (%)": 9.2,
        "Observaciones": "Grava limosa. SIMULADO",
    },
]


def render() -> None:
    """Renderiza la página de estudio de suelo."""
    st.title("🌍 Estudio de Suelo y Subrasante")
    st.markdown(
        "Registre las muestras de suelo del tramo, determine el **CBR de diseño** "
        "representativo y estime el **Módulo Resiliente (MR)** de la subrasante."
    )
    st.markdown("---")

    # ── Inicializar estado ────────────────────────────────────────────────────
    if "muestras_list" not in st.session_state:
        st.session_state["muestras_list"] = []

    # ── Opción de cargar datos demo ───────────────────────────────────────────
    st.subheader("📂 Datos de Ejemplo")
    if st.button("📥 Cargar Muestras Demostrativas (SIMULADO)", type="secondary"):
        st.session_state["muestras_list"] = MUESTRAS_DEMO.copy()
        st.session_state["muestras_suelo"] = len(MUESTRAS_DEMO)
        st.success(f"✅ Se cargaron {len(MUESTRAS_DEMO)} muestras demostrativas — **SIMULADO**")

    st.markdown("---")

    # ── Formulario de nueva muestra ───────────────────────────────────────────
    st.subheader("➕ Registrar Nueva Muestra")

    with st.form("form_muestra"):
        fc1, fc2 = st.columns(2)

        with fc1:
            descripcion = st.text_input("Descripción del punto", value="Calzada km 0+000")
            progresiva = st.number_input("Progresiva (km)", 0.0, 100.0, 0.0, 0.1)
            profundidad = st.number_input("Profundidad (m)", 0.1, 5.0, 1.5, 0.1)
            sucs = st.selectbox("Clasificación SUCS", CLASIFICACIONES_SUCS, index=4)
            aashto = st.selectbox("Clasificación AASHTO", CLASIFICACIONES_AASHTO, index=9)
            indice_grupo = st.number_input("Índice de Grupo (IG)", 0, 20, 5, 1)

        with fc2:
            cbr_val = st.number_input("CBR (%)", 0.5, 100.0, 5.0, 0.1)
            cbr_cond = st.selectbox("Condición del CBR", CONDICIONES_CBR)
            expansion = st.number_input("Expansión (%)", 0.0, 20.0, 1.0, 0.1)
            densidad = st.number_input("Dens. Máx. Proctor (kN/m³)", 10.0, 25.0, 18.0, 0.1)
            humedad_opt = st.number_input("Humedad Óptima (%)", 1.0, 40.0, 12.0, 0.1)
            drenaje = st.selectbox("Condición de Drenaje", TIPOS_DRENAJE)

        nivel_freatico = st.number_input(
            "Nivel Freático (m desde superficie, -1 si no observado)",
            -1.0, 10.0, -1.0, 0.5,
        )
        observaciones = st.text_area("Observaciones / Notas", height=80)

        submitted = st.form_submit_button("✅ Registrar Muestra", type="primary")

    if submitted:
        nueva_muestra = {
            "Descripción": descripcion,
            "Progresiva (km)": progresiva,
            "Profundidad (m)": profundidad,
            "SUCS": sucs,
            "AASHTO": aashto,
            "Índice de Grupo": indice_grupo,
            "CBR (%)": cbr_val,
            "Condición CBR": cbr_cond,
            "Expansión (%)": expansion,
            "Dens. Máx. Proctor (kN/m³)": densidad,
            "Humedad Óptima (%)": humedad_opt,
            "Observaciones": observaciones,
        }
        st.session_state["muestras_list"].append(nueva_muestra)
        st.session_state["muestras_suelo"] = len(st.session_state["muestras_list"])
        st.success(f"✅ Muestra registrada. Total: {len(st.session_state['muestras_list'])}")

    # ── Tabla de muestras registradas ─────────────────────────────────────────
    muestras = st.session_state.get("muestras_list", [])

    if muestras:
        st.markdown("---")
        st.subheader(f"📋 Muestras Registradas ({len(muestras)})")
        df_m = pd.DataFrame(muestras)
        st.dataframe(df_m, use_container_width=True, hide_index=True)

        # ── CBR de diseño ─────────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("🎯 CBR de Diseño Representativo")

        cbr_vals = [m["CBR (%)"] for m in muestras]

        col_cbr1, col_cbr2 = st.columns(2)
        with col_cbr1:
            percentil = st.selectbox(
                "Percentil de diseño (%)",
                PERCENTILES_DISENO,
                index=1,
                help=(
                    "AASHTO 93 recomienda percentil 75-85 para diseño conservador. "
                    "El valor seleccionado es una hipótesis de ingeniería."
                ),
            )

        cbr_diseno = _design_cbr(cbr_vals, int(percentil))
        mr_psi = _mr_from_cbr(cbr_diseno)
        mr_kpa = mr_psi * 6.895  # 1 psi = 6.895 kPa

        with col_cbr2:
            st.markdown(f"**CBR de diseño (percentil {percentil}%):**")
            st.markdown(f"### {cbr_diseno:.2f} %")

        st.info(
            f"⚙️ **Correlación MR = 1,500 × CBR (AASHTO 93 / Heukelom & Klomp)**\n\n"
            f"- CBR de diseño: **{cbr_diseno:.2f}%** (percentil {percentil}%)\n"
            f"- MR estimado: **{mr_psi:,.0f} psi** = **{mr_kpa:,.0f} kPa**\n\n"
            f"⚠️ Esta correlación es una estimación. Se recomienda realizar ensayos "
            f"triaxiales de carga repetida (AASHTO T-307) para valores definitivos.",
            icon="⚙️",
        )

        # Guardar en sesión
        st.session_state["cbr_diseno"] = cbr_diseno
        st.session_state["mr_psi"] = mr_psi

        # ── Gráfico de CBR ────────────────────────────────────────────────────
        df_cbr = pd.DataFrame({
            "Progresiva (km)": [m["Progresiva (km)"] for m in muestras],
            "CBR (%)": cbr_vals,
            "Descripción": [m["Descripción"] for m in muestras],
        })

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=[f"km {m['Progresiva (km)']:.1f}" for m in muestras],
            y=cbr_vals,
            name="CBR (%)",
            marker_color="#4A90D9",
        ))
        fig.add_hline(
            y=cbr_diseno,
            line_dash="dash",
            line_color="#F5A623",
            annotation_text=f"CBR diseño = {cbr_diseno:.2f}% (P{percentil})",
            annotation_position="top right",
        )
        fig.update_layout(
            title="Perfil de CBR a lo largo del Tramo",
            xaxis_title="Progresiva",
            yaxis_title="CBR (%)",
            plot_bgcolor="#0e1117",
            paper_bgcolor="#0e1117",
            font_color="#ffffff",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.info(
            "💡 **Siguiente paso:** Vaya al módulo **🛣️ Diseño de Pavimento** "
            f"— el CBR de diseño ({cbr_diseno:.2f}%) y MR ({mr_psi:,.0f} psi) "
            "se transferirán automáticamente."
        )

    else:
        st.info(
            "📂 **Sin muestras.** Use el botón de muestras demostrativas o registre "
            "manualmente las muestras de su proyecto."
        )

if __name__ == "__main__":
    render()

