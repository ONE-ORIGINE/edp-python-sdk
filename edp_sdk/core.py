from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .analytics import ImpactMatrix, ImpactRecord
from .contextualizer import ContextualizedDatum, Contextualizer, DataSignal
from .operational import OperationalEnvironmentState, SemanticRelationalGraph
from .semantics import SENSE_NULL, HarmonyProfile, SenseVector, compute_harmony
from .savoir import Savoir


class EnvironmentKind(str, Enum):
    REACTIVE = "reactive"
    DYNAMIC = "dynamic"
    OBSERVATIONAL = "observational"


class ContextKind(str, Enum):
    SEMANTIC = "semantic"
    EXECUTION = "execution"
    NAVIGATION = "navigation"
    EMERGENCY = "emergency"
    OBSERVATION = "observation"
    SWARM = "swarm"


class ActionCategory(str, Enum):
    COMMAND = "command"
    QUERY = "query"
    TRANSITION = "transition"
    SIGNAL = "signal"


class ReactionStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    REJECTED = "rejected"
    ERROR = "error"
    DEFERRED = "deferred"


class ImpactScope(str, Enum):
    ON_ACTOR = "on_actor"
    ON_TARGET = "on_target"
    ON_ENVIRONMENT = "on_environment"
    BROADCAST = "broadcast"


class Temporality(str, Enum):
    IMMEDIATE = "immediate"
    TEMPORARY = "temporary"
    DURABLE = "durable"
    DELAYED = "delayed"


@dataclass
class Circumstance:
    name: str
    description: str
    evaluator: Callable[["Context", Dict[str, Any]], bool]
    role: str = "enabler"

    def holds(self, context: "Context", frame: Dict[str, Any]) -> bool:
        return bool(self.evaluator(context, frame))

    def __and__(self, other: "Circumstance") -> "Circumstance":
        return Circumstance(
            name=f"({self.name}&{other.name})",
            description=f"{self.description} AND {other.description}",
            evaluator=lambda ctx, frame: self.holds(ctx, frame) and other.holds(ctx, frame),
            role=self.role,
        )

    def __or__(self, other: "Circumstance") -> "Circumstance":
        return Circumstance(
            name=f"({self.name}|{other.name})",
            description=f"{self.description} OR {other.description}",
            evaluator=lambda ctx, frame: self.holds(ctx, frame) or other.holds(ctx, frame),
            role=self.role,
        )

    def __invert__(self) -> "Circumstance":
        return Circumstance(
            name=f"¬{self.name}",
            description=f"NOT {self.description}",
            evaluator=lambda ctx, frame: not self.holds(ctx, frame),
            role=self.role,
        )

    @staticmethod
    def always(name: str, description: str = "Always true") -> "Circumstance":
        return Circumstance(name=name, description=description, evaluator=lambda _c, _f: True)

    @staticmethod
    def flag(name: str, description: str, key: str, expected: Any = True) -> "Circumstance":
        return Circumstance(name=name, description=description, evaluator=lambda ctx, frame: ctx.data.get(key) == expected)

    @staticmethod
    def when(name: str, description: str, predicate: Callable[["Context", Dict[str, Any]], bool]) -> "Circumstance":
        return Circumstance(name=name, description=description, evaluator=predicate)


@dataclass
class Situation:
    label: str
    basis: SenseVector
    qualities: Dict[str, Any]
    observed_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "basis": self.basis.to_dict(),
            "qualities": dict(self.qualities),
            "observed_at": self.observed_at,
        }


@dataclass
class Reaction:
    type: str
    status: ReactionStatus
    message: str
    sense: SenseVector = SENSE_NULL
    impact_scope: ImpactScope = ImpactScope.ON_ACTOR
    temporality: Temporality = Temporality.IMMEDIATE
    result: Dict[str, Any] = field(default_factory=dict)
    target_ids: List[str] = field(default_factory=list)
    chain: List[Tuple[str, Dict[str, Any], Optional[str]]] = field(default_factory=list)
    reaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @classmethod
    def ok(cls, type: str, message: str, **kwargs: Any) -> "Reaction":
        return cls(type=type, status=ReactionStatus.SUCCESS, message=message, **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reaction_id": self.reaction_id,
            "type": self.type,
            "status": self.status.value,
            "message": self.message,
            "sense": self.sense.to_dict(),
            "impact_scope": self.impact_scope.value,
            "temporality": self.temporality.value,
            "result": dict(self.result),
            "target_ids": list(self.target_ids),
            "chain": [list(step) for step in self.chain],
        }


