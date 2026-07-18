"""CSS local y acotado para los chips no cubiertos por Streamlit."""
from __future__ import annotations

import html
import streamlit as st


_CHIP_CLASS = {
    "success": "status-chip--success",
    "warning": "status-chip--warning",
    "error": "status-chip--error",
    "info": "status-chip--info",
    "neutral": "status-chip--neutral",
}


def load_dashboard_css() -> None:
    st.html("""
    <style>
      .status-chip {display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;
        font-weight:600;letter-spacing:.04em;text-transform:uppercase;border:1px solid;}
      .status-chip--success {color:#166534;background:#DCFCE7;border-color:#16A34A;}
      .status-chip--warning {color:#854D0E;background:#FEF08A;border-color:#CA8A04;}
      .status-chip--error {color:#991B1B;background:#FEE2E2;border-color:#DC2626;}
      .status-chip--info {color:#003FB1;background:#D4DCFF;border-color:#1A56DB;}
      .status-chip--neutral {color:#434654;background:#F3F3FE;border-color:#C3C5D7;}
    </style>
    """)


def render_status_chip(label: str, tone: str = "neutral") -> str:
    css_class = _CHIP_CLASS.get(tone, _CHIP_CLASS["neutral"])
    return f'<span class="status-chip {css_class}">{html.escape(label)}</span>'
