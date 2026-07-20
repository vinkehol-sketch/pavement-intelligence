from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from pavement_intelligence.vision.analysis import ocr_controller, ocr_models
from pavement_intelligence.vision.analysis.ocr_controller import (
    NormalizedPlateRoi,
    NormalizedRoiExtractor,
    PlateAnalysisConfig,
    PlateAnalysisController,
)
from pavement_intelligence.vision.analysis.ocr_models import (
    PlateAnalysisState,
    PlateReadingOrigin,
    PlateReadingStatus,
)
from pavement_intelligence.vision.capture.base import FrameResult, SourceInfo
from pavement_intelligence.vision.plates.base import PlateResult


FRAME = np.zeros((100, 200, 3), dtype=np.uint8)


class FakeSource:
    def __init__(
        self,
        frame_count: int = 3,
        *,
        source_id: str = "plate-camera:test",
        read_error: Exception | None = None,
        open_error: Exception | None = None,
    ) -> None:
        self.frames = [FRAME.copy() for _ in range(frame_count)]
        self._source_id = source_id
        self.read_error = read_error
        self.open_error = open_error
        self.position = 0
        self.opened = False
        self.close_calls = 0
        self.read_calls = 0

    @property
    def source_id(self) -> str:
        return self._source_id

    def open(self) -> bool:
        if self.open_error:
            raise self.open_error
        self.opened = True
        self.position = 0
        return True

    def is_open(self) -> bool:
        return self.opened

    def read(self) -> FrameResult:
        self.read_calls += 1
        if self.read_error:
            error, self.read_error = self.read_error, None
            raise error
        if self.position >= len(self.frames):
            return FrameResult(None, self.position, self.position * 1000.0, False, self.source_id)
        frame = self.frames[self.position]
        self.position += 1
        return FrameResult(frame, self.position, self.position * 1000.0, True, self.source_id)

    def close(self) -> None:
        self.close_calls += 1
        self.opened = False

    def source_info(self) -> SourceInfo:
        return SourceInfo(
            self.source_id,
            "test",
            1.0,
            200,
            100,
            len(self.frames),
            self.position,
        )


class FakeReader:
    def __init__(self, results=()) -> None:
        self.results = list(results)
        self.calls: list[tuple[np.ndarray, tuple[int, int, int, int]]] = []

    def detect_and_read(self, frame, bbox):
        self.calls.append((frame.copy(), bbox))
        if not self.results:
            return None
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def plate(text: str | None, confidence: float = 0.8) -> PlateResult:
    return PlateResult(text, None, confidence, None, is_anonymized=False)


def controller(
    *,
    source: FakeSource | None = None,
    reader: FakeReader | None = None,
    config: PlateAnalysisConfig | None = None,
) -> PlateAnalysisController:
    return PlateAnalysisController(
        source or FakeSource(),
        reader or FakeReader(),
        NormalizedRoiExtractor(),
        config or PlateAnalysisConfig(every_n_frames=1),
    )


def test_initial_state_is_idle_and_empty():
    subject = controller()
    assert subject.state is PlateAnalysisState.IDLE
    assert subject.readings == ()
    assert subject.last_result is None


def test_start_opens_valid_source_and_creates_independent_batch():
    subject = controller()
    info = subject.start()
    assert info.source_id == "plate-camera:test"
    assert subject.state is PlateAnalysisState.RUNNING
    assert subject.plate_batch_id.startswith("plate:")


def test_first_valid_reading_has_neutral_contract():
    subject = controller(reader=FakeReader([plate("abc-123", 0.91)]))
    subject.start()
    result = subject.process_next()
    reading = result.readings[0]
    assert reading.normalized_text == "ABC123"
    assert reading.raw_text == "abc-123"
    assert reading.confidence == 0.91
    assert reading.status is PlateReadingStatus.PENDING
    assert reading.origin is PlateReadingOrigin.OPERATIONAL_OCR
    assert reading.reviewed is False


def test_reader_without_result_emits_no_invented_reading():
    subject = controller(reader=FakeReader([None]))
    subject.start()
    assert subject.process_next().readings == ()
    assert subject.readings == ()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(" abc-123 ", "ABC123"), ("XY Z.987", "XYZ987"), ("ábc-12", "BC12")],
)
def test_text_normalization(raw, expected):
    subject = controller(reader=FakeReader([plate(raw)]))
    subject.start()
    assert subject.process_next().readings[0].normalized_text == expected


