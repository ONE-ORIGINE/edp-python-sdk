from edp_sdk.canonical import EnvironmentCanonicalBody
from edp_sdk.operational import SemanticRelationalGraph
from examples.cli import build_ops_runtime


def test_generation2_tensor_projection_and_dataset():
    _env, _gw, runtime = build_ops_runtime()
    body = EnvironmentCanonicalBody.from_environment(runtime.environment)
    tensor = body.tensor_graph_projection()
    dataset = body.causal_dataset_projection()
    assert 'node_matrices' in tensor
    assert 'edge_vectors' in tensor
    assert 'adjacency_operator' in tensor
    assert 'events' in dataset
    assert 'reactions' in dataset


def test_generation2_graph_operator_shapes():
    _env, _gw, runtime = build_ops_runtime()
    env = runtime.environment
    # graph already has context relations; ensure tensor export is structurally valid
    tensor = env.semantic_graph.tensor_projection().to_dict()
    node = next(iter(tensor['node_matrices'].values()))
    assert len(node['matrix']) == 4
    assert all(len(row) == 8 for row in node['matrix'])
    if tensor['edge_vectors']:
        edge = next(iter(tensor['edge_vectors'].values()))
        assert len(edge['sense_vector']) == 8
        assert len(edge['operator_matrix']) == 8
        assert all(len(row) == 8 for row in edge['operator_matrix'])
