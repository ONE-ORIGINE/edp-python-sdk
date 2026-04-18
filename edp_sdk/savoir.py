from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .semantics import SENSE_NULL, SenseVector


class CertaintyLevel(float):
    KNOWN = 1.00
    VERIFIED = 0.95
    PROBABLE = 0.75
    ESTIMATED = 0.50
    UNCERTAIN = 0.25
    UNKNOWN = 0.00


@dataclass
class Observation:
    fact: str
    value: Any
    source: str
    certainty: float
    observed_at: float = field(default_factory=time.time)
    sense: SenseVector = SENSE_NULL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fact": self.fact,
            "value": self.value,
            "source": self.source,
            "certainty": self.certainty,
            "observed_at": self.observed_at,
            "sense": self.sense.to_dict(),
        }


@dataclass
class BeliefAtom:
    state: str
    probability: float


@dataclass
class BeliefTrace:
    variable: str
    before: Dict[str, float]
    after: Dict[str, float]
    observation_weight: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variable": self.variable,
            "before": dict(self.before),
            "after": dict(self.after),
            "observation_weight": self.observation_weight,
            "timestamp": self.timestamp,
        }


@dataclass
class CertaintyRevision:
    fact: str
    previous_certainty: float
    current_certainty: float
    stale_penalty: float
    conflict_penalty: float
    support: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fact": self.fact,
            "previous_certainty": self.previous_certainty,
            "current_certainty": self.current_certainty,
            "stale_penalty": self.stale_penalty,
            "conflict_penalty": self.conflict_penalty,
            "support": self.support,
            "timestamp": self.timestamp,
        }


@dataclass
class FactorVariable:
    name: str
    value: Any


@dataclass
class Factor:
    name: str
    variables: Tuple[str, ...]
    evaluator: Any
    weight: float = 1.0
    kind: str = "generic"

    def residual(self, assignment: Dict[str, Any]) -> float:
        return float(self.evaluator(assignment))

    def energy(self, assignment: Dict[str, Any]) -> float:
        residual = self.residual(assignment)
        return 0.5 * self.weight * residual * residual

    def gradient_hint(self, assignment: Dict[str, Any], eps: float = 1e-3) -> Dict[str, float]:
        grads: Dict[str, float] = {}
        base = self.residual(assignment)
        for variable in self.variables:
            value = assignment.get(variable)
            if not isinstance(value, (int, float)):
                continue
            perturbed = dict(assignment)
            perturbed[variable] = float(value) + eps
            grads[variable] = (self.residual(perturbed) - base) / eps
        return grads


class FactorGraph:
    """Weighted sparse factor graph with simple iterative local relaxation."""

    def __init__(self) -> None:
        self.variables: Dict[str, FactorVariable] = {}
        self.factors: List[Factor] = []

    def set(self, name: str, value: Any) -> None:
        self.variables[name] = FactorVariable(name=name, value=value)

    def get(self, name: str, default: Any = None) -> Any:
        return self.variables.get(name, FactorVariable(name, default)).value

    def add_factor(self, factor: Factor) -> None:
        self.factors.append(factor)

    def assignment(self) -> Dict[str, Any]:
        return {k: v.value for k, v in self.variables.items()}

    def energy(self) -> float:
        assignment = self.assignment()
        return sum(f.energy(assignment) for f in self.factors)

    def local_energies(self) -> Dict[str, float]:
        assignment = self.assignment()
        out: Dict[str, float] = {k: 0.0 for k in self.variables}
        for factor in self.factors:
            e = factor.energy(assignment)
            for variable in factor.variables:
                out[variable] = out.get(variable, 0.0) + e
        return out

    def relax(self, steps: int = 12, lr: float = 0.05) -> Dict[str, Any]:
        assignment = self.assignment()
        for _ in range(steps):
            gradients: Dict[str, float] = {}
            for factor in self.factors:
                hint = factor.gradient_hint(assignment)
                residual = factor.residual(assignment)
                for variable, grad in hint.items():
                    gradients[variable] = gradients.get(variable, 0.0) + factor.weight * residual * grad
            if not gradients:
                break
            max_update = 0.0
            for variable, gradient in gradients.items():
                value = assignment.get(variable)
                if not isinstance(value, (int, float)):
                    continue
                update = lr * gradient
                assignment[variable] = float(value) - update
                max_update = max(max_update, abs(update))
            if max_update < 1e-6:
                break
        for name, value in assignment.items():
            self.set(name, value)
        return assignment

    def summary(self) -> Dict[str, Any]:
        return {
            "variable_count": len(self.variables),
            "factor_count": len(self.factors),
            "energy": self.energy(),
            "local_energies": self.local_energies(),
        }


