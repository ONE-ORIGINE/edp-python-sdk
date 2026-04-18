from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
from edp_sdk import EnvLangFormalCompiler
from examples.cli import build_ops_runtime, EnvLangInterpreter


def test_iteration16_compile_program_with_let_and_bind():
    body = (
        'let case_id = "INC-16" ; '
        'open_case: do alice :: case.open case=${var.case_id} severity=high ctx=Main => opened ; '
        'if result.open_case.success = true then { assign_case: do bob :: case.assign case=${var.case_id} target=bob ctx=Dispatch }'
    )
    program = EnvLangFormalCompiler.build_program('flow16', body)
    data = program.to_dict()
    assert data['root'][0]['kind'] == 'let'
    assert data['root'][1]['kind'] == 'command'


async def _run_iteration16_plan():
    env, gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=admin ctx=Main')
    await interp.execute('spawn bob:agent role=dispatcher ctx=Dispatch')
    await interp.execute('ctx add bob Main')
    await interp.execute(
        'plan flow16 = let case_id = "INC-16" ; '
        'open_case: do alice :: case.open case=${var.case_id} severity=high ctx=Main => opened ; '
        'if result.open_case.success = true then { assign_case: do bob :: case.assign case=${var.case_id} target=bob ctx=Dispatch }'
    )
    result = await interp.execute('run plan flow16')
    packet = result['formal_plan_execution']
    assert packet['success'] is True
    first = packet['results'][0]
    assert first['kind'] == 'let'
    second = packet['results'][1]
    assert second['label'] == 'open_case'
    assert second['bind'] == 'opened'
    if_entry = packet['results'][2]
    assert if_entry['holds'] is True
    assign = if_entry['results'][0]
    assert assign['label'] == 'assign_case'


def test_iteration16_formal_plan_variables_and_bindings():
    asyncio.run(_run_iteration16_plan())
