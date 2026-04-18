from pathlib import Path

from edp_sdk import MepGateway, MultiAgentRuntime, SQLiteRuntimeStore
from examples.cli import build_ops_runtime


def test_runtime_sqlite_store_roundtrip(tmp_path: Path):
    env, gateway, runtime = build_ops_runtime()
    state = runtime.runtime_state_payload()
    db = tmp_path / 'runtime.sqlite'
    store = SQLiteRuntimeStore(db)
    store.save_runtime_state(state)
    latest = store.latest_runtime_state()
    assert latest['environment_id'] == env.environment_id
    assert 'heartbeat' in latest


def test_runtime_merge_report_and_lock_conflict():
    _env1, _gw1, rt1 = build_ops_runtime()
    _env2, _gw2, rt2 = build_ops_runtime()
    rt1.acquire_lock('case:INC-1', 'alice', ttl_s=60)
    rt2.acquire_lock('case:INC-1', 'bob', ttl_s=10)
    packet = rt1.export_runtime_state()
    packet.locks = rt1.list_locks()
    packet.executions = rt1.execution_state().executions
    packet.peers = {}
    report = rt2.merge_runtime_state(packet)
    data = report.to_dict()
    assert data['replaced_locks'] >= 1 or data['imported_locks'] >= 1
    assert isinstance(data['conflicts'], list)


def test_release_audit_checks_new_docs():
    from mep_tools.release_checks import audit_repository
    root = Path(__file__).resolve().parents[1]
    report = audit_repository(root)
    assert report.ok is True
    assert 'docs/TECHNICAL_ARCHITECTURE.md' in report.details['docs_checked']
