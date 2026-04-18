from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

DIMS = 8


class Dim(IntEnum):
    CAUSAL = 0
    TEMPORAL = 1
    SPATIAL = 2
    NORMATIVE = 3
    SOCIAL = 4
    FINANCIAL = 5
    TECHNICAL = 6
    EMERGENT = 7


@dataclass(frozen=True)
class SenseVector:
    dimension: str
    meaning: str
    magnitude: float
    values: Tuple[float, ...]
    vector_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if len(self.values) != DIMS:
            raise ValueError(f"SenseVector must have {DIMS} dimensions")

    @staticmethod
    def zeros(label: str = "null") -> "SenseVector":
        return SenseVector("none", label, 0.0, tuple(0.0 for _ in range(DIMS)))

    @staticmethod
    def axis(dimension: str, meaning: str, axis: Dim, mag: float = 1.0) -> "SenseVector":
        v = [0.0] * DIMS
        v[int(axis)] = mag
        return SenseVector(dimension, meaning, mag, tuple(v))

    @staticmethod
    def combine(dimension: str, meaning: str, parts: Iterable[Tuple["SenseVector", float]]) -> "SenseVector":
        acc = [0.0] * DIMS
        total = 0.0
        for vec, weight in parts:
            total += abs(weight)
            for i, x in enumerate(vec.values):
                acc[i] += x * weight
        if total <= 0:
            return SenseVector.zeros(meaning)
        norm = math.sqrt(sum(x * x for x in acc)) or 1.0
        vals = tuple(x / norm for x in acc)
        return SenseVector(dimension, meaning, norm / total, vals)

    @staticmethod
    def from_dict(payload: Mapping[str, object]) -> "SenseVector":
        if not payload:
            return SENSE_NULL
        values = payload.get("values") or payload.get("v") or [0.0 for _ in range(DIMS)]
        values_t = tuple(float(x) for x in values)
        if len(values_t) != DIMS:
            values_t = tuple(list(values_t)[:DIMS] + [0.0] * max(0, DIMS - len(values_t)))
        return SenseVector(
            str(payload.get("dimension", "none")),
            str(payload.get("meaning", "")),
            float(payload.get("magnitude", 0.0)),
            values_t,
            str(payload.get("id", uuid.uuid4())),
        )

    @classmethod
    def causal(cls, m: str, g: float = 1.0) -> "SenseVector":
        return cls.axis("causal", m, Dim.CAUSAL, g)

    @classmethod
    def temporal(cls, m: str, g: float = 1.0) -> "SenseVector":
        return cls.axis("temporal", m, Dim.TEMPORAL, g)

    @classmethod
    def spatial(cls, m: str, g: float = 1.0) -> "SenseVector":
        return cls.axis("spatial", m, Dim.SPATIAL, g)

    @classmethod
    def normative(cls, m: str, g: float = 1.0) -> "SenseVector":
        return cls.axis("normative", m, Dim.NORMATIVE, g)

    @classmethod
    def social(cls, m: str, g: float = 1.0) -> "SenseVector":
        return cls.axis("social", m, Dim.SOCIAL, g)

    @classmethod
    def financial(cls, m: str, g: float = 1.0) -> "SenseVector":
        return cls.axis("financial", m, Dim.FINANCIAL, g)

    @classmethod
    def technical(cls, m: str, g: float = 1.0) -> "SenseVector":
        return cls.axis("technical", m, Dim.TECHNICAL, g)

    @classmethod
    def emergent(cls, m: str, g: float = 1.0) -> "SenseVector":
        return cls.axis("emergent", m, Dim.EMERGENT, g)

    def dot(self, other: "SenseVector") -> float:
        return sum(a * b for a, b in zip(self.values, other.values))

    def norm(self) -> float:
        return math.sqrt(sum(x * x for x in self.values))

    def cosine(self, other: "SenseVector") -> float:
        na = self.norm()
        nb = other.norm()
        if na <= 0 or nb <= 0:
            return 0.0
        return self.dot(other) / (na * nb)

    def angular_distance(self, other: "SenseVector") -> float:
        return math.acos(max(-1.0, min(1.0, self.cosine(other)))) / math.pi

    def hadamard(self, other: "SenseVector", meaning: Optional[str] = None) -> "SenseVector":
        values = tuple(a * b for a, b in zip(self.values, other.values))
        mag = math.sqrt(sum(x * x for x in values))
        return SenseVector(self.dimension, meaning or f"{self.meaning}⊙{other.meaning}", mag, values)

    def apply_context_operator(self, context_basis: "SenseVector", alpha: float = 0.65) -> "SenseVector":
        had = self.hadamard(context_basis, meaning=f"{self.meaning}@{context_basis.meaning}")
        values = tuple(alpha * a + (1 - alpha) * h for a, h in zip(self.values, had.values))
        mag = math.sqrt(sum(x * x for x in values)) or 1.0
        normed = tuple(x / mag for x in values)
        return SenseVector(self.dimension, f"{self.meaning}@{context_basis.meaning}", mag, normed)

    def delta(self, other: "SenseVector") -> "SenseVector":
        values = tuple(b - a for a, b in zip(self.values, other.values))
        mag = math.sqrt(sum(x * x for x in values))
        return SenseVector("delta", f"Δ({self.meaning}->{other.meaning})", mag, values)

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.vector_id,
            "dimension": self.dimension,
            "meaning": self.meaning,
            "magnitude": self.magnitude,
            "values": list(self.values),
        }


