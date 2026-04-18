from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .core import CausalMemory, Environment
from .protocol import MultiAgentRuntime
from .operational import SemanticRelationalGraph


@dataclass
class DoctorIssue:
    level: str
    code: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "data": dict(self.data),
        }


@dataclass
class HealthReport:
    environment_id: str
    generated_at: float
    issues: List[DoctorIssue] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "generated_at": self.generated_at,
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
            "metrics": dict(self.metrics),
        }


@dataclass
class OptimizationReport:
    environment_id: str
    optimized_at: float
    memory: Dict[str, Any] = field(default_factory=dict)
    graph: Dict[str, Any] = field(default_factory=dict)
    runtime: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "optimized_at": self.optimized_at,
            "memory": dict(self.memory),
            "graph": dict(self.graph),
            "runtime": dict(self.runtime),
        }


class EnvironmentDoctor:
    @staticmethod
    def inspect(environment: Environment, runtime: Optional[MultiAgentRuntime] = None) -> HealthReport:
        now = time.time()
        issues: List[DoctorIssue] = []
        graph = environment.semantic_graph
        memory = environment.memory

        # Graph issues: orphan edges / duplicate semantic edges.
        seen_edges = set()
        duplicate_edges = 0
        orphan_edges = 0
        for edge in list(graph.edges.values()):
            if edge.source_id not in graph.nodes or edge.target_id not in graph.nodes:
                orphan_edges += 1
                issues.append(DoctorIssue(
                    level="warning",
                    code="graph.orphan_edge",
                    message="semantic graph contains an edge with a missing endpoint",
                    data={"edge_id": edge.edge_id, "source_id": edge.source_id, "target_id": edge.target_id},
                ))
            key = (edge.source_id, edge.target_id, edge.relation, tuple(sorted(edge.payload.items())))
            if key in seen_edges:
                duplicate_edges += 1
            else:
                seen_edges.add(key)
        if duplicate_edges:
            issues.append(DoctorIssue(
                level="info",
                code="graph.duplicate_edges",
                message="semantic graph contains duplicate relation edges that can be compacted",
                data={"count": duplicate_edges},
            ))

        # Memory issues: dangling reactions, duplicate events, index drift.
        duplicate_events = 0
        seen_events = set()
        missing_reactions = 0
        for event in memory.events:
            ekey = (event.reaction_id, event.correlation_id, event.sequence_number, event.actor_id, event.action_type)
            if ekey in seen_events:
                duplicate_events += 1
            else:
                seen_events.add(ekey)
            if event.reaction_id not in memory.reactions:
                missing_reactions += 1
        if duplicate_events:
            issues.append(DoctorIssue(
                level="info",
                code="memory.duplicate_events",
                message="causal memory contains duplicate events that can be compacted",
                data={"count": duplicate_events},
            ))
        if missing_reactions:
            issues.append(DoctorIssue(
                level="warning",
                code="memory.missing_reactions",
                message="causal memory contains events whose reactions are missing",
                data={"count": missing_reactions},
            ))

        # Runtime issues: invalid active contexts, inaccessible interfaces, stale locks.
        runtime_metrics: Dict[str, Any] = {}
        if runtime is not None:
            stale_locks = 0
            if hasattr(runtime, '_leases'):
                stale_locks = len([lease for lease in runtime._leases.values() if getattr(lease, 'expires_at', 0.0) <= now])
            for alias, binding in getattr(runtime, 'bindings', {}).items():
                active_ctx = binding.active_context
                if active_ctx and active_ctx not in environment.contexts:
                    issues.append(DoctorIssue(
                        level="error",
                        code="runtime.invalid_active_context",
                        message="agent is focused on a context that does not exist in the environment",
                        data={"alias": alias, "context": active_ctx},
                    ))
                for iface_name, iface in binding.interfaces.items():
                    ctx = iface.get('context')
                    if ctx and ctx not in binding.accessible_contexts:
                        issues.append(DoctorIssue(
                            level="warning",
                            code="runtime.interface_scope_mismatch",
                            message="interface is bound to a context that is not accessible by the agent binding",
                            data={"alias": alias, "interface": iface_name, "context": ctx},
                        ))
            runtime_metrics = {
                "agents": len(getattr(runtime, 'agents', {})),
                "groups": len(getattr(runtime, 'groups', {})),
                "stale_locks": stale_locks,
                "active_executions": len([e for e in getattr(runtime, '_executions', {}).values() if e.get('state') == 'running']),
            }
            if stale_locks:
                issues.append(DoctorIssue(
                    level="info",
                    code="runtime.stale_locks",
                    message="runtime has expired locks that can be cleaned",
                    data={"count": stale_locks},
                ))

        metrics = {
            "contexts": len(environment.contexts),
            "elements": len(environment.elements),
            "graph_nodes": len(graph.nodes),
            "graph_edges": len(graph.edges),
            "memory_events": len(memory.events),
            "memory_reactions": len(memory.reactions),
            "memory_interactions": len(memory.interactions),
            "memory_phenomena": len(memory.phenomena),
            **runtime_metrics,
        }
        return HealthReport(environment_id=environment.environment_id, generated_at=now, issues=issues, metrics=metrics)


class RuntimeOptimizer:
    @staticmethod
    def optimize(environment: Environment, runtime: Optional[MultiAgentRuntime] = None) -> OptimizationReport:
        now = time.time()
        memory_report = environment.memory.compact()
        graph_report = environment.semantic_graph.compact()
        runtime_report: Dict[str, Any] = {}
        if runtime is not None:
            expired = runtime.cleanup_expired_locks() if hasattr(runtime, 'cleanup_expired_locks') else 0
            pruned = runtime.compact_executions() if hasattr(runtime, 'compact_executions') else 0
            runtime_report = {
                "expired_locks_removed": expired,
                "executions_compacted": pruned,
            }
        return OptimizationReport(environment_id=environment.environment_id, optimized_at=now, memory=memory_report, graph=graph_report, runtime=runtime_report)
