from __future__ import annotations

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

from examples.cli import EnvLangInterpreter, build_ops_runtime
from edp_sdk.protocol import ExecutionLease


def test_plan_preflight_detects_locked_resources():
    env, gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)

    async def run():
        await interp.execute('spawn alice:agent role=admin ctx=Main')
        await interp.execute('spawn bob:agent role=dispatcher ctx=Dispatch')
        await interp.execute('plan remote_case = do alice :: case.open case=INC-22 severity=high ctx=Main')
        await interp.execute('peer add mirror ops')
        peer_runtime = interp.peer_runtimes['mirror']
        peer_runtime.formal_plans = getattr(peer_runtime, 'formal_plans', {})
        peer_runtime.formal_plans['remote_case'] = interp.formal_plans['remote_case']
        peer_runtime.acquire_lock('case:INC-22', 'other-owner', ttl_s=60.0)
        return await interp.execute('show packet plan.preflight mirror remote_case')

    out = asyncio.run(run())
    body = out['packet']['body']
    assert out['packet']['header']['packet_type'] == 'plan.preflight'
    assert body['executable'] is False
    assert 'case:INC-22' in body['lock_status']['conflicts']


def test_run_remote_with_dependency_blocked_until_execution_completes():
    env, gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)

    async def run():
        await interp.execute('spawn alice:agent role=admin ctx=Main')
        await interp.execute('spawn bob:agent role=dispatcher ctx=Dispatch')
        await interp.execute('plan prereq = do alice :: case.open case=INC-220 severity=high ctx=Main')
        await interp.execute('plan remote_case = do alice :: case.open case=INC-221 severity=high ctx=Main')
        await interp.execute('peer add mirror ops')
        peer_runtime = interp.peer_runtimes['mirror']
        peer_runtime.formal_plans = getattr(peer_runtime, 'formal_plans', {})
        peer_runtime.formal_plans['remote_case'] = interp.formal_plans['remote_case']
        prereq = await interp.execute('run plan prereq')
        exec_id = next(iter(runtime._executions.keys()))
        blocked = await interp.execute('run remote mirror remote_case after=missing-exec')
        allowed = await interp.execute(f'run remote mirror remote_case after={exec_id}')
        return blocked, allowed

    blocked, allowed = asyncio.run(run())
    assert blocked['distributed_formal_plan']['success'] is False
    assert blocked['distributed_formal_plan']['result']['preflight']['dependency_status']['missing']
    assert allowed['distributed_formal_plan']['success'] is True


def test_merge_runtime_brings_newer_execution_and_locks():
    env, gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)

    async def run():
        await interp.execute('spawn alice:agent role=admin ctx=Main')
        await interp.execute('spawn bob:agent role=dispatcher ctx=Dispatch')
        await interp.execute('peer add mirror ops')
        peer_runtime = interp.peer_runtimes['mirror']
        peer_runtime._executions = {'exec-peer': {'execution_id': 'exec-peer', 'state': 'completed', 'success': True, 'started_at': 1.0, 'completed_at': 2.0}}
        peer_runtime._leases = {'case:INC-229': ExecutionLease(resource='case:INC-229', owner='peer', acquired_at=1.0, expires_at=9999999999.0)}
        return await interp.execute('merge runtime mirror')

    out = asyncio.run(run())
    assert out['merge']['execution_updates'] >= 1
    assert out['merge']['lock_updates'] >= 1
    assert out['packet']['header']['packet_type'] == 'runtime.merge_state'
