"""
Página de Inicio — Pavement Intelligence
=========================================
Muestra el resumen del sistema, estado de módulos y flujo de trabajo.
"""
from __future__ import annotations

import streamlit as st


def render() -> None:
    """Renderiza la página de inicio del panel."""
    # ── Encabezado principal ──────────────────────────────────────────────────
    st.markdown(
        """
        <div style="text-align:center; padding: 1.5rem 0;">
            <h1 style="font-size:3rem; margin-bottom:0.2rem;">🛣️ Pavement Intelligence</h1>
            <p style="font-size:1.25rem; color:#888;">
                Plataforma de Análisis de Tránsito y Diseño de Pavimentos
            </p>
            <p style="font-size:0.9rem; color:#aaa;">
                Bolivia · Método AASHTO 93 · Clasificación ABC Vial
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    demo_active = bool(st.session_state.get("demo_mode_active"))
    if not demo_active:
        st.caption(
            "Use **Cargar caso demostrativo** en la barra lateral para poblar el flujo "
            "completo sin mezclarlo con datos reales."
        )

    st.markdown("---")

    # ── Estado del flujo del MVP ──────────────────────────────────────────────
    st.subheader("🔄 Estado de Progreso del Flujo MVP")
    
    video_done = st.session_state.get("processing_done", False) or demo_active
    review_approved = st.session_state.get("traffic_review_approved", False)
    sent_to_tpda = st.session_state.get("tpda_input_from_review") is not None
    tpda_calculated = st.session_state.get("tpda_result") is not None
    
    # Determinar estados textuales
    if not video_done:
        video_status = "🔴 Video no procesado"
    else:
        video_status = "🟢 Conteo disponible"
        
    if not video_done:
        review_status = "⚪ Esperando video"
    elif not review_approved:
        review_status = "🟡 Revisión pendiente"
    else:
        review_status = "🟢 Aforo revisado y aprobado"
        
    if not review_approved:
        transfer_status = "⚪ Esperando aprobación"
    elif not sent_to_tpda:
        transfer_status = "🟡 Traspaso pendiente"
    else:
        transfer_status = "🟢 Datos enviados a TPDA"
        
    if not tpda_calculated:
        tpda_status = "⚪ TPDA sin calcular"
    else:
        tpda_status = "🟢 TPDA calculado"

    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        st.markdown(f"<div style='background:#1e2130; padding:10px; border-radius:6px; border-top: 3px solid #f63366;'><strong>1. Visión Artificial</strong><br>{video_status}</div>", unsafe_allow_html=True)
    with col_s2:
        st.markdown(f"<div style='background:#1e2130; padding:10px; border-radius:6px; border-top: 3px solid #f63366;'><strong>2. Auditoría Manual</strong><br>{review_status}</div>", unsafe_allow_html=True)
    with col_s3:
        st.markdown(f"<div style='background:#1e2130; padding:10px; border-radius:6px; border-top: 3px solid #f63366;'><strong>3. Traspaso a TPDA</strong><br>{transfer_status}</div>", unsafe_allow_html=True)
    with col_s4:
        st.markdown(f"<div style='background:#1e2130; padding:10px; border-radius:6px; border-top: 3px solid #f63366;'><strong>4. Diseño de Tránsito</strong><br>{tpda_status}</div>", unsafe_allow_html=True)

    st.markdown("---")

    if demo_active:
        summary = st.session_state.get("demo_case_summary", {})
        project = st.session_state.get("demo_project_metadata", {})
        parties = st.session_state.get("demo_responsible_parties", {})
        st.subheader("Resumen calculado del corredor ficticio")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Cruces observados", summary.get("observed_crossings", 0))
        m2.metric("Cruces aprobados", summary.get("approved_crossings", 0))
        m3.metric("TPDA base", f"{summary.get('tpda_base', 0):,.0f} veh/día")
        m4.metric("W18 de diseño", f"{summary.get('design_esal_w18', 0):,.0f}")
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("CBR de diseño", f"{summary.get('design_cbr_percent', 0):.1f} %")
        g2.metric("MR adoptado", f"{summary.get('adopted_mr_mpa', 0):.2f} MPa")
        g3.metric("SN requerido", f"{summary.get('required_sn', 0):.3f}")
        g4.metric("Reporte", summary.get("report_state", "—"))
        st.caption(
            f"Aforo sintético declarado: {summary.get('declared_duration_hours', 0):g} horas. "
            f"{summary.get('tpda_formula', '106 × 12 × 1 = 1.272 veh/día')}. "
            "Crecimiento 4,0 %, 20 años, FDD 0,52 y FDC 1,00."
        )
        with st.expander("Ficha sintética del caso", expanded=True):
            st.json(
                {
                    "proyecto": project,
                    "responsables_ficticios": parties,
                    "data_origin": "synthetic_demo",
                    "is_demo": True,
                }
            )

    st.markdown("---")

    # ── Métricas de estado del sistema ────────────────────────────────────────
    st.subheader("📊 Estado del Sistema")
    c1, c2, c3, c4 = st.columns(4)


    with c1:
        aforos = st.session_state.get("aforos_registrados", 0)
        st.metric(
            label="📋 Aforos Registrados",
            value=aforos,
            delta="Sin datos" if aforos == 0 else None,
            delta_color="off",
        )

    with c2:
        muestras = st.session_state.get("muestras_suelo", 0)
        st.metric(
            label="🌍 Muestras de Suelo",
            value=muestras,
            delta="Sin datos" if muestras == 0 else None,
            delta_color="off",
        )

    with c3:
        esal_calc = st.session_state.get("esal_calculado", False)
        st.metric(
            label="🔢 ESAL Calculado",
            value="✅ Sí" if esal_calc else "❌ No",
        )

    with c4:
        diseno_calc = st.session_state.get("diseno_calculado", False)
        st.metric(
            label="🛣️ Diseño Generado",
            value="✅ Sí" if diseno_calc else "❌ No",
        )

    st.markdown("---")

    # ── Flujo de trabajo ──────────────────────────────────────────────────────
    st.subheader("🔄 Flujo de Trabajo Recomendado")
    steps = [
        ("1️⃣", "Aforo y TPDA",       "Ingrese conteos vehiculares y calcule el TPDA de diseño."),
        ("2️⃣", "Datos de Pesaje",     "Importe registros de pesaje en báscula para caracterizar cargas."),
        ("3️⃣", "Cálculo ESAL",        "Obtenga los Ejes Equivalentes de diseño (W18) para el periodo."),
        ("4️⃣", "Estudio de Suelo",    "Registre muestras y determine el CBR de diseño representativo."),
        ("5️⃣", "Diseño de Pavimento", "Ejecute el diseño AASHTO 93 y obtenga espesores de capas."),
        ("6️⃣", "Reportes",            "Exporte los resultados en PDF o Excel para documentación."),
    ]

    col_a, col_b = st.columns([1, 2])
    with col_a:
        for icon, titulo, desc in steps:
            st.markdown(
                f"""
                <div style="background:#1e2130; border-radius:8px; padding:0.7rem 1rem;
                            margin-bottom:0.5rem; border-left: 4px solid #4A90D9;">
                    <strong>{icon} {titulo}</strong><br>
                    <span style="color:#aaa; font-size:0.85rem;">{desc}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with col_b:
        st.info(
            "### Caso demostrativo centralizado\n\n"
            "El corredor ficticio tiene dos sentidos, categorías livianas y pesadas, "
            "revisión manual, OCR aislado, expansión TPDA, pesaje sintético, ESAL, "
            "CBR/MR, AASHTO 93 y expediente final. Los resultados se construyen con "
            "los motores existentes y se limpian mediante **Reiniciar demostración**."
        )

    st.markdown("---")

    # ── Instrucciones rápidas ─────────────────────────────────────────────────
    st.subheader("📘 Inicio Rápido")
    with st.expander("Ver instrucciones de uso", expanded=False):
        st.markdown(
            """
            ### Pasos para usar el sistema

            1. **Navegue** usando el menú lateral izquierdo.
            2. **Ingrese datos reales** en cada módulo o use el caso demostrativo.
            3. **Los cálculos** se encadenan automáticamente: los resultados de Aforo
               alimentan el módulo ESAL, y este alimenta el Diseño de Pavimento.
            4. **Exporte** los resultados desde el módulo de Reportes.

            ### Datos Mínimos Requeridos

            | Módulo | Dato mínimo |
            |--------|-------------|
            | Aforo y TPDA | Conteo vehicular (mínimo 12h recomendado 24h) |
            | ESAL | TPDA por categoría + periodo de diseño |
            | Suelo | Al menos 3 muestras con CBR saturado |
            | Diseño | W18 + CBR de diseño + confiabilidad |

            ### Unidades del Sistema

            - Cargas: **kN** (kilonewtons)
            - Espesores: **cm** (centímetros)
            - MR Subrasante: **psi** (libras por pulgada cuadrada)
            - ESAL/W18: **repeticiones de 80 kN** (eje estándar AASHTO)
            """
        )

    # ── Información de versión ────────────────────────────────────────────────
    st.markdown("---")
    st.caption(
        "🛣️ Pavement Intelligence v0.1.0-beta · "
        "Método: AASHTO 93 Flexible · "
        "Clasificación vehicular: ABC Bolivia · "
        "Datos demo etiquetados como synthetic_demo"
    )

if __name__ == "__main__":
    render()

