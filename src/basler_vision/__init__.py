import os
import sys

if os.getenv("BASLER_VISION_WRITE_BYTECODE", "").strip().lower() not in {
    "1",
    "true",
    "yes",
    "on",
}:
    sys.dont_write_bytecode = True
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ.pop("PYTHONPYCACHEPREFIX", None)

from basler_vision.core import (
    CameraStreamController,
    CameraStreamPublisher,
    ExperimentEngine,
    build_metadata_filename,
    build_metadata_path,
    build_video_filename,
    build_video_path,
    camera_stream_process,
    ensure_runtime_defaults,
    load_base_config,
    load_runtime_config,
    merge_config,
)
from basler_vision.hardware import BaslerCamera
from basler_vision.hardware.frame_metadata import FrameMetadata
from basler_vision.output import MetadataWriter, VideoWriter
from basler_vision.resources import get_default_config_path, get_packaged_config_path

__all__ = [
    "BaslerCamera",
    "CameraStreamController",
    "CameraStreamPublisher",
    "FrameMetadata",
    "ExperimentEngine",
    "MetadataWriter",
    "VideoWriter",
    "build_metadata_filename",
    "build_metadata_path",
    "build_video_filename",
    "build_video_path",
    "camera_stream_process",
    "ensure_runtime_defaults",
    "get_default_config_path",
    "get_packaged_config_path",
    "load_base_config",
    "load_runtime_config",
    "merge_config",
]

__version__ = "0.1.0"
