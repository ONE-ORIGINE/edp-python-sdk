import asyncio

from examples.cli import build_ops_runtime, EnvLangInterpreter


async def _group_goal_explain_case():
    _env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=admin ctx=Main')
    await interp.execute('spawn bob:agent role=dispatcher ctx=Dispatch')
    await interp.execute('spawn cara:agent role=reviewer ctx=Review')
    await interp.execute('group create squad with alice,bob,cara ctx=Main,Dispatch,Review')
    res = await interp.execute('group goal explain squad :: open a high severity case INC-800')
    assert 'group_goal_explain' in res
    explain = res['group_goal_explain']
    assert 'preview' in explain and 'decision' in explain
    basis = explain['preview']['negotiation_basis']
    assert 'collective_attention' in basis
    assert 'member_alignment' in basis
    negotiated = explain['decision']['negotiated']
    assert 'phenomenon_pressure' in negotiated
    assert 'circumstance_pressure' in negotiated


async def _show_attention_case():
    _env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=admin ctx=Main')
    await interp.execute('spawn bob:agent role=dispatcher ctx=Dispatch')
    await interp.execute('group create squad with alice,bob ctx=Main,Dispatch')
    res_a = await interp.execute('show attention alice')
    assert 'attention' in res_a and 'vector' in res_a['attention']
    res_g = await interp.execute('show attention group squad')
    assert 'attention' in res_g and 'anchors' in res_g['attention']


def test_generation2_iteration8_group_goal_explain():
    asyncio.run(_group_goal_explain_case())


def test_generation2_iteration8_show_attention():
    asyncio.run(_show_attention_case())
