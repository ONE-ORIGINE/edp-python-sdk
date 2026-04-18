from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from .semantics import DIMS, SENSE_NULL, SenseVector

_CONTEXT_DIM_NAMES = [
    "causal",
    "temporal",
    "spatial",
    "normative",
    "social",
    "financial",
    "technical",
    "emergent",
]


def _kind_value(kind: Any) -> str:
    raw = getattr(kind, "value", kind)
    return str(raw or "semantic").lower()


@dataclass
class DataSignal:
    tag: str
    value: Any
    unit: str = ""
    source: str = "sensor"
    captured_at: float = field(default_factory=time.time)
    signal_type: str = "scalar"

    def numeric(self, default: float = 0.0) -> float:
        try:
            return float(self.value)
        except Exception:
            return default


@dataclass
class ContextualizedDatum:
    signal: DataSignal
    label: str
    relevance: float
    actionable: bool
    sense: SenseVector
    context_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tag": self.signal.tag,
            "value": self.signal.value,
            "label": self.label,
            "relevance": self.relevance,
            "actionable": self.actionable,
            "sense": self.sense.to_dict(),
            "context": self.context_name,
            "metadata": dict(self.metadata),
        }


@dataclass
class SignalProfile:
    signal_tag: str
    base_sense: SenseVector
    min_val: float = 0.0
    max_val: float = 1.0
    thresholds: Dict[str, float] = field(default_factory=dict)

    def normalize(self, value: float) -> float:
        rng = self.max_val - self.min_val
        if rng <= 0:
            return 0.0
        return max(0.0, min(1.0, (value - self.min_val) / rng))


@dataclass
class ContextualRule:
    signal_tag: str
    context_kind: Optional[str]
    sense_fn: Callable[[DataSignal, Any], SenseVector]
    relevance_fn: Callable[[DataSignal, Any], float]
    label_fn: Callable[[DataSignal, Any], str]
    actionable_fn: Callable[[DataSignal, Any, float], bool]
    priority: int = 0

    def matches(self, signal_tag: str, context_kind: str) -> bool:
        tag_ok = self.signal_tag in {signal_tag, "*"}
        if self.context_kind is None:
            kind_ok = True
        else:
            kind_ok = _kind_value(self.context_kind) == _kind_value(context_kind)
        return tag_ok and kind_ok


class ContextMatrix:
    """M_C ∈ ℝ^(C×D) — weights semantic dimensions per context kind."""

    DEFAULT: Dict[str, Sequence[float]] = {
        "global": [0.55, 0.55, 0.55, 0.55, 0.55, 0.45, 0.55, 0.55],
        "semantic": [0.60, 0.45, 0.30, 0.85, 0.70, 0.35, 0.60, 0.65],
        "execution": [0.75, 0.65, 0.35, 0.55, 0.45, 0.50, 0.95, 0.35],
        "navigation": [0.45, 0.55, 0.90, 0.35, 0.35, 0.25, 0.55, 0.45],
        "emergency": [1.00, 0.95, 0.40, 0.75, 0.55, 0.20, 0.90, 0.95],
        "observation": [0.55, 0.40, 0.60, 0.45, 0.50, 0.25, 0.85, 0.90],
        "swarm": [0.80, 0.65, 0.65, 0.45, 0.95, 0.20, 0.75, 0.85],
        "causal": [1.00, 0.65, 0.40, 0.45, 0.40, 0.25, 0.55, 0.80],
        "relational": [0.45, 0.45, 0.35, 0.45, 0.95, 0.20, 0.45, 0.50],
        "transactional": [0.50, 0.55, 0.20, 0.55, 0.40, 0.95, 0.55, 0.35],
    }

    def __init__(self, custom: Optional[Dict[str, Sequence[float]]] = None) -> None:
        self._matrix: Dict[str, List[float]] = {k: list(v) for k, v in self.DEFAULT.items()}
        if custom:
            for kind, values in custom.items():
                vals = [float(x) for x in values]
                if len(vals) != DIMS:
                    vals = vals[:DIMS] + [1.0] * max(0, DIMS - len(vals))
                self._matrix[_kind_value(kind)] = vals

    def weights(self, kind: Any) -> List[float]:
        key = _kind_value(kind)
        return list(self._matrix.get(key, self._matrix["global"]))

    def apply(self, sense: SenseVector, kind: Any) -> SenseVector:
        weights = self.weights(kind)
        weighted = [v * w for v, w in zip(sense.values, weights)]
        mag = math.sqrt(sum(x * x for x in weighted))
        if mag <= 0:
            return SenseVector(sense.dimension, f"{sense.meaning}@{_kind_value(kind)}", 0.0, tuple(0.0 for _ in range(DIMS)))
        normed = tuple(x / mag for x in weighted)
        return SenseVector(sense.dimension, f"{sense.meaning}@{_kind_value(kind)}", mag, normed)

    def to_matrix(self) -> List[List[float]]:
        return [self.weights(name) for name in sorted(self._matrix)]

    def export(self) -> Dict[str, Any]:
        return {
            "matrix": self.to_matrix(),
            "rows": sorted(self._matrix),
            "cols": list(_CONTEXT_DIM_NAMES),
            "description": "M_C[context_kind][semantic_dim] = contextual dimension weight",
        }


