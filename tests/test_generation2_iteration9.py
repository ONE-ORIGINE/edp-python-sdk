import asyncio

from examples.cli import EnvLangInterpreter, build_ops_runtime
from edp_sdk import ContextMatrix, Contextualizer, DataSignal, EnvironmentCanonicalBody, SenseVector, SignalProfile


async def _iteration9_cli_case():
    _env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=admin ctx=Main')
    await interp.execute('spawn bob:agent role=dispatcher ctx=Dispatch')
    await interp.execute('spawn cara:agent role=reviewer ctx=Review')
    await interp.execute('do alice :: case.open case=INC-900 severity=high')
    await interp.execute('do bob :: case.assign case=INC-900 target=alice')
    await interp.execute('do cara :: review.escalate case=INC-900')

    res_matrix = await interp.execute('show context matrix')
    assert 'context_matrix' in res_matrix
    assert 'semantic' in res_matrix['context_matrix']['rows']

    res_learning = await interp.execute('show learning')
    assert 'learning' in res_learning
    assert res_learning['learning']['recommendations']

    res_action = await interp.execute('show learning action case.open')
    assert 'learning_action' in res_action
    assert res_action['learning_action']['mean_impact'] > 0

    res_math = await interp.execute('show math body')
    assert 'math_body' in res_math and 'learning' in res_math
    assert 'M_C' in res_math['math_body']
    assert res_math['learning']['session_vector']


def test_generation2_iteration9_cli():
    asyncio.run(_iteration9_cli_case())


def test_generation2_iteration9_contextualizer_and_canonical_projection():
    cx = Contextualizer(context_matrix=ContextMatrix())
    cx.register_profile(SignalProfile('battery', SenseVector.temporal('battery state', 1.0), min_val=0.0, max_val=100.0))
    _env, _gateway, runtime = build_ops_runtime()
    _env.contextualizer = cx
    main = _env.contexts['Main']
    explained = cx.explain(DataSignal('battery', 15, unit='%'), main)
    assert explained['result']['metadata']['weights']
    assert explained['result']['sense']['meaning'].endswith('@semantic')

    body = EnvironmentCanonicalBody.from_environment(_env)
    assert 'context_operator' in body.contextualizer_projection()
    assert 'learning' in body.to_dict()['exports']
    assert 'M_C' in body.mathematical_projection()
