from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .semantics import DIMS, SENSE_NULL, SenseVector


@dataclass
class RelationalNodeMatrix:
    """
    Local node tensor-like representation.
    Rows:
      state      : dynamic numeric state view
      certainty  : certainty view from SAVOIR when available
      quality    : provenance / freshness / validity hints
      semantic   : basis vector of the node
    """
    node_id: str
    kind: str
    labels: List[str]
    state_row: Tuple[float, ...]
    certainty_row: Tuple[float, ...]
    quality_row: Tuple[float, ...]
    semantic_row: Tuple[float, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "labels": list(self.labels),
            "state_row": list(self.state_row),
            "certainty_row": list(self.certainty_row),
            "quality_row": list(self.quality_row),
            "semantic_row": list(self.semantic_row),
        }


@dataclass
class RelationalEdge:
    edge_id: str
    source_id: str
    target_id: str
    relation: str
    sense: SenseVector = SENSE_NULL
    precision: float = 1.0
    freshness: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
            "sense": self.sense.to_dict(),
            "precision": self.precision,
            "freshness": self.freshness,
            "payload": dict(self.payload),
        }


class SemanticRelationalGraph:
    def __init__(self) -> None:
        self.nodes: Dict[str, RelationalNodeMatrix] = {}
        self.edges: Dict[str, RelationalEdge] = {}

    @staticmethod
    def _numeric_projection(data: Dict[str, Any], limit: int = DIMS) -> Tuple[float, ...]:
        values: List[float] = []
        for value in data.values():
            if isinstance(value, bool):
                values.append(1.0 if value else 0.0)
            elif isinstance(value, (int, float)):
                values.append(float(value))
            elif isinstance(value, dict):
                for inner in value.values():
                    if isinstance(inner, bool):
                        values.append(1.0 if inner else 0.0)
                    elif isinstance(inner, (int, float)):
                        values.append(float(inner))
            if len(values) >= limit:
                break
        values = values[:limit]
        values.extend([0.0] * (limit - len(values)))
        return tuple(values)

    def upsert_node(self, node_id: str, kind: str, labels: Sequence[str], basis: SenseVector = SENSE_NULL,
                    dynamic_state: Optional[Dict[str, Any]] = None,
                    certainty: Optional[Dict[str, Tuple[Any, float]]] = None,
                    quality: Optional[Dict[str, Any]] = None) -> None:
        dynamic_state = dynamic_state or {}
        quality = quality or {}
        certainty_values: Dict[str, Any] = {}
        if certainty:
            certainty_values = {k: v[1] if isinstance(v, tuple) and len(v) == 2 else 0.0 for k, v in certainty.items()}
        matrix = RelationalNodeMatrix(
            node_id=node_id,
            kind=kind,
            labels=list(labels),
            state_row=self._numeric_projection(dynamic_state),
            certainty_row=self._numeric_projection(certainty_values),
            quality_row=self._numeric_projection(quality),
            semantic_row=tuple(basis.values),
        )
        self.nodes[node_id] = matrix

    def connect(self, source_id: str, target_id: str, relation: str,
                sense: SenseVector = SENSE_NULL, precision: float = 1.0,
                payload: Optional[Dict[str, Any]] = None) -> str:
        edge = RelationalEdge(
            edge_id=str(uuid.uuid4()),
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            sense=sense,
            precision=max(0.0, min(1.0, precision)),
            payload=dict(payload or {}),
        )
        self.edges[edge.edge_id] = edge
        return edge.edge_id

    def neighbors(self, node_id: str, relation: Optional[str] = None) -> List[RelationalEdge]:
        out = [e for e in self.edges.values() if e.source_id == node_id or e.target_id == node_id]
        if relation is not None:
            out = [e for e in out if e.relation == relation]
        return out


    def query_edges(self, *, relation: Optional[str] = None, source_id: Optional[str] = None,
                    target_id: Optional[str] = None, min_precision: float = 0.0) -> List[Dict[str, Any]]:
        edges = list(self.edges.values())
        if relation is not None:
            edges = [e for e in edges if e.relation == relation]
        if source_id is not None:
            edges = [e for e in edges if e.source_id == source_id]
        if target_id is not None:
            edges = [e for e in edges if e.target_id == target_id]
        edges = [e for e in edges if e.precision >= min_precision]
        return [e.to_dict() for e in edges]

    def adjacency(self) -> Dict[str, List[str]]:
        adj: Dict[str, List[str]] = {nid: [] for nid in self.nodes}
        for edge in self.edges.values():
            adj.setdefault(edge.source_id, []).append(edge.target_id)
        return adj

    def path_exists(self, source_id: str, target_id: str, max_depth: int = 4) -> bool:
        if source_id == target_id:
            return True
        adj = self.adjacency()
        frontier = [(source_id, 0)]
        seen = {source_id}
        while frontier:
            node, depth = frontier.pop(0)
            if depth >= max_depth:
                continue
            for nxt in adj.get(node, []):
                if nxt == target_id:
                    return True
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append((nxt, depth + 1))
        return False

    @staticmethod
    def _diag_operator(values: Sequence[float], precision: float = 1.0) -> List[List[float]]:
        rows: List[List[float]] = []
        for i in range(DIMS):
            row = [0.0] * DIMS
            row[i] = float(values[i]) * float(precision)
            rows.append(row)
        return rows

    @staticmethod
    def _outer_operator(values: Sequence[float], precision: float = 1.0) -> List[List[float]]:
        return [[float(a) * float(b) * float(precision) for b in values] for a in values]

    def node_matrix(self, node_id: str) -> List[List[float]]:
        node = self.nodes[node_id]
        return [
            list(node.state_row),
            list(node.certainty_row),
            list(node.quality_row),
            list(node.semantic_row),
        ]

    def edge_operator(self, edge_id: str, *, mode: str = 'diag') -> List[List[float]]:
        edge = self.edges[edge_id]
        values = list(edge.sense.values)
        if mode == 'outer':
            return self._outer_operator(values, edge.precision)
        return self._diag_operator(values, edge.precision)

    def apply_edge_operator(self, edge_id: str, *, source_row: str = 'semantic', mode: str = 'diag') -> List[float]:
        edge = self.edges[edge_id]
        node = self.nodes.get(edge.source_id)
        if node is None:
            return [0.0] * DIMS
        row_map = {
            'state': node.state_row,
            'certainty': node.certainty_row,
            'quality': node.quality_row,
            'semantic': node.semantic_row,
        }
        row = list(row_map.get(source_row, node.semantic_row))
        operator = self.edge_operator(edge_id, mode=mode)
        out: List[float] = []
        for op_row in operator:
            out.append(sum(float(a) * float(b) for a, b in zip(op_row, row)))
        return out

    def tensor_projection(self, *, operator_mode: str = 'diag') -> SemanticTensorGraphProjection:
        relation_index: Dict[str, List[str]] = {}
        node_views = {
            node_id: TensorNodeView(node_id=node_id, kind=node.kind, labels=list(node.labels), matrix=self.node_matrix(node_id))
            for node_id, node in self.nodes.items()
        }
        edge_views: Dict[str, TensorEdgeView] = {}
        for edge_id, edge in self.edges.items():
            relation_index.setdefault(edge.relation, []).append(edge_id)
            edge_views[edge_id] = TensorEdgeView(
                edge_id=edge.edge_id,
                source_id=edge.source_id,
                target_id=edge.target_id,
                relation=edge.relation,
                sense_vector=list(edge.sense.values),
                operator_matrix=self.edge_operator(edge_id, mode=operator_mode),
                precision=edge.precision,
                freshness=edge.freshness,
                payload=dict(edge.payload),
            )
        adjacency_operator = {
            'node_order': sorted(self.nodes.keys()),
            'edge_order': sorted(self.edges.keys()),
            'relation_counts': self.relation_counts(),
            'operator_mode': operator_mode,
        }
        return SemanticTensorGraphProjection(node_matrices=node_views, edge_vectors=edge_views, relation_index=relation_index, adjacency_operator=adjacency_operator)

    def export(self) -> Dict[str, Any]:
        return {
            "nodes": {node_id: node.to_dict() for node_id, node in self.nodes.items()},
            "edges": [edge.to_dict() for edge in self.edges.values()],
        }

    @classmethod
    def from_export(cls, payload: Dict[str, Any]) -> "SemanticRelationalGraph":
        graph = cls()
        for node_id, node in payload.get("nodes", {}).items():
            graph.nodes[node_id] = RelationalNodeMatrix(
                node_id=node.get("node_id", node_id),
                kind=node.get("kind", "unknown"),
                labels=list(node.get("labels", [])),
                state_row=tuple(node.get("state_row", [0.0] * DIMS)),
                certainty_row=tuple(node.get("certainty_row", [0.0] * DIMS)),
                quality_row=tuple(node.get("quality_row", [0.0] * DIMS)),
                semantic_row=tuple(node.get("semantic_row", [0.0] * DIMS)),
            )
        for edge in payload.get("edges", []):
            graph.edges[edge.get("edge_id", str(uuid.uuid4()))] = RelationalEdge(
                edge_id=edge.get("edge_id", str(uuid.uuid4())),
                source_id=edge.get("source_id", ""),
                target_id=edge.get("target_id", ""),
                relation=edge.get("relation", "related"),
                sense=SenseVector.from_dict(edge.get("sense", {})),
                precision=float(edge.get("precision", 1.0)),
                freshness=float(edge.get("freshness", time.time())),
                payload=dict(edge.get("payload", {})),
            )
        return graph

    def merge_export(self, payload: Dict[str, Any]) -> Dict[str, int]:
        added_nodes = 0
        added_edges = 0
        for node_id, node in payload.get("nodes", {}).items():
            if node_id not in self.nodes:
                self.nodes[node_id] = RelationalNodeMatrix(
                    node_id=node.get("node_id", node_id),
                    kind=node.get("kind", "unknown"),
                    labels=list(node.get("labels", [])),
                    state_row=tuple(node.get("state_row", [0.0] * DIMS)),
                    certainty_row=tuple(node.get("certainty_row", [0.0] * DIMS)),
                    quality_row=tuple(node.get("quality_row", [0.0] * DIMS)),
                    semantic_row=tuple(node.get("semantic_row", [0.0] * DIMS)),
                )
                added_nodes += 1
        known_edges = {(e.source_id, e.target_id, e.relation, tuple(sorted(e.payload.items()))) for e in self.edges.values()}
        for edge in payload.get("edges", []):
            key = (edge.get("source_id", ""), edge.get("target_id", ""), edge.get("relation", "related"), tuple(sorted(dict(edge.get("payload", {})).items())))
            if key in known_edges:
                continue
            edge_id = edge.get("edge_id", str(uuid.uuid4()))
            self.edges[edge_id] = RelationalEdge(
                edge_id=edge_id,
                source_id=edge.get("source_id", ""),
                target_id=edge.get("target_id", ""),
                relation=edge.get("relation", "related"),
                sense=SenseVector.from_dict(edge.get("sense", {})),
                precision=float(edge.get("precision", 1.0)),
                freshness=float(edge.get("freshness", time.time())),
                payload=dict(edge.get("payload", {})),
            )
            known_edges.add(key)
            added_edges += 1
        return {"nodes": added_nodes, "edges": added_edges}

    def relation_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for edge in self.edges.values():
            counts[edge.relation] = counts.get(edge.relation, 0) + 1
        return counts

    def compact(self) -> Dict[str, int]:
        before_edges = len(self.edges)
        before_nodes = len(self.nodes)
        orphan_ids = [eid for eid, edge in self.edges.items() if edge.source_id not in self.nodes or edge.target_id not in self.nodes]
        for eid in orphan_ids:
            self.edges.pop(eid, None)
        unique: Dict[tuple, RelationalEdge] = {}
        for edge in sorted(self.edges.values(), key=lambda e: (e.freshness, e.edge_id), reverse=True):
            key = (edge.source_id, edge.target_id, edge.relation, tuple(sorted(edge.payload.items())))
            current = unique.get(key)
            if current is None or edge.precision >= current.precision:
                unique[key] = edge
        self.edges = {edge.edge_id: edge for edge in unique.values()}
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "orphan_edges_removed": len(orphan_ids),
            "duplicate_edges_removed": max(0, before_edges - len(orphan_ids) - len(self.edges)),
            "nodes_before": before_nodes,
            "edges_before": before_edges,
        }