@pytest.mark.parametrize(
    ("confidence", "expected"),
    [(-0.5, 0.0), (0.0, 0.0), (0.6, 0.6), (1.0, 1.0), (4.0, 1.0), (float("nan"), 0.0)],
)
def test_confidence_is_bounded(confidence, expected):
    subject = controller(reader=FakeReader([plate("ABC123", confidence)]))
    subject.start()
    assert subject.process_next().readings[0].confidence == expected


@pytest.mark.parametrize("raw", [None, "", " - . "])
def test_empty_normalized_text_is_ignored(raw):
    subject = controller(reader=FakeReader([plate(raw)]))
    subject.start()
    assert subject.process_next().readings == ()


def test_duplicate_reading_is_not_appended_twice():
    subject = controller(reader=FakeReader([plate("ABC123", 0.8), plate("ABC-123", 0.7)]))
    subject.start()
    subject.process_next()
    subject.process_next()
    assert len(subject.readings) == 1
    assert subject.readings[0].confidence == 0.8


def test_duplicate_keeps_higher_confidence_and_reading_id():
    subject = controller(reader=FakeReader([plate("ABC123", 0.5), plate("ABC123", 0.95)]))
    subject.start()
    first = subject.process_next().readings[0]
    replacement = subject.process_next().readings[0]
    assert replacement.reading_id == first.reading_id
    assert subject.readings == (replacement,)
    assert replacement.confidence == 0.95


def test_same_text_outside_window_creates_new_reading():
    subject = controller(
        reader=FakeReader([plate("ABC123"), plate("ABC123")]),
        config=PlateAnalysisConfig(every_n_frames=1, dedup_window_seconds=0.5),
    )
    subject.start()
    subject.process_next()
    subject.process_next()
    assert len(subject.readings) == 2


def test_dedup_memory_is_bounded():
    subject = controller(
        source=FakeSource(frame_count=5),
        reader=FakeReader([plate(f"ABC12{i}") for i in range(5)]),
        config=PlateAnalysisConfig(every_n_frames=1, max_dedup_entries=2),
    )
    subject.start()
    for _ in range(5):
        subject.process_next()
    assert subject.dedup_entry_count == 2


def test_batch_memory_limit_is_bounded_and_warned():
    subject = controller(
        source=FakeSource(frame_count=3),
        reader=FakeReader([plate("AAA111"), plate("BBB222"), plate("CCC333")]),
        config=PlateAnalysisConfig(every_n_frames=1, max_batch_readings=2),
    )
    subject.start()
    for _ in range(3):
        subject.process_next()
    batch = subject.finish()
    assert len(batch.readings) == 2
    assert batch.warnings == ("Se alcanzó el límite de lecturas del lote OCR.",)


def test_processing_frequency_is_deterministic_every_n_frames():
    reader = FakeReader([plate("A11111"), plate("B22222"), plate("C33333")])
    subject = controller(
        source=FakeSource(frame_count=6),
        reader=reader,
        config=PlateAnalysisConfig(every_n_frames=2),
    )
    subject.start()
    for _ in range(6):
        subject.process_next()
    assert len(reader.calls) == 3
    assert [item.frame_index for item in subject.readings] == [1, 3, 5]


def test_pause_does_not_advance_source_or_metrics():
    source = FakeSource()
    subject = controller(source=source, reader=FakeReader([plate("ABC123")]))
    subject.start()
    first = subject.process_next()
    subject.pause()
    assert subject.process_next() is first
    assert source.read_calls == 1
    assert subject.state is PlateAnalysisState.PAUSED


def test_resume_continues_from_previous_frame():
    source = FakeSource()
    subject = controller(source=source)
    subject.start()
    subject.process_next()
    subject.pause()
    subject.resume()
    assert subject.process_next().frame_index == 2


def test_reset_clears_batch_dedup_error_and_returns_idle():
    subject = controller(reader=FakeReader([plate("ABC123")]))
    subject.start()
    subject.process_next()
    subject.reset()
    assert subject.state is PlateAnalysisState.IDLE
    assert subject.readings == ()
    assert subject.dedup_entry_count == 0
    assert subject.plate_batch_id == ""
    assert subject.last_result is None


def test_finish_is_idempotent_and_preserves_batch():
    subject = controller(reader=FakeReader([plate("ABC123")]))
    subject.start()
    subject.process_next()
    first = subject.finish()
    second = subject.finish()
    assert first == second
    assert first.state is PlateAnalysisState.FINISHED
    assert first.normative is False


