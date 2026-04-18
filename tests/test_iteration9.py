from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

from examples.cli import build_ops_runtime, EnvLangInterpreter


async def _group_consensus_case():
    _env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=admin ctx=Main')
    await interp.execute('spawn bob:agent role=dispatcher ctx=Dispatch')
    await interp.execute('group create squad with alice,bob ctx=Dispatch')
    groups = await interp.execute('show groups')
    assert groups['groups'][0]['name'] == 'squad'
    vote = await interp.execute('vote squad :: case.assign case=INC-44 target=bob ctx=Dispatch')
    assert vote['consensus']['group'] == 'squad'
    run = await interp.execute('run group squad :: case.assign case=INC-44 target=bob ctx=Dispatch threshold=0.5')
    assert run['consensus']['approved'] is True
    assert run['execution']['status'] == 'success'


async def _delegation_and_fanout_case():
    _env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=admin ctx=Main')
    await interp.execute('spawn bob:agent role=reviewer ctx=Review')
    await interp.execute('group create reviewteam with bob ctx=Review')
    deleg = await interp.execute('delegate alice -> bob :: review.resolve case=INC-9 ctx=Review')
    assert deleg['delegation']['delegatee'] == 'bob'
    fan = await interp.execute('fanout reviewteam :: review.resolve case=INC-9 ctx=Review')
    assert fan['group'] == 'reviewteam'
    assert len(fan['fanout']) == 1


def test_iteration9_group_consensus():
    asyncio.run(_group_consensus_case())


def test_iteration9_delegation_fanout():
    asyncio.run(_delegation_and_fanout_case())
