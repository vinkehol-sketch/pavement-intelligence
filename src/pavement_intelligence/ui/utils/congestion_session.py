"""Ciclo de sesión y deduplicación de congestión para el dashboard real."""

from __future__ import annotations

import logging
from typing import Any, MutableMapping

from pavement_intelligence.domain.traffic.congestion import CongestionEngine
from pavement_intelligence.domain.traffic.congestion_aggregation import (
    CongestionIntervalAggregator,
)
from pavement_intelligence.domain.traffic.congestion_runtime import (
    CongestionRuntimeState,
    TrafficCongestionCoordinator,
    TrafficCongestionSnapshot,
)
from pavement_intelligence.ui.utils.congestion_presentation import (
    CongestionAlertPresentation,
    CongestionPresentationState,
    present_congestion_alert,
    present_congestion_snapshot,
)


LOGGER = logging.getLogger(__name__)

COORDINATOR_KEY = "traffic_congestion_coordinator"
SNAPSHOT_KEY = "traffic_congestion_snapshot"
PRESENTATION_KEY = "traffic_congestion_presentation"
ERROR_KEY = "traffic_congestion_error"
SOURCE_ID_KEY = "traffic_congestion_source_id"
LAST_FRAME_KEY = "traffic_congestion_last_processed_frame_key"
ALERTS_KEY = "traffic_congestion_alerts"


def initialize_congestion_session(session: MutableMapping[str, Any]) -> None:
    session.setdefault(COORDINATOR_KEY, None)
    session.setdefault(SNAPSHOT_KEY, None)
    session.setdefault(PRESENTATION_KEY, None)
    session.setdefault(ERROR_KEY, "")
    session.setdefault(SOURCE_ID_KEY, None)
    session.setdefault(LAST_FRAME_KEY, None)
    session.setdefault(ALERTS_KEY, ())


def start_congestion_session(
    session: MutableMapping[str, Any],
    source_id: str,
    *,
    monitoring_point_id: str | None = None,
) -> TrafficCongestionCoordinator:
    clear_congestion_session(session)
    coordinator = TrafficCongestionCoordinator(
        CongestionIntervalAggregator(),
        CongestionEngine(),
        monitoring_point_id=monitoring_point_id,
    )
    coordinator.set_source(source_id)
    session[COORDINATOR_KEY] = coordinator
    session[SOURCE_ID_KEY] = source_id
    return coordinator


def clear_congestion_session(session: MutableMapping[str, Any]) -> None:
    initialize_congestion_session(session)
    coordinator = session.get(COORDINATOR_KEY)
    if coordinator is not None:
        coordinator.reset()
    session[COORDINATOR_KEY] = None
    session[SNAPSHOT_KEY] = None
    session[PRESENTATION_KEY] = None
    session[ERROR_KEY] = ""
    session[SOURCE_ID_KEY] = None
    session[LAST_FRAME_KEY] = None
    session[ALERTS_KEY] = ()


def reset_congestion_session(
    session: MutableMapping[str, Any], source_id: str
) -> TrafficCongestionCoordinator:
    initialize_congestion_session(session)
    coordinator = session.get(COORDINATOR_KEY)
    if coordinator is None:
        return start_congestion_session(session, source_id)
    coordinator.reset()
    coordinator.set_source(source_id)
    session[SOURCE_ID_KEY] = source_id
    session[SNAPSHOT_KEY] = None
    session[PRESENTATION_KEY] = None
    session[ERROR_KEY] = ""
    session[LAST_FRAME_KEY] = None
    session[ALERTS_KEY] = ()
    return coordinator


