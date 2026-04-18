import asyncio
from pathlib import Path

from examples.cli import build_ops_runtime, EnvLangInterpreter
from edp_sdk import EnvironmentCanonicalBody, StoreProjectionSuite
from mep_llm.runtime import AgentDecisionEngine
from mep_tools.llm_runtime import AgentDecisionEngine as CompatAgentDecisionEngine


def test_generation2_iteration7_store_export_and_llm_separation(tmp_path: Path):
    _env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    body = EnvironmentCanonicalBody.from_environment(interp.environment)
    suite = StoreProjectionSuite.from_envx(body)
    exported = suite.save(str(tmp_path / 'stores'))
    assert Path(exported['vector_store']).exists()
    loaded = StoreProjectionSuite.from_directory(str(tmp_path / 'stores'))
    assert loaded.vector.items
    assert AgentDecisionEngine is CompatAgentDecisionEngine


async def _cli_store_iteration7_case(tmp_path: Path):
    _env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    body = EnvironmentCanonicalBody.from_environment(interp.environment)
    suite = StoreProjectionSuite.from_envx(body)
    # get one relation
    relation = suite.graph.edges[0]['relation']
    res_rel = await interp.execute(f'store graph relation {relation}')
    assert 'graph_relation' in res_rel and res_rel['graph_relation']
    # get one or two edges
    edge_ids = list(suite.tensor.edge_vectors.keys())
    assert edge_ids
    res_aff = await interp.execute(f'store tensor affinity {edge_ids[0]} {edge_ids[min(1, len(edge_ids)-1)]}')
    assert 'tensor_affinity' in res_aff
    res_exp = await interp.execute(f'store export {tmp_path / "bundles"}')
    assert 'store_export' in res_exp


def test_generation2_iteration7_cli(tmp_path: Path):
    asyncio.run(_cli_store_iteration7_case(tmp_path))
