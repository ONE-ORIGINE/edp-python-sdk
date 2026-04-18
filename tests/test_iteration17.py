from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
from edp_sdk import EnvLangFormalCompiler
from examples.cli import build_ops_runtime, EnvLangInterpreter


def test_iteration17_compile_typed_let_and_function_refs():
    body = (
        'let case_id:str = "inc-17" ; '
        'open_case: do alice :: case.open case=${fn.upper(var.case_id)} severity=high ctx=Main => opened ; '
        'if agent.alice.role = admin then { assign_case: do bob :: case.assign case=${fn.upper(var.case_id)} target=${fn.lower(result.open_case.result.owner)} ctx=Dispatch }'
    )
    program = EnvLangFormalCompiler.build_program('flow17', body)
    data = program.to_dict()
    assert data['root'][0]['kind'] == 'let'
    assert data['root'][1]['label'] == 'open_case'
    assert data['root'][2]['kind'] == 'if'


async def _run_iteration17_remote_plan():
    env, gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=admin ctx=Main')
    await interp.execute('spawn bob:agent role=dispatcher ctx=Dispatch')
    await interp.execute('ctx add bob Main')
    await interp.execute('peer add mirror ops')
    peer = interp.peer_runtimes['mirror']
    await peer.spawn('alice', role='admin', context_name='Main')
    await peer.spawn('bob', role='dispatcher', context_name='Dispatch')
    peer.add_context_access('bob', 'Main')
    await interp.execute(
        'plan flow17 = let case_id:str = "inc-17" ; '
        'open_case: do alice :: case.open case=${fn.upper(var.case_id)} severity=high ctx=Main => opened ; '
        'if result.open_case.success = true then { assign_case: do bob :: case.assign case=${fn.upper(var.case_id)} target=${fn.lower(result.open_case.result.owner)} ctx=Dispatch }'
    )
    result = await interp.execute('run remote mirror flow17')
    packet = result['distributed_formal_plan']
    assert packet['success'] is True
    assert packet['target_peer'] == 'mirror'
    inner = packet['result']
    assert inner['success'] is True
    first_command = inner['results'][1]
    assert first_command['result']['result']['case'] == 'INC-17'


def test_iteration17_distributed_plan_and_functions():
    asyncio.run(_run_iteration17_remote_plan())
