import os

from pypylon import pylon

from hardware.base import AbstractCamera


class BaslerCamera(AbstractCamera):
    def __init__(self, serial_number=None, settings_path=None):
        self.serial = str(serial_number) if serial_number else None
        self.settings_path = settings_path
        self.camera = None

    def open(self):
        factory = pylon.TlFactory.GetInstance()
        devices = factory.EnumerateDevices()
        if not devices:
            raise RuntimeError('No Basler cameras detected.')

        available_serials = [d.GetSerialNumber() for d in devices]
        selected_device = None

        if self.serial:
            for device in devices:
                if device.GetSerialNumber() == self.serial:
                    selected_device = device
                    break
            if not selected_device:
                raise RuntimeError(f'Camera {self.serial} not found. Available: {available_serials}')

            self.camera = pylon.InstantCamera(factory.CreateDevice(selected_device))
            self.camera.Open()
        else:
            for device in devices:
                temp_cam = None
                try:
                    sn = device.GetSerialNumber()
                    temp_cam = pylon.InstantCamera(factory.CreateDevice(device))
                    temp_cam.Open()

                    self.camera = temp_cam
                    self.serial = sn
                    selected_device = device
                    print(f'Connected to available camera: {self.serial}')
                    break
                except Exception:
                    if temp_cam is not None and temp_cam.IsOpen():
                        temp_cam.Close()
                    continue

            if not selected_device:
                raise RuntimeError('No available cameras found. All connected cameras may be in use.')

        if self.settings_path and os.path.exists(self.settings_path):
            pylon.FeaturePersistence.Load(self.settings_path, self.camera.GetNodeMap(), False)

    def get_config(self):
        return {
            'width': self.camera.Width.GetValue(),
            'height': self.camera.Height.GetValue(),
            'fps': self.camera.AcquisitionFrameRate.GetValue(),
            'pixel_format': self.camera.PixelFormat.Value,
        }

    def start(self, fps=None):
        if fps:
            self.camera.AcquisitionFrameRateEnable.SetValue(True)
            self.camera.AcquisitionFrameRate.SetValue(fps)
        self.camera.StartGrabbing(pylon.GrabStrategy_OneByOne)

    def grab(self):
        res = self.camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
        try:
            if res.GrabSucceeded():
                img = res.Array.copy()
                ts = res.TimeStamp * 1e-9
                return img, ts
            return None, None
        finally:
            res.Release()

    def close(self):
        if self.camera:
            if self.camera.IsGrabbing():
                self.camera.StopGrabbing()
            if self.camera.IsOpen():
                self.camera.Close()
