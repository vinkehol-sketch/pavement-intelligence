"""Construcción segura de argumentos para widgets con estado presembrado."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def widget_default(
    session: Mapping[str, Any],
    key: str,
    default: Any,
    *,
    parameter: str = "value",
) -> dict[str, Any]:
    """No envía dos fuentes de verdad si la clave ya vive en session_state."""
    if key in session:
        return {"key": key}
    return {"key": key, parameter: default}
