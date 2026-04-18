from pathlib import Path

from mep_tools.release_checks import audit_repository
from edp_sdk.release import build_release_manifest, PROJECT_VERSION, CHANNEL


def test_release_audit_passes_repo_root():
    root = Path(__file__).resolve().parents[1]
    report = audit_repository(root)
    assert report.ok, report.to_dict()


def test_release_manifest_matches_runtime_line():
    manifest = build_release_manifest()
    assert manifest.version == PROJECT_VERSION
    assert manifest.channel == CHANNEL
