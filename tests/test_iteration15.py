from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
from edp_sdk import EnvLangFormalCompiler
from examples.cli import build_ops_runtime, EnvLangInterpreter


def test_iteration15_formal_program_nested_parse():
    body = (
        "open_case: do alice :: case.open case=INC-15 severity=high ctx=Main ; "
        "if result.open_case.success = true then { assign_case: do bob :: case.assign case=INC-15 target=bob ctx=Dispatch ; sequence{ ping_a: do alice :: system.ping ; ping_b: do bob :: system.ping } } "
        "else { fallback: do alice :: system.ping } ; "
        "parallel{ pa: do alice :: system.ping | pb: do bob :: system.ping }"
    )
    program = EnvLangFormalCompiler.build_program('triage', body)
    data = program.to_dict()
    assert data['name'] == 'triage'
    assert any(node['kind'] == 'if' for node in data['root'])
    assert any(node['kind'] == 'parallel' for node in data['root'])


async def _run_formal_plan():
    env, gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=admin ctx=Main')
    await interp.execute('spawn bob:agent role=dispatcher ctx=Dispatch')
    await interp.execute('ctx add bob Main')
    await interp.execute(
        'plan triage = open_case: do alice :: case.open case=INC-15 severity=high ctx=Main ; '
        'if result.open_case.success = true then { assign_case: do bob :: case.assign case=INC-15 target=bob ctx=Dispatch } else { fallback: do alice :: system.ping } ; '
        'parallel{ pa: do alice :: system.ping | pb: do bob :: system.ping }'
    )
    result = await interp.execute('run plan triage')
    packet = result['formal_plan_execution']
    assert packet['success'] is True
    labels = {entry.get('label'): entry for entry in packet['results']}
    assert 'open_case' in labels
    # locate if result
    if_entry = next(entry for entry in packet['results'] if entry['kind'] == 'if')
    assert if_entry['holds'] is True
    assert if_entry['results'][0]['label'] == 'assign_case'
    par_entry = next(entry for entry in packet['results'] if entry['kind'] == 'parallel')
    assert par_entry['success'] is True


def test_iteration15_formal_plan_execution():
    asyncio.run(_run_formal_plan())
