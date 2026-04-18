from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

from examples.cli import EnvLangInterpreter, build_ops_runtime


async def _goal_preview_case():
    _env, _gw, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=admin ctx=Main')
    out = await interp.execute('goal preview alice :: open a high severity case INC-200')
    preview = out['goal_preview']
    assert preview['selected_context'] == 'Main'
    assert preview['candidates']
    assert preview['candidates'][0]['action_type'] == 'case.open'


def test_goal_preview_case():
    asyncio.run(_goal_preview_case())


async def _goal_execute_case():
    _env, _gw, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=admin ctx=Main')
    await interp.execute('llm config provider=demo inject_memory=true inject_situation=true')
    status = await interp.execute('llm status')
    assert status['llm']['provider'] == 'demo'
    out = await interp.execute('goal alice :: open a high severity case INC-201')
    decision = out['goal_decision']
    assert decision['action_type'] == 'case.open'
    assert decision['execution']['status'] == 'success'
    assert decision['execution']['result']['case'] == 'INC-201'


def test_goal_execute_case():
    asyncio.run(_goal_execute_case())
