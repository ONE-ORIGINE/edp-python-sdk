from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .core import Context, Element, Environment


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


@dataclass
class RankedAction:
    action_type: str
    category: str
    description: str
    total_score: float
    harmony_score: float
    impact_support: float
    certainty_support: float
    belief_support: float
    forecast_support: float
    learned_support: float
    context_affinity: float
    causal_leverage: float
    recency_support: float
    risk_penalty: float
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "category": self.category,
            "description": self.description,
            "total_score": self.total_score,
            "harmony_score": self.harmony_score,
            "impact_support": self.impact_support,
            "certainty_support": self.certainty_support,
            "belief_support": self.belief_support,
            "forecast_support": self.forecast_support,
            "learned_support": self.learned_support,
            "context_affinity": self.context_affinity,
            "causal_leverage": self.causal_leverage,
            "recency_support": self.recency_support,
            "risk_penalty": self.risk_penalty,
            "details": dict(self.details),
        }


class PhenomenonForecaster:
    def __init__(self, environment: Environment) -> None:
        self.environment = environment

    def _chain_by_context(self, context_name: Optional[str]) -> List[str]:
        phenomena = self.environment.memory.phenomena
        if context_name is not None:
            phenomena = [p for p in phenomena if p.context_name == context_name]
        return [p.category for p in phenomena][-100:]

    def forecast(self, context_name: Optional[str] = None, horizon: int = 3) -> List[Dict[str, Any]]:
        seq = self._chain_by_context(context_name)
        if not seq:
            return []
        weighted_counts: Dict[str, float] = {}
        transitions: Dict[Tuple[str, str], float] = {}
        for i, category in enumerate(seq, start=1):
            weighted_counts[category] = weighted_counts.get(category, 0.0) + (0.5 + i / max(1, len(seq)))
            if i < len(seq):
                nxt = seq[i]
                transitions[(category, nxt)] = transitions.get((category, nxt), 0.0) + 1.0
        last = seq[-1]
        markov_boost: Dict[str, float] = {}
        denom = sum(v for (src, _), v in transitions.items() if src == last)
        if denom > 0:
            for (src, dst), v in transitions.items():
                if src == last:
                    markov_boost[dst] = v / denom
        total = sum(weighted_counts.values()) or 1.0
        out: List[Dict[str, Any]] = []
        for category, weight in weighted_counts.items():
            base = weight / total
            score = 0.7 * base + 0.3 * markov_boost.get(category, 0.0)
            out.append({
                "category": category,
                "score": score,
                "horizon": horizon,
                "sample_count": seq.count(category),
                "markov_support": markov_boost.get(category, 0.0),
            })
        out.sort(key=lambda item: item["score"], reverse=True)
        return out[:horizon]


class CausalActionLearner:
    def __init__(self, environment: Environment) -> None:
        self.environment = environment

    def action_stats(self, context_name: Optional[str] = None) -> Dict[str, Dict[str, float]]:
        stats: Dict[str, Dict[str, float]] = {}
        profile = self.environment.impact.action_profile()
        for action_type, p in profile.items():
            timeline = self.environment.memory.action_timeline(action_type)
            if context_name is not None:
                timeline = [e for e in timeline if e.context_name == context_name]
            if not timeline:
                continue
            mean_depth = sum(e.chain_depth for e in timeline) / max(1, len(timeline))
            success = sum(1 for e in timeline if self.environment.memory.reactions.get(e.reaction_id) and self.environment.memory.reactions[e.reaction_id].status.value == "success")
            prior = self.environment.impact.causal_prior(action_type, context_name)
            support = 0.38 * float(prior.get("learning_strength", 0.0)) + 0.22 * float(prior.get("success_rate", 0.0)) + 0.20 * float(prior.get("mean_impact", 0.0)) + 0.20 * float(prior.get("causal_leverage", 0.0))
            stats[action_type] = {
                "count": float(len(timeline)),
                "success_rate": success / max(1, len(timeline)),
                "mean_depth": mean_depth,
                "learned_support": support,
                "recency_support": float(prior.get("recency_support", 0.0)),
                "volatility": float(prior.get("volatility", 0.0)),
            }
        return stats

    def recommend_bonus(self, action_type: str, context_name: Optional[str] = None) -> float:
        stats = self.action_stats(context_name)
        item = stats.get(action_type)
        if not item:
            return 0.0
        volume_bonus = min(0.15, item["count"] / 100.0)
        depth_penalty = min(0.1, item["mean_depth"] / 20.0)
        volatility_penalty = min(0.12, float(item.get("volatility", 0.0)))
        return max(-1.0, min(1.0, item["learned_support"] + volume_bonus + 0.05 * float(item.get("recency_support", 0.0)) - depth_penalty - volatility_penalty))


