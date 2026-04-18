from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mep_tools.release_checks import audit_repository
from mep_tools.release_build import build_release_artifacts


def test_generation2_iteration11(tmp_path):
    root = Path(__file__).resolve().parents[1]
    report = audit_repository(root)
    assert report.ok, report.to_dict()
    result = build_release_artifacts(root, clean=True)
    assert any(name.endswith('.tar.gz') for name in result['artifacts'])
    assert any(name.endswith('.whl') for name in result['artifacts'])