def process_congestion_result_once(
    session: MutableMapping[str, Any], result: Any
) -> CongestionPresentationState | None:
    initialize_congestion_session(session)
    coordinator = session.get(COORDINATOR_KEY)
    source_id = session.get(SOURCE_ID_KEY)
    if coordinator is None or not source_id:
        session[ERROR_KEY] = "La estimación de congestión no tiene una fuente activa."
        return None

    try:
        frame_key = congestion_frame_key(str(source_id), result)
        if frame_key == session.get(LAST_FRAME_KEY):
            return session.get(PRESENTATION_KEY)
        snapshot = coordinator.process_frame_result(result)
    except Exception as exc:
        LOGGER.exception("Falló el procesamiento de congestión de un frame")
        session[ERROR_KEY] = str(exc) or exc.__class__.__name__
        return session.get(PRESENTATION_KEY)

    session[LAST_FRAME_KEY] = frame_key
    return _store_snapshot(session, snapshot)


def pause_congestion_session(
    session: MutableMapping[str, Any],
) -> CongestionPresentationState | None:
    initialize_congestion_session(session)
    coordinator = session.get(COORDINATOR_KEY)
    if coordinator is None or coordinator.state is CongestionRuntimeState.IDLE:
        return session.get(PRESENTATION_KEY)
    try:
        return _store_snapshot(session, coordinator.pause())
    except Exception as exc:
        return _store_error(session, "pausar", exc)


def resume_congestion_session(
    session: MutableMapping[str, Any],
) -> CongestionPresentationState | None:
    initialize_congestion_session(session)
    coordinator = session.get(COORDINATOR_KEY)
    if coordinator is None or coordinator.state is not CongestionRuntimeState.PAUSED:
        return session.get(PRESENTATION_KEY)
    try:
        return _store_snapshot(session, coordinator.resume())
    except Exception as exc:
        return _store_error(session, "continuar", exc)


def finish_congestion_session(
    session: MutableMapping[str, Any],
) -> CongestionPresentationState | None:
    initialize_congestion_session(session)
    coordinator = session.get(COORDINATOR_KEY)
    if coordinator is None:
        return session.get(PRESENTATION_KEY)
    try:
        return _store_snapshot(session, coordinator.finish())
    except Exception as exc:
        return _store_error(session, "finalizar", exc)


def congestion_frame_key(
    source_id: str, result: Any
) -> tuple[str, int | None, float, bool]:
    return (
        source_id,
        getattr(result, "frame_index", None),
        float(result.timestamp_seconds),
        bool(result.end_of_source),
    )


def _store_snapshot(
    session: MutableMapping[str, Any], snapshot: TrafficCongestionSnapshot
) -> CongestionPresentationState:
    presentation = present_congestion_snapshot(snapshot)
    session[SNAPSHOT_KEY] = snapshot
    session[PRESENTATION_KEY] = presentation
    session[ERROR_KEY] = ""
    if snapshot.alert is not None:
        _store_alert(session, present_congestion_alert(snapshot.alert))
    return presentation


def _store_alert(
    session: MutableMapping[str, Any], alert: CongestionAlertPresentation
) -> None:
    alerts = list(session.get(ALERTS_KEY, ()))
    for index, current in enumerate(alerts):
        if current.alert_id == alert.alert_id:
            alerts[index] = alert
            session[ALERTS_KEY] = tuple(alerts)
            return
    alerts.append(alert)
    session[ALERTS_KEY] = tuple(alerts)


def _store_error(
    session: MutableMapping[str, Any], action: str, exc: Exception
) -> CongestionPresentationState | None:
    LOGGER.exception("No se pudo %s la estimación de congestión", action)
    session[ERROR_KEY] = str(exc) or exc.__class__.__name__
    return session.get(PRESENTATION_KEY)


__all__ = [
    "ALERTS_KEY",
    "COORDINATOR_KEY",
    "ERROR_KEY",
    "LAST_FRAME_KEY",
    "PRESENTATION_KEY",
    "SNAPSHOT_KEY",
    "SOURCE_ID_KEY",
    "clear_congestion_session",
    "congestion_frame_key",
    "finish_congestion_session",
    "initialize_congestion_session",
    "pause_congestion_session",
    "process_congestion_result_once",
    "reset_congestion_session",
    "resume_congestion_session",
    "start_congestion_session",
]
