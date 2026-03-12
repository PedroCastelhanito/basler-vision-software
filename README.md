# basler-vision

`basler-vision` is a Python package for Basler camera discovery, configuration, preview streaming, callbacks, and recording.

## What this package provides

- Basler camera enumeration through `pypylon`
- A hardware wrapper for opening, configuring, grabbing, and closing cameras
- A reusable streaming controller for preview, callbacks, and recording
- Video and metadata writers for experiment output
- Packaged default configuration assets
- A console debug entry point for smoke testing

## Repository layout

```text
basler-vision-software/
  pyproject.toml
  requirements.txt
  README.md
  debug.py
  src/
    basler_vision/
      __init__.py
      cli.py
      resources.py
      configs/
      core/
      hardware/
      output/
```

The package uses a `src/` layout and a namespaced import root, which avoids collisions with generic module names such as `core` or `hardware`.

## Installation

Using `pip`:

```bash
pip install -r requirements.txt
pip install -e .
```

Using conda with an existing environment:

```bash
conda activate <your-environment>
pip install -r requirements.txt
pip install -e .
```

Editable install is recommended during active development.

## Quick start

### Python API

```python
from basler_vision import BaslerCamera, CameraStreamController

devices = BaslerCamera.enumerate_devices()
print(devices)

controller = CameraStreamController(
    {
        "camera_name": "PreviewCam",
        "serial": devices[0]["serial"],
        "record": False,
        "view": False,
        "fps": 30,
    }
)

controller.open_camera()
latest = controller.create_latest_frame_subscriber()
controller.start()

frame, timestamp = latest.get_latest()
print(timestamp, None if frame is None else frame.shape)

controller.cleanup()
```

### Debug CLI

```bash
basler-vision-debug --duration 10 --view --camera-name DebugCam
```

You can also run the repository helper directly:

```bash
python ./debug.py --duration 10 --view
```

## Packaged configuration assets

The package includes camera configuration files under `basler_vision/configs/`.

Use the helper functions:

```python
from basler_vision import get_default_config_path, get_packaged_config_path

default_json = get_default_config_path()
camera_pfs = get_packaged_config_path("acA4024-29uc_23439562.pfs")
```

## Runtime configuration shape

JSON configs are flattened at runtime from three sections:

- `camera_settings`
- `recording`
- `preview`

Example:

```json
{
  "camera_settings": {
    "serial": null,
    "settings_path": null,
    "camera_name": "Camera",
    "debug": false
  },
  "recording": {
    "record": true,
    "video_filename": "video.mp4",
    "out_dir": "C:\\temp",
    "fps": 30
  },
  "preview": {
    "view": true,
    "display_scale": 0.25,
    "window_pos": [100, 100]
  }
}
```

## Integration guidance

Recommended imports:

```python
from basler_vision import BaslerCamera, CameraStreamController
```

Recommended pattern:

1. Enumerate devices once in your application service layer.
2. Create one controller per connected serial number.
3. Use `LatestFrameSubscriber` for GUI preview polling.
4. Keep direct `pypylon` access inside this package, not in application UI code.

## Development notes

- Python 3.10+ is required.
- `pypylon` and the Basler runtime must be installed on the machine.
- The package currently targets Windows-based Basler workflows.
- GUI applications should use this package in-process for connect, preview, and disconnect operations.
- Long-running multiprocessing workflows should remain optional and separate from the UI bridge layer.

## Troubleshooting

### No cameras detected

- Confirm the camera is visible in Basler Pylon Viewer.
- Confirm no other process already owns the device.
- Confirm the correct USB or GigE transport drivers are installed.

### Import errors after install

- Re-activate your environment.
- Re-run `pip install -e .`.
- Check `python -c "import basler_vision; print(basler_vision.__file__)"`.

### Slow disconnects

If GUI disconnect feels slow, reduce camera grab timeouts in GUI mode and ensure acquisition is stopped before waiting on worker threads.

## Recommended next cleanup steps

- Add unit tests around config normalization and non-hardware subscribers.
- Split hardware-facing integration tests behind an explicit marker.
- Add a stable application-facing bridge layer instead of importing internal modules directly.
- Introduce structured logging if session diagnostics become more important.
- Add config validation for runtime JSON files.
