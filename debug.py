import json
import os
import threading
import time

from core.publisher import camera_stream_process


def load_base_config(config_path):
    """Loads and flattens the nested JSON configuration."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f'Config file not found at {config_path}')

    with open(config_path, 'r', encoding='utf-8') as f:
        raw_cfg = json.load(f)

    flattened_config = {
        **raw_cfg.get('camera_settings', {}),
        **raw_cfg.get('recording', {}),
        **raw_cfg.get('preview', {}),
    }
    return flattened_config


def run_test(config_path='./configs/default_parameters.json', overrides=None, duration=10):
    """
    Test script using JSON defaults with runtime overrides.
    """
    config = load_base_config(config_path)

    if overrides:
        config.update(overrides)

    if 'camera_name' not in config:
        config['camera_name'] = 'DebugCam'

    os.makedirs(config['out_dir'], exist_ok=True)

    print(f"--- Starting Test: {config['camera_name']} ---")
    print(f"Recording: {config['record']} | Viewing: {config['view']} | Duration: {duration}s")

    stop_event = threading.Event()
    test_thread = threading.Thread(
        target=camera_stream_process,
        args=(config, stop_event),
    )
    test_thread.start()

    start_time = time.time()
    try:
        while test_thread.is_alive():
            if time.time() - start_time > duration:
                print('\nDuration reached.')
                stop_event.set()
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        print('\nTest interrupted by user.')
        stop_event.set()

    test_thread.join(timeout=10)
    print('Test complete. Shutting down...')


if __name__ == '__main__':
    from pathlib import Path

    CONFIG_FILE_PATH = Path(__file__).parent / 'configs' / 'default_parameters.json'

    custom_values = {
        'view': True,
        'serial': None,
        'record': False,
        'display_scale': 0.3,
        'camera_name': 'Debug',
        'window_pos': [200, 200],
    }

    run_test(
        config_path=CONFIG_FILE_PATH,
        overrides=custom_values,
        duration=15,
    )
