from pathlib import Path

from mep_tools.release_checks import audit_repository


def test_release_audit_passes():
    root = Path(__file__).resolve().parents[1]
    report = audit_repository(root)
    assert report.ok is True
    assert report.missing == []


def test_packaged_examples_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / 'examples' / '__init__.py').exists()
