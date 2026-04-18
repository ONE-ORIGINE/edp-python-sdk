from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .pathing import ensure_parent_dir
from .semantics import DIMS, SENSE_NULL, SenseVector

ENVX_VERSION = "1.0"


@dataclass
class VectorStoreBundle:
    items: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {"items": list(self.items)}


@dataclass
class GraphStoreBundle:
    nodes: Dict[str, Any]
    edges: List[Dict[str, Any]]
    relation_counts: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {"nodes": dict(self.nodes), "edges": list(self.edges), "relation_counts": dict(self.relation_counts)}


@dataclass
class TensorStoreBundle:
    node_matrices: Dict[str, Any]
    edge_vectors: Dict[str, Any]
    relation_index: Dict[str, List[str]]
    adjacency_operator: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_matrices": dict(self.node_matrices),
            "edge_vectors": dict(self.edge_vectors),
            "relation_index": {k: list(v) for k, v in self.relation_index.items()},
            "adjacency_operator": dict(self.adjacency_operator),
        }


@dataclass
class SemanticAnnotation:
    anchor_type: str
    anchor_id: str
    sense: SenseVector = SENSE_NULL
    certainty: float = 0.0
    provenance: str = ""
    tags: List[str] = field(default_factory=list)
    note: str = ""
    epistemic_status: str = ""
    source_trust: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anchor_type": self.anchor_type,
            "anchor_id": self.anchor_id,
            "sense": self.sense.to_dict(),
            "certainty": self.certainty,
            "provenance": self.provenance,
            "tags": list(self.tags),
            "note": self.note,
            "epistemic_status": self.epistemic_status,
            "source_trust": self.source_trust,
        }


