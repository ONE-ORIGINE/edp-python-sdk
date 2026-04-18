from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

from examples.cli import build_ops_runtime, build_drone_runtime, EnvLangInterpreter


async def _cli_ops_case():
    _env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    result = await interp.execute('spawn alice:agent role=admin ctx=Main')
    assert result['spawned']['role'] == 'admin'
    result = await interp.execute('do alice :: case.open case=INC-1 severity=high')
    assert result['status'] == 'success'
    corr = result['correlation_id']
    result = await interp.execute('focus alice -> Dispatch')
    assert result['agent']['active_context'] == 'Dispatch'
    result = await interp.execute('do alice :: case.assign case=INC-1 target=bob')
    assert result['status'] == 'success'
    why = await interp.execute(f'why {corr}')
    assert why['correlation_id'] == corr
    recs = await interp.execute('ask alice')
    assert recs['recommendations']


async def _cli_drone_case():
    _sdk, runtime = await build_drone_runtime()
    interp = EnvLangInterpreter(runtime)
    recs = await interp.execute('ask scout')
    assert recs['recommendations']
    r = await interp.execute('do scout :: flight.takeoff')
    assert r['status'] == 'success'
    r2 = await interp.execute('msg tower -> scout topic=orders text=hold')
    assert r2['recipient'] == 'scout'
    inbox = await interp.execute('show inbox scout')
    assert inbox['inbox']


def test_iteration6_ops_cli():
    asyncio.run(_cli_ops_case())


def test_iteration6_drone_cli():
    asyncio.run(_cli_drone_case())
