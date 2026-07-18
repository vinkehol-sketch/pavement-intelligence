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

    # ── Aviso de datos simulados ──────────────────────────────────────────────
    st.warning(
        "⚠️ **AVISO IMPORTANTE:** Los datos sintéticos del caso demostrativo están "
        "etiquetados explícitamente como **SIMULADO**. Los resultados son de carácter "
        "educativo y **no reemplazan** un estudio de ingeniería vial formal. "
        "Reemplace los datos de ejemplo con información real antes de usar para toma "
        "de decisiones.",
        icon="⚠️",
    )

    st.markdown("---")

    # ── Estado del flujo del MVP ──────────────────────────────────────────────
    st.subheader("🔄 Estado de Progreso del Flujo MVP")
    
    video_done = st.session_state.get("processing_done", False)
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
            "### 🚀 Caso Demostrativo\n\n"
            "El proyecto incluye un **caso demostrativo completo** para la "
            "*Vía Secundaria Demostrativa — La Paz, Bolivia* con:\n\n"
            "- **Conteo vehicular** de 24 horas (48 registros horarios) — **SIMULADO**\n"
            "- **Datos de pesaje** de 50 vehículos pesados — **SIMULADO**\n"
            "- **5 muestras de suelo** con CBR entre 3.5% y 7.2% — **SIMULADO**\n"
            "- **Diseño AASHTO 93** para SN ≈ 3.84 — **CALCULADO**\n\n"
            "Ubique los archivos en `data/samples/caso_demostrativo/`."
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
        "Datos demostrativos etiquetados como SIMULADO"
    )

if __name__ == "__main__":
    render()

