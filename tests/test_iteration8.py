from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

from examples.cli import build_ops_runtime, EnvLangInterpreter


async def _multi_context_and_interface_case():
    _env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=operator ctx=Main')
    await interp.execute('ctx add alice Dispatch')
    await interp.execute('iface bind alice panel realm=ui ctx=Dispatch mode=surface shared=true')
    scope = await interp.execute('show scope alice')
    assert 'Dispatch' in scope['scope']['accessible_contexts']
    iface = await interp.execute('iface show alice')
    assert iface['interfaces'][0]['realm'] == 'ui'
    recs = await interp.execute('ask alice :: *')
    assert isinstance(recs['recommendations'], list)


async def _situation_and_policy_case():
    env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn bob:agent role=reviewer ctx=Review')
    # force critical situation in Review
    from edp_sdk.savoir import Factor
    env.savoir.factor_graph.add_factor(Factor('critical-load', ('ops',), lambda vals: 1.0, weight=11.0))
    denied = await interp.execute('do bob :: review.resolve case=INC-9')
    assert denied['status'] == 'policy_denied'
    assert 'critical' in str(denied['policy']['reasons']).lower()
    await interp.execute('cap grant bob critical')
    allowed = await interp.execute('do bob :: review.resolve case=INC-9')
    assert allowed['status'] == 'success'


def test_iteration8_multi_context_and_interface():
    asyncio.run(_multi_context_and_interface_case())


def test_iteration8_situation_guard():
    asyncio.run(_situation_and_policy_case())
