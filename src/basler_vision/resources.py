from importlib.resources import as_file, files
from pathlib import Path


def get_packaged_config_path(filename: str) -> Path:
    resource = files("basler_vision").joinpath("configs", filename)
    with as_file(resource) as path:
        return Path(path)


def get_default_config_path() -> Path:
    return get_packaged_config_path("default_parameters.json")
