"""Tests for chunk-data extraction and the metadata-carrying subscriber path.

These exercise the pure, pypylon-free seam (``extract_chunk_metadata``) against
fake grab results, plus the ``(frame, timestamp, metadata)`` contract that now
flows through the subscriber queue to ``CallbackSubscriber`` callbacks.
"""

from __future__ import annotations

import threading

from basler_vision.hardware.frame_metadata import (
    FrameMetadata,
    extract_chunk_metadata,
)
from basler_vision.core.subscribers import (
    CallbackSubscriber,
    FrameSubscriber,
    LatestFrameSubscriber,
)


class _ValueNode:
    """Mimics a pylon node read via ``.GetValue()``."""

    def __init__(self, value):
        self._value = value

    def GetValue(self):
        return self._value


class _AttrNode:
    """Mimics a pylon node read via ``.Value``."""

    def __init__(self, value):
        self.Value = value


class _RaisingNode:
    def GetValue(self):
        raise RuntimeError("chunk not enabled")


class _FakeResult:
    def __init__(self, **attrs):
        for name, value in attrs.items():
            setattr(self, name, value)


# --- extract_chunk_metadata -------------------------------------------------


def test_extracts_all_chunks_via_getvalue_nodes():
    result = _FakeResult(
        ChunkFrameID=_ValueNode(42),
        ChunkTimestamp=_ValueNode(1_000_000_000),  # ns -> 1.0 s
        ChunkExposureTime=_ValueNode(2500.0),
    )

    meta = extract_chunk_metadata(result)

    assert meta == FrameMetadata(
        frame_id=42, device_timestamp_s=1.0, exposure_time_us=2500.0
    )


def test_reads_value_attribute_and_raw_values():
    result = _FakeResult(
        ChunkFrameID=_AttrNode(7),
        ChunkTimestamp=2_000_000_000,  # raw int, ns -> 2.0 s
        ChunkExposureTime=_AttrNode(100.0),
    )

    meta = extract_chunk_metadata(result)

    assert meta.frame_id == 7
    assert meta.device_timestamp_s == 2.0
    assert meta.exposure_time_us == 100.0


def test_alternate_frame_counter_attribute_name():
    result = _FakeResult(ChunkFramecounter=_ValueNode(99))

    meta = extract_chunk_metadata(result)

    assert meta.frame_id == 99
    assert meta.device_timestamp_s is None


def test_counter_value_chunk_is_frame_id_fallback():
    result = _FakeResult(ChunkCounterValue=_ValueNode(1234))

    meta = extract_chunk_metadata(result)

    assert meta.frame_id == 1234
    assert meta.device_timestamp_s is None


def test_returns_none_when_no_chunk_attributes():
    assert extract_chunk_metadata(_FakeResult()) is None


def test_node_that_raises_on_read_is_skipped():
    result = _FakeResult(ChunkFrameID=_RaisingNode(), ChunkExposureTime=_ValueNode(5.0))

    meta = extract_chunk_metadata(result)

    assert meta.frame_id is None
    assert meta.exposure_time_us == 5.0


def test_is_empty_property():
    assert FrameMetadata().is_empty
    assert not FrameMetadata(frame_id=1).is_empty


# --- subscriber (frame, timestamp, metadata) contract -----------------------


def test_frame_subscriber_round_trips_metadata():
    sub = FrameSubscriber(threading.Event())
    meta = FrameMetadata(frame_id=3)

    sub.push("frame", 1.5, processed=True, metadata=meta)
    frame, timestamp, got = sub.grab(timeout=0.01)

    assert (frame, timestamp) == ("frame", 1.5)
    assert got is meta


def test_empty_grab_returns_three_none():
    sub = FrameSubscriber(threading.Event())

    assert sub.grab(timeout=0.01) == (None, None, None)
    assert sub.get_nowait() == (None, None, None)


def test_callback_receives_metadata():
    received = []
    stop = threading.Event()
    sub = CallbackSubscriber(
        lambda frame, timestamp, metadata: received.append((frame, timestamp, metadata)),
        stop,
    )
    meta = FrameMetadata(frame_id=11, device_timestamp_s=0.25)

    sub.start()
    try:
        sub.push("f", 0.25, processed=True, metadata=meta)
        deadline = threading.Event()
        # Spin briefly until the worker thread drains the frame.
        for _ in range(200):
            if received:
                break
            deadline.wait(0.01)
    finally:
        stop.set()
        sub.stop()
        sub.join(timeout=2)

    assert received == [("f", 0.25, meta)]


def test_latest_frame_subscriber_returns_metadata():
    sub = LatestFrameSubscriber(threading.Event())
    meta = FrameMetadata(exposure_time_us=42.0)

    assert sub.get_latest() == (None, None, None)
    sub.push("f", 9.0, processed=True, metadata=meta)
    assert sub.get_latest() == ("f", 9.0, meta)
