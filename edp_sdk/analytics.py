from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


@dataclass
class ImpactRecord:
    correlation_id: str
    action_type: str
    reaction_type: str
    context_name: str
    status: str
    impact_score: float
    chain_depth: int
    causal_delta: Optional[float] = None
    timestamp: float = field(default_factory=time.time)
    components: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "action_type": self.action_type,
            "reaction_type": self.reaction_type,
            "context_name": self.context_name,
            "status": self.status,
            "impact_score": float(self.impact_score),
            "chain_depth": int(self.chain_depth),
            "causal_delta": None if self.causal_delta is None else float(self.causal_delta),
            "timestamp": float(self.timestamp),
            "components": {k: float(v) for k, v in self.components.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImpactRecord":
        return cls(
            correlation_id=str(data.get("correlation_id", "")),
            action_type=str(data.get("action_type", "")),
            reaction_type=str(data.get("reaction_type", "")),
            context_name=str(data.get("context_name", "")),
            status=str(data.get("status", "")),
            impact_score=float(data.get("impact_score", 0.0) or 0.0),
            chain_depth=int(data.get("chain_depth", 0) or 0),
            causal_delta=(None if data.get("causal_delta") is None else float(data.get("causal_delta", 0.0) or 0.0)),
            timestamp=float(data.get("timestamp", time.time()) or time.time()),
            components={str(k): float(v) for k, v in dict(data.get("components", {}) or {}).items()},
        )


@dataclass
class LearningProjection:
    session_vector: List[float]
    action_vectors: Dict[str, List[float]]
    recommendations: List[Dict[str, Any]]
    context_vectors: Dict[str, List[float]]
    causal_surface: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_vector": list(self.session_vector),
            "action_vectors": {k: list(v) for k, v in self.action_vectors.items()},
            "recommendations": [dict(item) for item in self.recommendations],
            "context_vectors": {k: list(v) for k, v in self.context_vectors.items()},
            "causal_surface": [dict(item) for item in self.causal_surface],
        }


