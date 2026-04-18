from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

from examples.cli import build_ops_runtime, EnvLangInterpreter


async def _weighted_negotiation_and_plan_case():
    _env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=admin ctx=Main')
    await interp.execute('spawn bob:agent role=dispatcher ctx=Dispatch')
    await interp.execute('spawn cara:agent role=reviewer ctx=Review')
    await interp.execute('group create triad with alice,bob,cara ctx=Dispatch,Review')
    await interp.execute('group weight triad alice 0.2')
    await interp.execute('group weight triad bob 1.5')
    neg = await interp.execute('negotiate triad :: case.assign case=INC-77 target=cara ctx=Dispatch threshold=0.3')
    assert neg['negotiation']['group'] == 'triad'
    assert neg['negotiation']['selected_actor'] in {'alice', 'bob'}
    plan = await interp.execute('plan triage = do alice :: case.open case=INC-77 severity=high ; negotiate triad :: case.assign case=INC-77 target=cara ctx=Dispatch threshold=0.3 ; do cara :: review.resolve case=INC-77 ctx=Review')
    assert plan['plan']['name'] == 'triage'
    run = await interp.execute('run plan triage')
    assert run['plan_execution']['success'] is True


async def _runtime_merge_case():
    _env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=admin ctx=Main')
    await interp.execute('group create squad with alice ctx=Main')
    packet = runtime.export_runtime_state()

    _env2, _gateway2, runtime2 = build_ops_runtime()
    interp2 = EnvLangInterpreter(runtime2)
    await interp2.execute('spawn bob:agent role=dispatcher ctx=Dispatch')
    report = runtime2.merge_runtime_state(packet)
    assert report['merged_groups'] >= 1
    assert 'alice' in runtime2.gateway.peers


def test_iteration10_weighted_negotiation_and_plan():
    asyncio.run(_weighted_negotiation_and_plan_case())


def test_iteration10_runtime_merge():
    asyncio.run(_runtime_merge_case())
