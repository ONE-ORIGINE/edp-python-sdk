from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .canonical import EnvironmentCanonicalBody
from .pathing import ensure_parent_dir, normalize_user_path
from .semantics import SenseVector, nearest_by_cosine


@dataclass
class VectorStoreAdapter:
    items: List[Dict[str, Any]]

    @classmethod
    def from_envx(cls, body: EnvironmentCanonicalBody) -> "VectorStoreAdapter":
        bundle = body.store_bundle_projection().get('vector_store', {})
        return cls(items=list(bundle.get('items', [])))

    @classmethod
    def load(cls, path: str) -> "VectorStoreAdapter":
        return cls(items=list(json.loads(Path(normalize_user_path(path)).read_text(encoding='utf-8')).get('items', [])))

    def save(self, path: str) -> str:
        target = ensure_parent_dir(path)
        target.write_text(json.dumps({'items': self.items}, ensure_ascii=False, indent=2), encoding='utf-8')
        return str(target)

    def _sense_candidates(self, kind: Optional[str] = None) -> List[tuple[str, SenseVector]]:
        out: List[tuple[str, SenseVector]] = []
        for item in self.items:
            if kind is not None and item.get('kind') != kind:
                continue
            vec = item.get('vector', [])
            try:
                s = SenseVector('bundle', str(item.get('anchor_id', '')), 1.0, tuple(float(x) for x in vec))
            except Exception:
                continue
            out.append((str(item.get('anchor_id', '')), s))
        return out

    def similar(self, query: SenseVector, *, kind: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        candidates = self._sense_candidates(kind=kind)
        ranked = nearest_by_cosine(query, candidates, top_k=top_k)
        index = {str(item.get('anchor_id', '')): item for item in self.items}
        return [
            {'anchor_id': name, 'score': score, 'item': index.get(name, {})}
            for name, score in ranked
        ]

    def similar_to_anchor(self, anchor_id: str, *, kind: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        anchor = next((x for x in self.items if str(x.get('anchor_id', '')) == anchor_id), None)
        if not anchor:
            return []
        vec = anchor.get('vector', [])
        query = SenseVector('bundle', anchor_id, 1.0, tuple(float(x) for x in vec))
        results = self.similar(query, kind=kind, top_k=max(top_k + 1, top_k))
        return [r for r in results if r['anchor_id'] != anchor_id][:top_k]


@dataclass
class GraphStoreAdapter:
    nodes: Dict[str, Any]
    edges: List[Dict[str, Any]]

    @classmethod
    def from_envx(cls, body: EnvironmentCanonicalBody) -> "GraphStoreAdapter":
        bundle = body.store_bundle_projection().get('graph_store', {})
        return cls(nodes=dict(bundle.get('nodes', {})), edges=list(bundle.get('edges', [])))

    @classmethod
    def load(cls, path: str) -> "GraphStoreAdapter":
        data = json.loads(Path(normalize_user_path(path)).read_text(encoding='utf-8'))
        return cls(nodes=dict(data.get('nodes', {})), edges=list(data.get('edges', [])))

    def save(self, path: str) -> str:
        target = ensure_parent_dir(path)
        target.write_text(json.dumps({'nodes': self.nodes, 'edges': self.edges}, ensure_ascii=False, indent=2), encoding='utf-8')
        return str(target)

    def neighbors(self, node_id: str, *, relation: Optional[str] = None) -> List[Dict[str, Any]]:
        out = [e for e in self.edges if e.get('source_id') == node_id or e.get('target_id') == node_id]
        if relation is not None:
            out = [e for e in out if e.get('relation') == relation]
        return out

    def relations(self, relation: str) -> List[Dict[str, Any]]:
        return [e for e in self.edges if e.get('relation') == relation]

    def path(self, source_id: str, target_id: str, max_depth: int = 4) -> List[str]:
        if source_id == target_id:
            return [source_id]
        adj: Dict[str, List[str]] = {}
        for edge in self.edges:
            adj.setdefault(str(edge.get('source_id', '')), []).append(str(edge.get('target_id', '')))
        frontier: List[List[str]] = [[source_id]]
        seen = {source_id}
        while frontier:
            path = frontier.pop(0)
            node = path[-1]
            if len(path) - 1 >= max_depth:
                continue
            for nxt in adj.get(node, []):
                if nxt == target_id:
                    return path + [nxt]
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append(path + [nxt])
        return []


@dataclass
class TensorStoreAdapter:
    node_matrices: Dict[str, Any]
    edge_vectors: Dict[str, Any]

    @classmethod
    def from_envx(cls, body: EnvironmentCanonicalBody) -> "TensorStoreAdapter":
        bundle = body.store_bundle_projection().get('tensor_store', {})
        return cls(node_matrices=dict(bundle.get('node_matrices', {})), edge_vectors=dict(bundle.get('edge_vectors', {})))

    @classmethod
    def load(cls, path: str) -> "TensorStoreAdapter":
        data = json.loads(Path(normalize_user_path(path)).read_text(encoding='utf-8'))
        return cls(node_matrices=dict(data.get('node_matrices', {})), edge_vectors=dict(data.get('edge_vectors', {})))

    def save(self, path: str) -> str:
        target = ensure_parent_dir(path)
        target.write_text(json.dumps({'node_matrices': self.node_matrices, 'edge_vectors': self.edge_vectors}, ensure_ascii=False, indent=2), encoding='utf-8')
        return str(target)

    def inspect_node(self, node_id: str) -> Dict[str, Any]:
        return dict(self.node_matrices.get(node_id, {}))

    def inspect_edge(self, edge_id: str) -> Dict[str, Any]:
        return dict(self.edge_vectors.get(edge_id, {}))

    def apply_edge_operator(self, edge_id: str, vector: Sequence[float]) -> List[float]:
        edge = self.edge_vectors.get(edge_id, {})
        operator = edge.get('operator_matrix', []) or []
        if not operator:
            return []
        out: List[float] = []
        vec = [float(x) for x in vector]
        for row in operator:
            out.append(sum(float(a) * float(b) for a, b in zip(row, vec)))
        return out

    def edge_affinity(self, edge_a: str, edge_b: str) -> float:
        va = self.edge_vectors.get(edge_a, {}).get('sense_vector', []) or []
        vb = self.edge_vectors.get(edge_b, {}).get('sense_vector', []) or []
        if not va or not vb:
            return 0.0
        sa = SenseVector('edge', edge_a, 1.0, tuple(float(x) for x in va))
        sb = SenseVector('edge', edge_b, 1.0, tuple(float(x) for x in vb))
        return sa.cosine(sb)

    def compose_operators(self, edge_ids: Sequence[str]) -> List[List[float]]:
        matrices: List[List[List[float]]] = []
        for edge_id in edge_ids:
            op = self.edge_vectors.get(edge_id, {}).get('operator_matrix', []) or []
            if op:
                matrices.append([[float(x) for x in row] for row in op])
        if not matrices:
            return []
        cur = matrices[0]
        for nxt in matrices[1:]:
            rows, shared, cols = len(cur), len(cur[0]) if cur else 0, len(nxt[0]) if nxt else 0
            if not cur or not nxt or shared != len(nxt):
                return []
            prod = [[0.0 for _ in range(cols)] for _ in range(rows)]
            for i in range(rows):
                for j in range(cols):
                    prod[i][j] = sum(cur[i][k] * nxt[k][j] for k in range(shared))
            cur = prod
        return cur


@dataclass
class DatasetStoreAdapter:
    payload: Dict[str, Any]

    @classmethod
    def from_envx(cls, body: EnvironmentCanonicalBody) -> "DatasetStoreAdapter":
        bundle = body.store_bundle_projection().get('dataset_store', {})
        return cls(payload=dict(bundle))

    @classmethod
    def load(cls, path: str) -> "DatasetStoreAdapter":
        return cls(payload=dict(json.loads(Path(normalize_user_path(path)).read_text(encoding='utf-8'))))

    def save(self, path: str) -> str:
        target = ensure_parent_dir(path)
        target.write_text(json.dumps(self.payload, ensure_ascii=False, indent=2), encoding='utf-8')
        return str(target)

    def by_correlation(self, correlation_id: str) -> Dict[str, Any]:
        events = [e for e in self.payload.get('events', []) if e.get('correlation_id') == correlation_id]
        reactions = [r for r in self.payload.get('reactions', []) if r.get('correlation_id') == correlation_id]
        interactions = [i for i in self.payload.get('interactions', []) if i.get('correlation_id') == correlation_id]
        return {'events': events, 'reactions': reactions, 'interactions': interactions}

    def by_action(self, action_type: str) -> Dict[str, Any]:
        events = [e for e in self.payload.get('events', []) if e.get('action_type') == action_type]
        reactions = [r for r in self.payload.get('reactions', []) if r.get('source_action_type') == action_type or r.get('action_type') == action_type]
        return {'events': events, 'reactions': reactions}

    def by_phenomenon(self, category: str) -> Dict[str, Any]:
        phenomena = [p for p in self.payload.get('phenomena', []) if p.get('category') == category]
        return {'phenomena': phenomena}


@dataclass
class StoreProjectionSuite:
    vector: VectorStoreAdapter
    graph: GraphStoreAdapter
    tensor: TensorStoreAdapter
    dataset: DatasetStoreAdapter

    @classmethod
    def from_envx(cls, body: EnvironmentCanonicalBody) -> "StoreProjectionSuite":
        return cls(
            vector=VectorStoreAdapter.from_envx(body),
            graph=GraphStoreAdapter.from_envx(body),
            tensor=TensorStoreAdapter.from_envx(body),
            dataset=DatasetStoreAdapter.from_envx(body),
        )

    @classmethod
    def from_directory(cls, directory: str) -> "StoreProjectionSuite":
        base = Path(normalize_user_path(directory))
        return cls(
            vector=VectorStoreAdapter.load(str(base / 'vector_store.json')),
            graph=GraphStoreAdapter.load(str(base / 'graph_store.json')),
            tensor=TensorStoreAdapter.load(str(base / 'tensor_store.json')),
            dataset=DatasetStoreAdapter.load(str(base / 'dataset_store.json')),
        )

    def save(self, directory: str) -> Dict[str, str]:
        base = ensure_parent_dir(Path(directory) / 'dummy.txt').parent
        base.mkdir(parents=True, exist_ok=True)
        return {
            'vector_store': self.vector.save(str(base / 'vector_store.json')),
            'graph_store': self.graph.save(str(base / 'graph_store.json')),
            'tensor_store': self.tensor.save(str(base / 'tensor_store.json')),
            'dataset_store': self.dataset.save(str(base / 'dataset_store.json')),
        }
