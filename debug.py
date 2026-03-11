import os
import time

from core.config import load_runtime_config
from core.engine import ExperimentEngine
from core.logging_utils import log_step


def run_test(config_path='./configs/default_parameters.json', overrides=None, duration=10):
    """Test script using JSON defaults with runtime overrides."""
    config = load_runtime_config(config_path, overrides=overrides, default_camera_name='DebugCam')
    os.makedirs(config['out_dir'], exist_ok=True)

    log_step('run_test', f"Starting test for {config['camera_name']}.", config, always=True)
    log_step(
        'run_test',
        f"Recording={config['record']} | Viewing={config['view']} | Duration={duration}s",
        config,
        always=True,
    )

    engine = ExperimentEngine([config])
    engine.start()

    start_time = time.time()
    try:
        while any(process.is_alive() for process in engine.processes):
            if time.time() - start_time > duration:
                log_step('run_test', 'Duration reached.', config, always=True)
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        log_step('run_test', 'Test interrupted by user.', config, always=True)
    finally:
        engine.stop()

    log_step('run_test', 'Test complete. Shutting down...', config, always=True)


if __name__ == '__main__':
    from pathlib import Path

    CONFIG_FILE_PATH = Path(__file__).parent / 'configs' / 'default_parameters.json'

    custom_values = {
        'view': True,
        'debug': False,
        'serial': None,
        'record': True,
        'display_scale': 0.3,
        'camera_name': 'Debug',
        'window_pos': [200, 200],
        'video_filename': 'test.mp4',
    }

    run_test(
        config_path=CONFIG_FILE_PATH,
        overrides=custom_values,
        duration=10,
    )
