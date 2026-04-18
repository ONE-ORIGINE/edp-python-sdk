from __future__ import annotations

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

from examples.cli import EnvLangInterpreter, build_ops_runtime
from edp_sdk import EnvLangFormalCompiler, FormalPlanStaticAnalyzer, FormalPlanGraphBuilder, formal_plan_reference_report


def test_static_analyzer_detects_undefined_refs_and_duplicate_labels():
    body = 'open: do alice :: case.open case=${var.case_id} severity=high ctx=Main ; open: do bob :: case.assign case=${result.missing.result.case} target=bob ctx=Dispatch'
    program = EnvLangFormalCompiler.build_program('bad_plan', body)
    report = FormalPlanStaticAnalyzer.analyze(program, known_plans={'bad_plan': program})
    codes = {issue.code for issue in report.issues}
    assert 'undefined-variable' in codes
    assert 'undefined-result' in codes
    assert 'duplicate-label' in codes


def test_plan_graph_and_reference_report():
    body = 'let case_id:str = "INC-21" ; open_case: do alice :: case.open case=${var.case_id} severity=high ctx=Main => opened ; if result.open_case.success = true then { assign_case: do bob :: case.assign case=${var.case_id} target=bob ctx=Dispatch }'
    program = EnvLangFormalCompiler.build_program('flow21', body)
    graph = FormalPlanGraphBuilder.build(program)
    refs = formal_plan_reference_report(program)
    assert graph.nodes
    assert 'digraph' in graph.to_dot()
    assert 'case_id' in refs.variables_declared
    assert 'open_case' in refs.labels_declared


def test_cli_plan_graph_and_refs_commands():
    env, gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)

    async def run():
        await interp.execute('spawn alice:agent role=admin ctx=Main')
        await interp.execute('spawn bob:agent role=dispatcher ctx=Dispatch')
        await interp.execute('plan flow21 = let case_id:str = "INC-21" ; open_case: do alice :: case.open case=${var.case_id} severity=high ctx=Main => opened ; if result.open_case.success = true then { assign_case: do bob :: case.assign case=${var.case_id} target=bob ctx=Dispatch }')
        g = await interp.execute('plan graph flow21')
        r = await interp.execute('plan refs flow21')
        return g, r

    graph, refs = asyncio.run(run())
    assert 'graph' in graph and 'dot' in graph
    assert 'references' in refs
    assert 'case_id' in refs['references']['variables_declared']