SENSE_NULL = SenseVector.zeros()


@dataclass
class HarmonyProfile:
    context_alignment: float
    semantic_alignment: float
    reaction_coherence: float
    dissonance: float
    certainty_bonus: float = 0.0
    impact_bonus: float = 0.0
    score: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "context_alignment": self.context_alignment,
            "semantic_alignment": self.semantic_alignment,
            "reaction_coherence": self.reaction_coherence,
            "dissonance": self.dissonance,
            "certainty_bonus": self.certainty_bonus,
            "impact_bonus": self.impact_bonus,
            "score": self.score,
        }


def compute_harmony(
    action_basis: SenseVector,
    context_basis: SenseVector,
    current_sense: SenseVector,
    predicted_reaction: SenseVector = SENSE_NULL,
    observed_reaction: SenseVector = SENSE_NULL,
    *,
    alpha: float = 0.35,
    beta: float = 0.30,
    gamma: float = 0.20,
    delta: float = 0.15,
    certainty_bonus: float = 0.0,
    impact_bonus: float = 0.0,
) -> HarmonyProfile:
    context_alignment = action_basis.cosine(context_basis)
    semantic_alignment = action_basis.cosine(current_sense)
    reaction_coherence = predicted_reaction.cosine(observed_reaction) if predicted_reaction != SENSE_NULL and observed_reaction != SENSE_NULL else 0.0
    dissonance = action_basis.angular_distance(context_basis.apply_context_operator(current_sense))
    score = (
        alpha * context_alignment
        + beta * semantic_alignment
        + gamma * reaction_coherence
        - delta * dissonance
        + certainty_bonus
        + impact_bonus
    )
    return HarmonyProfile(
        context_alignment=context_alignment,
        semantic_alignment=semantic_alignment,
        reaction_coherence=reaction_coherence,
        dissonance=dissonance,
        certainty_bonus=certainty_bonus,
        impact_bonus=impact_bonus,
        score=score,
    )


def nearest_by_cosine(query: SenseVector, candidates: Sequence[Tuple[str, SenseVector]], top_k: int = 5) -> List[Tuple[str, float]]:
    ranked = sorted(((name, query.cosine(vec)) for name, vec in candidates), key=lambda x: x[1], reverse=True)
    return ranked[:top_k]
