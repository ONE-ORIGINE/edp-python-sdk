
import asyncio

from edp_sdk.envlang import EnvLangFormalCompiler, FormalPlanStaticAnalyzer
from examples.cli import build_ops_runtime


def test_iteration19_static_analyzer_parallel_conflict():
    program = EnvLangFormalCompiler.build_program(
        "p19",
        'parallel{ do alice :: case.open case=INC-19 severity=high ctx=Main | do alice :: case.open case=INC-19 severity=high ctx=Main }'
    )
    report = FormalPlanStaticAnalyzer.analyze(program, known_plans={"p19": program})
    assert report.ok is True
    assert any(issue.code == "parallel-resource-conflict" for issue in report.issues)


def test_iteration19_runtime_locks_and_execution_state():
    _env, _gateway, runtime = build_ops_runtime()
    asyncio.run(runtime.spawn('alice', role='admin', context_name='Main'))
    decision = runtime.acquire_lock('case:INC-19', 'tester', ttl_s=10.0)
    assert decision.granted is True
    denied = runtime.acquire_lock('case:INC-19', 'other', ttl_s=10.0)
    assert denied.granted is False
    runtime.release_lock('case:INC-19', 'tester')
    program = EnvLangFormalCompiler.build_program('flow19', 'do alice :: case.open case=INC-19 severity=high ctx=Main')
    packet = asyncio.run(runtime.execute_formal_plan(program))
    assert packet.success is True
    state = runtime.execution_state().to_dict()
    assert state['runtime_id'].startswith('runtime:')
    assert len(state['executions']) >= 1