@dataclass
class Event:
    event_type: str
    actor_id: str
    context_name: str
    action_type: str
    reaction_id: str
    correlation_id: str
    causation_id: Optional[str]
    chain_depth: int
    sequence_number: int = 0
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)
    target_ids: List[str] = field(default_factory=list)
    situation_before: Dict[str, Any] = field(default_factory=dict)
    situation_after: Dict[str, Any] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "actor_id": self.actor_id,
            "context_name": self.context_name,
            "action_type": self.action_type,
            "reaction_id": self.reaction_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "chain_depth": self.chain_depth,
            "sequence_number": self.sequence_number,
            "timestamp": self.timestamp,
            "payload": dict(self.payload),
            "target_ids": list(self.target_ids),
            "situation_before": dict(self.situation_before),
            "situation_after": dict(self.situation_after),
            "reasons": list(self.reasons),
        }


@dataclass
class ProvenanceTrace:
    correlation_id: str
    events: List[Event]
    reactions: List[Reaction]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "events": [e.to_dict() for e in self.events],
            "reactions": [r.to_dict() for r in self.reactions],
        }


@dataclass
class Interaction:
    category: str
    participants: List[str]
    correlation_id: str
    intensity: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "participants": list(self.participants),
            "correlation_id": self.correlation_id,
            "intensity": self.intensity,
            "timestamp": self.timestamp,
        }


@dataclass
class Phenomenon:
    category: str
    context_name: str
    correlation_id: str
    intensity: float
    summary: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "context_name": self.context_name,
            "correlation_id": self.correlation_id,
            "intensity": self.intensity,
            "summary": self.summary,
            "timestamp": self.timestamp,
        }


@dataclass
class Action:
    type: str
    category: ActionCategory
    description: str
    basis: SenseVector
    handler: Callable[["Element", Dict[str, Any], "Context", Dict[str, Any]], Any]
    circumstances: List[Circumstance] = field(default_factory=list)
    predicted_reaction: SenseVector = SENSE_NULL

    async def execute(self, actor: "Element", payload: Dict[str, Any], context: "Context", frame: Dict[str, Any]) -> Reaction:
        result = self.handler(actor, payload, context, frame)
        if hasattr(result, "__await__"):
            return await result
        return result


class Element:
    def __init__(self, name: str, kind: str, basis: SenseVector = SENSE_NULL, properties: Optional[Dict[str, Any]] = None) -> None:
        self.element_id = str(uuid.uuid4())
        self.name = name
        self.kind = kind
        self.basis = basis
        self.properties: Dict[str, Any] = dict(properties or {})
        self.dynamic: Dict[str, Any] = {}

    def snapshot(self) -> Dict[str, Any]:
        return {
            "element_id": self.element_id,
            "name": self.name,
            "kind": self.kind,
            "basis": self.basis.to_dict(),
            "properties": dict(self.properties),
            "dynamic": dict(self.dynamic),
        }

    async def on_impacted(self, reaction: Reaction, frame: Dict[str, Any]) -> None:
        return None


class Context:
    def __init__(self, environment: "Environment", name: str, kind: ContextKind, basis: SenseVector = SENSE_NULL,
                 circumstances: Optional[List[Circumstance]] = None) -> None:
        self.environment = environment
        self.context_id = str(uuid.uuid4())
        self.name = name
        self.kind = kind
        self.basis = basis
        self.data: Dict[str, Any] = {}
        self._elements: Dict[str, Dict[str, Any]] = {}
        self._actions: Dict[str, Action] = {}
        self._circumstances: List[Circumstance] = list(circumstances or [])

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def include(self, element_snapshot: Dict[str, Any]) -> None:
        self._elements[element_snapshot["element_id"]] = element_snapshot
        self.environment.semantic_graph.connect(
            self.context_id,
            element_snapshot["element_id"],
            relation="contains",
            sense=self.basis,
            precision=1.0,
            payload={"context": self.name},
        )

    def reg(self, action: Action) -> None:
        self._actions[action.type] = action
        self.environment.semantic_graph.connect(
            self.context_id,
            f"action:{action.type}",
            relation="enables",
            sense=action.basis.apply_context_operator(self.basis),
            precision=1.0,
            payload={"action": action.type},
        )

    @property
    def circumstances(self) -> List[Circumstance]:
        return list(self._circumstances)

    def topology(self) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for other_name, other in self.environment.contexts.items():
            if other_name == self.name:
                continue
            out[other_name] = self.basis.angular_distance(other.basis)
        return out

    def get_available_actions(self, actor: Dict[str, Any], frame: Dict[str, Any], current_sense: SenseVector = SENSE_NULL) -> List[Tuple[Action, HarmonyProfile]]:
        ranked: List[Tuple[Action, HarmonyProfile]] = []
        certainty_bonus = float(frame.get("certainty_bonus", 0.0))
        impact_bonus = float(frame.get("impact_bonus", 0.0))
        for action in self._actions.values():
            if all(c.holds(self, frame) for c in action.circumstances):
                h = compute_harmony(
                    action.basis,
                    self.basis,
                    current_sense,
                    predicted_reaction=action.predicted_reaction,
                    observed_reaction=SENSE_NULL,
                    certainty_bonus=certainty_bonus,
                    impact_bonus=impact_bonus,
                )
                ranked.append((action, h))
        ranked.sort(key=lambda item: item[1].score, reverse=True)
        return ranked

    def explain_why_not(self, action_type: str, frame: Dict[str, Any]) -> List[str]:
        action = self._actions.get(action_type)
        if not action:
            return ["unknown action"]
        return [c.name for c in action.circumstances if not c.holds(self, frame)]

    def action_reasons(self, actor: Dict[str, Any], frame: Dict[str, Any], current_sense: SenseVector = SENSE_NULL) -> Dict[str, Dict[str, Any]]:
        reasons: Dict[str, Dict[str, Any]] = {}
        for action, harmony in self.get_available_actions(actor, frame, current_sense):
            reasons[action.type] = {
                "harmony": harmony.to_dict(),
                "description": action.description,
                "category": action.category.value,
            }
        return reasons


