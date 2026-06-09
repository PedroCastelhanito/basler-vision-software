"""Per-frame hardware metadata carried alongside each grabbed frame.

This module is deliberately free of any ``pypylon`` import so the extraction
logic can be unit-tested against fake grab results and reused without hardware.
The values originate from pylon *chunk data* (enabled via
``BaslerCamera.enable_chunk_data``); when chunk mode is off, or a camera does not
expose a given chunk, the corresponding field stays ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass

# Candidate chunk attribute names on a pylon grab result, most-preferred first.
# Different Basler models expose the frame counter under different names.
_FRAME_ID_ATTRS = ("ChunkFrameID", "ChunkFramecounter", "ChunkFrameCounter")
_TIMESTAMP_ATTRS = ("ChunkTimestamp",)
_EXPOSURE_ATTRS = ("ChunkExposureTime",)


@dataclass(frozen=True)
class FrameMetadata:
    """Hardware-reported metadata for a single frame.

    ``frame_id`` is the monotonic hardware frame counter — a gap in it is a
    provable dropped frame (improvement-plan item 1.2). ``device_timestamp_s``
    is the camera's own clock in seconds (used for the wall-clock regression in
    1.2). ``exposure_time_us`` is the effective exposure for the frame.
    """

    frame_id: int | None = None
    device_timestamp_s: float | None = None
    exposure_time_us: float | None = None

    @property
    def is_empty(self) -> bool:
        return (
            self.frame_id is None
            and self.device_timestamp_s is None
            and self.exposure_time_us is None
        )


def _read_chunk_value(result: object, names: tuple[str, ...]) -> object | None:
    """Return the first readable chunk value among ``names`` on ``result``.

    Handles both the pylon node form (an object with ``GetValue`` / ``Value``)
    and a plain value. A chunk attribute that exists but raises on read (e.g.
    the chunk was never enabled) is skipped rather than propagated.
    """
    for name in names:
        node = getattr(result, name, None)
        if node is None:
            continue
        try:
            if hasattr(node, "GetValue"):
                return node.GetValue()
            if hasattr(node, "Value"):
                return node.Value
            return node
        except Exception:
            continue
    return None


def extract_chunk_metadata(result: object) -> FrameMetadata | None:
    """Pull FrameID / Timestamp / ExposureTime chunks off a pylon grab result.

    Returns ``None`` when no chunk value could be read, so callers can treat a
    chunk-less camera the same as chunk mode being disabled. The device
    timestamp chunk is reported in nanoseconds (like ``GrabResult.TimeStamp``)
    and converted to seconds here.
    """
    raw_frame_id = _read_chunk_value(result, _FRAME_ID_ATTRS)
    raw_timestamp = _read_chunk_value(result, _TIMESTAMP_ATTRS)
    raw_exposure = _read_chunk_value(result, _EXPOSURE_ATTRS)

    frame_id = None
    if raw_frame_id is not None:
        try:
            frame_id = int(raw_frame_id)
        except (TypeError, ValueError):
            frame_id = None

    device_timestamp_s = None
    if raw_timestamp is not None:
        try:
            device_timestamp_s = float(raw_timestamp) * 1e-9
        except (TypeError, ValueError):
            device_timestamp_s = None

    exposure_time_us = None
    if raw_exposure is not None:
        try:
            exposure_time_us = float(raw_exposure)
        except (TypeError, ValueError):
            exposure_time_us = None

    metadata = FrameMetadata(
        frame_id=frame_id,
        device_timestamp_s=device_timestamp_s,
        exposure_time_us=exposure_time_us,
    )
    return None if metadata.is_empty else metadata
