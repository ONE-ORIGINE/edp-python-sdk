from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

REQUIRED_ROOT_FILES = [
    'README.md', 'pyproject.toml', 'setup.py', 'LICENSE', 'CHANGELOG.md', 'CONTRIBUTING.md',
    'CODE_OF_CONDUCT.md', 'SECURITY.md', 'CITATION.cff', 'MANIFEST.in', '.gitignore', 'RELEASE_MANIFEST.json'
]
REQUIRED_GITHUB_FILES = [
    '.github/workflows/ci.yml',
    '.github/workflows/publish-pypi.yml',
]
REQUIRED_PACKAGES = ['edp_sdk', 'drone_edp', 'mep_tools', 'examples']
REQUIRED_DOCS = [
    'docs/TECHNICAL_ARCHITECTURE.md', 'docs/DISTRIBUTED_RUNTIME.md', 'docs/ENVX_CANONICAL.md',
    'docs/QUICKSTART.md', 'docs/CLI_REFERENCE.md', 'docs/ENVLANG_REFERENCE.md',
    'docs/GITHUB_PYPI_RELEASE.md', 'docs/RELEASE_PUBLISHING.md',
    'docs/GEN2_FINAL_STABLE.md', 'docs/MIGRATION_TO_2_0_0.md',
]


@dataclass
class ReleaseAuditReport:
    ok: bool
    missing: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'ok': self.ok,
            'missing': list(self.missing),
            'warnings': list(self.warnings),
            'details': dict(self.details),
        }


def _read_version_from_init(path: Path) -> str | None:
    text = path.read_text(encoding='utf-8') if path.exists() else ''
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else None


def _is_stable_version(version: str | None) -> bool:
    return bool(version and re.fullmatch(r'\d+\.\d+\.\d+', version))


def audit_repository(root: str | Path = '.') -> ReleaseAuditReport:
    root = Path(root).resolve()
    missing: List[str] = []
    warnings: List[str] = []
    for rel in REQUIRED_ROOT_FILES + REQUIRED_GITHUB_FILES + REQUIRED_DOCS:
        if not (root / rel).exists():
            missing.append(rel)
    for pkg in REQUIRED_PACKAGES:
        if not (root / pkg / '__init__.py').exists():
            missing.append(f'{pkg}/__init__.py')

    pyproject = root / 'pyproject.toml'
    pyproject_text = pyproject.read_text(encoding='utf-8') if pyproject.exists() else ''
    pyproject_data = tomllib.loads(pyproject_text) if pyproject_text else {}
    project = pyproject_data.get('project', {})
    pyproject_version = project.get('version')
    scripts = project.get('scripts', {})
    classifiers = project.get('classifiers', [])
    expected_scripts = {'edp-cli', 'edp-demo', 'edp-release-check', 'edp-build-release'}
    for token in ['[project]', 'version =', '[project.scripts]']:
        if token not in pyproject_text:
            warnings.append(f'pyproject missing expected token: {token}')
    missing_scripts = sorted(expected_scripts.difference(scripts.keys()))
    for script in missing_scripts:
        warnings.append(f'pyproject missing expected script: {script}')

    edp_version = _read_version_from_init(root / 'edp_sdk' / '__init__.py')
    drone_version = _read_version_from_init(root / 'drone_edp' / '__init__.py')
    tools_version = _read_version_from_init(root / 'mep_tools' / '__init__.py')

    release_py = root / 'edp_sdk' / 'release.py'
    release_text = release_py.read_text(encoding='utf-8') if release_py.exists() else ''
    release_match = re.search(r'PROJECT_VERSION\s*=\s*"([^"]+)"', release_text)
    release_version = release_match.group(1) if release_match else None
    channel_match = re.search(r'CHANNEL\s*=\s*"([^"]+)"', release_text)
    release_channel = channel_match.group(1) if channel_match else None

    manifest_path = root / 'RELEASE_MANIFEST.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    manifest_version = manifest.get('version')
    manifest_channel = manifest.get('channel')

    citation_text = (root / 'CITATION.cff').read_text(encoding='utf-8') if (root / 'CITATION.cff').exists() else ''
    citation_match = re.search(r'^version:\s*([^\n]+)$', citation_text, flags=re.MULTILINE)
    citation_version = citation_match.group(1).strip() if citation_match else None

    changelog_text = (root / 'CHANGELOG.md').read_text(encoding='utf-8') if (root / 'CHANGELOG.md').exists() else ''
    readme_text = (root / 'README.md').read_text(encoding='utf-8') if (root / 'README.md').exists() else ''

    versions = {
        'pyproject': pyproject_version,
        'edp_sdk': edp_version,
        'drone_edp': drone_version,
        'mep_tools': tools_version,
        'release_py': release_version,
        'manifest': manifest_version,
        'citation': citation_version,
    }
    unique_versions = sorted({v for v in versions.values() if v})
    if len(unique_versions) > 1:
        warnings.append(f'version mismatch detected: {versions}')
    if release_channel != manifest_channel:
        warnings.append(f'channel mismatch detected: release.py={release_channel} manifest={manifest_channel}')
    if pyproject_version and f'## {pyproject_version}' not in changelog_text:
        warnings.append(f'changelog missing release section for {pyproject_version}')

    is_stable = _is_stable_version(pyproject_version)
    if is_stable:
        if release_channel != 'stable' or manifest_channel != 'stable':
            warnings.append('stable version requires stable channel in release.py and manifest')
        if 'Development Status :: 5 - Production/Stable' not in classifiers:
            warnings.append('stable version should declare Production/Stable classifier')
        if 'Stable 2.0.0' not in readme_text and 'stable 2.0.0' not in readme_text.lower():
            warnings.append('README should identify the stable line explicitly')
    else:
        if release_channel == 'stable' or manifest_channel == 'stable':
            warnings.append('pre-release version should not advertise stable channel')

    details = {
        'root': str(root),
        'required_files': len(REQUIRED_ROOT_FILES) + len(REQUIRED_GITHUB_FILES) + len(REQUIRED_DOCS),
        'packages_checked': list(REQUIRED_PACKAGES),
        'docs_checked': list(REQUIRED_DOCS),
        'versions': versions,
        'channel': {
            'release_py': release_channel,
            'manifest': manifest_channel,
        },
        'scripts': sorted(scripts.keys()),
        'stable_release': is_stable,
    }
    return ReleaseAuditReport(ok=(len(missing) == 0 and len(warnings) == 0), missing=missing, warnings=warnings, details=details)


def main() -> int:
    report = audit_repository(Path(__file__).resolve().parents[1])
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.ok else 1


__all__ = ['ReleaseAuditReport', 'audit_repository', 'main']
