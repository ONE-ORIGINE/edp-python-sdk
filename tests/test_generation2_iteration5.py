from __future__ import annotations

import asyncio
from examples.cli import build_ops_runtime, EnvLangInterpreter
from edp_sdk.canonical import EnvironmentCanonicalBody


def test_generation2_iteration5_store_bundles():
    _env, _gw, runtime = build_ops_runtime()
    body = EnvironmentCanonicalBody.from_environment(runtime.environment)
    stores = body.store_bundle_projection()
    assert 'vector_store' in stores
    assert 'graph_store' in stores
    assert 'tensor_store' in stores
    assert stores['tensor_store']['node_matrices']


def test_generation2_iteration5_group_goal_preview_and_execute():
    async def case():
        _env, _gw, runtime = build_ops_runtime()
        await runtime.spawn('alice', role='admin', context_name='Main')
        await runtime.spawn('bob', role='dispatcher', context_name='Dispatch')
        runtime.create_group('squad', ['alice', 'bob'], shared_contexts=['Main', 'Dispatch'])
        interp = EnvLangInterpreter(runtime)
        pv = await interp.execute('group goal preview squad :: open a high severity case INC-500')
        assert 'group_goal_preview' in pv
        res = await interp.execute('group goal squad :: open a high severity case INC-501')
        assert 'group_goal_decision' in res
        assert res['group_goal_decision']['action_type']
    asyncio.run(case())


def test_generation2_iteration5_show_projection_stores_and_llm_bundle():
    async def case():
        _env, _gw, runtime = build_ops_runtime()
        interp = EnvLangInterpreter(runtime)
        proj = await interp.execute('show projection stores')
        assert 'projection' in proj and 'vector_store' in proj['projection']
        bundle = await interp.execute('show llm bundle alice')
        assert 'llm_bundle' in bundle
    asyncio.run(case())