class Contextualizer:
    def __init__(self, context_matrix: Optional[ContextMatrix] = None) -> None:
        self._profiles: Dict[str, SignalProfile] = {}
        self._rules: List[ContextualRule] = []
        self._matrix = context_matrix or ContextMatrix()
        self._history: List[ContextualizedDatum] = []

    def register_profile(self, profile: SignalProfile) -> None:
        self._profiles[profile.signal_tag] = profile

    def add_profile(self, profile: SignalProfile) -> "Contextualizer":
        self.register_profile(profile)
        return self

    def register_rule(self, rule: ContextualRule) -> None:
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def add_rule(self, rule: ContextualRule) -> "Contextualizer":
        self.register_rule(rule)
        return self

    @property
    def history(self) -> List[ContextualizedDatum]:
        return list(self._history)

    def context_matrix_export(self) -> Dict[str, Any]:
        return self._matrix.export()

    def _default(self, signal: DataSignal, context: Any) -> tuple[SenseVector, float, str, bool]:
        profile = self._profiles.get(signal.tag)
        numeric = signal.numeric()
        if profile:
            relevance = profile.normalize(numeric)
            base_sense = profile.base_sense
            label = f"{signal.tag} observed"
        else:
            relevance = max(0.0, min(1.0, abs(numeric) / 100.0)) if isinstance(numeric, float) else 0.0
            base_sense = SenseVector.technical(signal.tag, max(0.1, relevance)) if numeric or signal.value else SENSE_NULL
            label = signal.tag
        return base_sense, relevance, label, relevance >= 0.6

    def contextualize(self, signal: DataSignal, context: Any) -> ContextualizedDatum:
        context_kind = _kind_value(getattr(context, "kind", "semantic"))
        chosen_rule: Optional[ContextualRule] = None
        for rule in self._rules:
            if rule.matches(signal.tag, context_kind):
                chosen_rule = rule
                break

        if chosen_rule is not None:
            base_sense = chosen_rule.sense_fn(signal, context)
            base_relevance = max(0.0, min(1.0, chosen_rule.relevance_fn(signal, context)))
            label = chosen_rule.label_fn(signal, context)
            actionable = chosen_rule.actionable_fn(signal, context, base_relevance)
        else:
            base_sense, base_relevance, label, actionable = self._default(signal, context)

        weighted_sense = self._matrix.apply(base_sense, context_kind)
        context_basis = getattr(context, "basis", SENSE_NULL)
        context_alignment = weighted_sense.cosine(context_basis) if context_basis != SENSE_NULL else 0.0
        boosted_relevance = max(0.0, min(1.0, 0.72 * base_relevance + 0.28 * max(0.0, context_alignment)))
        actionable = bool(actionable or boosted_relevance >= 0.6)
        datum = ContextualizedDatum(
            signal=signal,
            label=label,
            relevance=boosted_relevance,
            actionable=actionable,
            sense=weighted_sense,
            context_name=getattr(context, "name", "unknown"),
            metadata={
                "context_kind": context_kind,
                "base_relevance": base_relevance,
                "context_alignment": context_alignment,
                "weights": self._matrix.weights(context_kind),
                "base_sense": base_sense.to_dict(),
                "weighted_sense": weighted_sense.to_dict(),
                "rule": chosen_rule.signal_tag if chosen_rule else "default",
            },
        )
        self._history.append(datum)
        return datum

    def contextualize_batch(self, signals: Iterable[DataSignal], context: Any) -> List[ContextualizedDatum]:
        return [self.contextualize(signal, context) for signal in signals]

    def process_batch(self, signals: Iterable[DataSignal], context: Any) -> List[ContextualizedDatum]:
        return self.contextualize_batch(signals, context)

    def actionable_signals(self, context: Any, signals: Iterable[DataSignal]) -> List[ContextualizedDatum]:
        return [datum for datum in self.contextualize_batch(signals, context) if datum.actionable]

    def explain(self, signal: DataSignal, context: Any) -> Dict[str, Any]:
        datum = self.contextualize(signal, context)
        return {
            "signal": {
                "tag": signal.tag,
                "value": signal.value,
                "unit": signal.unit,
                "source": signal.source,
            },
            "context": {
                "name": getattr(context, "name", "unknown"),
                "kind": _kind_value(getattr(context, "kind", "semantic")),
            },
            "result": datum.to_dict(),
            "context_matrix": self.context_matrix_export(),
        }


__all__ = [
    "DataSignal",
    "ContextualizedDatum",
    "SignalProfile",
    "ContextualRule",
    "ContextMatrix",
    "Contextualizer",
]
