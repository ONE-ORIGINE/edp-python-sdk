from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from .release_checks import audit_repository


def _run(cmd: Iterable[str], cwd: Path) -> None:
    subprocess.run(list(cmd), cwd=str(cwd), check=True)


def _build_command(root: Path) -> list[str]:
    try:
        import build  # type: ignore  # noqa: F401
        return [sys.executable, '-m', 'build', '--sdist', '--wheel']
    except Exception:
        return [sys.executable, 'setup.py', 'sdist', 'bdist_wheel']


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _write_release_index(root: Path, artifacts: list[Path]) -> dict:
    manifest = json.loads((root / 'RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
    dist = root / 'dist'
    sha_lines: list[str] = []
    artifact_rows: list[dict] = []
    for path in artifacts:
        checksum = _sha256(path)
        sha_lines.append(f"{checksum}  {path.name}")
        artifact_rows.append({'name': path.name, 'size': path.stat().st_size, 'sha256': checksum})
    sums_path = dist / 'RELEASE_SHA256SUMS.txt'
    sums_path.write_text('\n'.join(sha_lines) + ('\n' if sha_lines else ''), encoding='utf-8')
    index = {
        'version': manifest.get('version'),
        'channel': manifest.get('channel'),
        'artifacts': artifact_rows,
        'checksums_file': sums_path.name,
    }
    index_path = dist / 'RELEASE_INDEX.json'
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True), encoding='utf-8')
    return index


def build_release_artifacts(root: str | Path = '.', clean: bool = False, audit: bool = True) -> dict:
    root = Path(root).resolve()
    if audit:
        report = audit_repository(root)
        if not report.ok:
            raise RuntimeError(f'release audit failed: {report.to_dict()}')
    if clean:
        for rel in ('dist', 'build'):
            target = root / rel
            if target.exists():
                shutil.rmtree(target)
        for egg in root.glob('*.egg-info'):
            if egg.exists():
                shutil.rmtree(egg)
    _run(_build_command(root), root)
    dist = root / 'dist'
    artifact_paths = sorted(
        [p for p in dist.glob('*') if p.is_file() and p.suffix in {'.whl', '.gz'}],
        key=lambda p: p.name,
    )
    index = _write_release_index(root, artifact_paths)
    artifacts = sorted(p.name for p in dist.glob('*') if p.is_file())
    return {
        'root': str(root),
        'artifacts': artifacts,
        'release_index': index,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Build local release artifacts for the EDP Python SDK.')
    parser.add_argument('--root', default='.', help='Repository root')
    parser.add_argument('--clean', action='store_true', help='Remove old build artifacts before building')
    args = parser.parse_args()
    result = build_release_artifacts(args.root, clean=args.clean)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


__all__ = ['build_release_artifacts', 'main']