@dataclass
class TensorNodeView:
    node_id: str
    kind: str
    labels: List[str]
    matrix: List[List[float]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "labels": list(self.labels),
            "matrix": [list(row) for row in self.matrix],
        }


@dataclass
class TensorEdgeView:
    edge_id: str
    source_id: str
    target_id: str
    relation: str
    sense_vector: List[float]
    operator_matrix: List[List[float]]
    precision: float
    freshness: float
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
            "sense_vector": list(self.sense_vector),
            "operator_matrix": [list(row) for row in self.operator_matrix],
            "precision": self.precision,
            "freshness": self.freshness,
            "payload": dict(self.payload),
        }


@dataclass
class SemanticTensorGraphProjection:
    node_matrices: Dict[str, TensorNodeView]
    edge_vectors: Dict[str, TensorEdgeView]
    relation_index: Dict[str, List[str]]
    adjacency_operator: Dict[str, Any]
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_matrices": {k: v.to_dict() for k, v in self.node_matrices.items()},
            "edge_vectors": {k: v.to_dict() for k, v in self.edge_vectors.items()},
            "relation_index": {k: list(v) for k, v in self.relation_index.items()},
            "adjacency_operator": dict(self.adjacency_operator),
            "generated_at": self.generated_at,
        }


@dataclass
class OperationalEnvironmentState:
    """
    Compact version of 𝔈_t = (X_t, K_t, C_t, G_t, F_t, P_t).
    X_t : state matrix per node
    K_t : certainty matrix per node
    C_t : context basis matrix
    G_t : semantic relational graph snapshot
    F_t : factor graph / constraints summary
    P_t : protocol/session summary
    """
    X_t: Dict[str, List[float]]
    K_t: Dict[str, List[float]]
    C_t: Dict[str, List[float]]
    G_t: Dict[str, Any]
    F_t: Dict[str, Any]
    P_t: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "X_t": self.X_t,
            "K_t": self.K_t,
            "C_t": self.C_t,
            "G_t": self.G_t,
            "F_t": self.F_t,
            "P_t": self.P_t,
        }


__all__ = [
    "RelationalNodeMatrix",
    "RelationalEdge",
    "TensorNodeView",
    "TensorEdgeView",
    "SemanticTensorGraphProjection",
    "SemanticRelationalGraph",
    "OperationalEnvironmentState",
]
