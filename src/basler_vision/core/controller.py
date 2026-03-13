import threading
import time

from basler_vision.core.logging_utils import log_step
from basler_vision.core.paths import build_metadata_path, build_video_path
from basler_vision.core.subscribers import (
    CallbackSubscriber,
    DisplaySubscriber,
    LatestFrameSubscriber,
    QueueSubscriber,
    VideoSubscriber,
    preprocess_frame,
)
from basler_vision.hardware.basler import BaslerCamera
from basler_vision.output.metadata import MetadataWriter
from basler_vision.output.writer import VideoWriter


class CameraStreamController:
    """Reusable streaming controller for recording, broadcasting, and GUI integration."""

    def __init__(self, config, camera=None, stop_event=None):
        self.config = dict(config)
        self.stop_event = stop_event or threading.Event()
        self.camera = camera or BaslerCamera(
            self.config.get('serial'),
            self.config.get('settings_path'),
            log_config=self.config,
        )

        self.subscribers = []
        self.publisher_thread = None
        self.publisher_error = []
        self.video_subscriber = None
        self.display_subscriber = None
        self.latest_frame_subscriber = None
        self.metadata_writer = None
        self.video_writer = None
        self.raw_pixel_format = self.config.get('pixel_format', 'gray')
        self.fps = self.config.get('fps')
        self.frame_index = 0
        self.grab_timeout_ms = int(self.config.get('grab_timeout_ms', 250))
        self._cleaned_up = False

    def open_camera(self):
        self.camera.open()
        self.refresh_camera_config()
        return self.camera

    def refresh_camera_config(self):
        hw = self.camera.get_config()
        self.raw_pixel_format = hw['pixel_format']
        self.fps = self.config.get('fps', hw['fps'])
        self.config.update({'width': hw['width'], 'height': hw['height'], 'pixel_format': self.raw_pixel_format})
        log_step(
            'CameraStreamController.refresh_camera_config',
            f'Camera ready: {self.config["width"]}x{self.config["height"]} @ {self.fps} fps ({self.raw_pixel_format}).',
            self.config,
        )
        return dict(self.config)

    def is_running(self):
        return bool(self.publisher_thread and self.publisher_thread.is_alive())

    def add_subscriber(self, subscriber, start_if_running=True):
        self.subscribers.append(subscriber)
        starter = getattr(subscriber, 'start', None)
        thread = getattr(subscriber, 'thread', None)
        if self.is_running() and start_if_running and callable(starter) and (thread is None or not thread.is_alive()):
            starter()
        return subscriber

    def remove_subscriber(self, subscriber):
        if subscriber in self.subscribers:
            self.subscribers.remove(subscriber)
        if subscriber is self.video_subscriber:
            self.video_subscriber = None
        if subscriber is self.display_subscriber:
            self.display_subscriber = None
        if subscriber is self.latest_frame_subscriber:
            self.latest_frame_subscriber = None
        return subscriber

    def create_queue_subscriber(self, max_queue=10, pixel_format=None):
        subscriber = QueueSubscriber(self.stop_event, pixel_format or self.raw_pixel_format, maxlen=max_queue)
        return self.add_subscriber(subscriber)

    def create_latest_frame_subscriber(self, pixel_format=None):
        if self.latest_frame_subscriber is None:
            self.latest_frame_subscriber = LatestFrameSubscriber(self.stop_event, pixel_format or self.raw_pixel_format)
            self.add_subscriber(self.latest_frame_subscriber)
        return self.latest_frame_subscriber

    def create_callback_subscriber(self, callback, max_queue=10, pixel_format=None):
        subscriber = CallbackSubscriber(
            callback,
            self.stop_event,
            pixel_format or self.raw_pixel_format,
            max_queue=max_queue,
        )
        return self.add_subscriber(subscriber)

    def enable_preview(self):
        self.config['view'] = True
        if self.config.get('disable_native_preview', False):
            if self.latest_frame_subscriber is None:
                self.latest_frame_subscriber = LatestFrameSubscriber(self.stop_event, self.raw_pixel_format)
                self.add_subscriber(self.latest_frame_subscriber)
            return self.latest_frame_subscriber
        if self.display_subscriber is None:
            self.display_subscriber = DisplaySubscriber(self.stop_event, self.config)
            self.add_subscriber(self.display_subscriber)
        return self.display_subscriber

    def disable_preview(self):
        self.config['view'] = False
        if self.display_subscriber is not None:
            self.remove_subscriber(self.display_subscriber)
        return self

    def enable_recording(self, video_filename=None, metadata_filename=None):
        if video_filename:
            self.config['video_filename'] = video_filename
        if metadata_filename:
            self.config['metadata_filename'] = metadata_filename
        self.config['record'] = True

        if self.camera.is_open() and self.video_subscriber is None:
            self._prepare_recording()
            self._start_threaded_subscribers()
        return self.video_subscriber

    def disable_recording(self):
        self.config['record'] = False
        return self

    def get_latest_frame(self):
        if self.latest_frame_subscriber is None:
            return None, None
        return self.latest_frame_subscriber.get_latest()

    def get_state(self):
        return {
            'camera_name': self.config.get('camera_name', 'camera'),
            'is_open': self.camera.is_open(),
            'is_running': self.is_running(),
            'is_grabbing': self.camera.is_grabbing(),
            'recording_enabled': bool(self.video_subscriber),
            'preview_enabled': self.display_subscriber is not None,
            'subscriber_count': len(self.subscribers),
            'frame_index': self.frame_index,
        }

    def _prepare_recording(self):
        if self.video_subscriber is not None:
            return self.video_subscriber

        video_path = build_video_path(self.config)
        metadata_path = build_metadata_path(self.config)
        input_to_writer = 'rgb24' if 'bayer' in self.raw_pixel_format.lower() else self.raw_pixel_format

        self.metadata_writer = MetadataWriter(metadata_path, log_config=self.config)
        self.metadata_writer.open()
        self.video_writer = VideoWriter(
            video_path,
            self.fps,
            self.config['width'],
            self.config['height'],
            input_to_writer,
            writer_config=self.config,
        )
        self.video_writer.open()
        self.video_subscriber = VideoSubscriber(
            self.video_writer,
            self.stop_event,
            self.raw_pixel_format,
            max_queue=self.config.get('writer_queue_size'),
        )
        self.add_subscriber(self.video_subscriber, start_if_running=False)
        log_step('CameraStreamController.enable_recording', f'Recording enabled: {video_path}', self.config, always=True)
        return self.video_subscriber

    def _start_threaded_subscribers(self):
        for subscriber in self.subscribers:
            starter = getattr(subscriber, 'start', None)
            thread = getattr(subscriber, 'thread', None)
            if callable(starter) and (thread is None or not thread.is_alive()):
                starter()

    def _publisher_loop(self):
        try:
            self.camera.start(self.fps)
            log_step(
                'CameraStreamController._publisher_loop',
                f'Camera stream running for {self.config.get("camera_name", "camera")}.',
                self.config,
            )
            while not self.stop_event.is_set():
                frame, timestamp = self.camera.grab(timeout_ms=self.grab_timeout_ms)
                if frame is None:
                    continue

                processed_frame = preprocess_frame(frame, self.raw_pixel_format)
                for subscriber in list(self.subscribers):
                    subscriber.push(processed_frame, timestamp, processed=True)
                if self.metadata_writer is not None:
                    self.metadata_writer.log_frame(self.frame_index, timestamp)
                self.frame_index += 1
        except Exception as exc:
            self.publisher_error.append(exc)
            log_step('CameraStreamController._publisher_loop', f'Stopping due to error: {exc}', self.config, always=True)
            self.stop_event.set()

    def start(self):
        self._cleaned_up = False
        self.publisher_error = []
        self.frame_index = 0
        if hasattr(self.stop_event, 'clear'):
            self.stop_event.clear()

        self.open_camera()

        if self.config.get('record', True):
            self._prepare_recording()
        if self.config.get('view', False) and self.display_subscriber is None:
            self.enable_preview()

        self._start_threaded_subscribers()
        self.publisher_thread = threading.Thread(target=self._publisher_loop, daemon=True)
        self.publisher_thread.start()
        return self

    def wait(self, poll_interval=0.1):
        while not self.stop_event.is_set() and self.is_running():
            time.sleep(poll_interval)
        return self

    def run_preview_loop(self):
        if self.display_subscriber is None:
            raise RuntimeError('Preview has not been enabled. Call enable_preview() first.')
        self.display_subscriber.run_ui_loop()
        return self

    def raise_if_failed(self):
        if self.publisher_error:
            raise self.publisher_error[0]
        return self

    def stop(self):
        self.stop_event.set()
        return self

    def join(self, timeout=None):
        if self.publisher_thread:
            self.publisher_thread.join(timeout=timeout)

        for subscriber in self.subscribers:
            joiner = getattr(subscriber, 'join', None)
            if callable(joiner):
                joiner(timeout=timeout)
        return self

    def cleanup(self):
        if self._cleaned_up:
            return self

        self.stop_event.set()
        self.join(timeout=10)
        self.camera.close()
        if self.metadata_writer is not None:
            self.metadata_writer.close()
        self._cleaned_up = True
        log_step(
            'CameraStreamController.cleanup',
            f'Stream cleanup complete for {self.config.get("camera_name", "camera")}.',
            self.config,
        )
        return self

    def close(self):
        return self.cleanup()


class CameraStreamPublisher(CameraStreamController):
    """Backward-compatible alias for code that prefers the publisher naming."""

