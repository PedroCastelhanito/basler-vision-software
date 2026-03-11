import json
import os


def load_base_config(config_path):
    """Load and flatten the JSON configuration file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f'Config file not found at {config_path}')

    with open(config_path, 'r', encoding='utf-8') as file_handle:
        raw_cfg = json.load(file_handle)

    return {
        **raw_cfg.get('camera_settings', {}),
        **raw_cfg.get('recording', {}),
        **raw_cfg.get('preview', {}),
    }


def merge_config(config, overrides=None):
    merged = dict(config)
    if overrides:
        merged.update(overrides)
    return merged


def ensure_runtime_defaults(config, default_camera_name='DebugCam', default_out_dir='output'):
    normalized = dict(config)
    normalized.setdefault('camera_name', default_camera_name)
    normalized.setdefault('out_dir', default_out_dir)
    return normalized


def load_runtime_config(config_path, overrides=None, default_camera_name='DebugCam', default_out_dir='output'):
    config = load_base_config(config_path)
    config = merge_config(config, overrides=overrides)
    return ensure_runtime_defaults(
        config,
        default_camera_name=default_camera_name,
        default_out_dir=default_out_dir,
    )
