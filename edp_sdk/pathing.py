from __future__ import annotations

import os
import tempfile
from pathlib import Path


def ensure_portable_tmp() -> Path:
    """Ensure a portable /tmp-like directory exists even on Windows.

    Some tests and scripts use Path('/tmp/...'). On Windows this becomes \\tmp\\...,
    which may not exist by default. Creating it once is harmless on Unix and
    prevents cross-platform failures.
    """
    tmp = Path('/tmp')
    try:
        tmp.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return tmp


def normalize_user_path(raw: str | os.PathLike[str]) -> Path:
    value = str(raw).strip().strip('"').strip("'")
    value = os.path.expandvars(os.path.expanduser(value))
    p = Path(value)
    return p


def ensure_parent_dir(path: str | os.PathLike[str]) -> Path:
    p = normalize_user_path(path)
    parent = p.parent if str(p.parent) not in {'', '.'} else Path('.')
    parent.mkdir(parents=True, exist_ok=True)
    return p


def temp_base(name: str = 'edp') -> Path:
    base = Path(tempfile.gettempdir()) / name
    base.mkdir(parents=True, exist_ok=True)
    return base
