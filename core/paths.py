import os
from pathlib import Path


def build_video_filename(config):
    return config.get('video_filename', f"{config['camera_name']}.mp4")


def build_video_path(config):
    return os.path.join(config['out_dir'], build_video_filename(config))


def build_metadata_filename(config, video_filename=None):
    metadata_filename = config.get('metadata_filename')
    if metadata_filename:
        return metadata_filename

    video_filename = video_filename or build_video_filename(config)
    return f'{Path(video_filename).stem}_metadata.csv'


def build_metadata_path(config, video_filename=None):
    return os.path.join(config['out_dir'], build_metadata_filename(config, video_filename=video_filename))