class CausalMemory:
    def __init__(self) -> None:
        self.events: List[Event] = []
        self.reactions: Dict[str, Reaction] = {}
        self.interactions: List[Interaction] = []
        self.phenomena: List[Phenomenon] = []
        self._by_correlation: Dict[str, List[Event]] = {}
        self._by_actor: Dict[str, List[Event]] = {}
        self._by_context: Dict[str, List[Event]] = {}
        self._by_action: Dict[str, List[Event]] = {}
        self._by_target: Dict[str, List[Event]] = {}
        self._next_sequence: int = 1

    def record(self, event: Event, reaction: Reaction) -> None:
        if event.sequence_number <= 0:
            event.sequence_number = self._next_sequence
            self._next_sequence += 1
        else:
            self._next_sequence = max(self._next_sequence, event.sequence_number + 1)
        self.events.append(event)
        self.events.sort(key=lambda e: (e.sequence_number, e.timestamp))
        self.reactions[reaction.reaction_id] = reaction
        self._by_correlation.setdefault(event.correlation_id, []).append(event)
        self._by_actor.setdefault(event.actor_id, []).append(event)
        self._by_context.setdefault(event.context_name, []).append(event)
        self._by_action.setdefault(event.action_type, []).append(event)
        for target_id in event.target_ids:
            self._by_target.setdefault(target_id, []).append(event)

    def rebuild_indexes(self) -> Dict[str, int]:
        self._by_correlation = {}
        self._by_actor = {}
        self._by_context = {}
        self._by_action = {}
        self._by_target = {}
        self.events.sort(key=lambda e: (e.sequence_number, e.timestamp))
        max_sequence = 0
        for event in self.events:
            max_sequence = max(max_sequence, event.sequence_number)
            self._by_correlation.setdefault(event.correlation_id, []).append(event)
            self._by_actor.setdefault(event.actor_id, []).append(event)
            self._by_context.setdefault(event.context_name, []).append(event)
            self._by_action.setdefault(event.action_type, []).append(event)
            for target_id in event.target_ids:
                self._by_target.setdefault(target_id, []).append(event)
        self._next_sequence = max_sequence + 1 if self.events else 1
        return {
            "correlations": len(self._by_correlation),
            "actors": len(self._by_actor),
            "contexts": len(self._by_context),
            "actions": len(self._by_action),
            "targets": len(self._by_target),
            "last_sequence": self._next_sequence - 1,
        }

    def compact(self) -> Dict[str, int]:
        before_events = len(self.events)
        before_reactions = len(self.reactions)
        before_interactions = len(self.interactions)
        before_phenomena = len(self.phenomena)

        unique_events = {}
        for event in self.events:
            key = (event.reaction_id, event.correlation_id, event.sequence_number, event.actor_id, event.action_type)
            unique_events[key] = event
        self.events = sorted(unique_events.values(), key=lambda e: (e.sequence_number, e.timestamp))

        referenced_reactions = {event.reaction_id for event in self.events}
        self.reactions = {rid: reaction for rid, reaction in self.reactions.items() if rid in referenced_reactions}

        unique_interactions = {}
        for interaction in self.interactions:
            key = (interaction.category, interaction.correlation_id, tuple(sorted(interaction.participants)))
            unique_interactions[key] = interaction
        self.interactions = list(unique_interactions.values())

        unique_phenomena = {}
        for phenomenon in self.phenomena:
            key = (phenomenon.category, phenomenon.correlation_id, phenomenon.context_name)
            unique_phenomena[key] = phenomenon
        self.phenomena = list(unique_phenomena.values())

        self.rebuild_indexes()
        return {
            "events_removed": before_events - len(self.events),
            "reactions_removed": before_reactions - len(self.reactions),
            "interactions_removed": before_interactions - len(self.interactions),
            "phenomena_removed": before_phenomena - len(self.phenomena),
            "events": len(self.events),
            "reactions": len(self.reactions),
        }

    def merge(self, other: "CausalMemory") -> Dict[str, int]:
        merged_events = 0
        merged_reactions = 0
        known_event_keys = {(e.reaction_id, e.correlation_id, e.sequence_number, e.actor_id, e.action_type) for e in self.events}
        for reaction in other.reactions.values():
            if reaction.reaction_id not in self.reactions:
                self.reactions[reaction.reaction_id] = reaction
                merged_reactions += 1
        for event in other.events:
            key = (event.reaction_id, event.correlation_id, event.sequence_number, event.actor_id, event.action_type)
            if key in known_event_keys:
                continue
            reaction = other.reactions.get(event.reaction_id) or self.reactions.get(event.reaction_id)
            if reaction is None:
                reaction = Reaction(type="unknown", status=ReactionStatus.ERROR, message="missing reaction")
            self.record(event, reaction)
            merged_events += 1
        known_interactions = {(i.category, i.correlation_id, tuple(sorted(i.participants))) for i in self.interactions}
        for interaction in other.interactions:
            key = (interaction.category, interaction.correlation_id, tuple(sorted(interaction.participants)))
            if key not in known_interactions:
                self.interactions.append(interaction)
                known_interactions.add(key)
        known_phenomena = {(p.category, p.correlation_id, p.context_name) for p in self.phenomena}
        for phenomenon in other.phenomena:
            key = (phenomenon.category, phenomenon.correlation_id, phenomenon.context_name)
            if key not in known_phenomena:
                self.phenomena.append(phenomenon)
                known_phenomena.add(key)
        return {"events": merged_events, "reactions": merged_reactions, "interactions": len(self.interactions), "phenomena": len(self.phenomena)}

    def correlation_trace(self, correlation_id: str) -> List[Event]:
        return sorted(self._by_correlation.get(correlation_id, []), key=lambda e: (e.sequence_number, e.timestamp))

    def actor_timeline(self, actor_id: str) -> List[Event]:
        return sorted(self._by_actor.get(actor_id, []), key=lambda e: (e.sequence_number, e.timestamp))

    def context_timeline(self, context_name: str) -> List[Event]:
        return sorted(self._by_context.get(context_name, []), key=lambda e: (e.sequence_number, e.timestamp))

    def action_timeline(self, action_type: str) -> List[Event]:
        return sorted(self._by_action.get(action_type, []), key=lambda e: (e.sequence_number, e.timestamp))

    def target_timeline(self, target_id: str) -> List[Event]:
        return sorted(self._by_target.get(target_id, []), key=lambda e: (e.sequence_number, e.timestamp))

    def provenance(self, correlation_id: str) -> ProvenanceTrace:
        events = self.correlation_trace(correlation_id)
        reactions = [self.reactions[e.reaction_id] for e in events if e.reaction_id in self.reactions]
        return ProvenanceTrace(correlation_id=correlation_id, events=events, reactions=reactions)

    def event_journal(self) -> List[Dict[str, Any]]:
        return [{"sequence_number": e.sequence_number, **e.to_dict(), "reaction": self.reactions.get(e.reaction_id).to_dict() if e.reaction_id in self.reactions else None} for e in self.events]

    def replay(self, correlation_id: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for event in self.correlation_trace(correlation_id):
            reaction = self.reactions.get(event.reaction_id)
            out.append({
                "sequence_number": event.sequence_number,
                "event": event.to_dict(),
                "reaction": None if reaction is None else reaction.to_dict(),
            })
        return out

    def replay_until(self, correlation_id: str, sequence_number: int) -> List[Dict[str, Any]]:
        return [item for item in self.replay(correlation_id) if item["sequence_number"] <= sequence_number]

    def summary(self) -> Dict[str, Any]:
        return {
            "events": len(self.events),
            "reactions": len(self.reactions),
            "interactions": len(self.interactions),
            "phenomena": len(self.phenomena),
            "correlations": len(self._by_correlation),
            "actions": len(self._by_action),
            "targets": len(self._by_target),
            "last_sequence": self._next_sequence - 1,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "events": [event.to_dict() for event in self.events],
            "reactions": [reaction.to_dict() for reaction in self.reactions.values()],
            "interactions": [interaction.to_dict() for interaction in self.interactions],
            "phenomena": [phenomenon.to_dict() for phenomenon in self.phenomena],
            "summary": self.summary(),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CausalMemory":
        memory = cls()
        reaction_map: Dict[str, Reaction] = {}
        for item in payload.get("reactions", []):
            reaction = Reaction(
                type=item["type"],
                status=ReactionStatus(item["status"]),
                message=item["message"],
                sense=SenseVector.from_dict(item.get("sense", {})),
                impact_scope=ImpactScope(item.get("impact_scope", ImpactScope.ON_ACTOR.value)),
                temporality=Temporality(item.get("temporality", Temporality.IMMEDIATE.value)),
                result=dict(item.get("result", {})),
                target_ids=list(item.get("target_ids", [])),
                chain=[tuple(step) for step in item.get("chain", [])],
                reaction_id=item.get("reaction_id") or str(uuid.uuid4()),
            )
            reaction_map[reaction.reaction_id] = reaction
        for item in payload.get("events", []):
            event = Event(
                event_type=item["event_type"],
                actor_id=item["actor_id"],
                context_name=item["context_name"],
                action_type=item["action_type"],
                reaction_id=item["reaction_id"],
                correlation_id=item["correlation_id"],
                causation_id=item.get("causation_id"),
                chain_depth=int(item.get("chain_depth", 0)),
                sequence_number=int(item.get("sequence_number", 0)),
                timestamp=float(item.get("timestamp", time.time())),
                payload=dict(item.get("payload", {})),
                target_ids=list(item.get("target_ids", [])),
                situation_before=dict(item.get("situation_before", {})),
                situation_after=dict(item.get("situation_after", {})),
                reasons=list(item.get("reasons", [])),
            )
            reaction = reaction_map.get(event.reaction_id)
            if reaction is None:
                reaction = Reaction(type="unknown", status=ReactionStatus.ERROR, message="missing reaction")
            memory.record(event, reaction)
        for item in payload.get("interactions", []):
            memory.interactions.append(Interaction(item["category"], list(item.get("participants", [])), item["correlation_id"], float(item.get("intensity", 0.0)), float(item.get("timestamp", time.time()))))
        for item in payload.get("phenomena", []):
            memory.phenomena.append(Phenomenon(item["category"], item["context_name"], item["correlation_id"], float(item.get("intensity", 0.0)), item.get("summary", ""), float(item.get("timestamp", time.time()))))
        return memory


class Environment:
    def __init__(self, name: str, kind: EnvironmentKind, contextualizer: Optional[Contextualizer] = None,
                 savoir: Optional[Savoir] = None) -> None:
        self.name = name
        self.kind = kind
        self.contextualizer = contextualizer or Contextualizer()
        self.savoir = savoir or Savoir()
        self.environment_id = str(uuid.uuid4())
        self.contexts: Dict[str, Context] = {}
        self.elements: Dict[str, Element] = {}
        self.memory = CausalMemory()
        self.impact = ImpactMatrix()
        self.semantic_graph = SemanticRelationalGraph()
        self.native_store_suite: Any = None
        self._me_sessions: Dict[str, Dict[str, Any]] = {}

    def register_session(self, session_id: str, data: Dict[str, Any]) -> None:
        self._me_sessions[session_id] = dict(data)

    def attach_native_store_suite(self, suite: Any) -> Any:
        self.native_store_suite = suite
        return suite

    def persist_native_stores(self, base_dir: Optional[str] = None) -> Dict[str, Any]:
        if base_dir is not None:
            from .persistence import NativeSpecializedStoreSuite
            self.native_store_suite = NativeSpecializedStoreSuite(base_dir)
        if self.native_store_suite is None:
            return {}
        return self.native_store_suite.save_environment(self)

    def native_store_summary(self) -> Dict[str, Any]:
        if self.native_store_suite is None:
            return {}
        return self.native_store_suite.summary()


    def create_context(self, name: str, kind: ContextKind, basis: SenseVector = SENSE_NULL,
                       circumstances: Optional[List[Circumstance]] = None) -> Context:
        ctx = Context(self, name, kind, basis, circumstances)
        self.contexts[name] = ctx
        self.semantic_graph.upsert_node(
            node_id=ctx.context_id,
            kind="context",
            labels=[name, kind.value],
            basis=basis,
            dynamic_state=ctx.data,
            quality={"kind": float(len(self.contexts))},
        )
        for other in self.contexts.values():
            if other.name == name:
                continue
            distance = basis.angular_distance(other.basis)
            self.semantic_graph.connect(ctx.context_id, other.context_id, "context_distance", sense=basis, precision=max(0.0, 1.0 - distance), payload={"distance": distance})
            self.semantic_graph.connect(other.context_id, ctx.context_id, "context_distance", sense=other.basis, precision=max(0.0, 1.0 - distance), payload={"distance": distance})
        return ctx

    async def admit(self, element: Element) -> None:
        self.elements[element.element_id] = element
        self.semantic_graph.upsert_node(
            node_id=element.element_id,
            kind=element.kind,
            labels=[element.name, element.kind],
            basis=element.basis,
            dynamic_state=element.dynamic,
            certainty=self.savoir.certainty_matrix(),
            quality={"property_count": float(len(element.properties))},
        )

    def snapshot(self) -> Dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "name": self.name,
            "kind": self.kind.value,
            "contexts": {
                name: {
                    "context_id": c.context_id,
                    "kind": c.kind.value,
                    "basis": c.basis.to_dict(),
                    "data": dict(c.data),
                    "topology": c.topology(),
                }
                for name, c in self.contexts.items()
            },
            "elements": {eid: e.snapshot() for eid, e in self.elements.items()},
            "savoir": self.savoir.snapshot(),
            "operational": self.operational_state().to_dict(),
        }

    def operational_state(self) -> OperationalEnvironmentState:
        x_t = {node_id: list(node.state_row) for node_id, node in self.semantic_graph.nodes.items()}
        k_t = {node_id: list(node.certainty_row) for node_id, node in self.semantic_graph.nodes.items()}
        c_t = {name: list(ctx.basis.values) for name, ctx in self.contexts.items()}
        f_t = self.savoir.factor_graph.summary()
        p_t = {
            "session_count": len(self._me_sessions),
            "event_count": len(self.memory.events),
            "reaction_count": len(self.memory.reactions),
        }
        return OperationalEnvironmentState(X_t=x_t, K_t=k_t, C_t=c_t, G_t=self.semantic_graph.export(), F_t=f_t, P_t=p_t)

    def compute_situation(self, context: Context) -> Situation:
        active = [c.name for c in context.circumstances if c.holds(context, {})]
        factor_energy = self.savoir.factor_graph.energy()
        if any("emergency" in name for name in active) or factor_energy > 5.0:
            basis = SenseVector.causal("critical", 1.0)
            label = "critical"
        elif len(self.memory.events) > 5 or factor_energy > 1.0:
            basis = SenseVector.emergent("busy", 0.8)
            label = "degraded"
        else:
            basis = SenseVector.technical("operational", 0.5)
            label = "operational"
        return Situation(label=label, basis=basis, qualities={"active_circumstances": active, "event_count": len(self.memory.events), "factor_energy": factor_energy})

    def _score_causal_outcome(self, reaction: Reaction, context: Context, action_type: str, causal_delta: float, chain_depth: int, reasons: Optional[Sequence[str]] = None) -> tuple[float, Dict[str, float]]:
        reasons = list(reasons or [])
        status_component = {
            ReactionStatus.SUCCESS: 1.0,
            ReactionStatus.PARTIAL: 0.45,
            ReactionStatus.REJECTED: -0.35,
            ReactionStatus.ERROR: -0.75,
            ReactionStatus.DEFERRED: -0.10,
        }.get(reaction.status, 0.0)
        scope_component = {
            ImpactScope.ON_ACTOR: 0.28,
            ImpactScope.ON_TARGET: 0.42,
            ImpactScope.ON_ENVIRONMENT: 0.58,
            ImpactScope.BROADCAST: 0.72,
        }.get(reaction.impact_scope, 0.25)
        temporality_component = {
            Temporality.IMMEDIATE: 0.42,
            Temporality.TEMPORARY: 0.32,
            Temporality.DURABLE: 0.62,
            Temporality.DELAYED: 0.12,
        }.get(reaction.temporality, 0.25)
        sense_alignment = max(0.0, reaction.sense.cosine(context.basis)) if reaction.sense != SENSE_NULL else 0.0
        delta_component = max(0.0, min(1.0, float(causal_delta)))
        reach_component = 1.0 if reaction.impact_scope == ImpactScope.BROADCAST else min(1.0, len(reaction.target_ids) / 4.0)
        depth_penalty = min(1.0, chain_depth / 6.0)
        rejection_penalty = min(1.0, len(reasons) / 5.0)
        structural_bonus = 0.0
        if any(tok in action_type for tok in ("resolve", "stabilize", "recover", "mitigate", "assign", "open", "escalate")):
            structural_bonus = 0.28
        score = (
            0.34 * status_component
            + 0.14 * sense_alignment
            + 0.16 * delta_component
            + 0.12 * scope_component
            + 0.08 * temporality_component
            + 0.06 * reach_component
            + 0.10 * structural_bonus
            - 0.06 * depth_penalty
            - 0.06 * rejection_penalty
        )
        score = max(-1.0, min(1.0, score))
        return score, {
            "status_component": float(status_component),
            "sense_alignment": float(sense_alignment),
            "causal_delta_component": float(delta_component),
            "scope_component": float(scope_component),
            "temporality_component": float(temporality_component),
            "reach_component": float(reach_component),
            "structural_bonus": float(structural_bonus),
            "depth_penalty": float(depth_penalty),
            "rejection_penalty": float(rejection_penalty),
            "score": float(score),
        }

    def _build_frame(self, actor: Element, context: Context, payload: Dict[str, Any], correlation_id: str,
                     causation_id: Optional[str], chain_depth: int) -> Dict[str, Any]:
        certainty_matrix = self.savoir.certainty_matrix()
        certainty_bonus = min(0.2, max((c for _, c in certainty_matrix.values()), default=0.0) * 0.1)
        impact_bonus = 0.0
        actor_snapshot = actor.snapshot()
        return {
            "actor_id": actor.element_id,
            "actor_name": actor.name,
            "actor": actor_snapshot,
            "actor_role": actor_snapshot.get("properties", {}).get("role"),
            "context_name": context.name,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "chain_depth": chain_depth,
            "payload": payload,
            "certainty_bonus": certainty_bonus,
            "impact_bonus": impact_bonus,
        }

    async def dispatch(self, actor: Element, action_type: str, payload: Dict[str, Any], context: Context,
                       *, correlation_id: Optional[str] = None, causation_id: Optional[str] = None,
                       chain_depth: int = 0) -> Reaction:
        correlation_id = correlation_id or str(uuid.uuid4())
        situation_before = self.compute_situation(context)
        frame = self._build_frame(actor, context, payload, correlation_id, causation_id, chain_depth)
        available = context.get_available_actions(actor.snapshot(), frame, current_sense=situation_before.basis)
        action = next((a for a, _ in available if a.type == action_type), None)
        reasons: List[str] = []
        if action is None:
            reasons = context.explain_why_not(action_type, frame)
            reaction = Reaction(
                type=f"{action_type}.rejected",
                status=ReactionStatus.REJECTED,
                message=f"Action {action_type} not available",
                sense=SenseVector.normative("blocked action", 0.8),
                result={"missing": reasons},
            )
        else:
            reaction = await action.execute(actor, payload, context, frame)
        await self._apply_reaction(actor, reaction, frame)
        situation_after = self.compute_situation(context)
        event = Event(
            event_type="action.dispatched",
            actor_id=actor.element_id,
            context_name=context.name,
            action_type=action_type,
            reaction_id=reaction.reaction_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            chain_depth=chain_depth,
            payload=payload,
            target_ids=list(reaction.target_ids),
            situation_before=situation_before.to_dict(),
            situation_after=situation_after.to_dict(),
            reasons=reasons,
        )
        self.memory.record(event, reaction)
        causal_delta = situation_before.basis.delta(situation_after.basis).magnitude
        impact_score, impact_components = self._score_causal_outcome(reaction, context, action_type, causal_delta, chain_depth, reasons=reasons)
        self.impact.add(ImpactRecord(
            correlation_id=correlation_id,
            action_type=action_type,
            reaction_type=reaction.type,
            context_name=context.name,
            status=reaction.status.value,
            impact_score=impact_score,
            chain_depth=chain_depth,
            causal_delta=causal_delta,
            components=impact_components,
        ))
        if self.native_store_suite is not None:
            try:
                self.native_store_suite.learning.append_record(self.impact.records[-1])
            except Exception:
                pass
        support = 0.15 if reaction.status == ReactionStatus.SUCCESS else -0.25
        self.savoir.observe(
            f"corr:{correlation_id}:last_reaction",
            reaction.type,
            source="edp.dispatch",
            certainty=1.0 if reaction.status == ReactionStatus.SUCCESS else 0.6,
            sense=reaction.sense,
        )
        self.savoir.revise_certainty(f"corr:{correlation_id}:last_reaction", support=support)
        outcome_obs = {"success": 1.0 if reaction.status == ReactionStatus.SUCCESS else 0.0, "failure": 0.0 if reaction.status == ReactionStatus.SUCCESS else 1.0}
        transitions = {"success": {"success": 0.85, "failure": 0.15}, "failure": {"success": 0.20, "failure": 0.80}}
        self.savoir.update_belief(
            variable=f"corr:{correlation_id}:outcome",
            transitions=transitions,
            observation=outcome_obs,
            observation_weight=0.8,
        )
        self.savoir.update_belief(
            variable="global.outcome",
            transitions=transitions,
            observation=outcome_obs,
            observation_weight=0.55,
        )
        self._record_semantic_causality(actor, context, action_type, reaction, event)
        if reaction.chain and chain_depth < 8:
            for next_action, next_payload, target_id in reaction.chain:
                target = self.elements.get(target_id) if target_id else actor
                if target is None:
                    continue
                await self.dispatch(target, next_action, next_payload, context, correlation_id=correlation_id, causation_id=reaction.reaction_id, chain_depth=chain_depth + 1)
        self._detect_patterns(correlation_id, context)
        return reaction

    async def _apply_reaction(self, actor: Element, reaction: Reaction, frame: Dict[str, Any]) -> None:
        if reaction.impact_scope == ImpactScope.ON_ACTOR:
            await actor.on_impacted(reaction, frame)
            self.semantic_graph.upsert_node(actor.element_id, actor.kind, [actor.name, actor.kind], actor.basis, actor.dynamic, self.savoir.certainty_matrix())
        elif reaction.impact_scope == ImpactScope.BROADCAST:
            for element in self.elements.values():
                await element.on_impacted(reaction, frame)
                self.semantic_graph.upsert_node(element.element_id, element.kind, [element.name, element.kind], element.basis, element.dynamic, self.savoir.certainty_matrix())
        elif reaction.impact_scope == ImpactScope.ON_TARGET:
            for target_id in reaction.target_ids:
                target = self.elements.get(target_id)
                if target is not None:
                    await target.on_impacted(reaction, frame)
                    self.semantic_graph.upsert_node(target.element_id, target.kind, [target.name, target.kind], target.basis, target.dynamic, self.savoir.certainty_matrix())

    def _record_semantic_causality(self, actor: Element, context: Context, action_type: str, reaction: Reaction, event: Event) -> None:
        action_node = f"action:{action_type}"
        reaction_node = f"reaction:{reaction.reaction_id}"
        self.semantic_graph.upsert_node(action_node, "action", [action_type], context._actions.get(action_type, Action(action_type, ActionCategory.SIGNAL, action_type, SENSE_NULL, lambda *_: reaction)).basis if action_type in context._actions else SENSE_NULL)
        self.semantic_graph.upsert_node(reaction_node, "reaction", [reaction.type, reaction.status.value], reaction.sense, dynamic_state=reaction.result)
        self.semantic_graph.connect(actor.element_id, action_node, "triggers", sense=actor.basis.apply_context_operator(context.basis), precision=1.0, payload={"context": context.name, "event": event.event_type})
        self.semantic_graph.connect(action_node, reaction_node, "produces", sense=reaction.sense, precision=1.0, payload={"reaction_type": reaction.type})
        if reaction.impact_scope == ImpactScope.ON_ACTOR:
            self.semantic_graph.connect(reaction_node, actor.element_id, "impacts", sense=reaction.sense, precision=1.0, payload={"scope": reaction.impact_scope.value})
        for target_id in reaction.target_ids:
            self.semantic_graph.connect(reaction_node, target_id, "impacts", sense=reaction.sense, precision=1.0, payload={"scope": reaction.impact_scope.value})
        if reaction.impact_scope == ImpactScope.BROADCAST:
            for element_id in self.elements:
                self.semantic_graph.connect(reaction_node, element_id, "broadcasts_to", sense=reaction.sense, precision=0.8, payload={"scope": reaction.impact_scope.value})

    def _detect_patterns(self, correlation_id: str, context: Context) -> None:
        trace = self.memory.correlation_trace(correlation_id)
        participants = list({event.actor_id for event in trace})
        categories: List[str] = []
        if len(trace) >= 2:
            categories.append("propagation")
        if len(trace) >= 2 and len(participants) == 1:
            categories.append("feedback")
        if any((self.memory.reactions.get(event.reaction_id) is not None and self.memory.reactions[event.reaction_id].impact_scope == ImpactScope.BROADCAST) or len(event.target_ids) > 1 for event in trace):
            categories.append("broadcast")
        for category in categories:
            self.memory.interactions.append(Interaction(category, participants, correlation_id, min(1.0, len(trace) / 5.0)))
        if len(trace) >= 3 and len(participants) >= 2:
            self.memory.phenomena.append(Phenomenon("reaction_chain", context.name, correlation_id, min(1.0, len(trace) / 6.0), f"{len(trace)} events causal chain"))
        if "broadcast" in categories:
            self.memory.phenomena.append(Phenomenon("broadcast_coordination", context.name, correlation_id, 0.75, "broadcast detected in causal trace"))
        if "feedback" in categories:
            self.memory.phenomena.append(Phenomenon("feedback_loop", context.name, correlation_id, 0.70, "same actor produced chained effects"))

    def why(self, correlation_id: str) -> ProvenanceTrace:
        return self.memory.provenance(correlation_id)

    def whynot(self, actor: Element, context: Context, action_type: str, payload: Optional[Dict[str, Any]] = None) -> List[str]:
        payload = payload or {}
        situation = self.compute_situation(context)
        frame = self._build_frame(actor, context, payload, correlation_id="preview", causation_id=None, chain_depth=0)
        _ = situation
        return context.explain_why_not(action_type, frame)

    def replay(self, correlation_id: str) -> List[Dict[str, Any]]:
        return self.memory.replay(correlation_id)

    def replay_until(self, correlation_id: str, sequence_number: int) -> List[Dict[str, Any]]:
        return self.memory.replay_until(correlation_id, sequence_number)

    def merge_memory(self, other: CausalMemory) -> Dict[str, int]:
        return self.memory.merge(other)

    def persist_memory(self, path: str) -> str:
        from .persistence import JsonEventStore
        return str(JsonEventStore(path).save_memory(self.memory))

    def restore_memory(self, path: str) -> None:
        from .persistence import JsonEventStore
        payload = JsonEventStore(path).load_memory()
        self.memory = CausalMemory.from_dict(payload)

    def persist_graph(self, path: str) -> str:
        from .persistence import JsonGraphStore
        return str(JsonGraphStore(path).save(self.semantic_graph))

    def load_graph_snapshot(self, path: str) -> Dict[str, Any]:
        from .persistence import JsonGraphStore
        return JsonGraphStore(path).load()


__all__ = [
    "EnvironmentKind",
    "ContextKind",
    "ActionCategory",
    "ReactionStatus",
    "ImpactScope",
    "Temporality",
    "Circumstance",
    "Situation",
    "Reaction",
    "Event",
    "ProvenanceTrace",
    "Interaction",
    "Phenomenon",
    "Action",
    "Element",
    "Context",
    "CausalMemory",
    "Environment",
]