def test_end_of_source_emits_one_terminal_result_and_closes():
    source = FakeSource(frame_count=0)
    subject = controller(source=source)
    subject.start()
    terminal = subject.process_next()
    assert terminal.end_of_source is True
    assert subject.process_next() is None
    assert subject.state is PlateAnalysisState.FINISHED
    assert source.opened is False


def test_change_source_closes_and_clears_previous_batch():
    first_source = FakeSource(source_id="plate:first")
    subject = controller(source=first_source, reader=FakeReader([plate("ABC123")]))
    subject.start()
    subject.process_next()
    second_source = FakeSource(source_id="plate:second")
    subject.change_source(second_source)
    assert first_source.opened is False
    assert subject.source is second_source
    assert subject.readings == ()
    assert subject.state is PlateAnalysisState.IDLE


def test_reader_error_is_controlled_and_closes_source():
    source = FakeSource()
    subject = controller(source=source, reader=FakeReader([RuntimeError("reader failed")]))
    subject.start()
    result = subject.process_next()
    assert subject.state is PlateAnalysisState.ERROR
    assert result.warnings == ("reader failed",)
    assert source.opened is False
    assert subject.readings == ()


def test_source_read_error_is_controlled():
    subject = controller(source=FakeSource(read_error=OSError("source failed")))
    subject.start()
    assert subject.process_next().warnings == ("source failed",)
    assert subject.state is PlateAnalysisState.ERROR


def test_source_open_error_raises_and_leaves_error_state():
    subject = controller(source=FakeSource(open_error=OSError("cannot open")))
    with pytest.raises(OSError, match="cannot open"):
        subject.start()
    assert subject.state is PlateAnalysisState.ERROR


def test_error_recovery_requires_reset_and_can_restart():
    source = FakeSource(read_error=OSError("once"))
    subject = controller(source=source)
    subject.start()
    subject.process_next()
    subject.reset()
    subject.start()
    assert subject.state is PlateAnalysisState.RUNNING


def test_error_cannot_restart_without_reset():
    subject = controller(source=FakeSource(read_error=OSError("once")))
    subject.start()
    subject.process_next()
    with pytest.raises(RuntimeError, match="IDLE"):
        subject.start()


def test_close_is_explicit_and_idempotent():
    source = FakeSource()
    subject = controller(source=source)
    subject.start()
    subject.close()
    subject.close()
    assert source.opened is False
    assert source.close_calls >= 2


def test_configured_source_id_hides_physical_source_identity():
    subject = controller(
        source=FakeSource(source_id="temporary-random-name.mp4"),
        reader=FakeReader([plate("ABC123")]),
        config=PlateAnalysisConfig(every_n_frames=1, source_id="uploaded-video:stable"),
    )
    subject.start()
    reading = subject.process_next().readings[0]
    assert reading.source_id == "uploaded-video:stable"
    assert subject.batch_result().source_id == "uploaded-video:stable"


def test_roi_extractor_is_configurable_and_does_not_mutate_frame():
    frame = FRAME.copy()
    extractor = NormalizedRoiExtractor(NormalizedPlateRoi(0.25, 0.2, 0.75, 0.8))
    region = extractor.extract(frame)[0]
    assert region.bbox == (50, 20, 150, 80)
    assert np.array_equal(frame, FRAME)


@pytest.mark.parametrize(
    "roi",
    [NormalizedPlateRoi(), NormalizedPlateRoi(0.0, 0.0, 1.0, 1.0)],
)
def test_roi_contract_is_immutable(roi):
    with pytest.raises(FrozenInstanceError):
        roi.x1 = 0.4


@pytest.mark.parametrize(
    "kwargs",
    [
        {"every_n_frames": 0},
        {"dedup_window_seconds": -1},
        {"max_dedup_entries": 0},
        {"max_batch_readings": 0},
    ],
)
def test_invalid_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        PlateAnalysisConfig(**kwargs)


def test_controller_has_no_streamlit_tpda_or_traffic_pipeline_dependency():
    source = inspect.getsource(ocr_controller).lower()
    assert "streamlit" not in source
    assert "tpda" not in source
    assert "trafficanalysiscontroller" not in source
    assert "visionpipeline" not in source
    assert "track_id" not in source


def test_contracts_have_no_streamlit_state_or_mutability():
    source = inspect.getsource(ocr_models).lower()
    assert "streamlit" not in source
    assert "session_state" not in source
    subject = controller(reader=FakeReader([plate("ABC123")]))
    subject.start()
    reading = subject.process_next().readings[0]
    with pytest.raises(FrozenInstanceError):
        reading.confidence = 0.1
