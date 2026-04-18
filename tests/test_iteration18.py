
import asyncio

from edp_sdk.envlang import EnvLangFormalCompiler
from edp_sdk.protocol import PlanDispatchPacket, PlanResultPacket
from examples.cli import build_ops_runtime


def test_iteration18_parse_call_and_remote_nodes():
    program = EnvLangFormalCompiler.build_program('p18', 'call child ; remote mirror { do alice :: case.open case=INC-18 severity=high ctx=Main }')
    assert len(program.root) == 2
    assert program.root[0].kind == 'call'
    assert program.root[1].kind == 'remote'
    assert getattr(program.root[1], 'metadata', {}).get('peer') == 'mirror'


def test_iteration18_distributed_packets_and_execution():
    _env, _gateway, runtime = build_ops_runtime()
    _env2, _peer_gateway, peer_runtime = build_ops_runtime()
    runtime.register_runtime_peer('mirror', peer_runtime)
    child = EnvLangFormalCompiler.build_program('child', 'do alice :: case.open case=INC-180 severity=high ctx=Main')
    remote = EnvLangFormalCompiler.build_program('remote_main', 'remote mirror { call child }')
    asyncio.run(peer_runtime.spawn('alice', role='admin', context_name='Main'))
    peer_runtime.formal_plans = {'child': child}
    result = asyncio.run(runtime.execute_formal_plan(remote))
    assert result.success is True
    remote_entry = result.results[0]
    assert remote_entry['kind'] == 'remote'
    assert remote_entry['result_packet']['source_peer'] == 'mirror'
    dispatch = PlanDispatchPacket(packet_id='x', plan_name='p', target_peer='mirror', ast={'root': []})
    outcome = PlanResultPacket(packet_id='y', plan_name='p', source_peer='mirror', success=True, result={'ok': True})
    assert 'target_peer' in dispatch.__dict__
    assert outcome.success is True
