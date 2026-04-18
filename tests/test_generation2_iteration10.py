from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

from examples.cli import EnvLangInterpreter, build_ops_runtime
from edp_sdk import EnvironmentCanonicalBody, NativeSpecializedStoreSuite


async def _iteration10_case(tmp_path):
    env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=admin ctx=Main')
    await interp.execute('spawn bob:agent role=dispatcher ctx=Dispatch')
    await interp.execute('spawn cara:agent role=reviewer ctx=Review')
    await interp.execute('do alice :: case.open case=INC-910 severity=high')
    await interp.execute('do bob :: case.assign case=INC-910 target=alice')
    await interp.execute('do cara :: review.escalate case=INC-910')

    score = await interp.execute('show score alice :: open a high severity case INC-910')
    assert 'score' in score
    assert score['score']['candidates']
    assert 'causal_score_card' in score['score']['candidates'][0]
    assert 'causal_leverage' in score['score']['candidates'][0]['causal_score_card']

    persisted = await interp.execute(f'persist stores {tmp_path / "ops_gen2"}')
    assert persisted['stores']['learning']['record_count'] >= 3
    assert persisted['stores']['dataset']['event_count'] >= 3

    backend = await interp.execute('show learning backend')
    assert backend['learning_backend']['actions']
    assert backend['learning_backend']['latest_projection']['recommendations']

    body = EnvironmentCanonicalBody.from_environment(env)
    assert 'persistent_backends' in body.to_dict()['exports']
    assert 'S_t' in body.mathematical_projection()

    suite = NativeSpecializedStoreSuite(tmp_path / 'ops_gen2')
    env2, _gateway2, _runtime2 = build_ops_runtime()
    merged = suite.merge_into(env2)
    assert merged['learning_merge']['records_after'] >= 3
    assert suite.dataset.by_action('case.open')


def test_generation2_iteration10(tmp_path):
    asyncio.run(_iteration10_case(tmp_path))
