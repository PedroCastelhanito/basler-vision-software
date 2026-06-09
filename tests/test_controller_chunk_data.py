"""The controller enables chunk data on open only when the config opts in."""

from __future__ import annotations

import threading

from basler_vision.core.controller import CameraStreamController


class _FakeCamera:
    def __init__(self):
        self.opened = False
        self.chunk_enabled = False

    def open(self):
        self.opened = True
        return self

    def enable_chunk_data(self, features=None):
        self.chunk_enabled = True
        return self

    def get_config(self):
        return {"width": 8, "height": 8, "fps": 30, "pixel_format": "Mono8"}


def _make(config_extra):
    camera = _FakeCamera()
    config = {"serial": "X", "record": False, "view": False}
    config.update(config_extra)
    controller = CameraStreamController(config, camera=camera, stop_event=threading.Event())
    return controller, camera


def test_chunk_data_enabled_when_flag_set():
    controller, camera = _make({"enable_chunk_data": True})

    controller.open_camera()

    assert camera.opened
    assert camera.chunk_enabled


def test_chunk_data_not_enabled_by_default():
    controller, camera = _make({})

    controller.open_camera()

    assert camera.opened
    assert not camera.chunk_enabled


def test_open_survives_camera_without_chunk_support():
    # A camera lacking enable_chunk_data must not break open (hasattr guard).
    class _Bare:
        def __init__(self):
            self.opened = False

        def open(self):
            self.opened = True
            return self

        def get_config(self):
            return {"width": 8, "height": 8, "fps": 30, "pixel_format": "Mono8"}

    bare = _Bare()
    config = {"serial": "X", "record": False, "view": False, "enable_chunk_data": True}
    controller = CameraStreamController(config, camera=bare, stop_event=threading.Event())

    controller.open_camera()  # must not raise

    assert bare.opened