class BeliefState:
    """Soft twin of SAVOIR inspired by POMDP-style belief updates."""

    def __init__(self) -> None:
        self._beliefs: Dict[str, Dict[str, float]] = {}
        self._traces: List[BeliefTrace] = []

    def seed(self, variable: str, distribution: Dict[str, float]) -> None:
        total = sum(distribution.values()) or 1.0
        self._beliefs[variable] = {k: max(0.0, v) / total for k, v in distribution.items()}

    def update(self, variable: str, transitions: Dict[str, Dict[str, float]], observation: Dict[str, float], observation_weight: float = 0.7) -> Dict[str, float]:
        prior = dict(self._beliefs.get(variable, {}))
        if not prior:
            prior = {state: 1.0 / max(1, len(observation)) for state in observation}
        predicted: Dict[str, float] = {}
        for source_state, prior_prob in prior.items():
            row = transitions.get(source_state, {source_state: 1.0})
            for target_state, t_prob in row.items():
                predicted[target_state] = predicted.get(target_state, 0.0) + prior_prob * t_prob
        posterior: Dict[str, float] = {}
        for state in set(predicted) | set(observation):
            posterior[state] = max(0.0, predicted.get(state, 0.0) * (1.0 - observation_weight) + observation.get(state, 0.0) * observation_weight)
        total = sum(posterior.values()) or 1.0
        posterior = {k: v / total for k, v in posterior.items()}
        self._beliefs[variable] = posterior
        self._traces.append(BeliefTrace(variable=variable, before=prior, after=posterior, observation_weight=observation_weight))
        return posterior

    def distribution(self, variable: str) -> Dict[str, float]:
        return dict(self._beliefs.get(variable, {}))

    def most_likely(self, variable: str) -> Optional[BeliefAtom]:
        dist = self._beliefs.get(variable, {})
        if not dist:
            return None
        state, prob = max(dist.items(), key=lambda kv: kv[1])
        return BeliefAtom(state=state, probability=prob)

    def traces(self, variable: Optional[str] = None) -> List[BeliefTrace]:
        if variable is None:
            return list(self._traces)
        return [trace for trace in self._traces if trace.variable == variable]


class Savoir:
    def __init__(self) -> None:
        self._facts: Dict[str, Observation] = {}
        self._history: List[Observation] = []
        self._certainty_revisions: List[CertaintyRevision] = []
        self.belief = BeliefState()
        self.factor_graph = FactorGraph()

    def observe(self, fact: str, value: Any, source: str, certainty: float, sense: SenseVector = SENSE_NULL) -> Observation:
        certainty = max(0.0, min(1.0, certainty))
        obs = Observation(fact=fact, value=value, source=source, certainty=certainty, sense=sense)
        self._facts[fact] = obs
        self._history.append(obs)
        self.factor_graph.set(fact, value)
        return obs

    def revise_certainty(self, fact: str, support: float, *, alpha: float = 0.7, beta: float = 0.15, gamma: float = 0.3, now: Optional[float] = None, half_life_s: float = 300.0) -> float:
        obs = self._facts.get(fact)
        if obs is None:
            return 0.0
        now = now or time.time()
        age = max(0.0, now - obs.observed_at)
        stale_penalty = min(1.0, age / max(1.0, half_life_s)) * beta
        conflict_penalty = gamma if support < 0.0 else 0.0
        updated = max(0.0, min(1.0, alpha * obs.certainty + max(0.0, support) - stale_penalty - conflict_penalty))
        revision = CertaintyRevision(
            fact=fact,
            previous_certainty=obs.certainty,
            current_certainty=updated,
            stale_penalty=stale_penalty,
            conflict_penalty=conflict_penalty,
            support=support,
        )
        self._certainty_revisions.append(revision)
        self._facts[fact] = Observation(
            fact=obs.fact,
            value=obs.value,
            source=obs.source,
            certainty=updated,
            observed_at=obs.observed_at,
            sense=obs.sense,
        )
        return updated

    def update_belief(self, variable: str, transitions: Dict[str, Dict[str, float]], observation: Dict[str, float], observation_weight: float = 0.7) -> Dict[str, float]:
        return self.belief.update(variable, transitions, observation, observation_weight)

    def value_of(self, fact: str) -> Any:
        obs = self._facts.get(fact)
        return None if obs is None else obs.value

    def certainty_of(self, fact: str) -> float:
        obs = self._facts.get(fact)
        return 0.0 if obs is None else obs.certainty

    def degrade(self, now: Optional[float] = None, half_life_s: float = 300.0) -> None:
        now = now or time.time()
        for fact, obs in list(self._facts.items()):
            age = max(0.0, now - obs.observed_at)
            decay = math.exp(-math.log(2) * age / max(1.0, half_life_s))
            self._facts[fact] = Observation(
                fact=obs.fact,
                value=obs.value,
                source=obs.source,
                certainty=max(0.0, min(1.0, obs.certainty * decay)),
                observed_at=obs.observed_at,
                sense=obs.sense,
            )

    def certainty_matrix(self) -> Dict[str, Tuple[Any, float]]:
        return {fact: (obs.value, obs.certainty) for fact, obs in self._facts.items()}

    def history(self) -> List[Observation]:
        return list(self._history)

    def certainty_revisions(self) -> List[CertaintyRevision]:
        return list(self._certainty_revisions)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "facts": {fact: obs.to_dict() for fact, obs in self._facts.items()},
            "belief": {name: self.belief.distribution(name) for name in self._beliefs_keys()},
            "belief_traces": [trace.to_dict() for trace in self.belief.traces()[-20:]],
            "certainty_revisions": [revision.to_dict() for revision in self._certainty_revisions[-20:]],
            "factor_graph": self.factor_graph.summary(),
        }

    def _beliefs_keys(self) -> Iterable[str]:
        return list(self.belief._beliefs.keys())


__all__ = [
    "CertaintyLevel",
    "Observation",
    "BeliefAtom",
    "BeliefTrace",
    "CertaintyRevision",
    "Factor",
    "FactorGraph",
    "BeliefState",
    "Savoir",
]
