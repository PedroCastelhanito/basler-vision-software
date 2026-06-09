import os
import tempfile

from pypylon import pylon

from basler_vision.core.logging_utils import log_step
from basler_vision.hardware.base import AbstractCamera
from basler_vision.hardware.frame_metadata import extract_chunk_metadata


class BaslerCamera(AbstractCamera):
    # Chunk features and the ChunkSelector entries that supply them, tried in
    # order (model-dependent naming). See enable_chunk_data.
    CHUNK_FEATURES = {
        "frame_id": ("FrameID", "Framecounter", "CounterValue"),
        "timestamp": ("Timestamp",),
        "exposure": ("ExposureTime",),
    }

    def __init__(self, serial_number=None, settings_path=None, log_config=None):
        self.serial = str(serial_number) if serial_number else None
        self.settings_path = settings_path
        self.log_config = log_config
        self.camera = None
        # Set by enable_chunk_data(); gates the per-grab chunk read so cameras
        # without chunk support pay no cost on the grab hot path.
        self._chunk_active = False

    @classmethod
    def enumerate_devices(cls):
        factory = pylon.TlFactory.GetInstance()
        devices = factory.EnumerateDevices()
        return [
            {
                'serial': device.GetSerialNumber(),
                'model': device.GetModelName(),
                'friendly_name': device.GetFriendlyName(),
                'vendor': device.GetVendorName(),
            }
            for device in devices
        ]

    def _get_factory(self):
        return pylon.TlFactory.GetInstance()

    def _require_camera(self):
        if not self.camera:
            raise RuntimeError('Camera is not connected. Call open() first.')
        return self.camera

    def _select_device(self, devices):
        if self.serial:
            for device in devices:
                if device.GetSerialNumber() == self.serial:
                    return device
            raise RuntimeError(f'Camera {self.serial} not found. Available: {[d.GetSerialNumber() for d in devices]}')

        last_error = None
        for device in devices:
            temp_cam = None
            try:
                temp_cam = pylon.InstantCamera(self._get_factory().CreateDevice(device))
                temp_cam.Open()
                temp_cam.Close()
                self.serial = device.GetSerialNumber()
                return device
            except Exception as exc:
                last_error = exc
                if temp_cam is not None and temp_cam.IsOpen():
                    temp_cam.Close()

        raise RuntimeError('No available cameras found. All connected cameras may be in use.') from last_error

    def open(self):
        if self.is_open():
            log_step('BaslerCamera.open', f'Camera {self.serial or "unknown"} already open.', self.log_config)
            return self

        log_step('BaslerCamera.open', 'Enumerating connected cameras.', self.log_config)
        factory = self._get_factory()
        devices = factory.EnumerateDevices()
        if not devices:
            raise RuntimeError('No Basler cameras detected.')

        selected_device = self._select_device(devices)
        self.camera = pylon.InstantCamera(factory.CreateDevice(selected_device))
        self.camera.Open()
        log_step('BaslerCamera.open', f'Connected to camera {self.serial}.', self.log_config, always=True)

        if self.settings_path:
            self.load_settings(self.settings_path)
        return self

    def load_settings(self, settings_path=None):
        settings_path = settings_path or self.settings_path
        if not settings_path:
            return self
        if not os.path.exists(settings_path):
            raise FileNotFoundError(f'Settings file not found: {settings_path}')

        self._require_camera()
        try:
            self._load_settings_file(settings_path)
        except Exception as exc:
            if not self._is_unreadable_node_error(exc, 'TriggerActivation'):
                raise RuntimeError(
                    f'Failed to load settings from {settings_path}: {exc}'
                ) from exc
            filtered_path = self._filtered_pfs_path(
                settings_path, {'TriggerActivation'}
            )
            try:
                self._load_settings_file(filtered_path)
            except Exception as retry_exc:
                raise RuntimeError(
                    f'Failed to load settings from {settings_path} after skipping '
                    f'unreadable TriggerActivation entries: {retry_exc}'
                ) from retry_exc
            finally:
                try:
                    os.unlink(filtered_path)
                except OSError:
                    pass
        self.settings_path = settings_path
        log_step('BaslerCamera.load_settings', f'Loaded settings from {settings_path}.', self.log_config)
        return self

    def _load_settings_file(self, settings_path):
        pylon.FeaturePersistence.Load(settings_path, self.camera.GetNodeMap(), False)

    @staticmethod
    def _is_unreadable_node_error(exc, node_name):
        message = str(exc)
        return node_name in message and 'not readable' in message.lower()

    @staticmethod
    def _filtered_pfs_path(settings_path, skipped_nodes):
        skipped_nodes = {str(node) for node in skipped_nodes}
        with open(settings_path, 'r', encoding='utf-8', errors='replace') as source:
            lines = source.readlines()

        temp_dirs = [os.path.dirname(os.path.abspath(settings_path)) or None, None]
        last_error = None
        handle = None
        for temp_dir in temp_dirs:
            try:
                handle = tempfile.NamedTemporaryFile(
                    'w',
                    encoding='utf-8',
                    suffix='.pfs',
                    prefix='basler_filtered_',
                    delete=False,
                    dir=temp_dir,
                )
                break
            except OSError as exc:
                last_error = exc
        if handle is None:
            raise last_error or OSError('Could not create a filtered PFS file.')
        try:
            with handle:
                for line in lines:
                    stripped = line.lstrip()
                    parts = stripped.split(None, 1)
                    node_name = parts[0] if parts else ''
                    if node_name in skipped_nodes:
                        continue
                    handle.write(line)
            return handle.name
        except Exception:
            try:
                os.unlink(handle.name)
            except OSError:
                pass
            raise

    def save_settings(self, settings_path):
        self._require_camera()
        pylon.FeaturePersistence.Save(settings_path, self.camera.GetNodeMap())
        log_step('BaslerCamera.save_settings', f'Saved settings to {settings_path}.', self.log_config)
        return settings_path

    def is_open(self):
        return bool(self.camera and self.camera.IsOpen())

    def is_grabbing(self):
        return bool(self.camera and self.camera.IsGrabbing())

    def get_device_info(self):
        cam = self._require_camera()
        info = cam.GetDeviceInfo()
        return {
            'serial': info.GetSerialNumber(),
            'model': info.GetModelName(),
            'friendly_name': info.GetFriendlyName(),
            'vendor': info.GetVendorName(),
        }

    def get_node(self, name):
        cam = self._require_camera()
        if hasattr(cam, name):
            return getattr(cam, name)

        node = cam.GetNodeMap().GetNode(name)
        if node is None:
            raise AttributeError(f'Camera parameter {name!r} was not found.')
        return node

    def _read_node_value(self, node):
        if hasattr(node, 'GetValue'):
            return node.GetValue()
        if hasattr(node, 'Value'):
            return node.Value
        return node

    def _write_node_value(self, node, value):
        if hasattr(node, 'SetValue'):
            node.SetValue(value)
            return
        if hasattr(node, 'FromString'):
            node.FromString(str(value))
            return
        if hasattr(node, 'Value'):
            node.Value = value
            return
        raise AttributeError('Parameter does not support value assignment.')

    def get_parameter(self, name, default=None):
        try:
            node = self.get_node(name)
        except AttributeError:
            if default is not None:
                return default
            raise
        try:
            return self._read_node_value(node)
        except Exception as exc:
            if default is not None:
                return default
            raise RuntimeError(
                f'Failed to read camera parameter {name}: {exc}'
            ) from exc

    def get_parameters(self, names):
        return {name: self.get_parameter(name) for name in names}

    def get_parameter_limits(self, name):
        node = self.get_node(name)

        minimum = None
        maximum = None
        increment = None

        if hasattr(node, 'GetMin'):
            minimum = node.GetMin()
        elif hasattr(node, 'Min'):
            minimum = node.Min

        if hasattr(node, 'GetMax'):
            maximum = node.GetMax()
        elif hasattr(node, 'Max'):
            maximum = node.Max

        if hasattr(node, 'GetInc'):
            try:
                increment = node.GetInc()
            except Exception:
                increment = None
        elif hasattr(node, 'Inc'):
            increment = node.Inc

        return {
            'min': minimum,
            'max': maximum,
            'inc': increment or 1,
        }

    def set_parameter(self, name, value):
        try:
            node = self.get_node(name)
            self._write_node_value(node, value)
        except Exception as exc:
            raise RuntimeError(
                f'Failed to set camera parameter {name} to {value}: {exc}'
            ) from exc
        log_step('BaslerCamera.set_parameter', f'Set {name} to {value}.', self.log_config)
        return value

    def apply_parameters(self, parameters):
        for name, value in parameters.items():
            self.set_parameter(name, value)
        return self

    def set_frame_rate(self, fps):
        self.set_parameter('AcquisitionFrameRateEnable', True)
        self.set_parameter('AcquisitionFrameRate', fps)
        return fps

    def set_pixel_format(self, pixel_format):
        self.set_parameter('PixelFormat', pixel_format)
        return pixel_format

    def set_exposure(self, exposure_us):
        self.set_parameter('ExposureTime', exposure_us)
        return exposure_us

    def set_gain(self, gain):
        self.set_parameter('Gain', gain)
        return gain

    def set_roi(self, width=None, height=None, offset_x=None, offset_y=None):
        updates = {}
        if width is not None:
            updates['Width'] = width
        if height is not None:
            updates['Height'] = height
        if offset_x is not None:
            updates['OffsetX'] = offset_x
        if offset_y is not None:
            updates['OffsetY'] = offset_y
        self.apply_parameters(updates)
        return self.get_parameters(updates.keys())

    def enable_chunk_data(self, features=None):
        """Activate pylon chunk mode so each grab result self-describes.

        Enables the FrameID, device-timestamp, and exposure chunks (or the
        subset named in ``features``) so :meth:`grab` can attach a
        :class:`FrameMetadata` to every frame (improvement-plan item 1.1).

        Best-effort by design: ``ChunkModeActive`` or any individual chunk that
        the connected model does not expose is logged and skipped rather than
        failing the connection. Must be called while the camera is open and not
        grabbing. ``self._chunk_active`` reflects whether any chunk was enabled.
        """
        self._require_camera()
        requested = list(features) if features is not None else list(self.CHUNK_FEATURES)
        try:
            self.set_parameter("ChunkModeActive", True)
        except Exception as exc:
            log_step(
                "BaslerCamera.enable_chunk_data",
                f"ChunkModeActive unavailable; chunk data disabled: {exc}",
                self.log_config,
                always=True,
            )
            self._chunk_active = False
            return self

        enabled = []
        for feature in requested:
            for selector in self.CHUNK_FEATURES.get(feature, ()):
                try:
                    self.set_parameter("ChunkSelector", selector)
                    self.set_parameter("ChunkEnable", True)
                    enabled.append(selector)
                    break
                except Exception:
                    continue
        self._chunk_active = bool(enabled)
        log_step(
            "BaslerCamera.enable_chunk_data",
            f"Chunk data enabled for: {enabled or 'none'}.",
            self.log_config,
            always=True,
        )
        return self

    def get_config(self):
        self._require_camera()
        return {
            'width': self.get_parameter('Width'),
            'height': self.get_parameter('Height'),
            'fps': self.get_parameter('AcquisitionFrameRate'),
            'pixel_format': self.get_parameter('PixelFormat'),
        }

    def start(self, fps=None):
        cam = self._require_camera()
        if fps:
            self.set_frame_rate(fps)
        if not cam.IsGrabbing():
            cam.StartGrabbing(pylon.GrabStrategy_OneByOne)
            log_step('BaslerCamera.start', 'Acquisition started.', self.log_config)
        return self

    def grab(self, timeout_ms=5000):
        """Grab one frame, returning ``(image, timestamp_s, metadata)``.

        ``metadata`` is a :class:`FrameMetadata` when chunk data is active (see
        :meth:`enable_chunk_data`) and ``None`` otherwise. The empty result on
        no-frame / failed grab is ``(None, None, None)``.
        """
        cam = self._require_camera()
        if not cam.IsGrabbing():
            return None, None, None

        res = cam.RetrieveResult(timeout_ms, pylon.TimeoutHandling_ThrowException)
        try:
            if not res or not res.GrabSucceeded():
                return None, None, None
            try:
                img = res.Array.copy()
                ts = res.TimeStamp * 1e-9
            except Exception as exc:
                if 'No grab result data is referenced' in str(exc):
                    return None, None, None
                raise
            metadata = extract_chunk_metadata(res) if self._chunk_active else None
            return img, ts, metadata
        finally:
            if res is not None:
                res.Release()

    def grab_many(self, count, timeout_ms=5000):
        frames = []
        for _ in range(count):
            frame, timestamp, metadata = self.grab(timeout_ms=timeout_ms)
            if frame is None:
                break
            frames.append((frame, timestamp, metadata))
        return frames

    def stop(self):
        if self.is_grabbing():
            self.camera.StopGrabbing()
            log_step('BaslerCamera.stop', 'Acquisition stopped.', self.log_config)
        return self

    def close(self):
        if self.camera:
            self.stop()
            if self.camera.IsOpen():
                self.camera.Close()
            log_step('BaslerCamera.close', f'Camera {self.serial or "unknown"} closed.', self.log_config)
        return self

