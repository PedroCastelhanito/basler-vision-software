from __future__ import annotations

import shutil
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def cleanup_stale_python_temp_artifacts(root: Path | None = None) -> None:
    target_root = Path(root) if root is not None else repo_root()
    try:
        target_root = target_root.resolve()
    except OSError:
        return
    if not target_root.exists():
        return
    if root is None and not (target_root / "pyproject.toml").exists():
        return

    _remove_tree_if_inside(target_root / ".tmp_pycache", target_root)

    for search_root_name in ("src", "tests"):
        search_root = target_root / search_root_name
        if not search_root.exists():
            continue
        try:
            candidates = list(search_root.rglob("*.pyc.*"))
        except OSError:
            continue
        for candidate in candidates:
            if not _is_inside(candidate, target_root):
                continue
            if not _looks_like_python_cache_temp(candidate):
                continue
            try:
                candidate.unlink()
            except OSError:
                pass


def _remove_tree_if_inside(path: Path, root: Path) -> None:
    if not path.exists() or not _is_inside(path, root):
        return
    try:
        shutil.rmtree(path)
    except OSError:
        pass


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root)
        return True
    except (OSError, ValueError):
        return False


def _looks_like_python_cache_temp(path: Path) -> bool:
    suffixes = path.name.split(".pyc.", 1)
    if len(suffixes) != 2:
        return False
    return bool(suffixes[1]) and suffixes[1].isdigit()