class ImpactMatrix:
    def __init__(self) -> None:
        self.records: List[ImpactRecord] = []

    def add(self, record: ImpactRecord) -> None:
        self.records.append(record)

    def extend(self, records: Iterable[ImpactRecord]) -> None:
        for record in records:
            self.add(record)

    def load_records(self, rows: Iterable[Dict[str, Any]]) -> None:
        self.records = [ImpactRecord.from_dict(row) for row in rows]

    def export_records(self) -> List[Dict[str, Any]]:
        return [record.to_dict() for record in self.records]

    def records_for(self, action_type: Optional[str] = None, *, context_name: Optional[str] = None, status: Optional[str] = None) -> List[ImpactRecord]:
        rows = list(self.records)
        if action_type is not None:
            rows = [r for r in rows if r.action_type == action_type]
        if context_name is not None:
            rows = [r for r in rows if r.context_name == context_name]
        if status is not None:
            rows = [r for r in rows if r.status == status]
        return rows

    def mean_impact(self, action_type: str, reaction_type: str = "*", *, context_name: Optional[str] = None) -> float:
        filtered = [r for r in self.records if r.action_type == action_type and (context_name is None or r.context_name == context_name)]
        if reaction_type != "*":
            filtered = [r for r in filtered if r.reaction_type == reaction_type]
        if not filtered:
            return 0.0
        return sum(r.impact_score for r in filtered) / len(filtered)

    def matrix(self) -> Dict[str, Dict[str, float]]:
        buckets: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
        for r in self.records:
            buckets[r.action_type][r.reaction_type].append(r.impact_score)
        return {
            action: {reaction: sum(vals) / len(vals) for reaction, vals in row.items()}
            for action, row in buckets.items()
        }

    def profile_for(self, action_type: str) -> Dict[str, Any]:
        records = [r for r in self.records if r.action_type == action_type]
        if not records:
            return {
                "action_type": action_type,
                "count": 0.0,
                "success_rate": 0.0,
                "mean_impact": 0.0,
                "max_positive": 0.0,
                "min_negative": 0.0,
                "mean_causal_delta": 0.0,
                "contexts": {},
                "reactions": {},
                "component_means": {},
            }
        mean_impact = sum(r.impact_score for r in records) / len(records)
        success = sum(1 for r in records if r.status == "success")
        mean_delta = sum(float(r.causal_delta or 0.0) for r in records) / len(records)
        reactions: Dict[str, List[float]] = defaultdict(list)
        contexts: Dict[str, List[float]] = defaultdict(list)
        components: Dict[str, List[float]] = defaultdict(list)
        for r in records:
            reactions[r.reaction_type].append(r.impact_score)
            contexts[r.context_name].append(r.impact_score)
            for name, value in (r.components or {}).items():
                components[name].append(float(value))
        return {
            "action_type": action_type,
            "count": float(len(records)),
            "success_rate": success / max(1, len(records)),
            "mean_impact": mean_impact,
            "max_positive": max(r.impact_score for r in records),
            "min_negative": min(r.impact_score for r in records),
            "mean_causal_delta": mean_delta,
            "contexts": {k: sum(v) / len(v) for k, v in contexts.items()},
            "reactions": {k: sum(v) / len(v) for k, v in reactions.items()},
            "component_means": {k: sum(v) / len(v) for k, v in components.items()},
        }

    def action_profile(self) -> Dict[str, Dict[str, float]]:
        out: Dict[str, Dict[str, float]] = {}
        for action in sorted({r.action_type for r in self.records}):
            p = self.profile_for(action)
            out[action] = {
                "count": float(p["count"]),
                "success_rate": float(p["success_rate"]),
                "mean_impact": float(p["mean_impact"]),
                "mean_causal_delta": float(p["mean_causal_delta"]),
            }
        return out

    def context_profile(self) -> Dict[str, Dict[str, float]]:
        contexts: Dict[str, List[ImpactRecord]] = defaultdict(list)
        for r in self.records:
            contexts[r.context_name].append(r)
        out: Dict[str, Dict[str, float]] = {}
        for name, records in contexts.items():
            success = sum(1 for r in records if r.status == "success")
            out[name] = {
                "count": float(len(records)),
                "success_rate": success / max(1, len(records)),
                "mean_impact": sum(r.impact_score for r in records) / max(1, len(records)),
                "mean_causal_delta": sum(float(r.causal_delta or 0.0) for r in records) / max(1, len(records)),
            }
        return out

    def action_context_profile(self, action_type: str, context_name: Optional[str] = None) -> Dict[str, Any]:
        records = self.records_for(action_type, context_name=context_name)
        if not records:
            return {
                "action_type": action_type,
                "context_name": context_name,
                "count": 0,
                "success_rate": 0.0,
                "mean_impact": 0.0,
                "mean_causal_delta": 0.0,
                "volatility": 0.0,
                "recency_support": 0.0,
                "reaction_distribution": {},
                "component_means": {},
            }
        impacts = [r.impact_score for r in records]
        mean_impact = sum(impacts) / len(impacts)
        mean_delta = sum(float(r.causal_delta or 0.0) for r in records) / len(records)
        success_rate = sum(1 for r in records if r.status == "success") / max(1, len(records))
        variance = sum((x - mean_impact) ** 2 for x in impacts) / len(impacts)
        latest_ts = max(r.timestamp for r in records)
        earliest_ts = min(r.timestamp for r in records)
        span = max(1.0, latest_ts - earliest_ts)
        recency_support = 0.0
        for r in records:
            freshness = 1.0 - ((latest_ts - r.timestamp) / span)
            recency_support += freshness * ((r.impact_score + 1.0) / 2.0)
        recency_support /= max(1, len(records))
        reactions: Dict[str, float] = defaultdict(float)
        component_means: Dict[str, List[float]] = defaultdict(list)
        for r in records:
            reactions[r.reaction_type] += 1.0
            for name, value in (r.components or {}).items():
                component_means[name].append(float(value))
        return {
            "action_type": action_type,
            "context_name": context_name,
            "count": len(records),
            "success_rate": success_rate,
            "mean_impact": mean_impact,
            "mean_causal_delta": mean_delta,
            "volatility": variance,
            "recency_support": recency_support,
            "reaction_distribution": {k: v / len(records) for k, v in reactions.items()},
            "component_means": {k: sum(v) / len(v) for k, v in component_means.items()},
        }

    def causal_prior(self, action_type: str, context_name: Optional[str] = None) -> Dict[str, float]:
        global_profile = self.profile_for(action_type)
        ctx_profile = self.action_context_profile(action_type, context_name)
        context_weight = min(0.7, ctx_profile.get("count", 0) / 8.0) if context_name else 0.0
        mean_impact = (1.0 - context_weight) * float(global_profile.get("mean_impact", 0.0)) + context_weight * float(ctx_profile.get("mean_impact", 0.0))
        success_rate = (1.0 - context_weight) * float(global_profile.get("success_rate", 0.0)) + context_weight * float(ctx_profile.get("success_rate", 0.0))
        causal_leverage = (1.0 - context_weight) * float(global_profile.get("mean_causal_delta", 0.0)) + context_weight * float(ctx_profile.get("mean_causal_delta", 0.0))
        recency_support = float(ctx_profile.get("recency_support", 0.0)) if context_name else 0.0
        volatility = float(ctx_profile.get("volatility", 0.0)) if context_name else 0.0
        learning_strength = _clamp(0.42 * mean_impact + 0.24 * success_rate + 0.22 * causal_leverage + 0.12 * recency_support, -1.0, 1.0)
        return {
            "mean_impact": mean_impact,
            "success_rate": success_rate,
            "causal_leverage": causal_leverage,
            "recency_support": recency_support,
            "volatility": volatility,
            "learning_strength": learning_strength,
            "context_support": context_weight,
        }

    def context_tension(self, context_name: str) -> float:
        profile = self.context_profile().get(context_name)
        if not profile:
            return 0.0
        negative_pressure = max(0.0, -float(profile.get("mean_impact", 0.0)))
        failure_pressure = 1.0 - float(profile.get("success_rate", 0.0))
        causal_pressure = min(1.0, float(profile.get("mean_causal_delta", 0.0)))
        return _clamp(0.45 * negative_pressure + 0.35 * failure_pressure + 0.20 * causal_pressure, 0.0, 1.0)

    def learning_backend_state(self) -> Dict[str, Any]:
        latest = max((r.timestamp for r in self.records), default=0.0)
        return {
            "record_count": len(self.records),
            "actions": sorted({r.action_type for r in self.records}),
            "contexts": sorted({r.context_name for r in self.records}),
            "latest_timestamp": latest,
        }

    def top_actions(self, n: int = 5) -> List[Tuple[str, float]]:
        profiles = [(action, self.profile_for(action)["mean_impact"]) for action in {r.action_type for r in self.records}]
        return sorted(profiles, key=lambda item: (-item[1], item[0]))[:n]

    def worst_actions(self, n: int = 5) -> List[Tuple[str, float]]:
        profiles = [(action, self.profile_for(action)["mean_impact"]) for action in {r.action_type for r in self.records}]
        return sorted(profiles, key=lambda item: (item[1], item[0]))[:n]

    def to_matrix_export(self) -> Dict[str, Any]:
        matrix = self.matrix()
        rows = sorted(matrix)
        cols = sorted({reaction for row in matrix.values() for reaction in row})
        return {
            "rows": rows,
            "cols": cols,
            "matrix": [[float(matrix.get(action, {}).get(reaction, 0.0)) for reaction in cols] for action in rows],
            "description": "M_I[action][reaction] = mean impact score",
        }

    def session_vector(self) -> List[float]:
        pairs = sorted((r.action_type, r.reaction_type) for r in self.records)
        unique_pairs: List[Tuple[str, str]] = []
        seen = set()
        for pair in pairs:
            if pair not in seen:
                seen.add(pair)
                unique_pairs.append(pair)
        return [self.mean_impact(action, reaction) for action, reaction in unique_pairs]

    def learning_projection(self, *, top_k: int = 5) -> LearningProjection:
        action_vectors: Dict[str, List[float]] = {}
        recommendations: List[Dict[str, Any]] = []
        context_vectors: Dict[str, List[float]] = {}
        causal_surface: List[Dict[str, Any]] = []

        for action in sorted({r.action_type for r in self.records}):
            p = self.profile_for(action)
            prior = self.causal_prior(action)
            contexts = p["contexts"]
            context_spread = len(contexts)
            variance = 0.0
            if contexts:
                vals = list(contexts.values())
                mean = sum(vals) / len(vals)
                variance = sum((v - mean) ** 2 for v in vals) / len(vals)
            stability = 1.0 / (1.0 + variance)
            vector = [
                float(p["mean_impact"]),
                float(p["success_rate"]),
                float(p["mean_causal_delta"]),
                float(context_spread),
                stability,
                float(prior["recency_support"]),
            ]
            action_vectors[action] = vector
            learning_score = 0.34 * vector[0] + 0.20 * vector[1] + 0.18 * vector[2] + 0.10 * min(1.0, context_spread / 3.0) + 0.08 * vector[4] + 0.10 * vector[5]
            recommendations.append({
                "action_type": action,
                "learning_score": learning_score,
                "mean_impact": vector[0],
                "success_rate": vector[1],
                "causal_leverage": vector[2],
                "context_spread": context_spread,
                "stability": vector[4],
                "recency_support": vector[5],
            })

        for ctx, p in self.context_profile().items():
            context_vectors[ctx] = [
                float(p["mean_impact"]),
                float(p["success_rate"]),
                float(p["mean_causal_delta"]),
                float(self.context_tension(ctx)),
            ]

        grouped: Dict[Tuple[str, str, str], List[ImpactRecord]] = defaultdict(list)
        for record in self.records:
            grouped[(record.action_type, record.reaction_type, record.context_name)].append(record)
        for (action, reaction, ctx), records in grouped.items():
            causal_surface.append({
                "action_type": action,
                "reaction_type": reaction,
                "context_name": ctx,
                "weight": sum(r.impact_score for r in records) / len(records),
                "count": len(records),
                "mean_causal_delta": sum(float(r.causal_delta or 0.0) for r in records) / len(records),
                "context_tension": self.context_tension(ctx),
            })

        recommendations = sorted(recommendations, key=lambda item: (-item["learning_score"], item["action_type"]))[:top_k]
        causal_surface = sorted(causal_surface, key=lambda item: (-item["weight"], -item["mean_causal_delta"], item["action_type"]))
        return LearningProjection(
            session_vector=self.session_vector(),
            action_vectors=action_vectors,
            recommendations=recommendations,
            context_vectors=context_vectors,
            causal_surface=causal_surface,
        )

    def summary(self) -> Dict[str, object]:
        return {
            "records": len(self.records),
            "matrix": self.matrix(),
            "matrix_export": self.to_matrix_export(),
            "action_profile": self.action_profile(),
            "context_profile": self.context_profile(),
            "top_actions": self.top_actions(),
            "worst_actions": self.worst_actions(),
            "learning_projection": self.learning_projection().to_dict(),
            "backend_state": self.learning_backend_state(),
        }