class ActionRanker:
    def __init__(self, environment: Environment) -> None:
        self.environment = environment
        self.forecaster = PhenomenonForecaster(environment)
        self.learner = CausalActionLearner(environment)

    def rank(self, actor: Element, context: Context, payload: Optional[Dict[str, Any]] = None) -> List[RankedAction]:
        payload = payload or {}
        situation = self.environment.compute_situation(context)
        frame = self.environment._build_frame(actor, context, payload, correlation_id="preview", causation_id=None, chain_depth=0)
        available = context.get_available_actions(actor.snapshot(), frame, current_sense=situation.basis)
        impact_profile = self.environment.impact.action_profile()
        certainty_matrix = self.environment.savoir.certainty_matrix()
        certainty_support = 0.0
        if certainty_matrix:
            certainty_support = sum(cert for _, cert in certainty_matrix.values()) / max(1, len(certainty_matrix))
        outcome_belief = self.environment.savoir.belief.distribution("global.outcome")
        global_belief = outcome_belief.get("success", 0.0)
        forecast_map = {item["category"]: item for item in self.forecaster.forecast(context.name, horizon=6)}
        learned_stats_all = self.learner.action_stats(context.name)
        ranked: List[RankedAction] = []
        for action, harmony in available:
            profile = impact_profile.get(action.type, {})
            prior = self.environment.impact.causal_prior(action.type, context.name)
            impact_support = float(profile.get("mean_impact", 0.0))
            belief_support = global_belief
            learned_support = self.learner.recommend_bonus(action.type, context.name)
            context_affinity = action.basis.cosine(context.basis)
            causal_leverage = float(prior.get("causal_leverage", 0.0))
            recency_support = float(prior.get("recency_support", 0.0))
            risk_penalty = self.environment.impact.context_tension(context.name)
            forecast_support = 0.0
            if any(key in action.type for key in ("return_home", "land", "stabilize", "recover", "mitigate", "escalate", "resolve")):
                forecast_support = max((item["score"] for cat, item in forecast_map.items() if any(tok in cat for tok in ("chain", "escalation", "feedback", "drift", "broadcast"))), default=0.0)
            elif forecast_map:
                forecast_support = 0.15 * max(item["score"] for item in forecast_map.values())
            total_score = (
                0.29 * harmony.score
                + 0.12 * impact_support
                + 0.08 * certainty_support
                + 0.07 * belief_support
                + 0.07 * forecast_support
                + 0.14 * learned_support
                + 0.10 * context_affinity
                + 0.09 * causal_leverage
                + 0.08 * recency_support
                - 0.04 * risk_penalty
            )
            total_score = _clamp(total_score, -1.0, 1.5)
            causal_score_card = {
                "harmony": harmony.score,
                "impact_support": impact_support,
                "certainty_support": certainty_support,
                "belief_support": belief_support,
                "forecast_support": forecast_support,
                "learned_support": learned_support,
                "context_affinity": context_affinity,
                "causal_leverage": causal_leverage,
                "recency_support": recency_support,
                "risk_penalty": risk_penalty,
                "learning_strength": float(prior.get("learning_strength", 0.0)),
                "context_support": float(prior.get("context_support", 0.0)),
                "total_score": total_score,
            }
            ranked.append(RankedAction(
                action_type=action.type,
                category=action.category.value,
                description=action.description,
                total_score=total_score,
                harmony_score=harmony.score,
                impact_support=impact_support,
                certainty_support=certainty_support,
                belief_support=belief_support,
                forecast_support=forecast_support,
                learned_support=learned_support,
                context_affinity=context_affinity,
                causal_leverage=causal_leverage,
                recency_support=recency_support,
                risk_penalty=risk_penalty,
                details={
                    "harmony": harmony.to_dict(),
                    "situation": situation.to_dict(),
                    "impact_profile": profile,
                    "forecast_map": forecast_map,
                    "learned_stats": learned_stats_all.get(action.type, {}),
                    "causal_prior": prior,
                    "causal_score_card": causal_score_card,
                },
            ))
        ranked.sort(key=lambda item: item.total_score, reverse=True)
        return ranked
