from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
from edp_sdk import ProtocolCodec, SQLiteEventStore, SQLiteGraphStore
from examples.cli import build_ops_runtime, EnvLangInterpreter


async def _protocol_and_sqlite_case(tmp_path: Path):
    _env, gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=admin ctx=Main')
    await interp.execute('do alice :: case.open case=INC-100 severity=high')

    env_card = gateway.environment_card()
    pkt = ProtocolCodec.pack('environment.card', env_card.to_dict())
    restored = ProtocolCodec.unpack(pkt.to_json())
    assert restored.header.packet_type == 'environment.card'
    assert restored.body['environment_id'] == env_card.environment_id

    event_store = SQLiteEventStore(tmp_path / 'mem.sqlite')
    graph_store = SQLiteGraphStore(tmp_path / 'graph.sqlite')
    event_store.save_memory(runtime.environment.memory)
    graph_store.save(runtime.environment.semantic_graph)
    assert len(event_store.by_actor(runtime.agents['alice'].element_id)) >= 1
    assert len(graph_store.query_relation('contains')) >= 1

    _env2, _gateway2, runtime2 = build_ops_runtime()
    event_report = event_store.merge_into(runtime2.environment.memory)
    graph_report = graph_store.merge_into(runtime2.environment.semantic_graph)
    assert event_report['events'] >= 1
    assert graph_report['nodes'] >= 1


async def _cli_source_case(tmp_path: Path):
    _env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    script = tmp_path / 'ops.envl'
    script.write_text('\n'.join([
        'spawn alice:agent role=admin ctx=Main',
        'show card env',
        'save sqlite ' + str(tmp_path / 'snapshot'),
    ]), encoding='utf-8')
    result = await interp.execute(f'source {script}')
    assert result['script'].endswith('ops.envl')
    assert len(result['results']) == 3


def test_iteration11_protocol_and_sqlite(tmp_path: Path):
    asyncio.run(_protocol_and_sqlite_case(tmp_path))


def test_iteration11_cli_source(tmp_path: Path):
    asyncio.run(_cli_source_case(tmp_path))
