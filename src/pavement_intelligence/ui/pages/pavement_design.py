"""
Página de Diseño de Pavimento Flexible — AASHTO 93
====================================================
Módulo completo para el diseño de pavimento flexible por el
método AASHTO 93, incluyendo cálculo del Número Estructural (SN)
y propuesta de espesores de capas.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ── Tablas de parámetros AASHTO 93 ───────────────────────────────────────────

# ZR según nivel de confiabilidad (R%)
ZR_TABLE: Dict[int, float] = {
    50: 0.000, 60: -0.253, 70: -0.524, 75: -0.674,
    80: -0.842, 85: -1.037, 90: -1.282, 95: -1.645,
    99: -2.327,
}

# Coeficientes de capa típicos (a_i)
LAYER_A_COEFF: Dict[str, float] = {
    "Carpeta Asfáltica (Concreto Bituminoso)": 0.44,
    "Tratamiento Superficial Doble (TSD)": 0.20,
    "Base Granular Estabilizada CBR≥80%": 0.14,
    "Base Granular CBR≥60%": 0.12,
    "Subbase Granular CBR≥30%": 0.11,
    "Subbase Granular CBR≥20%": 0.08,
}

LAYER_MATERIALS_ORDERED = list(LAYER_A_COEFF.keys())

# Espesores mínimos recomendados AASHTO 93 (cm) por tipo y W18
THICKNESS_LIMITS: Dict[str, Tuple[float, float]] = {
    "Carpeta Asfáltica (Concreto Bituminoso)": (5.0, 30.0),
    "Tratamiento Superficial Doble (TSD)": (2.5, 5.0),
    "Base Granular Estabilizada CBR≥80%": (10.0, 40.0),
    "Base Granular CBR≥60%": (10.0, 40.0),
    "Subbase Granular CBR≥30%": (10.0, 50.0),
    "Subbase Granular CBR≥20%": (10.0, 50.0),
}


@dataclass
class LayerDesign:
    """Diseño de una capa del pavimento."""
    layer_number: int
    material: str
    thickness_cm: float
    layer_coefficient: float

    @property
    def sn_contribution(self) -> float:
        """Contribución de la capa al SN total (sin factor de drenaje m_i)."""
        return self.layer_coefficient * self.thickness_cm * (1 / 2.54)  # cm → in


@dataclass
class PavementDesignResult:
    """Resultado del diseño de pavimento AASHTO 93."""
    design_converged: bool
    required_sn: float
    provided_sn: float
    layers: List[LayerDesign]
    warnings: List[str]
    z_r: float
    s_0: float
    delta_psi: float
    mr_psi: float
    design_esal_w18: float


def _get_zr(reliability_pct: float) -> float:
    """Interpola ZR para el nivel de confiabilidad dado."""
    r_int = int(round(reliability_pct / 5.0) * 5)
    r_int = max(50, min(99, r_int))
    return ZR_TABLE.get(r_int, ZR_TABLE[85])


def _log10_w18_from_sn(
    sn: float,
    z_r: float,
    s_0: float,
    delta_psi: float,
    mr_psi: float,
) -> float:
    """
    Calcula log10(W18) usando la ecuación AASHTO 93 para pavimento flexible.
    Ecuación 5.1 del manual AASHTO Guide for Design of Pavement Structures 1993.
    """
    if mr_psi <= 0 or sn <= 0:
        return 0.0

    term1 = z_r * s_0
    term2 = 9.36 * math.log10(sn + 1) - 0.20
    term3 = math.log10(delta_psi / (4.2 - 1.5)) / (0.40 + 1094 / (sn + 1) ** 5.19)
    term4 = 2.32 * math.log10(mr_psi) - 8.07

    return term1 + term2 + term3 + term4


def _solve_sn(
    target_log_w18: float,
    z_r: float,
    s_0: float,
    delta_psi: float,
    mr_psi: float,
    sn_min: float = 0.5,
    sn_max: float = 10.0,
    tol: float = 1e-4,
    max_iter: int = 100,
) -> Tuple[float, bool]:
    """Resuelve el SN requerido por bisección."""
    for _ in range(max_iter):
        sn_mid = (sn_min + sn_max) / 2.0
        val = _log10_w18_from_sn(sn_mid, z_r, s_0, delta_psi, mr_psi)
        if abs(val - target_log_w18) < tol:
            return sn_mid, True
        if val < target_log_w18:
            sn_min = sn_mid
        else:
            sn_max = sn_mid
    return (sn_min + sn_max) / 2.0, True


def _design_pavement(
    design_esal_w18: float,
    subgrade_cbr_percent: float,
    reliability_percent: float,
    s0: float = 0.45,
    initial_psi: float = 4.2,
    terminal_psi: float = 2.5,
    layers_config: Optional[List[Dict]] = None,
) -> PavementDesignResult:
    """Ejecuta el diseño de pavimento flexible AASHTO 93."""
    warnings: List[str] = []

    # Validaciones
    if subgrade_cbr_percent <= 0:
        warnings.append("❌ CBR de subrasante debe ser mayor a 0%.")
        return PavementDesignResult(False, 0, 0, [], warnings, 0, s0, 0, 0, design_esal_w18)

    if design_esal_w18 <= 0:
        warnings.append("❌ El ESAL de diseño (W18) debe ser mayor a 0.")
        return PavementDesignResult(False, 0, 0, [], warnings, 0, s0, 0, 0, design_esal_w18)

    if subgrade_cbr_percent < 3.0:
        warnings.append("⚠️ CBR < 3%: Subrasante muy débil. Considere mejoramiento antes del diseño.")
    if subgrade_cbr_percent > 30.0:
        warnings.append("ℹ️ CBR > 30%: Subrasante excelente — verifique clasificación de subrasante vs. subbase.")

    mr_psi = 1500.0 * subgrade_cbr_percent
    z_r = _get_zr(reliability_percent)
    delta_psi = initial_psi - terminal_psi

    if delta_psi <= 0:
        warnings.append("❌ PSI inicial debe ser mayor al PSI terminal.")
        return PavementDesignResult(False, 0, 0, [], warnings, z_r, s0, delta_psi, mr_psi, design_esal_w18)

    target_log_w18 = math.log10(max(design_esal_w18, 1.0))
    required_sn, converged = _solve_sn(target_log_w18, z_r, s0, delta_psi, mr_psi)

    if not converged:
        warnings.append("⚠️ El proceso iterativo no convergió. Revise los parámetros.")

    # ── Diseño de capas por defecto ───────────────────────────────────────────
    if layers_config is None:
        # Propuesta estándar: carpeta + base + subbase
        layers_config = [
            {"material": "Carpeta Asfáltica (Concreto Bituminoso)", "a": 0.44, "thickness_cm": 10.0},
            {"material": "Base Granular CBR≥60%", "a": 0.12, "thickness_cm": 20.0},
            {"material": "Subbase Granular CBR≥30%", "a": 0.11, "thickness_cm": 25.0},
        ]

    # Ajuste automático del espesor de la carpeta para satisfacer SN
    layers: List[LayerDesign] = []
    sn_acumulado = 0.0
    for i, lc in enumerate(layers_config):
        ld = LayerDesign(
            layer_number=i + 1,
            material=lc["material"],
            thickness_cm=lc["thickness_cm"],
            layer_coefficient=lc["a"],
        )
        layers.append(ld)
        sn_acumulado += ld.sn_contribution

    # Si el SN provisto es insuficiente, aumentar carpeta asfáltica
    deficit = required_sn - sn_acumulado
    if deficit > 0.05 and layers:
        extra_in = deficit / layers[0].layer_coefficient
        extra_cm = extra_in * 2.54
        layers[0] = LayerDesign(
            layer_number=1,
            material=layers[0].material,
            thickness_cm=layers[0].thickness_cm + extra_cm,
            layer_coefficient=layers[0].layer_coefficient,
        )

    provided_sn = sum(ld.sn_contribution for ld in layers)

    if provided_sn < required_sn * 0.99:
        warnings.append(f"⚠️ SN provisto ({provided_sn:.2f}) < SN requerido ({required_sn:.2f}). Aumente espesores.")

    return PavementDesignResult(
        design_converged=converged,
        required_sn=required_sn,
        provided_sn=provided_sn,
        layers=layers,
        warnings=warnings,
        z_r=z_r,
        s_0=s0,
        delta_psi=delta_psi,
        mr_psi=mr_psi,
        design_esal_w18=design_esal_w18,
    )


# ── Render ────────────────────────────────────────────────────────────────────

def render() -> None:
    """Renderiza la página de diseño de pavimento flexible."""
    st.title("🛣️ Diseño de Pavimento Flexible — AASHTO 93")
    st.markdown(
        "Diseñe el paquete estructural de pavimento flexible utilizando el "
        "**Método AASHTO 93**. Complete los parámetros de cada sección y "
        "ejecute el diseño."
    )
    st.markdown("---")

    # ── Sección 1: Parámetros de tránsito ─────────────────────────────────────
    st.subheader("1️⃣ Parámetros de Tránsito")

    esal_result = st.session_state.get("esal_result")
    esal_default = 1_850_000.0

    if esal_result is not None:
        esal_default = esal_result.total_esal_w18
        st.success(
            f"✅ W18 disponible desde el módulo ESAL: "
            f"**{esal_default:,.0f} repeticiones de eje estándar**"
        )
    else:
        st.info("ℹ️ Sin ESAL calculado en sesión. Use el valor demostrativo o calcule primero.")

    w18 = st.number_input(
        "W18 — ESAL de Diseño (repeticiones de eje estándar 80 kN)",
        min_value=1_000.0,
        max_value=500_000_000.0,
        value=esal_default,
        step=10_000.0,
        format="%.0f",
        help="Número de repeticiones de ejes equivalentes de 80 kN durante el período de diseño.",
    )

    if esal_result is None:
        st.caption(
            "📌 Valor por defecto: **SIMULADO** — caso demostrativo Vía Secundaria La Paz, Bolivia."
        )

    # ── Sección 2: Confiabilidad ───────────────────────────────────────────────
    st.markdown("---")
    st.subheader("2️⃣ Parámetros de Confiabilidad")

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        confiabilidad = st.slider(
            "Nivel de Confiabilidad R (%)",
            min_value=50, max_value=99, value=85, step=5,
            help=(
                "AASHTO recomienda: "
                "R=85% para vías principales rurales, "
                "R=90-95% para vías urbanas principales."
            ),
        )
        zr_val = _get_zr(float(confiabilidad))
        st.metric("ZR correspondiente", f"{zr_val:.3f}")

    with col_r2:
        s0 = st.slider(
            "Desviación Estándar Global S₀",
            min_value=0.30, max_value=0.60, value=0.45, step=0.05,
            help=(
                "Contempla la variabilidad en los materiales y en la predicción del tránsito. "
                "AASHTO: 0.40-0.50 para pavimento flexible."
            ),
        )
        st.caption(
            "S₀ representa la variabilidad total del proceso de diseño. "
            "Valores típicos: 0.40 – 0.50 (AASHTO)."
        )

    # ── Sección 3: Serviciabilidad ─────────────────────────────────────────────
    st.markdown("---")
    st.subheader("3️⃣ Serviciabilidad (PSI)")

    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        p0 = st.number_input(
            "PSI Inicial p₀",
            min_value=3.0, max_value=5.0, value=4.2, step=0.1,
            help="Índice de Serviciabilidad Inicial. AASHTO: 4.2 para pavimento nuevo.",
        )
    with col_s2:
        pt = st.number_input(
            "PSI Terminal pₜ",
            min_value=1.5, max_value=3.5, value=2.5, step=0.1,
            help=(
                "Índice de Serviciabilidad Terminal (mínimo aceptable). "
                "AASHTO: 2.5 para vías principales, 2.0 para secundarias."
            ),
        )
    with col_s3:
        delta_psi = p0 - pt
        st.metric("ΔPSI = p₀ - pₜ", f"{delta_psi:.1f}")
        if delta_psi <= 0:
            st.error("❌ p₀ debe ser mayor que pₜ.")

    # ── Sección 4: Subrasante ──────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("4️⃣ Características de la Subrasante")

    cbr_session = st.session_state.get("cbr_diseno")
    mr_session = st.session_state.get("mr_psi")
    cbr_default = float(cbr_session) if cbr_session is not None else 5.0

    if cbr_session is not None:
        st.success(
            f"✅ CBR de diseño disponible desde el módulo de Suelo: "
            f"**{cbr_session:.2f}%** → MR = **{mr_session:,.0f} psi**"
        )
    else:
        st.info("ℹ️ Sin CBR calculado en sesión. Use el valor demostrativo o calcule en el módulo de Suelo.")

    col_cbr1, col_cbr2, col_cbr3 = st.columns(3)
    with col_cbr1:
        cbr_input = st.number_input(
            "CBR de Subrasante (%)",
            min_value=0.5, max_value=100.0, value=cbr_default, step=0.5,
            help="CBR del percentil de diseño (saturado). Ver módulo de Estudio de Suelo.",
        )
    with col_cbr2:
        mr_calc = 1500.0 * cbr_input
        st.metric("MR estimado (psi)", f"{mr_calc:,.0f}")
        st.caption("MR = 1,500 × CBR")
    with col_cbr3:
        mr_kpa = mr_calc * 6.895
        st.metric("MR estimado (kPa)", f"{mr_kpa:,.0f}")

    st.warning(
        "⚠️ **Hipótesis de correlación:** MR = 1,500 × CBR (Heukelom & Klomp, 1962). "
        "Esta correlación es una aproximación. Se recomienda realizar ensayos triaxiales "
        "de carga repetida (AASHTO T-307) para diseños definitivos.",
        icon="⚠️",
    )

    # ── Sección 5: Período de diseño ──────────────────────────────────────────
    st.markdown("---")
    st.subheader("5️⃣ Período de Diseño")

    periodo_diseno = st.slider(
        "Período de diseño (años)",
        min_value=10, max_value=30, value=20, step=5,
        help="AASHTO recomienda 20 años para vías secundarias.",
    )

    # ── Configuración de capas ─────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("6️⃣ Configuración de Capas del Pavimento")
    st.caption(
        "Configure el paquete estructural. El sistema ajustará el espesor de la "
        "capa superior para cumplir el SN requerido."
    )

    col_lyr = st.columns(3)
    layers_config = []

    LAYER_DEFAULTS = [
        ("Carpeta Asfáltica (Concreto Bituminoso)", 0.44, 10.0),
        ("Base Granular CBR≥60%", 0.12, 20.0),
        ("Subbase Granular CBR≥30%", 0.11, 25.0),
    ]

    for i, (col, (mat_def, a_def, t_def)) in enumerate(zip(col_lyr, LAYER_DEFAULTS)):
        with col:
            st.markdown(f"**Capa {i+1}**")
            mat = st.selectbox(
                f"Material (Capa {i+1})",
                LAYER_MATERIALS_ORDERED,
                index=LAYER_MATERIALS_ORDERED.index(mat_def),
                key=f"layer_mat_{i}",
            )
            a_i = st.number_input(
                f"Coeficiente a{i+1}",
                0.01, 0.60,
                value=LAYER_A_COEFF.get(mat, a_def),
                step=0.01,
                format="%.2f",
                key=f"layer_a_{i}",
            )
            t_i = st.number_input(
                f"Espesor propuesto (cm)",
                5.0, 60.0, value=t_def, step=1.0,
                key=f"layer_t_{i}",
            )
            layers_config.append({"material": mat, "a": a_i, "thickness_cm": t_i})

    # ── Botón principal ────────────────────────────────────────────────────────
    st.markdown("---")
    ejecutar = st.button(
        "🛣️ Ejecutar Diseño AASHTO 93",
        type="primary",
        use_container_width=True,
        help="Calcula el SN requerido y verifica el paquete estructural propuesto.",
    )

    if ejecutar:
        if delta_psi <= 0:
            st.error("❌ Corrija los valores de PSI antes de ejecutar el diseño.")
            return

        with st.spinner("Calculando diseño AASHTO 93..."):
            resultado = _design_pavement(
                design_esal_w18=float(w18),
                subgrade_cbr_percent=float(cbr_input),
                reliability_percent=float(confiabilidad),
                s0=float(s0),
                initial_psi=float(p0),
                terminal_psi=float(pt),
                layers_config=layers_config,
            )

        st.session_state["diseno_result"] = resultado
        st.session_state["diseno_calculado"] = True

        st.success("✅ **CALCULADO** — Diseño AASHTO 93 completado.")
        st.markdown("---")

        # ── Resultado principal ────────────────────────────────────────────────
        st.subheader("📊 Resultados del Diseño — CALCULADO")

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("SN Requerido", f"{resultado.required_sn:.2f}")
        with m2:
            delta_sn = resultado.provided_sn - resultado.required_sn
            st.metric("SN Provisto", f"{resultado.provided_sn:.2f}", delta=f"{delta_sn:+.2f}")
        with m3:
            estado = "✅ OK" if resultado.provided_sn >= resultado.required_sn * 0.99 else "❌ Insuficiente"
            st.metric("Estado del Diseño", estado)
        with m4:
            st.metric("Nivel de Confiabilidad", f"{confiabilidad}%")

        # ── Tabla de capas ─────────────────────────────────────────────────────
        st.markdown("#### 📋 Paquete Estructural — CALCULADO")
        df_layers = pd.DataFrame(
            [
                {
                    "Capa": ld.layer_number,
                    "Material": ld.material,
                    "Espesor (cm)": round(ld.thickness_cm, 1),
                    "Espesor (in)": round(ld.thickness_cm / 2.54, 2),
                    "Coef. Capa (a_i)": round(ld.layer_coefficient, 3),
                    "SN Parcial": round(ld.sn_contribution, 3),
                }
                for ld in resultado.layers
            ]
        )

        # Fila de totales
        total_row = pd.DataFrame([{
            "Capa": "TOTAL",
            "Material": "—",
            "Espesor (cm)": round(sum(ld.thickness_cm for ld in resultado.layers), 1),
            "Espesor (in)": round(sum(ld.thickness_cm / 2.54 for ld in resultado.layers), 2),
            "Coef. Capa (a_i)": "—",
            "SN Parcial": round(resultado.provided_sn, 3),
        }])
        df_display = pd.concat([df_layers, total_row], ignore_index=True)
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        # ── Gráfico de barras de capas ─────────────────────────────────────────
        colores_capas = ["#2C3E50", "#7F8C8D", "#BDC3C7"]
        fig_capas = go.Figure()
        y_pos = 0.0
        for i, ld in enumerate(reversed(resultado.layers)):
            color = colores_capas[i % len(colores_capas)]
            fig_capas.add_trace(go.Bar(
                x=[ld.thickness_cm],
                y=[ld.material],
                orientation="h",
                marker_color=color,
                name=ld.material,
                text=f"{ld.thickness_cm:.1f} cm",
                textposition="inside",
            ))
        fig_capas.update_layout(
            title="Estructura de Capas del Pavimento — CALCULADO",
            xaxis_title="Espesor (cm)",
            barmode="group",
            plot_bgcolor="#0e1117",
            paper_bgcolor="#0e1117",
            font_color="#ffffff",
            showlegend=False,
        )
        st.plotly_chart(fig_capas, use_container_width=True)

        # ── Advertencias ──────────────────────────────────────────────────────
        if resultado.warnings:
            st.markdown("---")
            st.subheader("⚠️ Advertencias del Sistema")
            for w in resultado.warnings:
                st.warning(w)

        # ── Resumen de parámetros ─────────────────────────────────────────────
        st.markdown("---")
        st.subheader("📝 Resumen de Parámetros de Diseño")
        st.markdown(
            f"""
            | Parámetro | Valor |
            |-----------|-------|
            | Método | AASHTO Guide for Design of Pavement Structures, 1993 |
            | Tipo | Pavimento Flexible |
            | W18 (ESAL de diseño) | `{w18:,.0f}` repeticiones de eje estándar 80 kN |
            | Confiabilidad (R) | `{confiabilidad}%` |
            | ZR | `{resultado.z_r:.3f}` |
            | S₀ (desviación estándar global) | `{resultado.s_0:.2f}` |
            | PSI inicial (p₀) | `{p0}` |
            | PSI terminal (pₜ) | `{pt}` |
            | ΔPSI | `{resultado.delta_psi:.1f}` |
            | CBR de subrasante | `{cbr_input:.1f}%` (saturado) |
            | MR de subrasante | `{resultado.mr_psi:,.0f} psi` |
            | **SN Requerido** | **`{resultado.required_sn:.2f}`** |
            | **SN Provisto** | **`{resultado.provided_sn:.2f}`** |
            | Estado de diseño | {"✅ Satisfactorio" if resultado.design_converged else "⚠️ Revisar"} |
            """
        )

        # ── Disclaimer ────────────────────────────────────────────────────────
        st.markdown("---")
        st.error(
            "📌 **DISCLAIMER:** Los resultados de este módulo son de carácter **educativo y "
            "demostrativo**. El diseño final de pavimentos requiere la intervención de un "
            "Ingeniero Vial certificado, estudios de campo verificados, y el cumplimiento de "
            "las normativas vigentes del país (Bolivia: ABC — Administradora Boliviana de "
            "Carreteras). **No utilice estos resultados para construcción real** sin la "
            "validación de un profesional habilitado.",
            icon="🚨",
        )

if __name__ == "__main__":
    render()

