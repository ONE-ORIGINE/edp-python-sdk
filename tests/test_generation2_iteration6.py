import asyncio

from examples.cli import build_ops_runtime, EnvLangInterpreter
from edp_sdk import EnvironmentCanonicalBody, StoreProjectionSuite


def test_generation2_iteration6_store_suite():
    _env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    body = EnvironmentCanonicalBody.from_environment(interp.environment)
    suite = StoreProjectionSuite.from_envx(body)
    assert suite.vector.items
    any_anchor = suite.vector.items[0]['anchor_id']
    sims = suite.vector.similar_to_anchor(any_anchor, top_k=3)
    assert isinstance(sims, list)
    math_body = body.mathematical_projection()
    assert 'X_t' in math_body and 'G_t' in math_body


async def _cli_store_case():
    _env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    math_res = await interp.execute('show projection math')
    assert 'projection_math' in math_res
    store_res = await interp.execute('show projection stores')
    assert 'projection_stores' in store_res
    bundle = store_res['projection_stores']['vector_store']['items']
    assert bundle
    anchor = bundle[0]['anchor_id']
    sim_res = await interp.execute(f'store vector similar anchor={anchor} top=2')
    assert 'vector_similar' in sim_res
    graph_res = await interp.execute('store graph neighbors ctx:Main')
    assert 'graph_neighbors' in graph_res


def test_generation2_iteration6_cli():
    asyncio.run(_cli_store_case())