@dataclass
class EnvironmentCanonicalBody:
    environment_id: str
    name: str
    kind: str
    version: str
    state: Dict[str, List[float]]
    certainty: Dict[str, Any]
    belief: Dict[str, Dict[str, float]]
    contexts: Dict[str, Any]
    graph: Dict[str, Any]
    factors: Dict[str, Any]
    protocol: Dict[str, Any]
    annotations: List[Dict[str, Any]]
    history: Dict[str, Any]
    exports: Dict[str, Any]
    generated_at: float = field(default_factory=time.time)

    @staticmethod
    def _flatten(mapping: Dict[str, List[float]]) -> List[float]:
        flat: List[float] = []
        for key in sorted(mapping):
            flat.extend(float(x) for x in mapping[key])
        return flat

    @staticmethod
    def _vector_bundle(state: Dict[str, List[float]], certainty_rows: Dict[str, List[float]], contexts: Dict[str, Any], annotations: List[Dict[str, Any]]) -> VectorStoreBundle:
        items: List[Dict[str, Any]] = []
        for element_id, row in state.items():
            items.append({"kind": "state", "anchor_id": element_id, "vector": list(row)})
        for fact, row in certainty_rows.items():
            items.append({"kind": "certainty", "anchor_id": fact, "vector": list(row)})
        for name, ctx in contexts.items():
            items.append({"kind": "context", "anchor_id": name, "vector": list(ctx.get("basis", {}).get("values", [0.0] * DIMS))})
        for ann in annotations:
            items.append({"kind": "annotation", "anchor_id": ann.get("anchor_id", ""), "vector": list((ann.get("sense") or {}).get("values", [0.0] * DIMS))})
        return VectorStoreBundle(items=items)

    @staticmethod
    def _graph_bundle(graph_export: Dict[str, Any], relation_counts: Dict[str, int]) -> GraphStoreBundle:
        return GraphStoreBundle(nodes=dict(graph_export.get("nodes", {})), edges=list(graph_export.get("edges", [])), relation_counts=dict(relation_counts))

    @staticmethod
    def _tensor_bundle(tensor_graph: Dict[str, Any]) -> TensorStoreBundle:
        return TensorStoreBundle(
            node_matrices=dict(tensor_graph.get("node_matrices", {})),
            edge_vectors=dict(tensor_graph.get("edge_vectors", {})),
            relation_index={k: list(v) for k, v in tensor_graph.get("relation_index", {}).items()},
            adjacency_operator=dict(tensor_graph.get("adjacency_operator", {})),
        )

    @classmethod
    def from_environment(cls, environment: Any) -> "EnvironmentCanonicalBody":
        env_snapshot = environment.snapshot()
        operational = environment.operational_state().to_dict()
        savoir_snapshot = environment.savoir.snapshot()
        state = {k: list(v) for k, v in operational.get("X_t", {}).items()}
        certainty_rows = {k: list(v) for k, v in operational.get("K_t", {}).items()}
        certainty_facts = savoir_snapshot.get("facts", {})
        contexts = env_snapshot.get("contexts", {})
        graph = operational.get("G_t", {})
        factors = operational.get("F_t", {})
        protocol = operational.get("P_t", {})
        belief = savoir_snapshot.get("belief", {})
        annotations: List[Dict[str, Any]] = []

        for fact, obs in certainty_facts.items():
            annotations.append(
                SemanticAnnotation(
                    anchor_type="fact",
                    anchor_id=fact,
                    sense=SenseVector.from_dict(obs.get("sense", {})),
                    certainty=float(obs.get("certainty", 0.0)),
                    provenance=str(obs.get("source", "")),
                    tags=["savoir", "fact"],
                    note=f"fact:{fact}",
                    epistemic_status=str(obs.get("level", "")),
                    source_trust=float(obs.get("certainty", 0.0)),
                ).to_dict()
            )

        for ctx_name, ctx in contexts.items():
            annotations.append(
                SemanticAnnotation(
                    anchor_type="context",
                    anchor_id=str(ctx.get("context_id", ctx_name)),
                    sense=SenseVector.from_dict(ctx.get("basis", {})),
                    certainty=1.0,
                    provenance="environment",
                    tags=["context", ctx_name],
                    note=f"context:{ctx_name}",
                    epistemic_status="contextual",
                    source_trust=1.0,
                ).to_dict()
            )

        for element_id, snapshot in env_snapshot.get("elements", {}).items():
            annotations.append(
                SemanticAnnotation(
                    anchor_type="element",
                    anchor_id=element_id,
                    sense=SenseVector.from_dict(snapshot.get("basis", {})),
                    certainty=1.0,
                    provenance="environment",
                    tags=["element", snapshot.get("kind", "unknown")],
                    note=f"element:{snapshot.get('name', element_id)}",
                    epistemic_status="structural",
                    source_trust=1.0,
                ).to_dict()
            )

        context_operator = environment.contextualizer.context_matrix_export() if hasattr(environment.contextualizer, "context_matrix_export") else {}
        learning_projection = environment.impact.learning_projection().to_dict() if hasattr(environment.impact, "learning_projection") else {}
        contextual_history = [item.to_dict() for item in getattr(environment.contextualizer, "history", [])[-64:]]
        persistent_backends = environment.native_store_summary() if hasattr(environment, "native_store_summary") else {}

        matrix_export = {
            "state_matrix": state,
            "certainty_matrix": certainty_rows,
            "belief_matrix": {k: dict(v) for k, v in belief.items()},
            "context_matrix": {name: list(ctx.get("basis", {}).get("values", [0.0] * DIMS)) for name, ctx in contexts.items()},
            "context_operator_matrix": context_operator,
        }
        vector_export = {
            "environment_vector": cls._flatten(state) + cls._flatten(certainty_rows),
            "context_vectors": {name: list(ctx.get("basis", {}).get("values", [0.0] * DIMS)) for name, ctx in contexts.items()},
            "belief_vectors": {name: [float(v) for _, v in sorted(dist.items())] for name, dist in belief.items()},
            "learning_session_vector": list(learning_projection.get("session_vector", [])),
        }
        graph_export = {
            "nodes": graph.get("nodes", {}),
            "edges": graph.get("edges", []),
            "relation_counts": environment.semantic_graph.relation_counts(),
        }
        tensor_graph = environment.semantic_graph.tensor_projection(operator_mode="diag").to_dict()
        certainty = {"rows": certainty_rows, "facts": certainty_facts, "revisions": savoir_snapshot.get("certainty_revisions", [])}
        history = {
            "memory_summary": environment.memory.summary(),
            "recent_events": [e.to_dict() for e in environment.memory.events[-20:]],
            "recent_interactions": [i.to_dict() for i in environment.memory.interactions[-20:]],
            "recent_phenomena": [p.to_dict() for p in environment.memory.phenomena[-20:]],
            "contextualizer_history": contextual_history,
        }
        causal_dataset = {
            "events": [e.to_dict() for e in environment.memory.events[-256:]],
            "reactions": [r.to_dict() for r in list(environment.memory.reactions.values())[-256:]],
            "interactions": [i.to_dict() for i in environment.memory.interactions[-128:]],
            "phenomena": [p.to_dict() for p in environment.memory.phenomena[-128:]],
        }
        math_body = {
            "state_order": sorted(state.keys()),
            "context_order": sorted(contexts.keys()),
            "belief_order": sorted(belief.keys()),
            "X_t": state,
            "K_t": certainty_rows,
            "B_t": {k: dict(v) for k, v in belief.items()},
            "C_t": {name: list(ctx.get("basis", {}).get("values", [0.0] * DIMS)) for name, ctx in contexts.items()},
            "G_t": graph_export,
            "F_t": factors,
            "P_t": protocol,
            "A_t": annotations,
            "M_C": context_operator,
            "L_t": {
                "session_vector_dim": len(learning_projection.get("session_vector", [])),
                "action_vector_dim": max((len(v) for v in learning_projection.get("action_vectors", {}).values()), default=0),
                "recommendation_count": len(learning_projection.get("recommendations", [])),
            },
            "tensor_summary": {
                "node_count": len(tensor_graph.get("node_matrices", {})),
                "edge_count": len(tensor_graph.get("edge_vectors", {})),
                "relation_count": len(tensor_graph.get("relation_index", {})),
            },
            "S_t": persistent_backends,
        }
        exports = {
            "vector": vector_export,
            "matrix": matrix_export,
            "graph": graph_export,
            "tensor_graph": tensor_graph,
            "causal_dataset": causal_dataset,
            "contextualizer": {
                "context_operator": context_operator,
                "history": contextual_history,
            },
            "learning": learning_projection,
            "math_body": math_body,
            "store_bundles": {
                "vector_store": cls._vector_bundle(state, certainty_rows, contexts, annotations).to_dict(),
                "graph_store": cls._graph_bundle(graph_export, environment.semantic_graph.relation_counts()).to_dict(),
                "tensor_store": cls._tensor_bundle(tensor_graph).to_dict(),
                "dataset_store": causal_dataset,
                "native_stores": persistent_backends,
            },
            "persistent_backends": persistent_backends,
        }
        return cls(
            environment_id=environment.environment_id,
            name=environment.name,
            kind=environment.kind.value,
            version=ENVX_VERSION,
            state=state,
            certainty=certainty,
            belief={k: dict(v) for k, v in belief.items()},
            contexts=contexts,
            graph=graph_export,
            factors=factors,
            protocol=protocol,
            annotations=annotations,
            history=history,
            exports=exports,
        )

    def vector_projection(self) -> Dict[str, Any]:
        return dict(self.exports.get("vector", {}))

    def matrix_projection(self) -> Dict[str, Any]:
        return dict(self.exports.get("matrix", {}))

    def graph_projection(self) -> Dict[str, Any]:
        return dict(self.exports.get("graph", {}))

    def tensor_graph_projection(self) -> Dict[str, Any]:
        return dict(self.exports.get("tensor_graph", {}))

    def causal_dataset_projection(self) -> Dict[str, Any]:
        return dict(self.exports.get("causal_dataset", {}))

    def contextualizer_projection(self) -> Dict[str, Any]:
        return dict(self.exports.get("contextualizer", {}))

    def learning_projection(self) -> Dict[str, Any]:
        return dict(self.exports.get("learning", {}))

    def store_bundle_projection(self) -> Dict[str, Any]:
        return dict(self.exports.get("store_bundles", {}))

    def annotation_projection(self) -> List[Dict[str, Any]]:
        return list(self.annotations)

    def mathematical_projection(self) -> Dict[str, Any]:
        return dict(self.exports.get("math_body", {}))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "name": self.name,
            "kind": self.kind,
            "version": self.version,
            "state": self.state,
            "certainty": self.certainty,
            "belief": self.belief,
            "contexts": self.contexts,
            "graph": self.graph,
            "factors": self.factors,
            "protocol": self.protocol,
            "annotations": self.annotations,
            "history": self.history,
            "exports": self.exports,
            "generated_at": self.generated_at,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def save(self, path: str) -> str:
        target = ensure_parent_dir(path)
        with target.open("w", encoding="utf-8") as f:
            f.write(self.to_json())
        return str(target)
