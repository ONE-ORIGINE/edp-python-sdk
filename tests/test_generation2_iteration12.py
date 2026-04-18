from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mep_tools.release_checks import audit_repository
from mep_tools.release_build import build_release_artifacts


def test_generation2_iteration12_stable_release(tmp_path):
    root = Path(__file__).resolve().parents[1]
    report = audit_repository(root)
    assert report.ok, report.to_dict()
    assert report.details['stable_release'] is True
    result = build_release_artifacts(root, clean=True)
    assert 'RELEASE_SHA256SUMS.txt' in result['artifacts']
    assert 'RELEASE_INDEX.json' in result['artifacts']
    index = json.loads((root / 'dist' / 'RELEASE_INDEX.json').read_text(encoding='utf-8'))
    assert index['version'] == '2.0.0'
    assert index['channel'] == 'stable'
    assert any(item['name'].endswith('.whl') for item in index['artifacts'])
    assert any(item['name'].endswith('.tar.gz') for item in index['artifacts'])
