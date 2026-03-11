from abc import ABC, abstractmethod


class AbstractCamera(ABC):
    @classmethod
    @abstractmethod
    def enumerate_devices(cls):
        """Return the available cameras/devices for this backend."""

    @abstractmethod
    def open(self):
        """Connect to the camera."""

    @abstractmethod
    def start(self, fps=None):
        """Start frame acquisition."""

    @abstractmethod
    def grab(self, timeout_ms=5000):
        """Grab a single frame and timestamp."""

    @abstractmethod
    def stop(self):
        """Stop frame acquisition."""

    @abstractmethod
    def close(self):
        """Close the camera connection."""

    @abstractmethod
    def is_open(self):
        """Return whether the camera connection is open."""

    @abstractmethod
    def is_grabbing(self):
        """Return whether the camera is currently streaming."""

    @abstractmethod
    def get_config(self):
        """Return the active camera configuration."""

    @abstractmethod
    def get_parameter(self, name):
        """Return a single camera parameter by name."""

    @abstractmethod
    def set_parameter(self, name, value):
        """Set a single camera parameter by name."""
