from pavement_intelligence.ui.utils.demo_data import load_demo_dashboard
from pavement_intelligence.ui.utils.traffic_analysis_state import prepare_session_for_real_analysis


def synthetic_session():
    return {
        "is_synthetic_review": True,
        "vision_events_raw": [{"event_id": "demo"}],
        "vision_events_reviewed": [{"event_id": "demo"}],
        "vision_batch_metadata": {"source": "demo"},
        "traffic_counts_corrected": {"AUTO": 15},
        "traffic_review_approved": True,
        "traffic_review_source_fingerprint": "synthetic:demo",
        "tpda_input_from_review": {"synthetic": True},
        "traffic_demo_playing": True,
        "traffic_demo_frame_index": 42,
        "traffic_analysis_current_result": "old-real-result",
        "traffic_analysis_batch_events": ["old-event"],
    }


def test_starting_real_video_removes_synthetic_metrics_and_selection():
    session = synthetic_session()
    prepare_session_for_real_analysis(session)
    assert session["is_synthetic_review"] is False
    assert session["traffic_counts_corrected"] == {}
    assert session["traffic_review_approved"] is False
    assert session["traffic_demo_playing"] is False
    assert session["traffic_demo_frame_index"] == 0


def test_starting_real_camera_hides_previous_synthetic_batch_from_review():
    session = synthetic_session()
    prepare_session_for_real_analysis(session)
    assert session["vision_events_raw"] == []
    assert session["vision_events_reviewed"] == []
    assert session["vision_batch_metadata"] == {}
    assert session["traffic_review_source_fingerprint"] is None
    assert session["tpda_input_from_review"] is None


def test_real_temporary_events_are_cleared_but_finalized_real_batch_is_preserved():
    session = synthetic_session()
    session.update({
        "is_synthetic_review": False,
        "vision_events_raw": [{"event_id": "real-finalized"}],
        "vision_events_reviewed": [{"event_id": "real-finalized"}],
    })
    prepare_session_for_real_analysis(session)
    assert session["vision_events_raw"] == [{"event_id": "real-finalized"}]
    assert session["vision_events_reviewed"] == [{"event_id": "real-finalized"}]
    assert session["traffic_analysis_current_result"] is None
    assert session["traffic_analysis_batch_events"] == []


def test_demo_source_data_remains_available_after_real_cleanup():
    session = synthetic_session()
    prepare_session_for_real_analysis(session)
    dashboard = load_demo_dashboard()
    assert dashboard.demo_mode is True
    assert dashboard.metrics.accumulated_total > 0
