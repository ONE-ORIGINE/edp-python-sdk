from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

from examples.cli import build_ops_runtime, EnvLangInterpreter


async def _policy_cli_case():
    _env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=reviewer ctx=Review')
    # reviewer can resolve by default
    ok = await interp.execute('do alice :: review.resolve case=INC-2')
    assert ok['status'] == 'success'
    # deny reviewer escalation in Review
    policy = await interp.execute('policy deny role=reviewer action=review.escalate ctx=Review desc=no_escalation')
    assert policy['policy']['rules']
    denied = await interp.execute('do alice :: review.escalate case=INC-2')
    assert denied['status'] == 'policy_denied'
    gov = await interp.execute('show governance')
    assert 'policy' in gov['governance'] or 'role_capabilities' in gov['governance']


async def _capability_case():
    _env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn bob:agent role=agent ctx=Main')
    denied = await interp.execute('do bob :: case.open case=INC-3 severity=low')
    assert denied['status'] == 'policy_denied'
    await interp.execute('cap grant bob dispatch')
    allowed = await interp.execute('do bob :: system.ping')
    assert allowed['status'] == 'success'
    graph = await interp.execute('show graph relation produces')
    assert 'edges' in graph


def test_iteration7_policy_cli():
    asyncio.run(_policy_cli_case())


def test_iteration7_capability_cli():
    asyncio.run(_capability_case())
