from __future__ import annotations

import re
import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .core import Context, Element, Environment, CausalMemory, ActionCategory
from .operational import SemanticRelationalGraph
from .persistence import JsonEventStore, JsonGraphStore
from .policy import PolicyDecision, PolicyEngine
from .canonical import EnvironmentCanonicalBody


@dataclass
class ContextEnvelope:
    ctx_id: str
    name: str
    kind: str
    depth: int
    data: Dict[str, Any] = field(default_factory=dict)
    circumstances: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    harmony_map: Dict[str, Dict[str, float]] = field(default_factory=dict)
    situation: Optional[Dict[str, Any]] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    memory: List[Dict[str, Any]] = field(default_factory=list)
    attention: List[str] = field(default_factory=list)
    phenomena: List[Dict[str, Any]] = field(default_factory=list)
    topology: Dict[str, float] = field(default_factory=dict)
    why_not: Dict[str, List[str]] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class StateSnapshot:
    environment_id: str
    timestamp: float
    operational: Dict[str, Any]
    savoir: Dict[str, Any]
    contexts: Dict[str, Any]
    elements: Dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class StateDelta:
    previous_timestamp: float
    current_timestamp: float
    delta: Dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class MepCard:
    environment_id: str
    environment_name: str
    contexts: List[Dict[str, Any]]
    action_catalog: List[Dict[str, Any]]
    protocol_version: str = "0.5.0"

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class WorldPacket:
    packet_id: str
    snapshot: Dict[str, Any]
    delta: Optional[Dict[str, Any]]
    contexts: Dict[str, Any]
    topology: Dict[str, Dict[str, float]]
    emitted_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class CertaintyPacket:
    packet_id: str
    facts: Dict[str, Any]
    belief: Dict[str, Any]
    certainty_revisions: List[Dict[str, Any]]
    factor_graph: Dict[str, Any]
    emitted_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class CausalityPacket:
    packet_id: str
    correlation_id: str
    trace: Dict[str, Any]
    replay: List[Dict[str, Any]] = field(default_factory=list)
    why_not: Optional[Dict[str, Any]] = None
    interaction_categories: List[str] = field(default_factory=list)
    phenomenon_categories: List[str] = field(default_factory=list)
    emitted_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class DistributedHello:
    packet_id: str
    agent_id: str
    capabilities: List[str]
    emitted_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class DistributedSyncPacket:
    packet_id: str
    source_environment_id: str
    memory_summary: Dict[str, Any]
    graph_summary: Dict[str, Any]
    emitted_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class ReplayResponse:
    packet_id: str
    correlation_id: str
    replay: List[Dict[str, Any]]
    emitted_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class ResyncRequest:
    packet_id: str
    requester_id: str
    want_memory_since: int = 0
    include_graph: bool = True
    emitted_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class ResyncResponse:
    packet_id: str
    source_environment_id: str
    journal: List[Dict[str, Any]]
    graph: Optional[Dict[str, Any]]
    summary: Dict[str, Any]
    emitted_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class MergeReport:
    packet_id: str
    source_environment_id: str
    merged_events: int
    merged_reactions: int
    merged_nodes: int
    merged_edges: int
    emitted_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class GovernancePacket:
    packet_id: str
    policy: Dict[str, Any]
    emitted_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class InterfaceBinding:
    name: str
    realm: str = "logical"
    context_name: str = ""
    mode: str = "internal"
    shared: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "realm": self.realm,
            "context_name": self.context_name,
            "mode": self.mode,
            "shared": self.shared,
            "metadata": dict(self.metadata),
        }


@dataclass
class AgentScopePacket:
    packet_id: str
    agent: Dict[str, Any]
    active_context: str
    accessible_contexts: List[str]
    shared_contexts: List[str]
    interfaces: List[Dict[str, Any]]
    situation_map: Dict[str, Any]
    topology: Dict[str, Dict[str, float]]
    emitted_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)




@dataclass
class GroupProfile:
    name: str
    members: List[str] = field(default_factory=list)
    shared_contexts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "members": list(self.members),
            "shared_contexts": list(self.shared_contexts),
            "metadata": dict(self.metadata),
        }


@dataclass
class DelegationRecord:
    delegation_id: str
    delegator: str
    delegatee: str
    action_type: str
    context_name: str
    payload: Dict[str, Any]
    accepted: bool
    reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delegation_id": self.delegation_id,
            "delegator": self.delegator,
            "delegatee": self.delegatee,
            "action_type": self.action_type,
            "context_name": self.context_name,
            "payload": dict(self.payload),
            "accepted": self.accepted,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass
class ConsensusPacket:
    packet_id: str
    group: str
    action_type: str
    context_name: str
    threshold: float
    voters: List[Dict[str, Any]]
    approved: bool
    selected_actor: Optional[str] = None
    emitted_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class GroupScopePacket:
    packet_id: str
    group: Dict[str, Any]
    member_scopes: Dict[str, Any]
    topology: Dict[str, Dict[str, float]]
    emitted_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)




@dataclass
class NegotiationProposal:
    agent: str
    context_name: str
    action_type: str
    score: float
    acceptable: bool
    reasons: List[str] = field(default_factory=list)
    preferred_executor: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "context_name": self.context_name,
            "action_type": self.action_type,
            "score": self.score,
            "acceptable": self.acceptable,
            "reasons": list(self.reasons),
            "preferred_executor": self.preferred_executor,
        }


@dataclass
class NegotiationPacket:
    packet_id: str
    group: str
    action_type: str
    context_name: str
    proposals: List[Dict[str, Any]]
    selected_actor: Optional[str]
    agreed: bool
    emitted_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class TaskStep:
    step_id: str
    action_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    actor: Optional[str] = None
    group: Optional[str] = None
    context_name: Optional[str] = None
    interface_name: Optional[str] = None
    threshold: float = 0.5
    mode: str = "single"  # single | group | fanout | negotiate

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action_type": self.action_type,
            "payload": dict(self.payload),
            "actor": self.actor,
            "group": self.group,
            "context_name": self.context_name,
            "interface_name": self.interface_name,
            "threshold": self.threshold,
            "mode": self.mode,
        }


@dataclass
class TaskPlan:
    plan_id: str
    name: str
    steps: List[TaskStep] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "name": self.name,
            "steps": [s.to_dict() for s in self.steps],
            "metadata": dict(self.metadata),
        }


@dataclass
class PlanExecutionPacket:
    packet_id: str
    plan: Dict[str, Any]
    results: List[Dict[str, Any]]
    success: bool
    emitted_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class RuntimeStatePacket:
    packet_id: str
    environment_id: str
    agents: List[Dict[str, Any]]
    groups: List[Dict[str, Any]]
    policy: Dict[str, Any]
    journal: List[Dict[str, Any]]
    graph: Dict[str, Any]
    emitted_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


class MepGateway:
    def __init__(self, environment: Environment, policy_engine: Optional[PolicyEngine] = None) -> None:
        self.environment = environment
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.peers: Dict[str, Dict[str, Any]] = {}
        self.policy_engine = policy_engine or PolicyEngine()

    def governance(self) -> GovernancePacket:
        return GovernancePacket(packet_id=str(uuid.uuid4()), policy=self.policy_engine.snapshot())

    def open_session(self, agent_name: str, primary_context: str) -> str:
        sid = str(uuid.uuid4())
        info = {"agent_name": agent_name, "primary_context": primary_context, "opened_at": time.time()}
        self.sessions[sid] = info
        self.environment.register_session(sid, info)
        return sid

    def register_peer(self, agent_id: str, capabilities: Optional[List[str]] = None) -> DistributedHello:
        capabilities = list(capabilities or ["world", "certainty", "causality", "replay", "resync"])
        self.peers[agent_id] = {"capabilities": capabilities, "registered_at": time.time()}
        return DistributedHello(packet_id=str(uuid.uuid4()), agent_id=agent_id, capabilities=capabilities)

    def distributed_sync(self) -> DistributedSyncPacket:
        graph = self.environment.operational_state().G_t
        summary = self.environment.memory.summary()
        graph_summary = {
            "node_count": len(graph["nodes"]),
            "edge_count": len(graph["edges"]),
            "relation_counts": self.environment.semantic_graph.relation_counts(),
        }
        return DistributedSyncPacket(packet_id=str(uuid.uuid4()), source_environment_id=self.environment.environment_id, memory_summary=summary, graph_summary=graph_summary)

    def describe(self) -> MepCard:
        catalog: List[Dict[str, Any]] = []
        seen = set()
        for context in self.environment.contexts.values():
            for action in context._actions.values():
                if action.type in seen:
                    continue
                seen.add(action.type)
                catalog.append({
                    "type": action.type,
                    "category": action.category.value,
                    "description": action.description,
                    "basis": action.basis.to_dict(),
                    "contexts": [name for name, c in self.environment.contexts.items() if action.type in c._actions],
                })
        contexts = [
            {
                "name": ctx.name,
                "id": ctx.context_id,
                "kind": ctx.kind.value,
                "basis": ctx.basis.to_dict(),
                "topology": ctx.topology(),
            }
            for ctx in self.environment.contexts.values()
        ]
        return MepCard(self.environment.environment_id, self.environment.name, contexts, catalog)

    def envelope(self, actor: Element, context: Context, payload: Optional[Dict[str, Any]] = None) -> ContextEnvelope:
        payload = payload or {}
        situation = self.environment.compute_situation(context)
        frame = self.environment._build_frame(actor, context, payload, correlation_id="preview", causation_id=None, chain_depth=0)
        actions = context.get_available_actions(actor.snapshot(), frame, situation.basis)
        harmony_map = {action.type: hp.to_dict() for action, hp in actions}
        known_actions = {action.type: [] for action in context._actions.values()}
        for action_type in list(known_actions):
            blockers = context.explain_why_not(action_type, frame)
            if blockers:
                known_actions[action_type] = blockers
        recent_events = [e.to_dict() for e in self.environment.memory.context_timeline(context.name)[-5:]]
        memory = [e.to_dict() for e in self.environment.memory.actor_timeline(actor.element_id)[-5:]]
        phenomena = [p.to_dict() for p in self.environment.memory.phenomena[-5:] if p.context_name == context.name]
        attention = [f"{p['category']}:{p['summary']}" for p in phenomena[-3:]]
        return ContextEnvelope(
            ctx_id=context.context_id,
            name=context.name,
            kind=context.kind.value,
            depth=0,
            data=dict(context.data),
            circumstances=[{"name": c.name, "description": c.description, "holds": c.holds(context, frame), "role": c.role} for c in context.circumstances],
            actions=[
                {
                    "type": action.type,
                    "category": action.category.value,
                    "description": action.description,
                    "score": hp.score,
                    "basis": action.basis.to_dict(),
                }
                for action, hp in actions
            ],
            harmony_map=harmony_map,
            situation=situation.to_dict(),
            events=recent_events,
            memory=memory,
            attention=attention,
            phenomena=phenomena,
            topology=context.topology(),
            why_not=known_actions,
        )

    async def dispatch(self, actor: Element, context_name: str, action_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        context = self.environment.contexts[context_name]
        reaction = await self.environment.dispatch(actor, action_type, payload, context)
        return {
            "reaction_id": reaction.reaction_id,
            "type": reaction.type,
            "status": reaction.status.value,
            "message": reaction.message,
            "result": reaction.result,
        }

    def recommend_actions(self, actor: Element, context_name: str, payload: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        from .intelligence import ActionRanker
        context = self.environment.contexts[context_name]
        ranker = ActionRanker(self.environment)
        return [item.to_dict() for item in ranker.rank(actor, context, payload)]

    def forecast_phenomena(self, context_name: Optional[str] = None) -> List[Dict[str, Any]]:
        from .intelligence import PhenomenonForecaster
        return PhenomenonForecaster(self.environment).forecast(context_name=context_name)

    def state_snapshot(self) -> StateSnapshot:
        snap = self.environment.snapshot()
        return StateSnapshot(
            environment_id=snap["environment_id"],
            timestamp=time.time(),
            operational=snap["operational"],
            savoir=snap["savoir"],
            contexts=snap["contexts"],
            elements=snap["elements"],
        )

    @staticmethod
    def state_delta(previous: StateSnapshot, current: StateSnapshot) -> StateDelta:
        delta: Dict[str, Any] = {"contexts": {}, "elements": {}, "savoir": {}, "operational": {}}
        for ctx_name, ctx in current.contexts.items():
            if previous.contexts.get(ctx_name) != ctx:
                delta["contexts"][ctx_name] = ctx
        for element_id, element in current.elements.items():
            if previous.elements.get(element_id) != element:
                delta["elements"][element_id] = element
        if previous.savoir != current.savoir:
            delta["savoir"] = current.savoir
        if previous.operational != current.operational:
            delta["operational"] = current.operational
        return StateDelta(previous.timestamp, current.timestamp, delta)

    def world_packet(self, previous: Optional[StateSnapshot] = None) -> WorldPacket:
        current = self.state_snapshot()
        delta = self.state_delta(previous, current).delta if previous is not None else None
        topology = {name: ctx.topology() for name, ctx in self.environment.contexts.items()}
        return WorldPacket(packet_id=str(uuid.uuid4()), snapshot=current.__dict__, delta=delta, contexts=current.contexts, topology=topology)

    def certainty_packet(self) -> CertaintyPacket:
        savoir = self.environment.savoir.snapshot()
        return CertaintyPacket(packet_id=str(uuid.uuid4()), facts=savoir["facts"], belief=savoir["belief"], certainty_revisions=savoir.get("certainty_revisions", []), factor_graph=savoir.get("factor_graph", {}))

    def causality_packet(self, correlation_id: str, *, actor: Optional[Element] = None, context_name: Optional[str] = None, action_type: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> CausalityPacket:
        trace = self.why(correlation_id)
        why_not: Optional[Dict[str, Any]] = None
        if actor is not None and context_name is not None and action_type is not None:
            why_not = self.whynot(actor, context_name, action_type, payload or {})
        interactions = [i.category for i in self.environment.memory.interactions if i.correlation_id == correlation_id]
        phenomena = [p.category for p in self.environment.memory.phenomena if p.correlation_id == correlation_id]
        return CausalityPacket(packet_id=str(uuid.uuid4()), correlation_id=correlation_id, trace=trace, replay=self.environment.replay(correlation_id), why_not=why_not, interaction_categories=interactions, phenomenon_categories=phenomena)

    def replay_packet(self, correlation_id: str) -> ReplayResponse:
        return ReplayResponse(packet_id=str(uuid.uuid4()), correlation_id=correlation_id, replay=self.environment.replay(correlation_id))

    def why(self, correlation_id: str) -> Dict[str, Any]:
        return self.environment.why(correlation_id).to_dict()

    def whynot(self, actor: Element, context_name: str, action_type: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = self.environment.contexts[context_name]
        reasons = self.environment.whynot(actor, context, action_type, payload)
        return {"blocked": len(reasons) > 0, "reasons": reasons}

    def build_resync_request(self, requester_id: str, *, want_memory_since: int = 0, include_graph: bool = True) -> ResyncRequest:
        return ResyncRequest(packet_id=str(uuid.uuid4()), requester_id=requester_id, want_memory_since=want_memory_since, include_graph=include_graph)

    def respond_resync(self, request: ResyncRequest) -> ResyncResponse:
        journal = [entry for entry in self.environment.memory.event_journal() if entry.get("sequence_number", 0) > request.want_memory_since]
        graph = self.environment.semantic_graph.export() if request.include_graph else None
        return ResyncResponse(packet_id=str(uuid.uuid4()), source_environment_id=self.environment.environment_id, journal=journal, graph=graph, summary=self.environment.memory.summary())

    def merge_resync(self, response: ResyncResponse) -> MergeReport:
        # rebuild causal memory from journal into temporary memory for merge
        events = []
        reactions = []
        for entry in response.journal:
            if "event" in entry:
                events.append(entry["event"])
                if entry.get("reaction") is not None:
                    reactions.append(entry["reaction"])
            else:
                events.append({k: v for k, v in entry.items() if k != "reaction"})
                if entry.get("reaction") is not None:
                    reactions.append(entry["reaction"])
        journal_payload = {
            "events": events,
            "reactions": reactions,
            "interactions": [],
            "phenomena": [],
        }
        other_memory = CausalMemory.from_dict(journal_payload)
        mem_report = self.environment.merge_memory(other_memory)
        graph_report = {"nodes": 0, "edges": 0}
        if response.graph is not None:
            graph_report = self.environment.semantic_graph.merge_export(response.graph)
        return MergeReport(
            packet_id=str(uuid.uuid4()),
            source_environment_id=response.source_environment_id,
            merged_events=mem_report.get("events", 0),
            merged_reactions=mem_report.get("reactions", 0),
            merged_nodes=graph_report.get("nodes", 0),
            merged_edges=graph_report.get("edges", 0),
        )

    def persist_state(self, memory_path: str, graph_path: str) -> Dict[str, Any]:
        mem_store = JsonEventStore(memory_path)
        graph_store = JsonGraphStore(graph_path)
        mem_store.save_memory(self.environment.memory)
        graph_store.save(self.environment.semantic_graph)
        return {
            "memory": memory_path,
            "memory_summary": mem_store.load_summary(),
            "graph": graph_path,
            "graph_index": graph_store.load_index(),
        }


@dataclass
class AgentProfile:
    alias: str
    element_id: str
    role: str
    kind: str
    active_context: str
    session_id: str
    capabilities: List[str] = field(default_factory=list)
    accessible_contexts: List[str] = field(default_factory=list)
    shared_contexts: List[str] = field(default_factory=list)
    interfaces: Dict[str, InterfaceBinding] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alias": self.alias,
            "element_id": self.element_id,
            "role": self.role,
            "kind": self.kind,
            "active_context": self.active_context,
            "session_id": self.session_id,
            "capabilities": list(self.capabilities),
            "accessible_contexts": list(self.accessible_contexts),
            "shared_contexts": list(self.shared_contexts),
            "interfaces": {k: v.to_dict() for k, v in self.interfaces.items()},
            "metadata": dict(self.metadata),
        }


@dataclass
class AgentMessage:
    message_id: str
    sender: str
    recipient: str
    topic: str
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "topic": self.topic,
            "payload": dict(self.payload),
            "timestamp": self.timestamp,
        }


class AgentElement(Element):
    def __init__(self, name: str, *, kind: str = "agent", role: str = "operator") -> None:
        super().__init__(name=name, kind=kind, properties={"role": role, "alias": name})
        self.inbox: List[Dict[str, Any]] = []
        self.outbox: List[Dict[str, Any]] = []

    async def on_impacted(self, reaction, frame):
        self.dynamic["last_reaction"] = reaction.type
        self.dynamic["last_status"] = reaction.status.value
        self.dynamic["last_correlation_id"] = frame.get("correlation_id")

    def deliver(self, message: AgentMessage) -> None:
        self.inbox.append(message.to_dict())
        self.dynamic["inbox_count"] = len(self.inbox)


class MultiAgentRuntime:
    """
    Flexible multi-agent layer over one EDP environment.
    Agents are environment elements with roles, active contexts, sessions and inboxes.
    """

    def __init__(self, gateway: MepGateway) -> None:
        self.gateway = gateway
        self.environment = gateway.environment
        self.agents: Dict[str, AgentProfile] = {}
        self.groups: Dict[str, GroupProfile] = {}
        self.delegations: List[DelegationRecord] = []
        self.messages: List[AgentMessage] = []
        self._install_default_governance()

    def _install_default_governance(self) -> None:
        pe = self.gateway.policy_engine
        defaults = {
            "admin": ["dispatch", "recommend", "whynot", "why", "message", "govern"],
            "dispatcher": ["dispatch", "recommend", "whynot", "why", "message"],
            "reviewer": ["dispatch", "recommend", "whynot", "why", "message"],
            "operator": ["dispatch", "recommend", "whynot", "message"],
            "pilot": ["dispatch", "recommend", "whynot", "message"],
            "controller": ["dispatch", "recommend", "whynot", "message", "govern"],
            "agent": ["recommend", "whynot", "message"],
        }
        for role, caps in defaults.items():
            if role not in pe.snapshot()["role_capabilities"]:
                pe.set_role_capabilities(role, caps)

    def set_group_weight(self, group_name: str, alias: str, weight: float) -> Dict[str, Any]:
        group = self.groups[group_name]
        weights = group.metadata.setdefault("weights", {})
        weights[alias] = max(0.0, float(weight))
        return group.to_dict()

    def _group_weight(self, group_name: str, alias: str) -> float:
        group = self.groups[group_name]
        weights = group.metadata.get("weights", {})
        return float(weights.get(alias, 1.0))

    def _action_score(self, alias: str, action_type: str, *, context_name: Optional[str] = None, interface_name: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> float:
        recs = self.recommend(alias, context_name=context_name, interface_name=interface_name, payload=payload)
        for rec in recs:
            if rec.get("action_type") == action_type:
                return float(rec.get("total_score", rec.get("score", 0.0)))
        return 0.0

    def grant_capability(self, alias: str, capability: str) -> Dict[str, Any]:
        profile = self.agents[alias]
        if capability not in profile.capabilities:
            profile.capabilities.append(capability)
        return profile.to_dict()

    def revoke_capability(self, alias: str, capability: str) -> Dict[str, Any]:
        profile = self.agents[alias]
        profile.capabilities = [c for c in profile.capabilities if c != capability]
        return profile.to_dict()

    def add_context_access(self, alias: str, context_name: str, *, shared: bool = False, activate: bool = False) -> Dict[str, Any]:
        if context_name not in self.environment.contexts:
            raise KeyError(f"unknown context: {context_name}")
        profile = self.agents[alias]
        if context_name not in profile.accessible_contexts:
            profile.accessible_contexts.append(context_name)
        if shared and context_name not in profile.shared_contexts:
            profile.shared_contexts.append(context_name)
        self.environment.contexts[context_name].include(self._element(alias).snapshot())
        if activate:
            profile.active_context = context_name
        return profile.to_dict()

    def remove_context_access(self, alias: str, context_name: str) -> Dict[str, Any]:
        profile = self.agents[alias]
        profile.accessible_contexts = [c for c in profile.accessible_contexts if c != context_name]
        profile.shared_contexts = [c for c in profile.shared_contexts if c != context_name]
        if profile.active_context == context_name:
            profile.active_context = profile.accessible_contexts[0] if profile.accessible_contexts else next(iter(self.environment.contexts.keys()))
        return profile.to_dict()

    def bind_interface(self, alias: str, interface_name: str, *, realm: str = "logical", context_name: Optional[str] = None,
                       mode: str = "internal", shared: bool = False, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        profile = self.agents[alias]
        ctx_name = context_name or profile.active_context
        if ctx_name not in self.environment.contexts:
            raise KeyError(f"unknown context: {ctx_name}")
        binding = InterfaceBinding(name=interface_name, realm=realm, context_name=ctx_name, mode=mode, shared=shared, metadata=dict(metadata or {}))
        profile.interfaces[interface_name] = binding
        self.add_context_access(alias, ctx_name, shared=shared)
        return binding.to_dict()

    def unbind_interface(self, alias: str, interface_name: str) -> Dict[str, Any]:
        profile = self.agents[alias]
        binding = profile.interfaces.pop(interface_name, None)
        return {"removed": None if binding is None else binding.to_dict()}

    def interfaces(self, alias: str) -> List[Dict[str, Any]]:
        return [b.to_dict() for b in self.agents[alias].interfaces.values()]

    def allow_action(self, *, rule_id: str, role: Optional[str], action_type: str, context_name: Optional[str] = None,
                     capability: Optional[str] = None, situation_label: Optional[str] = None,
                     interface_name: Optional[str] = None, interface_realm: Optional[str] = None,
                     description: str = "", priority: int = 10) -> Dict[str, Any]:
        self.gateway.policy_engine.allow(rule_id, action_type, role=role, context_name=context_name, capability=capability,
                                         situation_label=situation_label, interface_name=interface_name, interface_realm=interface_realm,
                                         description=description, priority=priority)
        return self.gateway.policy_engine.snapshot()

    def deny_action(self, *, rule_id: str, role: Optional[str], action_type: str, context_name: Optional[str] = None,
                    capability: Optional[str] = None, situation_label: Optional[str] = None,
                    interface_name: Optional[str] = None, interface_realm: Optional[str] = None,
                    description: str = "", priority: int = 100) -> Dict[str, Any]:
        self.gateway.policy_engine.deny(rule_id, action_type, role=role, context_name=context_name, capability=capability,
                                        situation_label=situation_label, interface_name=interface_name, interface_realm=interface_realm,
                                        description=description, priority=priority)
        return self.gateway.policy_engine.snapshot()

    def governance(self) -> Dict[str, Any]:
        return self.gateway.policy_engine.snapshot()

    def accessible_contexts(self, alias: str) -> List[str]:
        profile = self.agents[alias]
        ordered = [profile.active_context] + profile.accessible_contexts + profile.shared_contexts
        out: List[str] = []
        for ctx in ordered:
            if ctx in self.environment.contexts and ctx not in out:
                out.append(ctx)
        return out or [profile.active_context]

    def scope_packet(self, alias: str) -> AgentScopePacket:
        profile = self.agents[alias]
        situation_map = {ctx: self.environment.compute_situation(self.environment.contexts[ctx]).to_dict() for ctx in self.accessible_contexts(alias)}
        topology = {ctx: self.environment.contexts[ctx].topology() for ctx in self.accessible_contexts(alias)}
        return AgentScopePacket(packet_id=str(uuid.uuid4()), agent=profile.to_dict(), active_context=profile.active_context,
                                accessible_contexts=self.accessible_contexts(alias), shared_contexts=list(profile.shared_contexts),
                                interfaces=self.interfaces(alias), situation_map=situation_map, topology=topology)

    def _resolve_interface(self, alias: str, interface_name: Optional[str]) -> Optional[InterfaceBinding]:
        if interface_name is None:
            return None
        profile = self.agents[alias]
        if interface_name not in profile.interfaces:
            raise KeyError(f"unknown interface {interface_name} for {alias}")
        return profile.interfaces[interface_name]

    def _context_for(self, alias: str, context_name: Optional[str] = None, interface_name: Optional[str] = None) -> str:
        profile = self.agents[alias]
        if interface_name is not None:
            binding = self._resolve_interface(alias, interface_name)
            ctx_name = binding.context_name
        else:
            ctx_name = context_name or profile.active_context
        if ctx_name not in self.accessible_contexts(alias):
            raise PermissionError(f"agent {alias} has no access to context {ctx_name}")
        return ctx_name

    def _situation_guard(self, alias: str, action_type: str, context_name: str) -> Optional[str]:
        profile = self.agents[alias]
        context = self.environment.contexts[context_name]
        situation = self.environment.compute_situation(context)
        action = context._actions.get(action_type)
        if action is None:
            return None
        if situation.label == "critical" and action.category in {ActionCategory.COMMAND, ActionCategory.TRANSITION}:
            privileged_roles = {"admin", "controller"}
            if profile.role not in privileged_roles and "critical" not in profile.capabilities:
                return f"critical situation restricts state-changing action {action_type} for role {profile.role}"
        return None

    def evaluate_policy(self, alias: str, action_type: str, *, context_name: Optional[str] = None, interface_name: Optional[str] = None) -> PolicyDecision:
        profile = self.agents[alias]
        ctx_name = self._context_for(alias, context_name, interface_name)
        binding = self._resolve_interface(alias, interface_name) if interface_name else None
        situation = self.environment.compute_situation(self.environment.contexts[ctx_name])
        decision = self.gateway.policy_engine.evaluate(
            role=profile.role,
            action_type=action_type,
            context_name=ctx_name,
            explicit_capabilities=profile.capabilities,
            situation_label=situation.label,
            interface_name=None if binding is None else binding.name,
            interface_realm=None if binding is None else binding.realm,
        )
        guard = self._situation_guard(alias, action_type, ctx_name)
        if guard:
            decision.allowed = False
            decision.reasons.append(guard)
            decision.matched_rules.append("situation-guard")
        return decision

    async def spawn(self, alias: str, *, role: str = "operator", kind: str = "agent", context_name: Optional[str] = None,
                    capabilities: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None) -> AgentProfile:
        if alias in self.agents:
            raise ValueError(f"agent alias already exists: {alias}")
        element = AgentElement(alias, kind=kind, role=role)
        await self.environment.admit(element)
        default_context = context_name or next(iter(self.environment.contexts.keys()))
        for context in self.environment.contexts.values():
            context.include(element.snapshot())
        return self.register_existing(alias, element, role=role, context_name=default_context, capabilities=capabilities, metadata=metadata)

    def register_existing(self, alias: str, element: Element, *, role: Optional[str] = None, context_name: Optional[str] = None,
                          capabilities: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None) -> AgentProfile:
        if alias in self.agents:
            raise ValueError(f"agent alias already exists: {alias}")
        if role is not None:
            element.properties["role"] = role
        element.properties["alias"] = alias
        default_context = context_name or next(iter(self.environment.contexts.keys()))
        session_id = self.gateway.open_session(alias, default_context)
        role_name = element.properties.get("role", "operator")
        inherited_caps = sorted(self.gateway.policy_engine.capabilities_for(role_name, capabilities)) if capabilities is None else list(capabilities)
        profile = AgentProfile(
            alias=alias,
            element_id=element.element_id,
            role=role_name,
            kind=element.kind,
            active_context=default_context,
            session_id=session_id,
            capabilities=inherited_caps,
            accessible_contexts=[default_context],
            shared_contexts=[],
            interfaces={},
            metadata=dict(metadata or {}),
        )
        self.agents[alias] = profile
        return profile

    def _element(self, alias: str) -> Element:
        profile = self.agents[alias]
        return self.environment.elements[profile.element_id]

    def set_role(self, alias: str, role: str) -> AgentProfile:
        profile = self.agents[alias]
        element = self._element(alias)
        element.properties["role"] = role
        profile.role = role
        return profile

    def focus(self, alias: str, context_name: str) -> AgentProfile:
        if context_name not in self.environment.contexts:
            raise KeyError(f"unknown context: {context_name}")
        self.add_context_access(alias, context_name)
        profile = self.agents[alias]
        profile.active_context = context_name
        self.environment.contexts[context_name].include(self._element(alias).snapshot())
        return profile

    def share_context(self, context_name: str, aliases: List[str]) -> Dict[str, Any]:
        for alias in aliases:
            self.add_context_access(alias, context_name, shared=True)
        return {"context": context_name, "shared_with": aliases}

    def create_group(self, name: str, members: List[str], *, shared_contexts: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if name in self.groups:
            raise ValueError(f"group already exists: {name}")
        for alias in members:
            if alias not in self.agents:
                raise KeyError(f"unknown agent: {alias}")
        profile = GroupProfile(name=name, members=list(dict.fromkeys(members)), shared_contexts=list(shared_contexts or []), metadata=dict(metadata or {}))
        self.groups[name] = profile
        self.environment.semantic_graph.upsert_node(name, "group", ["group", name], dynamic_state={"member_count": len(profile.members)}, quality={"shared_contexts": float(len(profile.shared_contexts))})
        for ctx in profile.shared_contexts:
            self.share_context(ctx, profile.members)
        for alias in profile.members:
            self.environment.semantic_graph.connect(name, self.agents[alias].element_id, "group_member", payload={"group": name}, precision=0.95)
        return profile.to_dict()

    def add_group_member(self, group_name: str, alias: str) -> Dict[str, Any]:
        if alias not in self.agents:
            raise KeyError(f"unknown agent: {alias}")
        group = self.groups[group_name]
        if alias not in group.members:
            group.members.append(alias)
            self.environment.semantic_graph.upsert_node(group_name, "group", ["group", group_name], dynamic_state={"member_count": len(group.members)}, quality={"shared_contexts": float(len(group.shared_contexts))})
            self.environment.semantic_graph.connect(group_name, self.agents[alias].element_id, "group_member", payload={"group": group_name}, precision=0.95)
            for ctx in group.shared_contexts:
                self.add_context_access(alias, ctx, shared=True)
        return group.to_dict()

    def remove_group_member(self, group_name: str, alias: str) -> Dict[str, Any]:
        group = self.groups[group_name]
        group.members = [a for a in group.members if a != alias]
        self.environment.semantic_graph.upsert_node(group_name, "group", ["group", group_name], dynamic_state={"member_count": len(group.members)}, quality={"shared_contexts": float(len(group.shared_contexts))})
        return group.to_dict()

    def group_scope(self, group_name: str) -> GroupScopePacket:
        group = self.groups[group_name]
        scopes = {alias: self.scope_packet(alias).__dict__ for alias in group.members}
        topo: Dict[str, Dict[str, float]] = {}
        for alias in group.members:
            for ctx in self.accessible_contexts(alias):
                topo.setdefault(ctx, self.environment.contexts[ctx].topology())
        return GroupScopePacket(packet_id=str(uuid.uuid4()), group=group.to_dict(), member_scopes=scopes, topology=topo)

    def describe_groups(self) -> List[Dict[str, Any]]:
        return [g.to_dict() for g in self.groups.values()]

    def group_recommend(self, group_name: str, *, context_name: Optional[str] = None, interface_name: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        group = self.groups[group_name]
        out: List[Dict[str, Any]] = []
        for alias in group.members:
            for rec in self.recommend(alias, context_name=context_name, interface_name=interface_name, payload=payload):
                item = dict(rec)
                item["agent"] = alias
                out.append(item)
        out.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return {"group": group_name, "recommendations": out}

    def delegate(self, delegator: str, delegatee: str, action_type: str, payload: Optional[Dict[str, Any]] = None, *, context_name: Optional[str] = None, interface_name: Optional[str] = None) -> Dict[str, Any]:
        payload = dict(payload or {})
        ctx_name = self._context_for(delegatee, context_name, interface_name)
        decision = self.evaluate_policy(delegatee, action_type, context_name=ctx_name, interface_name=interface_name)
        accepted = bool(decision.allowed)
        record = DelegationRecord(
            delegation_id=str(uuid.uuid4()),
            delegator=delegator,
            delegatee=delegatee,
            action_type=action_type,
            context_name=ctx_name,
            payload=payload,
            accepted=accepted,
            reason="; ".join(decision.reasons),
        )
        self.delegations.append(record)
        self.environment.semantic_graph.connect(self.agents[delegator].element_id, self.agents[delegatee].element_id, "delegates_to", payload={"action_type": action_type, "accepted": accepted, "context": ctx_name}, precision=0.9 if accepted else 0.4)
        return {"delegation": record.to_dict(), "policy": decision.to_dict()}

    def consensus(self, group_name: str, action_type: str, payload: Optional[Dict[str, Any]] = None, *, context_name: Optional[str] = None, threshold: float = 0.5, interface_name: Optional[str] = None, weighted: bool = False) -> ConsensusPacket:
        payload = dict(payload or {})
        group = self.groups[group_name]
        voters: List[Dict[str, Any]] = []
        approved_aliases: List[str] = []
        total_weight = 0.0
        approved_weight = 0.0
        for alias in group.members:
            ctx_name = self._context_for(alias, context_name, interface_name)
            weight = self._group_weight(group_name, alias) if weighted else 1.0
            total_weight += weight
            policy = self.evaluate_policy(alias, action_type, context_name=ctx_name, interface_name=interface_name)
            whynot = self.whynot(alias, action_type, context_name=ctx_name, interface_name=interface_name, payload=payload)
            admissible = len(whynot.get("reasons", [])) == 0
            score = self._action_score(alias, action_type, context_name=ctx_name, interface_name=interface_name, payload=payload)
            acceptable = policy.allowed and admissible
            if acceptable:
                approved_aliases.append(alias)
                approved_weight += weight
            voters.append({
                "agent": alias,
                "context": ctx_name,
                "policy_allowed": policy.allowed,
                "admissible": admissible,
                "score": score,
                "weight": weight,
                "reasons": whynot.get("reasons", []) + ([] if policy.allowed else policy.reasons),
            })
        ratio = (approved_weight / total_weight) if total_weight > 0 else 0.0
        selected_actor = None
        if approved_aliases:
            ranked: List[Tuple[float, str]] = []
            for alias in approved_aliases:
                score = self._action_score(alias, action_type, context_name=context_name, interface_name=interface_name, payload=payload)
                weight = self._group_weight(group_name, alias) if weighted else 1.0
                ranked.append((score * weight, alias))
            ranked.sort(reverse=True)
            selected_actor = ranked[0][1]
        packet = ConsensusPacket(packet_id=str(uuid.uuid4()), group=group_name, action_type=action_type, context_name=context_name or "*", threshold=threshold, voters=voters, approved=(ratio >= threshold), selected_actor=selected_actor)
        if selected_actor is not None:
            self.environment.semantic_graph.connect(group_name, self.agents[selected_actor].element_id, "consensus_selects", payload={"action_type": action_type, "approved": packet.approved, "threshold": threshold, "weighted": weighted}, precision=ratio)
        return packet

    async def group_execute(self, group_name: str, action_type: str, payload: Optional[Dict[str, Any]] = None, *, context_name: Optional[str] = None, threshold: float = 0.5, interface_name: Optional[str] = None, weighted: bool = False) -> Dict[str, Any]:
        packet = self.consensus(group_name, action_type, payload, context_name=context_name, threshold=threshold, interface_name=interface_name, weighted=weighted)
        response: Dict[str, Any] = {"consensus": packet.__dict__}
        if packet.approved and packet.selected_actor is not None:
            response["execution"] = await self.execute(packet.selected_actor, action_type, payload, context_name=context_name, interface_name=interface_name)
        return response

    async def fanout(self, group_name: str, action_type: str, payload: Optional[Dict[str, Any]] = None, *, context_name: Optional[str] = None, interface_name: Optional[str] = None) -> Dict[str, Any]:
        group = self.groups[group_name]
        results = []
        for alias in group.members:
            try:
                res = await self.execute(alias, action_type, dict(payload or {}), context_name=context_name, interface_name=interface_name)
            except Exception as exc:
                res = {"agent": alias, "status": "error", "error": str(exc)}
            results.append(res)
        return {"group": group_name, "fanout": results}

    def negotiate(self, group_name: str, action_type: str, payload: Optional[Dict[str, Any]] = None, *, context_name: Optional[str] = None, interface_name: Optional[str] = None, threshold: float = 0.5) -> NegotiationPacket:
        payload = dict(payload or {})
        group = self.groups[group_name]
        proposals: List[NegotiationProposal] = []
        tally: Dict[str, float] = {}
        for alias in group.members:
            ctx_name = self._context_for(alias, context_name, interface_name)
            decision = self.evaluate_policy(alias, action_type, context_name=ctx_name, interface_name=interface_name)
            why = self.whynot(alias, action_type, context_name=ctx_name, interface_name=interface_name, payload=payload)
            acceptable = decision.allowed and not why.get("reasons")
            score = self._action_score(alias, action_type, context_name=ctx_name, interface_name=interface_name, payload=payload)
            pref = alias if acceptable else None
            proposal = NegotiationProposal(agent=alias, context_name=ctx_name, action_type=action_type, score=score, acceptable=acceptable, reasons=(why.get("reasons", []) + ([] if decision.allowed else decision.reasons)), preferred_executor=pref)
            proposals.append(proposal)
            if pref:
                tally[pref] = tally.get(pref, 0.0) + score * self._group_weight(group_name, alias)
        selected_actor = None
        agreed = False
        if tally:
            selected_actor = max(tally.items(), key=lambda kv: kv[1])[0]
            total = sum(self._group_weight(group_name, a) for a in group.members) or 1.0
            support = sum(self._group_weight(group_name, p.agent) for p in proposals if p.acceptable and p.preferred_executor == selected_actor) / total
            agreed = support >= threshold
        if selected_actor:
            self.environment.semantic_graph.connect(group_name, self.agents[selected_actor].element_id, "negotiates_for", payload={"action_type": action_type, "agreed": agreed}, precision=max(tally.values()) if tally else 0.0)
        return NegotiationPacket(packet_id=str(uuid.uuid4()), group=group_name, action_type=action_type, context_name=context_name or "*", proposals=[p.to_dict() for p in proposals], selected_actor=selected_actor, agreed=agreed)

    async def execute_plan(self, plan: TaskPlan) -> PlanExecutionPacket:
        results: List[Dict[str, Any]] = []
        success = True
        for step in plan.steps:
            if step.mode == "single":
                if step.actor is None:
                    raise ValueError(f"step {step.step_id} requires actor")
                res = await self.execute(step.actor, step.action_type, dict(step.payload), context_name=step.context_name, interface_name=step.interface_name)
            elif step.mode == "group":
                if step.group is None:
                    raise ValueError(f"step {step.step_id} requires group")
                res = await self.group_execute(step.group, step.action_type, dict(step.payload), context_name=step.context_name, threshold=step.threshold, interface_name=step.interface_name, weighted=True)
            elif step.mode == "fanout":
                if step.group is None:
                    raise ValueError(f"step {step.step_id} requires group")
                res = await self.fanout(step.group, step.action_type, dict(step.payload), context_name=step.context_name, interface_name=step.interface_name)
            elif step.mode == "negotiate":
                if step.group is None:
                    raise ValueError(f"step {step.step_id} requires group")
                packet = self.negotiate(step.group, step.action_type, dict(step.payload), context_name=step.context_name, interface_name=step.interface_name, threshold=step.threshold)
                res = {"negotiation": packet.__dict__}
                if packet.agreed and packet.selected_actor:
                    res["execution"] = await self.execute(packet.selected_actor, step.action_type, dict(step.payload), context_name=step.context_name, interface_name=step.interface_name)
            else:
                raise ValueError(f"unknown step mode: {step.mode}")
            results.append({"step": step.to_dict(), "result": res})
            step_ok = True
            if isinstance(res, dict):
                if "status" in res and res.get("status") != "success":
                    step_ok = False
                if "execution" in res and isinstance(res["execution"], dict) and res["execution"].get("status") not in (None, "success"):
                    step_ok = False
            success = success and step_ok
            if not step_ok:
                break
        return PlanExecutionPacket(packet_id=str(uuid.uuid4()), plan=plan.to_dict(), results=results, success=success)

    def export_runtime_state(self) -> RuntimeStatePacket:
        return RuntimeStatePacket(packet_id=str(uuid.uuid4()), environment_id=self.environment.environment_id, agents=self.describe_agents(), groups=self.describe_groups(), policy=self.governance(), journal=self.environment.memory.event_journal(), graph=self.environment.semantic_graph.export())

    def merge_runtime_state(self, packet: RuntimeStatePacket) -> Dict[str, Any]:
        local_ids = {a["alias"]: a for a in self.describe_agents()}
        merged_agents = 0
        for agent in packet.agents:
            alias = agent.get("alias")
            if alias and alias not in local_ids:
                self.peers_hint(alias, agent)
                merged_agents += 1
        merged_groups = 0
        for group in packet.groups:
            name = group.get("name")
            if not name:
                continue
            if name not in self.groups:
                self.groups[name] = GroupProfile(name=name, members=list(group.get("members", [])), shared_contexts=list(group.get("shared_contexts", [])), metadata=dict(group.get("metadata", {})))
                merged_groups += 1
            else:
                current = self.groups[name]
                current.members = list(dict.fromkeys(current.members + list(group.get("members", []))))
                current.shared_contexts = list(dict.fromkeys(current.shared_contexts + list(group.get("shared_contexts", []))))
                current.metadata.update(group.get("metadata", {}))
        # smarter journal merge by sequence_number then id uniqueness
        existing_seq = max([e.get("sequence_number", 0) for e in self.environment.memory.event_journal()] or [0])
        filtered = [j for j in packet.journal if j.get("sequence_number", 0) > 0]
        filtered.sort(key=lambda j: (j.get("sequence_number", 0), j.get("event", {}).get("occurred_at", 0.0)))
        other_memory = CausalMemory.from_dict({
            "events": [j.get("event", j) for j in filtered],
            "reactions": [j.get("reaction") for j in filtered if j.get("reaction") is not None],
            "interactions": [],
            "phenomena": [],
        })
        mem_report = self.environment.merge_memory(other_memory)
        graph_report = self.environment.semantic_graph.merge_export(packet.graph)
        return {
            "merged_agents": merged_agents,
            "merged_groups": merged_groups,
            "merged_events": mem_report.get("events", 0),
            "merged_reactions": mem_report.get("reactions", 0),
            "merged_nodes": graph_report.get("nodes", 0),
            "merged_edges": graph_report.get("edges", 0),
            "local_high_watermark": existing_seq,
        }

    def peers_hint(self, alias: str, agent: Dict[str, Any]) -> None:
        self.gateway.peers[alias] = {"capabilities": list(agent.get("capabilities", [])), "registered_at": time.time(), "hint": agent}

    def describe_agents(self) -> List[Dict[str, Any]]:
        return [profile.to_dict() for profile in self.agents.values()]

    async def execute(self, alias: str, action_type: str, payload: Optional[Dict[str, Any]] = None, *, context_name: Optional[str] = None,
                      interface_name: Optional[str] = None) -> Dict[str, Any]:
        payload = dict(payload or {})
        profile = self.agents[alias]
        element = self._element(alias)
        ctx_name = self._context_for(alias, context_name, interface_name)
        decision = self.evaluate_policy(alias, action_type, context_name=ctx_name, interface_name=interface_name)
        if not decision.allowed:
            return {
                "agent": alias,
                "role": profile.role,
                "context": ctx_name,
                "interface": interface_name,
                "status": "policy_denied",
                "action_type": action_type,
                "policy": decision.to_dict(),
            }
        context = self.environment.contexts[ctx_name]
        correlation_id = str(uuid.uuid4())
        reaction = await self.environment.dispatch(element, action_type, payload, context, correlation_id=correlation_id)
        profile.active_context = ctx_name
        return {
            "agent": alias,
            "role": profile.role,
            "context": ctx_name,
            "interface": interface_name,
            "correlation_id": correlation_id,
            "reaction_id": reaction.reaction_id,
            "reaction_type": reaction.type,
            "status": reaction.status.value,
            "message": reaction.message,
            "result": reaction.result,
            "policy": decision.to_dict(),
        }

    def recommend(self, alias: str, *, context_name: Optional[str] = None, interface_name: Optional[str] = None,
                  payload: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        profile = self.agents[alias]
        if context_name == "*":
            contexts = self.accessible_contexts(alias)
        else:
            contexts = [self._context_for(alias, context_name, interface_name)]
        out: List[Dict[str, Any]] = []
        for ctx_name in contexts:
            ranked = self.gateway.recommend_actions(self._element(alias), ctx_name, payload)
            for r in ranked:
                if self.evaluate_policy(alias, r["action_type"], context_name=ctx_name, interface_name=interface_name).allowed:
                    item = dict(r)
                    item["context_name"] = ctx_name
                    out.append(item)
        out.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return out

    def whynot(self, alias: str, action_type: str, *, context_name: Optional[str] = None, interface_name: Optional[str] = None,
               payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        profile = self.agents[alias]
        ctx_name = self._context_for(alias, context_name, interface_name)
        result = self.gateway.whynot(self._element(alias), ctx_name, action_type, payload)
        decision = self.evaluate_policy(alias, action_type, context_name=ctx_name, interface_name=interface_name)
        if not decision.allowed:
            result.setdefault("policy", decision.to_dict())
            result.setdefault("reasons", [])
            result["reasons"].extend(decision.reasons)
        return result

    def envelope(self, alias: str, *, context_name: Optional[str] = None, interface_name: Optional[str] = None,
                 payload: Optional[Dict[str, Any]] = None) -> ContextEnvelope:
        profile = self.agents[alias]
        ctx_name = self._context_for(alias, context_name, interface_name)
        return self.gateway.envelope(self._element(alias), self.environment.contexts[ctx_name], payload)

    def send(self, sender: str, recipient: str, topic: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = dict(payload or {})
        profile = self.agents[sender]
        if "message" not in profile.capabilities:
            return {"status": "policy_denied", "reason": f"agent {sender} lacks messaging capability"}
        msg = AgentMessage(message_id=str(uuid.uuid4()), sender=sender, recipient=recipient, topic=topic, payload=payload)
        self.messages.append(msg)
        target = self._element(recipient)
        if hasattr(target, "deliver"):
            target.deliver(msg)
        else:
            mailbox = target.dynamic.setdefault("agent_inbox", [])
            mailbox.append(msg.to_dict())
        source = self._element(sender)
        if hasattr(source, "outbox"):
            source.outbox.append(msg.to_dict())
        else:
            source.dynamic.setdefault("agent_outbox", []).append(msg.to_dict())
        self.environment.semantic_graph.connect(self.agents[sender].element_id, self.agents[recipient].element_id, "agent_message", payload={"topic": topic}, precision=0.9)
        return msg.to_dict()

    def inbox(self, alias: str) -> List[Dict[str, Any]]:
        element = self._element(alias)
        return list(getattr(element, "inbox", element.dynamic.get("agent_inbox", [])))

    def outbox(self, alias: str) -> List[Dict[str, Any]]:
        element = self._element(alias)
        return list(getattr(element, "outbox", element.dynamic.get("agent_outbox", [])))


__all__ = [
    "ContextEnvelope",
    "StateSnapshot",
    "StateDelta",
    "MepCard",
    "WorldPacket",
    "CertaintyPacket",
    "CausalityPacket",
    "DistributedHello",
    "DistributedSyncPacket",
    "ReplayResponse",
    "ResyncRequest",
    "ResyncResponse",
    "MergeReport",
    "GovernancePacket",
    "InterfaceBinding",
    "AgentScopePacket",
    "GroupProfile",
    "DelegationRecord",
    "ConsensusPacket",
    "GroupScopePacket",
    "NegotiationProposal",
    "NegotiationPacket",
    "TaskStep",
    "TaskPlan",
    "PlanExecutionPacket",
    "RuntimeStatePacket",
    "AgentProfile",
    "AgentMessage",
    "AgentElement",
    "MultiAgentRuntime",
    "MepGateway",
]


# Strict / canonical protocol layer -------------------------------------------

@dataclass
class ProtocolHeader:
    packet_type: str
    schema_version: str = "1.0"
    packet_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    emitted_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "packet_type": self.packet_type,
            "schema_version": self.schema_version,
            "packet_id": self.packet_id,
            "emitted_at": self.emitted_at,
        }


@dataclass
class CanonicalPacket:
    header: ProtocolHeader
    body: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"header": self.header.to_dict(), "body": dict(self.body)}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)


@dataclass
class EnvironmentCard:
    environment_id: str
    name: str
    protocol_version: str
    contexts: List[Dict[str, Any]]
    capabilities: List[str]
    topology: Dict[str, Dict[str, float]]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "name": self.name,
            "protocol_version": self.protocol_version,
            "contexts": list(self.contexts),
            "capabilities": list(self.capabilities),
            "topology": dict(self.topology),
            "metadata": dict(self.metadata),
        }


@dataclass
class AgentCard:
    alias: str
    element_id: str
    role: str
    active_context: str
    accessible_contexts: List[str]
    shared_contexts: List[str]
    capabilities: List[str]
    interfaces: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alias": self.alias,
            "element_id": self.element_id,
            "role": self.role,
            "active_context": self.active_context,
            "accessible_contexts": list(self.accessible_contexts),
            "shared_contexts": list(self.shared_contexts),
            "capabilities": list(self.capabilities),
            "interfaces": dict(self.interfaces),
            "metadata": dict(self.metadata),
        }


class ProtocolCodec:
    REQUIRED_BODY = {
        "world": {"snapshot", "contexts", "topology"},
        "certainty": {"facts", "belief", "factor_graph"},
        "causality": {"correlation_id", "trace"},
        "governance": {"policy"},
        "scope": {"agent", "contexts"},
        "runtime": {"environment_id", "agents", "groups", "policy"},
        "environment.card": {"environment_id", "name", "contexts", "capabilities", "topology"},
        "agent.card": {"alias", "element_id", "role", "active_context", "accessible_contexts", "capabilities"},
    }

    @classmethod
    def pack(cls, packet_type: str, body: Dict[str, Any], *, schema_version: str = "1.0") -> CanonicalPacket:
        packet = CanonicalPacket(header=ProtocolHeader(packet_type=packet_type, schema_version=schema_version), body=body)
        cls.validate(packet)
        return packet

    @classmethod
    def validate(cls, packet: CanonicalPacket | Dict[str, Any]) -> Dict[str, Any]:
        payload = packet.to_dict() if isinstance(packet, CanonicalPacket) else dict(packet)
        header = payload.get("header", {})
        body = payload.get("body", {})
        missing_header = [k for k in ("packet_type", "schema_version", "packet_id", "emitted_at") if k not in header]
        if missing_header:
            raise ValueError(f"protocol header missing keys: {missing_header}")
        packet_type = str(header.get("packet_type"))
        required = cls.REQUIRED_BODY.get(packet_type, set())
        missing_body = [k for k in required if k not in body]
        if missing_body:
            raise ValueError(f"protocol body missing keys for {packet_type}: {missing_body}")
        return payload

    @classmethod
    def unpack(cls, raw: str | Dict[str, Any]) -> CanonicalPacket:
        payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
        cls.validate(payload)
        h = payload["header"]
        return CanonicalPacket(
            header=ProtocolHeader(packet_type=h["packet_type"], schema_version=h["schema_version"], packet_id=h["packet_id"], emitted_at=float(h["emitted_at"])),
            body=dict(payload.get("body", {})),
        )


def _gateway_environment_card(self: MepGateway) -> EnvironmentCard:
    contexts = []
    topology = {}
    for ctx in self.environment.contexts.values():
        contexts.append({
            "id": ctx.context_id,
            "name": ctx.name,
            "kind": ctx.kind.value,
            "basis": ctx.basis.to_dict(),
        })
        topology[ctx.name] = ctx.topology()
    return EnvironmentCard(
        environment_id=self.environment.environment_id,
        name=self.environment.name,
        protocol_version="1.0",
        contexts=contexts,
        capabilities=["world", "certainty", "causality", "governance", "runtime", "multi-agent"],
        topology=topology,
        metadata={"kind": self.environment.kind.value},
    )


def _runtime_agent_card(self: MultiAgentRuntime, alias: str) -> AgentCard:
    profile = self.agents[alias]
    return AgentCard(
        alias=profile.alias,
        element_id=profile.element_id,
        role=profile.role,
        active_context=profile.active_context,
        accessible_contexts=list(profile.accessible_contexts),
        shared_contexts=list(profile.shared_contexts),
        capabilities=list(profile.capabilities),
        interfaces={k: v.to_dict() for k, v in profile.interfaces.items()},
        metadata=dict(profile.metadata),
    )


def _runtime_scope_packet_canonical(self: MultiAgentRuntime, alias: str) -> CanonicalPacket:
    scope = self.scope_packet(alias)
    return ProtocolCodec.pack("scope", {
        "agent": scope.agent,
        "active_context": scope.active_context,
        "contexts": scope.contexts,
        "shared_contexts": scope.shared_contexts,
        "interfaces": scope.interfaces,
        "situations": scope.situations,
        "topology": scope.topology,
    })


MepGateway.environment_card = _gateway_environment_card
MultiAgentRuntime.agent_card = _runtime_agent_card
MultiAgentRuntime.scope_packet_canonical = _runtime_scope_packet_canonical

__all__.extend(["ProtocolHeader", "CanonicalPacket", "EnvironmentCard", "AgentCard", "ProtocolCodec"])


# Schema registry / versioned protocol layer ---------------------------------

import hashlib
from dataclasses import dataclass as _proto_dataclass, field as _proto_field
from typing import Tuple as _ProtoTuple


@_proto_dataclass(frozen=True)
class PacketSchema:
    packet_type: str
    version: str
    required_body: tuple[str, ...] = _proto_field(default_factory=tuple)
    optional_body: tuple[str, ...] = _proto_field(default_factory=tuple)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'packet_type': self.packet_type,
            'version': self.version,
            'required_body': list(self.required_body),
            'optional_body': list(self.optional_body),
            'description': self.description,
        }


class ProtocolSchemaRegistry:
    def __init__(self) -> None:
        self._schemas: Dict[_ProtoTuple[str, str], PacketSchema] = {}

    def register(self, schema: PacketSchema) -> PacketSchema:
        self._schemas[(schema.packet_type, schema.version)] = schema
        return schema

    def get(self, packet_type: str, version: str) -> Optional[PacketSchema]:
        return self._schemas.get((packet_type, version))

    def latest(self, packet_type: str) -> Optional[PacketSchema]:
        matches = [s for (ptype, _), s in self._schemas.items() if ptype == packet_type]
        if not matches:
            return None
        return sorted(matches, key=lambda s: tuple(int(x) for x in s.version.split('.')))[-1]

    def export(self) -> Dict[str, Any]:
        out: Dict[str, List[Dict[str, Any]]] = {}
        for schema in sorted(self._schemas.values(), key=lambda s: (s.packet_type, s.version)):
            out.setdefault(schema.packet_type, []).append(schema.to_dict())
        return {'packet_types': out}


PROTOCOL_SCHEMAS = ProtocolSchemaRegistry()


def _register_default_protocol_schemas() -> None:
    defaults = {
        'world': (('snapshot','contexts','topology'), ('delta',), 'environment world view'),
        'certainty': (('facts','belief','factor_graph'), ('certainty_revisions',), 'certainty and belief state'),
        'causality': (('correlation_id','trace'), ('replay','why_not'), 'causal trace'),
        'governance': (('policy',), (), 'governance and policy'),
        'scope': (('agent','active_context','contexts','shared_contexts','interfaces','situations','topology'), (), 'agent scope'),
        'runtime': (('environment_id','agents','groups','policy'), ('journal','graph'), 'runtime state'),
        'environment.card': (('environment_id','name','contexts','capabilities','topology'), ('metadata',), 'environment discovery card'),
        'agent.card': (('alias','element_id','role','active_context','accessible_contexts','capabilities'), ('shared_contexts','interfaces','metadata'), 'agent discovery card'),
        'schema.registry': (('packet_types',), (), 'available protocol schemas'),
        'envx.body': (('environment_id','name','kind','version','state','certainty','belief','contexts','graph','factors','protocol','annotations','history','exports','generated_at'), (), 'canonical environment body'),
    }
    for ptype, (required, optional, description) in defaults.items():
        PROTOCOL_SCHEMAS.register(PacketSchema(packet_type=ptype, version='1.0', required_body=tuple(required), optional_body=tuple(optional), description=description))


if not PROTOCOL_SCHEMAS.export()['packet_types']:
    _register_default_protocol_schemas()


def _canonical_body(body: Dict[str, Any]) -> str:
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _body_digest(body: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_body(body).encode('utf-8')).hexdigest()


def _codec_pack(cls, packet_type: str, body: Dict[str, Any], *, schema_version: str = '1.0') -> CanonicalPacket:
    packet = CanonicalPacket(header=ProtocolHeader(packet_type=packet_type, schema_version=schema_version), body=body)
    payload = packet.to_dict()
    payload['header']['body_digest'] = _body_digest(body)
    cls.validate(payload)
    return CanonicalPacket(
        header=ProtocolHeader(packet_type=payload['header']['packet_type'], schema_version=payload['header']['schema_version'], packet_id=payload['header']['packet_id'], emitted_at=float(payload['header']['emitted_at'])),
        body=body,
    )


def _codec_validate(cls, packet: CanonicalPacket | Dict[str, Any]) -> Dict[str, Any]:
    payload = packet.to_dict() if isinstance(packet, CanonicalPacket) else dict(packet)
    header = dict(payload.get('header', {}))
    body = dict(payload.get('body', {}))
    missing_header = [k for k in ('packet_type','schema_version','packet_id','emitted_at') if k not in header]
    if missing_header:
        raise ValueError(f'protocol header missing keys: {missing_header}')
    packet_type = str(header['packet_type'])
    version = str(header.get('schema_version', '1.0'))
    schema = PROTOCOL_SCHEMAS.get(packet_type, version) or PROTOCOL_SCHEMAS.latest(packet_type)
    if schema is None:
        raise ValueError(f'unknown protocol schema: {packet_type}@{version}')
    missing_body = [k for k in schema.required_body if k not in body]
    if missing_body:
        raise ValueError(f'protocol body missing keys for {packet_type}@{schema.version}: {missing_body}')
    if 'body_digest' in header:
        expected = _body_digest(body)
        if header['body_digest'] != expected:
            raise ValueError('protocol body digest mismatch')
    return {'header': header, 'body': body, 'schema': schema.to_dict()}


def _codec_unpack(cls, raw: str | Dict[str, Any]) -> CanonicalPacket:
    payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
    cls.validate(payload)
    h = payload['header']
    return CanonicalPacket(header=ProtocolHeader(packet_type=h['packet_type'], schema_version=h['schema_version'], packet_id=h['packet_id'], emitted_at=float(h['emitted_at'])), body=dict(payload.get('body', {})))


def _codec_schema_packet(cls) -> CanonicalPacket:
    return cls.pack('schema.registry', PROTOCOL_SCHEMAS.export())


def _codec_export_schemas(cls) -> Dict[str, Any]:
    return PROTOCOL_SCHEMAS.export()


ProtocolCodec.pack = classmethod(_codec_pack)
ProtocolCodec.validate = classmethod(_codec_validate)
ProtocolCodec.unpack = classmethod(_codec_unpack)
ProtocolCodec.schema_packet = classmethod(_codec_schema_packet)
ProtocolCodec.export_schemas = classmethod(_codec_export_schemas)
ProtocolCodec.schemas = PROTOCOL_SCHEMAS

__all__.extend(['PacketSchema', 'ProtocolSchemaRegistry', 'PROTOCOL_SCHEMAS'])


def _canonicalpacket_to_dict(self: CanonicalPacket) -> Dict[str, Any]:
    header = self.header.to_dict()
    header['body_digest'] = _body_digest(self.body)
    return {'header': header, 'body': dict(self.body)}


def _protocolheader_to_dict(self: ProtocolHeader) -> Dict[str, Any]:
    return {
        'packet_type': self.packet_type,
        'schema_version': self.schema_version,
        'packet_id': self.packet_id,
        'emitted_at': self.emitted_at,
    }

ProtocolHeader.to_dict = _protocolheader_to_dict
CanonicalPacket.to_dict = _canonicalpacket_to_dict


def _gateway_schema_registry_packet(self: MepGateway) -> CanonicalPacket:
    return ProtocolCodec.schema_packet()

MepGateway.schema_registry_packet = _gateway_schema_registry_packet


def _gateway_envx_packet(self: MepGateway) -> CanonicalPacket:
    body = EnvironmentCanonicalBody.from_environment(self.environment).to_dict()
    return ProtocolCodec.pack('envx.body', body)

MepGateway.envx_packet = _gateway_envx_packet


# Cross-validation packets ----------------------------------------------------

@dataclass
class ActionRequestPacket:
    packet_id: str
    actor_alias: str
    element_id: str
    role: str
    action_type: str
    context_name: str
    accessible_contexts: List[str]
    capabilities: List[str]
    payload: Dict[str, Any] = field(default_factory=dict)
    interface_name: Optional[str] = None
    interface_realm: Optional[str] = None
    situation_label: Optional[str] = None
    emitted_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'packet_id': self.packet_id,
            'actor_alias': self.actor_alias,
            'element_id': self.element_id,
            'role': self.role,
            'action_type': self.action_type,
            'context_name': self.context_name,
            'accessible_contexts': list(self.accessible_contexts),
            'capabilities': list(self.capabilities),
            'payload': dict(self.payload),
            'interface_name': self.interface_name,
            'interface_realm': self.interface_realm,
            'situation_label': self.situation_label,
            'emitted_at': self.emitted_at,
        }


@dataclass
class ActionValidationPacket:
    packet_id: str
    request: Dict[str, Any]
    allowed: bool
    context_exists: bool
    context_accessible: bool
    policy_allowed: bool
    situation_allowed: bool
    circumstances_satisfied: bool
    reasons: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    decision: Dict[str, Any] = field(default_factory=dict)
    emitted_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'packet_id': self.packet_id,
            'request': dict(self.request),
            'allowed': self.allowed,
            'context_exists': self.context_exists,
            'context_accessible': self.context_accessible,
            'policy_allowed': self.policy_allowed,
            'situation_allowed': self.situation_allowed,
            'circumstances_satisfied': self.circumstances_satisfied,
            'reasons': list(self.reasons),
            'blockers': list(self.blockers),
            'decision': dict(self.decision),
            'emitted_at': self.emitted_at,
        }


def _runtime_action_request(self: MultiAgentRuntime, alias: str, action_type: str, payload: Optional[Dict[str, Any]] = None, *, context_name: Optional[str] = None, interface_name: Optional[str] = None) -> ActionRequestPacket:
    profile = self.agents[alias]
    ctx_name = self._context_for(alias, context_name, interface_name)
    binding = self._resolve_interface(alias, interface_name) if interface_name else None
    situation = self.environment.compute_situation(self.environment.contexts[ctx_name])
    return ActionRequestPacket(
        packet_id=str(uuid.uuid4()),
        actor_alias=alias,
        element_id=profile.element_id,
        role=profile.role,
        action_type=action_type,
        context_name=ctx_name,
        accessible_contexts=self.accessible_contexts(alias),
        capabilities=list(profile.capabilities),
        payload=dict(payload or {}),
        interface_name=None if binding is None else binding.name,
        interface_realm=None if binding is None else binding.realm,
        situation_label=situation.label,
    )


def _runtime_validate_action_request(self: MultiAgentRuntime, request: ActionRequestPacket) -> ActionValidationPacket:
    reasons: List[str] = []
    blockers: List[str] = []
    context_exists = request.context_name in self.environment.contexts
    context_accessible = request.context_name in self.accessible_contexts(request.actor_alias) if request.actor_alias in self.agents else False
    policy_allowed = False
    situation_allowed = False
    circumstances_satisfied = False
    decision_dict: Dict[str, Any] = {}
    if not context_exists:
        reasons.append(f'unknown context {request.context_name}')
    if context_exists and not context_accessible:
        reasons.append(f'actor {request.actor_alias} has no access to context {request.context_name}')
    if context_exists and context_accessible:
        decision = self.evaluate_policy(request.actor_alias, request.action_type, context_name=request.context_name, interface_name=request.interface_name)
        decision_dict = decision.to_dict()
        policy_allowed = decision.allowed
        if not decision.allowed:
            reasons.extend(decision.reasons)
        guard = self._situation_guard(request.actor_alias, request.action_type, request.context_name)
        situation_allowed = guard is None
        if guard is not None:
            reasons.append(guard)
        context = self.environment.contexts[request.context_name]
        frame = self.environment._build_frame(self._element(request.actor_alias), context, request.payload, correlation_id='validate', causation_id=None, chain_depth=0)
        blockers = context.explain_why_not(request.action_type, frame)
        circumstances_satisfied = len(blockers) == 0
        if blockers:
            reasons.extend(blockers)
    allowed = context_exists and context_accessible and policy_allowed and situation_allowed and circumstances_satisfied
    return ActionValidationPacket(
        packet_id=str(uuid.uuid4()),
        request=request.to_dict(),
        allowed=allowed,
        context_exists=context_exists,
        context_accessible=context_accessible,
        policy_allowed=policy_allowed,
        situation_allowed=situation_allowed,
        circumstances_satisfied=circumstances_satisfied,
        reasons=list(dict.fromkeys(reasons)),
        blockers=blockers,
        decision=decision_dict,
    )


MultiAgentRuntime.action_request = _runtime_action_request
MultiAgentRuntime.validate_action_request = _runtime_validate_action_request

_old_runtime_execute = MultiAgentRuntime.execute
async def _runtime_execute_validated(self: MultiAgentRuntime, alias: str, action_type: str, payload: Optional[Dict[str, Any]] = None, *, context_name: Optional[str] = None, interface_name: Optional[str] = None) -> Dict[str, Any]:
    request = self.action_request(alias, action_type, payload, context_name=context_name, interface_name=interface_name)
    validation = self.validate_action_request(request)
    if not validation.allowed:
        status = 'policy_denied' if (not validation.policy_allowed or not validation.situation_allowed) else 'validation_denied'
        return {
            'agent': alias,
            'role': self.agents[alias].role,
            'context': request.context_name,
            'interface': interface_name,
            'status': status,
            'action_type': action_type,
            'validation': validation.to_dict(),
            'policy': validation.decision,
        }
    result = await _old_runtime_execute(self, alias, action_type, payload, context_name=context_name, interface_name=interface_name)
    result['validation'] = validation.to_dict()
    return result

MultiAgentRuntime.execute = _runtime_execute_validated


def _register_iteration14_protocol_schemas() -> None:
    extras = {
        'distributed.hello': (('agent_id','capabilities'), (), 'distributed peer hello'),
        'distributed.sync': (('source_environment_id','memory_summary','graph_summary'), (), 'distributed sync summary'),
        'distributed.resync.request': (('requester_environment_id','since_sequence'), (), 'resync request'),
        'distributed.resync.response': (('source_environment_id','events','reactions','interactions','phenomena'), ('high_watermark',), 'resync response'),
        'merge.report': (('merged_agents','merged_groups','merged_events','merged_reactions','merged_nodes','merged_edges','local_high_watermark'), (), 'merge report'),
        'action.request': (('actor_alias','element_id','role','action_type','context_name','accessible_contexts','capabilities','payload'), ('interface_name','interface_realm','situation_label'), 'action request with protocol-level constraints'),
        'action.validation': (('request','allowed','context_exists','context_accessible','policy_allowed','situation_allowed','circumstances_satisfied'), ('reasons','blockers','decision'), 'cross-validation result for action request'),
        'plan.execution': (('plan','results','success'), (), 'formal plan execution result'),
        'consensus': (('group','action_type','context_name','votes','selected_actor','agreed'), (), 'group consensus packet'),
        'negotiation': (('group','action_type','context_name','proposals','selected_actor','agreed'), (), 'negotiation packet'),
        'scope.group': (('group','members','shared_contexts','topology'), (), 'group scope packet'),
    }
    for ptype, (required, optional, description) in extras.items():
        if PROTOCOL_SCHEMAS.get(ptype, '1.0') is None:
            PROTOCOL_SCHEMAS.register(PacketSchema(packet_type=ptype, version='1.0', required_body=tuple(required), optional_body=tuple(optional), description=description))

_register_iteration14_protocol_schemas()


def _gateway_action_request_packet(self: MepGateway, runtime: MultiAgentRuntime, alias: str, action_type: str, payload: Optional[Dict[str, Any]] = None, *, context_name: Optional[str] = None, interface_name: Optional[str] = None) -> CanonicalPacket:
    req = runtime.action_request(alias, action_type, payload, context_name=context_name, interface_name=interface_name)
    return ProtocolCodec.pack('action.request', req.to_dict())


def _gateway_action_validation_packet(self: MepGateway, runtime: MultiAgentRuntime, alias: str, action_type: str, payload: Optional[Dict[str, Any]] = None, *, context_name: Optional[str] = None, interface_name: Optional[str] = None) -> CanonicalPacket:
    req = runtime.action_request(alias, action_type, payload, context_name=context_name, interface_name=interface_name)
    val = runtime.validate_action_request(req)
    return ProtocolCodec.pack('action.validation', val.to_dict())

MepGateway.action_request_packet = _gateway_action_request_packet
MepGateway.action_validation_packet = _gateway_action_validation_packet

__all__.extend(['ActionRequestPacket', 'ActionValidationPacket'])

# Iteration 15 — executable formal plans --------------------------------------

@dataclass
class FormalPlanExecutionPacket:
    packet_id: str
    plan_name: str
    ast: Dict[str, Any]
    results: List[Dict[str, Any]]
    success: bool
    emitted_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'packet_id': self.packet_id,
            'plan_name': self.plan_name,
            'ast': dict(self.ast),
            'results': list(self.results),
            'success': self.success,
            'emitted_at': self.emitted_at,
        }


def _runtime_resolve_condition_value(self: MultiAgentRuntime, spec: str, state: Dict[str, Any]) -> Any:
    spec = str(spec).strip()
    if spec.startswith('agent.'):
        parts = spec.split('.')
        if len(parts) >= 3:
            alias = parts[1]
            profile = self.agents.get(alias)
            if profile is None:
                return None
            if parts[2] == 'role':
                return profile.role
            if parts[2] == 'context':
                return profile.active_context
            if parts[2] == 'capabilities':
                return list(profile.capabilities)
            if parts[2] == 'interfaces':
                return list(profile.interfaces.keys())
    if spec.startswith('group.'):
        parts = spec.split('.')
        if len(parts) >= 3:
            group = self.groups.get(parts[1])
            if group is None:
                return None
            if parts[2] == 'size':
                return len(group.members)
            if parts[2] == 'contexts':
                return list(group.shared_contexts)
    if spec.startswith('context.'):
        parts = spec.split('.')
        if len(parts) >= 3:
            ctx = self.environment.contexts.get(parts[1])
            if ctx is None:
                return None
            if parts[2] == 'situation':
                return self.environment.compute_situation(ctx).label
            if parts[2] == 'kind':
                return ctx.kind.value
    if spec.startswith('result.'):
        parts = spec.split('.')
        if len(parts) >= 3:
            entry = state.get('labels', {}).get(parts[1])
            if entry is None:
                return None
            value: Any = entry
            for p in parts[2:]:
                if isinstance(value, dict):
                    value = value.get(p)
                else:
                    return None
            return value
    if spec == 'last.success':
        return state.get('last_success')
    if spec == 'memory.events':
        return len(self.environment.memory.events)
    if spec == 'memory.interactions':
        return len(self.environment.memory.interactions)
    if spec == 'memory.phenomena':
        return len(self.environment.memory.phenomena)
    return spec


def _runtime_evaluate_formal_condition(self: MultiAgentRuntime, condition: Any, state: Dict[str, Any]) -> bool:
    left = _runtime_resolve_condition_value(self, getattr(condition, 'field', ''), state)
    right = getattr(condition, 'value', None)
    op = getattr(condition, 'op', '=')
    if isinstance(left, list) and op == '=':
        return right in left
    if op == '=':
        return left == right
    if op == '!=':
        return left != right
    try:
        if op == '>':
            return float(left) > float(right)
        if op == '<':
            return float(left) < float(right)
        if op == '>=':
            return float(left) >= float(right)
        if op == '<=':
            return float(left) <= float(right)
    except Exception:
        return False
    return False


async def _runtime_execute_formal_node(self: MultiAgentRuntime, node: Any, state: Dict[str, Any]) -> Dict[str, Any]:
    kind = getattr(node, 'kind', '')
    label = getattr(node, 'label', '')
    if kind == 'command':
        cmd = node.command
        if cmd is None:
            return {'kind': 'command', 'label': label, 'success': False, 'error': 'missing command'}
        res: Dict[str, Any]

        async def _execute_with_context_fallback() -> Dict[str, Any]:
            explicit_ctx = cmd.payload.get('ctx') if isinstance(cmd.payload, dict) else None
            if cmd.kind != 'do' or explicit_ctx:
                return await self.execute(cmd.subject, cmd.action, dict(cmd.payload), interface_name=cmd.interface, context_name=explicit_ctx)
            profile = self.agents.get(cmd.subject or '')
            candidate_contexts: List[str] = []
            if profile is not None:
                candidate_contexts.extend([profile.active_context])
                candidate_contexts.extend([c for c in profile.accessible_contexts if c not in candidate_contexts])
            else:
                candidate_contexts.extend(list(self.environment.contexts.keys()))
            last: Dict[str, Any] = {'status': 'validation_denied'}
            for ctx_name in candidate_contexts:
                probe = await self.execute(cmd.subject, cmd.action, dict(cmd.payload), interface_name=cmd.interface, context_name=ctx_name)
                last = probe
                if probe.get('status') == 'success':
                    return probe
            return last

        if cmd.kind == 'do':
            res = await _execute_with_context_fallback()
        elif cmd.kind == 'vote':
            packet = self.consensus(cmd.subject, cmd.action, dict(cmd.payload), context_name=cmd.metadata.get('context') or cmd.payload.get('ctx'), interface_name=cmd.interface, threshold=float(cmd.payload.get('threshold', 0.5)), weighted=bool(cmd.payload.get('weighted', False)))
            res = {'consensus': packet.__dict__}
        elif cmd.kind == 'negotiate':
            packet = self.negotiate(cmd.subject, cmd.action, dict(cmd.payload), context_name=cmd.metadata.get('context') or cmd.payload.get('ctx'), interface_name=cmd.interface, threshold=float(cmd.payload.get('threshold', 0.5)))
            res = {'negotiation': packet.__dict__}
        elif cmd.kind == 'run.group':
            res = await self.group_execute(cmd.subject, cmd.action, dict(cmd.payload), context_name=cmd.payload.get('ctx'), threshold=float(cmd.payload.get('threshold', 0.5)), interface_name=cmd.interface, weighted=bool(cmd.payload.get('weighted', False)))
        elif cmd.kind == 'fanout':
            res = await self.fanout(cmd.subject, cmd.action, dict(cmd.payload), context_name=cmd.payload.get('ctx'), interface_name=cmd.interface)
        elif cmd.kind == 'delegate':
            res = self.delegate(cmd.subject, cmd.target or '', cmd.action or '', dict(cmd.payload), context_name=cmd.payload.get('ctx'))
        else:
            res = {'status': 'unsupported', 'kind': cmd.kind}
        success = True
        if isinstance(res, dict):
            if res.get('status') not in (None, 'success'):
                success = False
            if 'result' in res and isinstance(res['result'], dict) and res['result'].get('status') not in (None, 'success'):
                success = False
        packet = {'kind': 'command', 'label': label, 'command': cmd.to_dict(), 'result': res, 'success': success}
        if label:
            state.setdefault('labels', {})[label] = packet
        state['last_success'] = success
        return packet
    if kind == 'parallel':
        children = getattr(node, 'children', [])
        branch_results = await asyncio.gather(*[_runtime_execute_formal_node(self, child, state) for child in children])
        success = all(bool(r.get('success', True)) for r in branch_results)
        packet = {'kind': 'parallel', 'label': label, 'results': branch_results, 'success': success}
        if label:
            state.setdefault('labels', {})[label] = packet
        state['last_success'] = success
        return packet
    if kind == 'sequence':
        results: List[Dict[str, Any]] = []
        success = True
        for child in getattr(node, 'children', []):
            branch = await _runtime_execute_formal_node(self, child, state)
            results.append(branch)
            success = success and bool(branch.get('success', True))
            if not success:
                break
        packet = {'kind': 'sequence', 'label': label, 'results': results, 'success': success}
        if label:
            state.setdefault('labels', {})[label] = packet
        state['last_success'] = success
        return packet
    if kind == 'if':
        cond = getattr(node, 'condition', None)
        holds = _runtime_evaluate_formal_condition(self, cond, state)
        branch = getattr(node, 'then_branch', []) if holds else getattr(node, 'else_branch', [])
        results = [await _runtime_execute_formal_node(self, child, state) for child in branch]
        success = all(bool(r.get('success', True)) for r in results)
        packet = {'kind': 'if', 'label': label, 'condition': None if cond is None else cond.to_dict(), 'holds': holds, 'branch': 'then' if holds else 'else', 'results': results, 'success': success}
        if label:
            state.setdefault('labels', {})[label] = packet
        state['last_success'] = success
        return packet
    return {'kind': kind, 'label': label, 'success': False, 'error': 'unsupported node'}


async def _runtime_execute_formal_plan(self: MultiAgentRuntime, program: Any) -> FormalPlanExecutionPacket:
    state: Dict[str, Any] = {'labels': {}, 'last_success': True}
    results: List[Dict[str, Any]] = []
    success = True
    for node in getattr(program, 'root', []):
        entry = await _runtime_execute_formal_node(self, node, state)
        results.append(entry)
        success = success and bool(entry.get('success', True))
        if not success:
            break
    return FormalPlanExecutionPacket(packet_id=str(uuid.uuid4()), plan_name=getattr(program, 'name', 'unknown'), ast=program.to_dict(), results=results, success=success)


MultiAgentRuntime.evaluate_formal_condition = _runtime_evaluate_formal_condition
MultiAgentRuntime.execute_formal_plan = _runtime_execute_formal_plan


def _register_iteration15_protocol_schemas() -> None:
    extras = {
        'formal.plan.execution': (('plan_name','ast','results','success'), (), 'execution result for a formal EnvLang plan'),
    }
    for ptype, (required, optional, description) in extras.items():
        if PROTOCOL_SCHEMAS.get(ptype, '1.0') is None:
            PROTOCOL_SCHEMAS.register(PacketSchema(packet_type=ptype, version='1.0', required_body=tuple(required), optional_body=tuple(optional), description=description))

_register_iteration15_protocol_schemas()

__all__.extend(['FormalPlanExecutionPacket'])


# Iteration 16 — formal variables, named output bindings and interpolation -----

def _runtime_resolve_reference_v16(self: MultiAgentRuntime, spec: str, state: Dict[str, Any]) -> Any:
    spec = str(spec).strip()
    if spec.startswith('var.'):
        value: Any = state.get('vars', {})
        for p in spec.split('.')[1:]:
            if isinstance(value, dict):
                value = value.get(p)
            else:
                return None
        return value
    if spec.startswith('result.'):
        parts = spec.split('.')
        value: Any = state.get('labels', {}).get(parts[1]) if len(parts) > 1 else None
        for p in parts[2:]:
            if isinstance(value, dict):
                value = value.get(p)
            else:
                return None
        return value
    return _runtime_resolve_condition_value(self, spec, state)


def _runtime_interpolate_value_v16(self: MultiAgentRuntime, value: Any, state: Dict[str, Any]) -> Any:
    if isinstance(value, str):
        full = re.fullmatch(r'\$\{([^}]+)\}', value.strip())
        if full:
            return _runtime_resolve_reference_v16(self, full.group(1), state)
        def repl(match: re.Match[str]) -> str:
            resolved = _runtime_resolve_reference_v16(self, match.group(1), state)
            return '' if resolved is None else str(resolved)
        return re.sub(r'\$\{([^}]+)\}', repl, value)
    if isinstance(value, dict):
        return {k: _runtime_interpolate_value_v16(self, v, state) for k, v in value.items()}
    if isinstance(value, list):
        return [_runtime_interpolate_value_v16(self, v, state) for v in value]
    return value


def _runtime_evaluate_formal_condition_v16(self: MultiAgentRuntime, condition: Any, state: Dict[str, Any]) -> bool:
    left = _runtime_resolve_reference_v16(self, getattr(condition, 'field', ''), state)
    right = _runtime_interpolate_value_v16(self, getattr(condition, 'value', None), state)
    op = getattr(condition, 'op', '=')
    if isinstance(left, list) and op == '=':
        return right in left
    if op == '=':
        return left == right
    if op == '!=':
        return left != right
    try:
        if op == '>':
            return float(left) > float(right)
        if op == '<':
            return float(left) < float(right)
        if op == '>=':
            return float(left) >= float(right)
        if op == '<=':
            return float(left) <= float(right)
    except Exception:
        return False
    return False


async def _runtime_execute_formal_node_v16(self: MultiAgentRuntime, node: Any, state: Dict[str, Any]) -> Dict[str, Any]:
    kind = getattr(node, 'kind', '')
    label = getattr(node, 'label', '')
    metadata = getattr(node, 'metadata', {}) or {}
    if kind == 'let':
        binding = metadata.get('binding', {})
        name = binding.get('name')
        expr = binding.get('expr')
        value = _runtime_interpolate_value_v16(self, expr, state)
        state.setdefault('vars', {})[name] = value
        packet = {'kind': 'let', 'label': label, 'name': name, 'value': value, 'success': True}
        if label:
            state.setdefault('labels', {})[label] = packet
        state['last_success'] = True
        return packet
    if kind == 'command':
        cmd = node.command
        if cmd is None:
            return {'kind': 'command', 'label': label, 'success': False, 'error': 'missing command'}
        payload = _runtime_interpolate_value_v16(self, dict(cmd.payload) if isinstance(cmd.payload, dict) else {}, state)
        subject = _runtime_interpolate_value_v16(self, cmd.subject, state) if isinstance(cmd.subject, str) else cmd.subject
        target = _runtime_interpolate_value_v16(self, cmd.target, state) if isinstance(cmd.target, str) else cmd.target
        iface = _runtime_interpolate_value_v16(self, cmd.interface, state) if isinstance(cmd.interface, str) else cmd.interface

        async def _execute_with_context_fallback() -> Dict[str, Any]:
            explicit_ctx = payload.get('ctx') if isinstance(payload, dict) else None
            if cmd.kind != 'do' or explicit_ctx:
                return await self.execute(subject, cmd.action, dict(payload), interface_name=iface, context_name=explicit_ctx)
            profile = self.agents.get(subject or '')
            candidate_contexts: List[str] = []
            if profile is not None:
                candidate_contexts.extend([profile.active_context])
                candidate_contexts.extend([c for c in profile.accessible_contexts if c not in candidate_contexts])
            else:
                candidate_contexts.extend(list(self.environment.contexts.keys()))
            last: Dict[str, Any] = {'status': 'validation_denied'}
            for ctx_name in candidate_contexts:
                probe = await self.execute(subject, cmd.action, dict(payload), interface_name=iface, context_name=ctx_name)
                last = probe
                if probe.get('status') == 'success':
                    return probe
            return last

        if cmd.kind == 'do':
            res = await _execute_with_context_fallback()
        elif cmd.kind == 'vote':
            packet = self.consensus(subject, cmd.action, dict(payload), context_name=cmd.metadata.get('context') or payload.get('ctx'), interface_name=iface, threshold=float(payload.get('threshold', 0.5)), weighted=bool(payload.get('weighted', False)))
            res = {'consensus': packet.__dict__}
        elif cmd.kind == 'negotiate':
            packet = self.negotiate(subject, cmd.action, dict(payload), context_name=cmd.metadata.get('context') or payload.get('ctx'), interface_name=iface, threshold=float(payload.get('threshold', 0.5)))
            res = {'negotiation': packet.__dict__}
        elif cmd.kind == 'run.group':
            res = await self.group_execute(subject, cmd.action, dict(payload), context_name=payload.get('ctx'), threshold=float(payload.get('threshold', 0.5)), interface_name=iface, weighted=bool(payload.get('weighted', False)))
        elif cmd.kind == 'fanout':
            res = await self.fanout(subject, cmd.action, dict(payload), context_name=payload.get('ctx'), interface_name=iface)
        elif cmd.kind == 'delegate':
            res = self.delegate(subject, target or '', cmd.action or '', dict(payload), context_name=payload.get('ctx'))
        else:
            res = {'status': 'unsupported', 'kind': cmd.kind}
        success = True
        if isinstance(res, dict):
            if res.get('status') not in (None, 'success'):
                success = False
            if 'result' in res and isinstance(res['result'], dict) and res['result'].get('status') not in (None, 'success'):
                success = False
        packet = {'kind': 'command', 'label': label, 'command': cmd.to_dict(), 'result': res, 'success': success}
        bind = metadata.get('bind')
        if bind:
            state.setdefault('vars', {})[bind] = res
            packet['bind'] = bind
        if label:
            state.setdefault('labels', {})[label] = packet
        state['last_success'] = success
        return packet
    if kind == 'parallel':
        children = getattr(node, 'children', [])
        branch_results = await asyncio.gather(*[_runtime_execute_formal_node_v16(self, child, state) for child in children])
        success = all(bool(r.get('success', True)) for r in branch_results)
        packet = {'kind': 'parallel', 'label': label, 'results': branch_results, 'success': success}
        if label:
            state.setdefault('labels', {})[label] = packet
        state['last_success'] = success
        return packet
    if kind == 'sequence':
        results: List[Dict[str, Any]] = []
        success = True
        for child in getattr(node, 'children', []):
            branch = await _runtime_execute_formal_node_v16(self, child, state)
            results.append(branch)
            success = success and bool(branch.get('success', True))
            if not success:
                break
        packet = {'kind': 'sequence', 'label': label, 'results': results, 'success': success}
        if label:
            state.setdefault('labels', {})[label] = packet
        state['last_success'] = success
        return packet
    if kind == 'if':
        cond = getattr(node, 'condition', None)
        holds = _runtime_evaluate_formal_condition_v16(self, cond, state)
        branch = getattr(node, 'then_branch', []) if holds else getattr(node, 'else_branch', [])
        results = [await _runtime_execute_formal_node_v16(self, child, state) for child in branch]
        success = all(bool(r.get('success', True)) for r in results)
        packet = {'kind': 'if', 'label': label, 'condition': None if cond is None else cond.to_dict(), 'holds': holds, 'branch': 'then' if holds else 'else', 'results': results, 'success': success}
        if label:
            state.setdefault('labels', {})[label] = packet
        state['last_success'] = success
        return packet
    return {'kind': kind, 'label': label, 'success': False, 'error': 'unsupported node'}


async def _runtime_execute_formal_plan_v16(self: MultiAgentRuntime, program: Any) -> FormalPlanExecutionPacket:
    state: Dict[str, Any] = {'labels': {}, 'vars': {}, 'last_success': True}
    results: List[Dict[str, Any]] = []
    success = True
    for node in getattr(program, 'root', []):
        entry = await _runtime_execute_formal_node_v16(self, node, state)
        results.append(entry)
        success = success and bool(entry.get('success', True))
        if not success:
            break
    return FormalPlanExecutionPacket(packet_id=str(uuid.uuid4()), plan_name=getattr(program, 'name', 'unknown'), ast=program.to_dict(), results=results, success=success)

MultiAgentRuntime.evaluate_formal_condition = _runtime_evaluate_formal_condition_v16
MultiAgentRuntime.execute_formal_plan = _runtime_execute_formal_plan_v16


# Iteration 17 — typed scopes, builtin functions, and distributed formal plans ---

def _coerce_typed_value_v17(value: Any, declared_type: str) -> Any:
    dtype = (declared_type or 'auto').lower()
    if dtype in {'', 'auto', 'any'}:
        return value
    if dtype in {'str', 'string'}:
        return '' if value is None else str(value)
    if dtype in {'int', 'integer'}:
        return 0 if value is None else int(float(value))
    if dtype in {'float', 'number'}:
        return 0.0 if value is None else float(value)
    if dtype in {'bool', 'boolean'}:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {'1', 'true', 'yes', 'on'}
        return bool(value)
    if dtype == 'json':
        if isinstance(value, str):
            return json.loads(value)
        return value
    if dtype == 'list':
        if isinstance(value, list):
            return value
        if value is None:
            return []
        if isinstance(value, str):
            s = value.strip()
            if s.startswith('[') and s.endswith(']'):
                return json.loads(s)
            return [seg.strip() for seg in s.split(',') if seg.strip()]
        return [value]
    return value

@dataclass
class DistributedFormalPlanPacket:
    packet_id: str
    plan_name: str
    target_peer: str
    ast: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    success: bool = False
    emitted_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


def _runtime_scope_clone_v17(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'labels': dict(state.get('labels', {})),
        'vars': dict(state.get('vars', {})),
        'last_success': state.get('last_success', True),
    }


def _runtime_scope_commit_v17(parent: Dict[str, Any], child: Dict[str, Any], *, allow_vars: bool = True) -> None:
    parent.setdefault('labels', {}).update(child.get('labels', {}))
    if allow_vars:
        parent.setdefault('vars', {}).update(child.get('vars', {}))
    parent['last_success'] = child.get('last_success', parent.get('last_success', True))


def _runtime_resolve_agent_ref_v17(self: MultiAgentRuntime, spec: str) -> Any:
    # agent.<alias>.<field>, agent.<alias>.iface.<name>.<field>
    parts = spec.split('.')
    if len(parts) < 3:
        return None
    alias = parts[1]
    profile = self.agents.get(alias)
    if profile is None:
        return None
    if len(parts) >= 5 and parts[2] == 'iface':
        iface = profile.interfaces.get(parts[3])
        if iface is None:
            return None
        value: Any = iface.to_dict()
        for p in parts[4:]:
            if isinstance(value, dict):
                value = value.get(p)
            else:
                return None
        return value
    value: Any = profile.to_dict()
    for p in parts[2:]:
        if isinstance(value, dict):
            value = value.get(p)
        else:
            return None
    return value


def _split_top_level_v17(text: str, sep: str) -> List[str]:
    parts: List[str] = []
    buf: List[str] = []
    brace = bracket = paren = 0
    quote: Optional[str] = None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in {'"', "'"}:
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch == '{':
            brace += 1
        elif ch == '}':
            brace = max(0, brace - 1)
        elif ch == '[':
            bracket += 1
        elif ch == ']':
            bracket = max(0, bracket - 1)
        elif ch == '(':
            paren += 1
        elif ch == ')':
            paren = max(0, paren - 1)
        if ch == sep and brace == 0 and bracket == 0 and paren == 0:
            part = ''.join(buf).strip()
            if part:
                parts.append(part)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = ''.join(buf).strip()
    if tail:
        parts.append(tail)
    return parts

def _runtime_eval_arg_expr_v17(self: MultiAgentRuntime, expr: str, state: Dict[str, Any]) -> Any:
    expr = expr.strip()
    if not expr:
        return None
    if expr.startswith('fn.') and '(' in expr and expr.endswith(')'):
        fn_name = expr[3:expr.index('(')]
        inner = expr[expr.index('(') + 1:-1]
        arg_specs = []
        if inner.strip():
            arg_specs = _split_top_level_v17(inner, ',')
        args = [_runtime_eval_arg_expr_v17(self, arg, state) for arg in arg_specs]
        return _function_apply_v17(fn_name, args)
    return _runtime_resolve_reference_v17(self, expr, state)


def _runtime_resolve_reference_v17(self: MultiAgentRuntime, spec: str, state: Dict[str, Any]) -> Any:
    spec = str(spec).strip()
    if spec.startswith('agent.'):
        return _runtime_resolve_agent_ref_v17(self, spec)
    if spec.startswith('iface.'):
        # iface.<alias>.<iface>.<field>
        parts = spec.split('.')
        if len(parts) >= 4:
            return _runtime_resolve_agent_ref_v17(self, 'agent.' + parts[1] + '.iface.' + parts[2] + '.' + '.'.join(parts[3:]))
    return _runtime_resolve_reference_v16(self, spec, state)


def _runtime_interpolate_value_v17(self: MultiAgentRuntime, value: Any, state: Dict[str, Any]) -> Any:
    if isinstance(value, str):
        full = re.fullmatch(r'\$\{([^}]+)\}', value.strip())
        if full:
            return _runtime_eval_arg_expr_v17(self, full.group(1), state)
        def repl(match: re.Match[str]) -> str:
            resolved = _runtime_eval_arg_expr_v17(self, match.group(1), state)
            return '' if resolved is None else str(resolved)
        return re.sub(r'\$\{([^}]+)\}', repl, value)
    if isinstance(value, dict):
        return {k: _runtime_interpolate_value_v17(self, v, state) for k, v in value.items()}
    if isinstance(value, list):
        return [_runtime_interpolate_value_v17(self, v, state) for v in value]
    return value


def _runtime_evaluate_formal_condition_v17(self: MultiAgentRuntime, condition: Any, state: Dict[str, Any]) -> bool:
    left = _runtime_eval_arg_expr_v17(self, getattr(condition, 'field', ''), state)
    right = _runtime_interpolate_value_v17(self, getattr(condition, 'value', None), state)
    op = getattr(condition, 'op', '=')
    if isinstance(left, list) and op == '=':
        return right in left
    if op == '=':
        return left == right
    if op == '!=':
        return left != right
    try:
        if op == '>':
            return float(left) > float(right)
        if op == '<':
            return float(left) < float(right)
        if op == '>=':
            return float(left) >= float(right)
        if op == '<=':
            return float(left) <= float(right)
    except Exception:
        return False
    return False


async def _runtime_execute_formal_node_v17(self: MultiAgentRuntime, node: Any, state: Dict[str, Any]) -> Dict[str, Any]:
    kind = getattr(node, 'kind', '')
    label = getattr(node, 'label', '')
    metadata = getattr(node, 'metadata', {}) or {}
    if kind == 'let':
        binding = metadata.get('binding', {})
        name = binding.get('name')
        expr = binding.get('expr')
        declared_type = binding.get('declared_type', 'auto')
        value = _runtime_interpolate_value_v17(self, expr, state)
        value = _coerce_typed_value_v17(value, declared_type)
        state.setdefault('vars', {})[name] = value
        packet = {'kind': 'let', 'label': label, 'name': name, 'declared_type': declared_type, 'value': value, 'success': True}
        if label:
            state.setdefault('labels', {})[label] = packet
        state['last_success'] = True
        return packet
    if kind == 'command':
        cmd = node.command
        if cmd is None:
            return {'kind': 'command', 'label': label, 'success': False, 'error': 'missing command'}
        payload = _runtime_interpolate_value_v17(self, dict(cmd.payload) if isinstance(cmd.payload, dict) else {}, state)
        subject = _runtime_interpolate_value_v17(self, cmd.subject, state) if isinstance(cmd.subject, str) else cmd.subject
        target = _runtime_interpolate_value_v17(self, cmd.target, state) if isinstance(cmd.target, str) else cmd.target
        iface = _runtime_interpolate_value_v17(self, cmd.interface, state) if isinstance(cmd.interface, str) else cmd.interface

        async def _execute_with_context_fallback() -> Dict[str, Any]:
            explicit_ctx = payload.get('ctx') if isinstance(payload, dict) else None
            if cmd.kind != 'do' or explicit_ctx:
                return await self.execute(subject, cmd.action, dict(payload), interface_name=iface, context_name=explicit_ctx)
            profile = self.agents.get(subject or '')
            candidate_contexts: List[str] = []
            if profile is not None:
                candidate_contexts.extend([profile.active_context])
                candidate_contexts.extend([c for c in profile.accessible_contexts if c not in candidate_contexts])
            else:
                candidate_contexts.extend(list(self.environment.contexts.keys()))
            last: Dict[str, Any] = {'status': 'validation_denied'}
            for ctx_name in candidate_contexts:
                probe = await self.execute(subject, cmd.action, dict(payload), interface_name=iface, context_name=ctx_name)
                last = probe
                if probe.get('status') == 'success':
                    return probe
            return last

        if cmd.kind == 'do':
            res = await _execute_with_context_fallback()
        elif cmd.kind == 'vote':
            packet = self.consensus(subject, cmd.action, dict(payload), context_name=cmd.metadata.get('context') or payload.get('ctx'), interface_name=iface, threshold=float(payload.get('threshold', 0.5)), weighted=bool(payload.get('weighted', False)))
            res = {'consensus': packet.__dict__}
        elif cmd.kind == 'negotiate':
            packet = self.negotiate(subject, cmd.action, dict(payload), context_name=cmd.metadata.get('context') or payload.get('ctx'), interface_name=iface, threshold=float(payload.get('threshold', 0.5)))
            res = {'negotiation': packet.__dict__}
        elif cmd.kind == 'run.group':
            res = await self.group_execute(subject, cmd.action, dict(payload), context_name=payload.get('ctx'), threshold=float(payload.get('threshold', 0.5)), interface_name=iface, weighted=bool(payload.get('weighted', False)))
        elif cmd.kind == 'fanout':
            res = await self.fanout(subject, cmd.action, dict(payload), context_name=payload.get('ctx'), interface_name=iface)
        elif cmd.kind == 'delegate':
            res = self.delegate(subject, target or '', cmd.action or '', dict(payload), context_name=payload.get('ctx'))
        else:
            res = {'status': 'unsupported', 'kind': cmd.kind}
        success = True
        if isinstance(res, dict):
            if res.get('status') not in (None, 'success'):
                success = False
            if 'result' in res and isinstance(res['result'], dict) and res['result'].get('status') not in (None, 'success'):
                success = False
        packet = {'kind': 'command', 'label': label, 'command': cmd.to_dict(), 'result': res, 'success': success}
        bind = metadata.get('bind')
        if bind:
            state.setdefault('vars', {})[bind] = res
            packet['bind'] = bind
        if label:
            state.setdefault('labels', {})[label] = packet
        state['last_success'] = success
        return packet
    if kind == 'parallel':
        children = getattr(node, 'children', [])
        branch_states = [_runtime_scope_clone_v17(state) for _ in children]
        branch_results = await asyncio.gather(*[_runtime_execute_formal_node_v17(self, child, branch_state) for child, branch_state in zip(children, branch_states)])
        success = all(bool(r.get('success', True)) for r in branch_results)
        packet = {'kind': 'parallel', 'label': label, 'results': branch_results, 'scope_results': [{'vars': s.get('vars', {}), 'labels': list(s.get('labels', {}).keys())} for s in branch_states], 'success': success}
        if label:
            state.setdefault('labels', {})[label] = packet
        state['last_success'] = success
        return packet
    if kind == 'sequence':
        results: List[Dict[str, Any]] = []
        success = True
        for child in getattr(node, 'children', []):
            branch = await _runtime_execute_formal_node_v17(self, child, state)
            results.append(branch)
            success = success and bool(branch.get('success', True))
            if not success:
                break
        packet = {'kind': 'sequence', 'label': label, 'results': results, 'success': success}
        if label:
            state.setdefault('labels', {})[label] = packet
        state['last_success'] = success
        return packet
    if kind == 'if':
        cond = getattr(node, 'condition', None)
        holds = _runtime_evaluate_formal_condition_v17(self, cond, state)
        branch = getattr(node, 'then_branch', []) if holds else getattr(node, 'else_branch', [])
        branch_state = _runtime_scope_clone_v17(state)
        results = [await _runtime_execute_formal_node_v17(self, child, branch_state) for child in branch]
        _runtime_scope_commit_v17(state, branch_state, allow_vars=True)
        success = all(bool(r.get('success', True)) for r in results)
        packet = {'kind': 'if', 'label': label, 'condition': None if cond is None else cond.to_dict(), 'holds': holds, 'branch': 'then' if holds else 'else', 'results': results, 'scope': {'vars': branch_state.get('vars', {})}, 'success': success}
        if label:
            state.setdefault('labels', {})[label] = packet
        state['last_success'] = success
        return packet
    return {'kind': kind, 'label': label, 'success': False, 'error': 'unsupported node'}


async def _runtime_execute_formal_plan_v17(self: MultiAgentRuntime, program: Any) -> FormalPlanExecutionPacket:
    state: Dict[str, Any] = {'labels': {}, 'vars': {}, 'last_success': True}
    results: List[Dict[str, Any]] = []
    success = True
    for node in getattr(program, 'root', []):
        entry = await _runtime_execute_formal_node_v17(self, node, state)
        results.append(entry)
        success = success and bool(entry.get('success', True))
        if not success:
            break
    return FormalPlanExecutionPacket(packet_id=str(uuid.uuid4()), plan_name=getattr(program, 'name', 'unknown'), ast=program.to_dict(), results=results, success=success)


def _runtime_register_runtime_peer_v17(self: MultiAgentRuntime, peer_name: str, peer_runtime: 'MultiAgentRuntime') -> Dict[str, Any]:
    registry = getattr(self, '_runtime_peers', None)
    if registry is None:
        registry = {}
        setattr(self, '_runtime_peers', registry)
    registry[peer_name] = peer_runtime
    hello = self.gateway.register_peer(peer_name, capabilities=['world', 'certainty', 'causality', 'replay', 'resync', 'formal-plan'])
    return {'peer': peer_name, 'hello': hello.__dict__}


def _runtime_runtime_peers_v17(self: MultiAgentRuntime) -> List[str]:
    return sorted(list(getattr(self, '_runtime_peers', {}).keys()))


async def _runtime_execute_distributed_formal_plan_v17(self: MultiAgentRuntime, peer_name: str, plan_name: str) -> DistributedFormalPlanPacket:
    peers = getattr(self, '_runtime_peers', {})
    if peer_name not in peers:
        raise KeyError(f'unknown runtime peer: {peer_name}')
    peer = peers[peer_name]
    if not hasattr(peer, 'formal_plans'):
        raise AttributeError(f'peer {peer_name} has no formal_plans registry')
    program = peer.formal_plans.get(plan_name)
    if program is None:
        raise KeyError(f'peer {peer_name} has no plan named {plan_name}')
    result = await peer.execute_formal_plan(program)
    return DistributedFormalPlanPacket(packet_id=str(uuid.uuid4()), plan_name=plan_name, target_peer=peer_name, ast=program.to_dict(), result=result.__dict__, success=bool(result.success))


MultiAgentRuntime.evaluate_formal_condition = _runtime_evaluate_formal_condition_v17
MultiAgentRuntime.execute_formal_plan = _runtime_execute_formal_plan_v17
MultiAgentRuntime.register_runtime_peer = _runtime_register_runtime_peer_v17
MultiAgentRuntime.runtime_peers = _runtime_runtime_peers_v17
MultiAgentRuntime.execute_distributed_formal_plan = _runtime_execute_distributed_formal_plan_v17

try:
    __all__.extend(['DistributedFormalPlanPacket'])
except Exception:
    pass

# Iteration 17 helper completion ------------------------------------------------
if '_function_apply_v17' not in globals():
    def _function_apply_v17(name: str, args: List[Any]) -> Any:
        lname = name.lower()
        if lname == 'upper':
            return '' if not args or args[0] is None else str(args[0]).upper()
        if lname == 'lower':
            return '' if not args or args[0] is None else str(args[0]).lower()
        if lname == 'title':
            return '' if not args or args[0] is None else str(args[0]).title()
        if lname == 'len':
            return len(args[0]) if args else 0
        if lname == 'int':
            return _coerce_typed_value_v17(args[0] if args else 0, 'int')
        if lname == 'float':
            return _coerce_typed_value_v17(args[0] if args else 0.0, 'float')
        if lname == 'bool':
            return _coerce_typed_value_v17(args[0] if args else False, 'bool')
        if lname == 'str':
            return _coerce_typed_value_v17(args[0] if args else '', 'str')
        if lname == 'json':
            return json.dumps(args[0] if args else None, ensure_ascii=False, sort_keys=True)
        if lname == 'default':
            if not args:
                return None
            return args[0] if args[0] not in (None, '', []) else (args[1] if len(args) > 1 else None)
        if lname == 'coalesce':
            for arg in args:
                if arg not in (None, '', []):
                    return arg
            return None
        raise KeyError(f'unknown EnvLang function: {name}')


# Iteration 18 — deeper distributed formal plans -------------------------------

@dataclass
class PlanDispatchPacket:
    packet_id: str
    plan_name: str
    target_peer: str
    ast: Dict[str, Any]
    dispatched_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class PlanResultPacket:
    packet_id: str
    plan_name: str
    source_peer: str
    success: bool
    result: Dict[str, Any]
    completed_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


def _register_iteration18_schemas() -> None:
    packets = {
        'plan.dispatch': {
            'required': ('packet_id', 'plan_name', 'target_peer', 'ast'),
            'optional': ('dispatched_at',),
            'description': 'Dispatch a formal plan AST toward a runtime peer.',
        },
        'plan.result': {
            'required': ('packet_id', 'plan_name', 'source_peer', 'success', 'result'),
            'optional': ('completed_at',),
            'description': 'Return the result of a formal plan execution from a runtime peer.',
        },
    }
    for ptype, spec in packets.items():
        if PROTOCOL_SCHEMAS.get(ptype, '1.0') is None:
            PROTOCOL_SCHEMAS.register(PacketSchema(packet_type=ptype, version='1.0', required_body=tuple(spec['required']), optional_body=tuple(spec['optional']), description=spec['description']))


_register_iteration18_schemas()


async def _runtime_execute_formal_node_v18(self: MultiAgentRuntime, node: Any, state: Dict[str, Any]) -> Dict[str, Any]:
    kind = getattr(node, 'kind', '')
    label = getattr(node, 'label', '') or ''
    metadata = getattr(node, 'metadata', {}) or {}
    if kind == 'call':
        cmd = getattr(node, 'command', None)
        plan_name = getattr(cmd, 'subject', None) or metadata.get('plan')
        registry = getattr(self, 'formal_plans', {})
        stack = state.setdefault('__plan_stack__', [])
        if not plan_name:
            packet = {'kind': 'call', 'label': label, 'success': False, 'error': 'missing plan name'}
        elif plan_name in stack:
            packet = {'kind': 'call', 'label': label, 'success': False, 'error': f'recursive plan call: {plan_name}', 'stack': list(stack)}
        elif plan_name not in registry:
            packet = {'kind': 'call', 'label': label, 'success': False, 'error': f'unknown plan: {plan_name}'}
        else:
            stack.append(plan_name)
            result = await self.execute_formal_plan(registry[plan_name])
            stack.pop()
            packet = {'kind': 'call', 'label': label, 'plan': plan_name, 'result': result.__dict__, 'success': bool(result.success)}
        if label:
            state.setdefault('labels', {})[label] = packet
        state['last_success'] = bool(packet.get('success', False))
        return packet
    if kind == 'remote':
        peer_name = metadata.get('peer')
        peers = getattr(self, '_runtime_peers', {})
        if not peer_name or peer_name not in peers:
            packet = {'kind': 'remote', 'label': label, 'success': False, 'error': f'unknown runtime peer: {peer_name}'}
        else:
            peer = peers[peer_name]
            from .envlang import FormalPlanProgram  # local import to avoid cycles
            remote_program = FormalPlanProgram(name=f'remote::{peer_name}', root=list(getattr(node, 'children', [])), source=f'remote {peer_name}')
            dispatch = PlanDispatchPacket(packet_id=str(uuid.uuid4()), plan_name=remote_program.name, target_peer=peer_name, ast=remote_program.to_dict())
            result = await peer.execute_formal_plan(remote_program)
            result_packet = PlanResultPacket(packet_id=str(uuid.uuid4()), plan_name=remote_program.name, source_peer=peer_name, success=bool(result.success), result=result.__dict__)
            packet = {'kind': 'remote', 'label': label, 'peer': peer_name, 'dispatch': dispatch.__dict__, 'result_packet': result_packet.__dict__, 'success': bool(result.success)}
        if label:
            state.setdefault('labels', {})[label] = packet
        state['last_success'] = bool(packet.get('success', False))
        return packet
    return await _runtime_execute_formal_node_v17(self, node, state)


async def _runtime_execute_formal_plan_v18(self: MultiAgentRuntime, program: Any) -> FormalPlanExecutionPacket:
    state: Dict[str, Any] = {'labels': {}, 'vars': {}, 'last_success': True, '__plan_stack__': [getattr(program, 'name', 'root')]}
    results: List[Dict[str, Any]] = []
    success = True
    for node in getattr(program, 'root', []):
        entry = await _runtime_execute_formal_node_v18(self, node, state)
        results.append(entry)
        success = success and bool(entry.get('success', True))
        if not success:
            break
    return FormalPlanExecutionPacket(packet_id=str(uuid.uuid4()), plan_name=getattr(program, 'name', 'unknown'), ast=program.to_dict(), results=results, success=success)


async def _runtime_execute_distributed_formal_plan_v18(self: MultiAgentRuntime, peer_name: str, plan_name: str) -> DistributedFormalPlanPacket:
    peers = getattr(self, '_runtime_peers', {})
    if peer_name not in peers:
        raise KeyError(f'unknown runtime peer: {peer_name}')
    peer = peers[peer_name]
    if not hasattr(peer, 'formal_plans'):
        raise AttributeError(f'peer {peer_name} has no formal_plans registry')
    program = peer.formal_plans.get(plan_name)
    if program is None:
        raise KeyError(f'peer {peer_name} has no plan named {plan_name}')
    dispatch = PlanDispatchPacket(packet_id=str(uuid.uuid4()), plan_name=plan_name, target_peer=peer_name, ast=program.to_dict())
    result = await peer.execute_formal_plan(program)
    result_packet = PlanResultPacket(packet_id=str(uuid.uuid4()), plan_name=plan_name, source_peer=peer_name, success=bool(result.success), result=result.__dict__)
    payload = dict(result.__dict__)
    payload['dispatch'] = dispatch.__dict__
    payload['result_packet'] = result_packet.__dict__
    return DistributedFormalPlanPacket(packet_id=str(uuid.uuid4()), plan_name=plan_name, target_peer=peer_name, ast=program.to_dict(), result=payload, success=bool(result.success))


MultiAgentRuntime.execute_formal_plan = _runtime_execute_formal_plan_v18
MultiAgentRuntime.execute_distributed_formal_plan = _runtime_execute_distributed_formal_plan_v18

try:
    __all__.extend(['PlanDispatchPacket', 'PlanResultPacket'])
except Exception:
    pass


# Iteration 19 — distributed coordination, leases, execution registry ---------

@dataclass
class LockRequestPacket:
    packet_id: str
    resource: str
    owner: str
    ttl_s: float = 30.0
    requested_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class LockDecisionPacket:
    packet_id: str
    resource: str
    owner: str
    granted: bool
    reason: str = ''
    holder: Optional[str] = None
    expires_at: Optional[float] = None
    decided_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class RuntimeHeartbeatPacket:
    packet_id: str
    runtime_id: str
    active_agents: int
    active_executions: int
    locks: int
    emitted_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class RuntimeExecutionStatePacket:
    packet_id: str
    runtime_id: str
    executions: List[Dict[str, Any]]
    emitted_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class ExecutionLease:
    resource: str
    owner: str
    acquired_at: float
    expires_at: float

    @property
    def active(self) -> bool:
        return time.time() < self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            'resource': self.resource,
            'owner': self.owner,
            'acquired_at': self.acquired_at,
            'expires_at': self.expires_at,
            'active': self.active,
        }


def _register_iteration19_schemas() -> None:
    packets = {
        'lock.request': {
            'required': ('packet_id', 'resource', 'owner'),
            'optional': ('ttl_s', 'requested_at'),
            'description': 'Request a short-lived execution lease on a logical resource.',
        },
        'lock.decision': {
            'required': ('packet_id', 'resource', 'owner', 'granted'),
            'optional': ('reason', 'holder', 'expires_at', 'decided_at'),
            'description': 'Decision for a logical resource lease request.',
        },
        'runtime.heartbeat': {
            'required': ('packet_id', 'runtime_id', 'active_agents', 'active_executions', 'locks'),
            'optional': ('emitted_at',),
            'description': 'Summarize liveness and current coordination load for a runtime.',
        },
        'runtime.execution_state': {
            'required': ('packet_id', 'runtime_id', 'executions'),
            'optional': ('emitted_at',),
            'description': 'Expose active and recent formal plan executions for coordination.',
        },
    }
    for ptype, spec in packets.items():
        if PROTOCOL_SCHEMAS.get(ptype, '1.0') is None:
            PROTOCOL_SCHEMAS.register(PacketSchema(packet_type=ptype, version='1.0', required_body=tuple(spec['required']), optional_body=tuple(spec['optional']), description=spec['description']))


_register_iteration19_schemas()


def _runtime_coordination_init(self: MultiAgentRuntime) -> None:
    if not hasattr(self, '_leases'):
        self._leases = {}
    if not hasattr(self, '_executions'):
        self._executions = {}
    if not hasattr(self, 'runtime_id'):
        self.runtime_id = f'runtime:{id(self)}'


def _runtime_acquire_lock(self: MultiAgentRuntime, resource: str, owner: str, ttl_s: float = 30.0) -> LockDecisionPacket:
    _runtime_coordination_init(self)
    now = time.time()
    lease = self._leases.get(resource)
    if lease and lease.active and lease.owner != owner:
        return LockDecisionPacket(packet_id=str(uuid.uuid4()), resource=resource, owner=owner, granted=False, reason='resource already leased', holder=lease.owner, expires_at=lease.expires_at)
    expires = now + max(1.0, float(ttl_s))
    self._leases[resource] = ExecutionLease(resource=resource, owner=owner, acquired_at=now, expires_at=expires)
    return LockDecisionPacket(packet_id=str(uuid.uuid4()), resource=resource, owner=owner, granted=True, holder=owner, expires_at=expires)


def _runtime_release_lock(self: MultiAgentRuntime, resource: str, owner: str) -> Dict[str, Any]:
    _runtime_coordination_init(self)
    lease = self._leases.get(resource)
    if lease is None:
        return {'released': False, 'reason': 'unknown resource'}
    if lease.owner != owner:
        return {'released': False, 'reason': f'owned by {lease.owner}'}
    self._leases.pop(resource, None)
    return {'released': True, 'resource': resource, 'owner': owner}


def _runtime_list_locks(self: MultiAgentRuntime) -> List[Dict[str, Any]]:
    _runtime_coordination_init(self)
    now = time.time()
    expired = [k for k, v in self._leases.items() if v.expires_at <= now]
    for key in expired:
        self._leases.pop(key, None)
    return [lease.to_dict() for lease in self._leases.values()]


def _runtime_heartbeat(self: MultiAgentRuntime) -> RuntimeHeartbeatPacket:
    _runtime_coordination_init(self)
    return RuntimeHeartbeatPacket(packet_id=str(uuid.uuid4()), runtime_id=self.runtime_id, active_agents=len(self.agents), active_executions=len([e for e in self._executions.values() if e.get('state') == 'running']), locks=len(self._runtime_list_locks()))


def _runtime_execution_state(self: MultiAgentRuntime) -> RuntimeExecutionStatePacket:
    _runtime_coordination_init(self)
    return RuntimeExecutionStatePacket(packet_id=str(uuid.uuid4()), runtime_id=self.runtime_id, executions=list(self._executions.values()))


def _infer_plan_resources(self: MultiAgentRuntime, program: Any) -> List[str]:
    resources: List[str] = [f'plan:{getattr(program, "name", "unknown")}']
    def walk(node: Any) -> None:
        kind = getattr(node, 'kind', '')
        cmd = getattr(node, 'command', None)
        if kind in {'do', 'vote', 'negotiate', 'run.group', 'fanout', 'delegate'} and cmd is not None:
            action = getattr(cmd, 'action', None)
            payload = getattr(cmd, 'payload', {}) or {}
            if action:
                resources.append(f'action:{action}')
            for key in ('case', 'drone', 'mission', 'target', 'group'):
                if key in payload and payload[key] not in (None, ''):
                    resources.append(f'{key}:{payload[key]}')
        for child in getattr(node, 'children', []) or []:
            walk(child)
    for node in getattr(program, 'root', []) or []:
        walk(node)
    out: List[str] = []
    for res in resources:
        if res not in out:
            out.append(res)
    return out


def _runtime_cleanup_expired_locks(self: MultiAgentRuntime) -> int:
    _runtime_coordination_init(self)
    now = time.time()
    expired = [name for name, lease in self._leases.items() if lease.expires_at <= now]
    for name in expired:
        self._leases.pop(name, None)
    return len(expired)

def _runtime_compact_executions(self: MultiAgentRuntime, keep_completed: int = 25) -> int:
    _runtime_coordination_init(self)
    completed = [(eid, data) for eid, data in self._executions.items() if data.get('state') != 'running']
    completed.sort(key=lambda item: item[1].get('completed_at', item[1].get('started_at', 0.0)), reverse=True)
    removable = completed[keep_completed:]
    for eid, _ in removable:
        self._executions.pop(eid, None)
    return len(removable)

MultiAgentRuntime.acquire_lock = _runtime_acquire_lock
MultiAgentRuntime.release_lock = _runtime_release_lock
MultiAgentRuntime.list_locks = _runtime_list_locks
MultiAgentRuntime.heartbeat = _runtime_heartbeat
MultiAgentRuntime.execution_state = _runtime_execution_state
MultiAgentRuntime._infer_plan_resources = _infer_plan_resources
MultiAgentRuntime.cleanup_expired_locks = _runtime_cleanup_expired_locks
MultiAgentRuntime.compact_executions = _runtime_compact_executions

_old_execute_formal_plan_v18 = MultiAgentRuntime.execute_formal_plan

async def _runtime_execute_formal_plan_v19(self: MultiAgentRuntime, program: Any) -> FormalPlanExecutionPacket:
    _runtime_coordination_init(self)
    execution_id = str(uuid.uuid4())
    owner = getattr(program, 'name', 'unknown')
    resources = self._infer_plan_resources(program)
    decisions = [self.acquire_lock(res, owner, ttl_s=30.0) for res in resources]
    denied = [d for d in decisions if not d.granted]
    self._executions[execution_id] = {
        'execution_id': execution_id,
        'plan_name': getattr(program, 'name', 'unknown'),
        'state': 'running' if not denied else 'blocked',
        'resources': resources,
        'started_at': time.time(),
        'lock_decisions': [d.to_dict() for d in decisions],
    }
    if denied:
        packet = FormalPlanExecutionPacket(packet_id=execution_id, plan_name=getattr(program, 'name', 'unknown'), ast=program.to_dict(), results=[{'kind': 'lock', 'success': False, 'decisions': [d.to_dict() for d in decisions]}], success=False)
        self._executions[execution_id]['completed_at'] = time.time()
        return packet
    try:
        packet = await _old_execute_formal_plan_v18(self, program)
        self._executions[execution_id]['state'] = 'completed' if packet.success else 'failed'
        self._executions[execution_id]['completed_at'] = time.time()
        self._executions[execution_id]['success'] = bool(packet.success)
        self._executions[execution_id]['packet_id'] = packet.packet_id
        packet.results.append({'kind': 'lock', 'success': True, 'decisions': [d.to_dict() for d in decisions]})
        return packet
    finally:
        for res in resources:
            self.release_lock(res, owner)


MultiAgentRuntime.execute_formal_plan = _runtime_execute_formal_plan_v19


def _gateway_lock_request_packet(self: MepGateway, resource: str, owner: str, ttl_s: float = 30.0) -> CanonicalPacket:
    req = LockRequestPacket(packet_id=str(uuid.uuid4()), resource=resource, owner=owner, ttl_s=ttl_s)
    return ProtocolCodec.pack('lock.request', req.to_dict())


def _gateway_lock_decision_packet(self: MepGateway, runtime: MultiAgentRuntime, resource: str, owner: str, ttl_s: float = 30.0) -> CanonicalPacket:
    decision = runtime.acquire_lock(resource, owner, ttl_s=ttl_s)
    if decision.granted:
        runtime.release_lock(resource, owner)
    return ProtocolCodec.pack('lock.decision', decision.to_dict())


def _gateway_runtime_heartbeat_packet(self: MepGateway, runtime: MultiAgentRuntime) -> CanonicalPacket:
    return ProtocolCodec.pack('runtime.heartbeat', runtime.heartbeat().to_dict())


def _gateway_runtime_execution_state_packet(self: MepGateway, runtime: MultiAgentRuntime) -> CanonicalPacket:
    return ProtocolCodec.pack('runtime.execution_state', runtime.execution_state().to_dict())


MepGateway.lock_request_packet = _gateway_lock_request_packet
MepGateway.lock_decision_packet = _gateway_lock_decision_packet
MepGateway.runtime_heartbeat_packet = _gateway_runtime_heartbeat_packet
MepGateway.runtime_execution_state_packet = _gateway_runtime_execution_state_packet

try:
    __all__.extend(['LockRequestPacket', 'LockDecisionPacket', 'RuntimeHeartbeatPacket', 'RuntimeExecutionStatePacket'])
except Exception:
    pass


# Iteration 22 — distributed preflight and intelligent runtime merge ---------

@dataclass
class PlanPreflightPacket:
    packet_id: str
    source_runtime_id: str
    target_peer: str
    plan_name: str
    executable: bool
    dependency_status: Dict[str, Any] = field(default_factory=dict)
    lock_status: Dict[str, Any] = field(default_factory=dict)
    peer_status: Dict[str, Any] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
    emitted_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class RuntimeMergePacket:
    packet_id: str
    source_runtime_id: str
    target_runtime_id: str
    peer_count_delta: int
    execution_updates: int
    lock_updates: int
    merged_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def _register_iteration22_schemas() -> None:
    packets = {
        'plan.preflight': {
            'required': ('packet_id', 'source_runtime_id', 'target_peer', 'plan_name', 'executable'),
            'optional': ('dependency_status', 'lock_status', 'peer_status', 'reasons', 'emitted_at'),
            'description': 'Preflight validation for a distributed formal plan before dispatch.',
        },
        'runtime.merge_state': {
            'required': ('packet_id', 'source_runtime_id', 'target_runtime_id', 'peer_count_delta', 'execution_updates', 'lock_updates'),
            'optional': ('merged_at',),
            'description': 'Report a runtime-aware state merge between peers.',
        },
    }
    for ptype, spec in packets.items():
        if PROTOCOL_SCHEMAS.get(ptype, '1.0') is None:
            PROTOCOL_SCHEMAS.register(PacketSchema(packet_type=ptype, version='1.0', required_body=tuple(spec['required']), optional_body=tuple(spec['optional']), description=spec['description']))


_register_iteration22_schemas()


def _runtime_preflight_distributed_plan(self: MultiAgentRuntime, peer_name: str, plan_name: str, depends_on: Optional[List[str]] = None) -> PlanPreflightPacket:
    _runtime_coordination_init(self)
    depends_on = [d for d in (depends_on or []) if d]
    reasons: List[str] = []
    peers = getattr(self, '_runtime_peers', {})
    peer = peers.get(peer_name)
    peer_status: Dict[str, Any] = {'known': peer is not None, 'peer': peer_name}
    if peer is None:
        reasons.append(f'unknown runtime peer: {peer_name}')
        return PlanPreflightPacket(packet_id=str(uuid.uuid4()), source_runtime_id=self.runtime_id, target_peer=peer_name, plan_name=plan_name, executable=False, dependency_status={'depends_on': depends_on, 'satisfied': []}, lock_status={'conflicts': []}, peer_status=peer_status, reasons=reasons)
    peer_status['runtime_id'] = getattr(peer, 'runtime_id', peer_name)
    peer_status['heartbeat'] = getattr(peer, 'heartbeat', lambda: None)()
    program = getattr(peer, 'formal_plans', {}).get(plan_name)
    if program is None:
        reasons.append(f'peer {peer_name} has no plan named {plan_name}')
        return PlanPreflightPacket(packet_id=str(uuid.uuid4()), source_runtime_id=self.runtime_id, target_peer=peer_name, plan_name=plan_name, executable=False, dependency_status={'depends_on': depends_on, 'satisfied': []}, lock_status={'conflicts': []}, peer_status=peer_status, reasons=reasons)
    satisfied: List[str] = []
    missing: List[str] = []
    for dep in depends_on:
        execution = self._executions.get(dep)
        if execution and execution.get('state') == 'completed' and bool(execution.get('success', False)):
            satisfied.append(dep)
        else:
            missing.append(dep)
    if missing:
        reasons.append(f'unsatisfied dependencies: {missing}')
    resources = self._infer_plan_resources(program)
    conflicts: List[str] = []
    peer_leases = getattr(peer, '_leases', {})
    now = time.time()
    for resource in resources:
        lease = peer_leases.get(resource)
        if lease is not None and getattr(lease, 'expires_at', 0.0) > now:
            conflicts.append(resource)
    if conflicts:
        reasons.append(f'locked resources on peer: {conflicts}')
    executable = not reasons
    return PlanPreflightPacket(
        packet_id=str(uuid.uuid4()),
        source_runtime_id=self.runtime_id,
        target_peer=peer_name,
        plan_name=plan_name,
        executable=executable,
        dependency_status={'depends_on': depends_on, 'satisfied': satisfied, 'missing': missing},
        lock_status={'resources': resources, 'conflicts': conflicts},
        peer_status={k: (v.to_dict() if hasattr(v, 'to_dict') else v) for k, v in peer_status.items()},
        reasons=reasons,
    )


def _runtime_merge_peer_state(self: MultiAgentRuntime, peer_name: str) -> RuntimeMergePacket:
    _runtime_coordination_init(self)
    peers = getattr(self, '_runtime_peers', {})
    if peer_name not in peers:
        raise KeyError(f'unknown runtime peer: {peer_name}')
    peer = peers[peer_name]
    peer_count_before = len(self.gateway.peers)
    # Merge peer registry info
    self.gateway.peers.update(getattr(peer.gateway, 'peers', {}))
    self.gateway.peers.setdefault(peer_name, {'capabilities': ['world', 'certainty', 'causality', 'replay', 'resync', 'formal-plan'], 'registered_at': time.time()})
    peer_count_delta = len(self.gateway.peers) - peer_count_before

    def _execution_ts(data: Dict[str, Any]) -> float:
        return float(data.get('completed_at') or data.get('started_at') or 0.0)

    execution_updates = 0
    for eid, pdata in getattr(peer, '_executions', {}).items():
        local = self._executions.get(eid)
        if local is None or _execution_ts(pdata) > _execution_ts(local) or (local.get('state') != 'completed' and pdata.get('state') == 'completed'):
            self._executions[eid] = dict(pdata)
            execution_updates += 1

    lock_updates = 0
    for resource, please in getattr(peer, '_leases', {}).items():
        local = self._leases.get(resource)
        if local is None or getattr(please, 'expires_at', 0.0) > getattr(local, 'expires_at', 0.0):
            self._leases[resource] = please
            lock_updates += 1

    return RuntimeMergePacket(
        packet_id=str(uuid.uuid4()),
        source_runtime_id=self.runtime_id,
        target_runtime_id=getattr(peer, 'runtime_id', peer_name),
        peer_count_delta=peer_count_delta,
        execution_updates=execution_updates,
        lock_updates=lock_updates,
    )


async def _runtime_execute_distributed_formal_plan_v22(self: MultiAgentRuntime, peer_name: str, plan_name: str, depends_on: Optional[List[str]] = None) -> DistributedFormalPlanPacket:
    preflight = self.preflight_distributed_plan(peer_name, plan_name, depends_on=depends_on)
    peers = getattr(self, '_runtime_peers', {})
    peer = peers.get(peer_name)
    if not preflight.executable or peer is None:
        payload = {'preflight': preflight.to_dict(), 'reason': '; '.join(preflight.reasons) or 'preflight failed'}
        return DistributedFormalPlanPacket(packet_id=str(uuid.uuid4()), plan_name=plan_name, target_peer=peer_name, ast={}, result=payload, success=False)
    program = getattr(peer, 'formal_plans', {}).get(plan_name)
    dispatch = PlanDispatchPacket(packet_id=str(uuid.uuid4()), plan_name=plan_name, target_peer=peer_name, ast=program.to_dict())
    result = await peer.execute_formal_plan(program)
    result_packet = PlanResultPacket(packet_id=str(uuid.uuid4()), plan_name=plan_name, source_peer=peer_name, success=bool(result.success), result=result.__dict__)
    payload = dict(result.__dict__)
    payload['dispatch'] = dispatch.__dict__
    payload['result_packet'] = result_packet.__dict__
    payload['preflight'] = preflight.to_dict()
    return DistributedFormalPlanPacket(packet_id=str(uuid.uuid4()), plan_name=plan_name, target_peer=peer_name, ast=program.to_dict(), result=payload, success=bool(result.success))


MultiAgentRuntime.preflight_distributed_plan = _runtime_preflight_distributed_plan
MultiAgentRuntime.merge_peer_state = _runtime_merge_peer_state
MultiAgentRuntime.execute_distributed_formal_plan = _runtime_execute_distributed_formal_plan_v22


def _gateway_plan_preflight_packet(self: MepGateway, runtime: MultiAgentRuntime, peer_name: str, plan_name: str, depends_on: Optional[List[str]] = None) -> CanonicalPacket:
    return ProtocolCodec.pack('plan.preflight', runtime.preflight_distributed_plan(peer_name, plan_name, depends_on=depends_on).to_dict())


def _gateway_runtime_merge_packet(self: MepGateway, runtime: MultiAgentRuntime, peer_name: str) -> CanonicalPacket:
    return ProtocolCodec.pack('runtime.merge_state', runtime.merge_peer_state(peer_name).to_dict())


MepGateway.plan_preflight_packet = _gateway_plan_preflight_packet
MepGateway.runtime_merge_packet = _gateway_runtime_merge_packet

try:
    __all__.extend(['PlanPreflightPacket', 'RuntimeMergePacket'])
except Exception:
    pass


# Iteration 22 hotfixes --------------------------------------------------------

def _runtime_heartbeat_v22(self: MultiAgentRuntime) -> RuntimeHeartbeatPacket:
    _runtime_coordination_init(self)
    active_executions = len([e for e in self._executions.values() if e.get('state') == 'running'])
    locks = len(self.list_locks())
    return RuntimeHeartbeatPacket(packet_id=str(uuid.uuid4()), runtime_id=self.runtime_id, active_agents=len(self.agents), active_executions=active_executions, locks=locks)

MultiAgentRuntime.heartbeat = _runtime_heartbeat_v22


def _runtime_collect_plan_aliases(self: MultiAgentRuntime, program: Any) -> List[str]:
    aliases: List[str] = []
    def walk(node: Any) -> None:
        cmd = getattr(node, 'command', None)
        if cmd is not None:
            subject = getattr(cmd, 'subject', None)
            if subject and subject not in aliases:
                aliases.append(subject)
        for child in getattr(node, 'children', []) or []:
            walk(child)
        for child in getattr(node, 'then_branch', []) or []:
            walk(child)
        for child in getattr(node, 'else_branch', []) or []:
            walk(child)
    for node in getattr(program, 'root', []) or []:
        walk(node)
    return aliases

async def _runtime_sync_plan_agents_to_peer(self: MultiAgentRuntime, peer: 'MultiAgentRuntime', program: Any) -> Dict[str, Any]:
    synced: List[str] = []
    missing: List[str] = []
    for alias in self._collect_plan_aliases(program):
        if alias in peer.agents:
            continue
        local = self.agents.get(alias)
        if local is None:
            missing.append(alias)
            continue
        context_name = local.active_context or (next(iter(local.accessible_contexts)) if local.accessible_contexts else next(iter(peer.environment.contexts.keys())))
        kind = str(local.metadata.get('kind', 'agent'))
        await peer.spawn(alias, role=local.role, kind=kind, context_name=context_name)
        for ctx in sorted(local.accessible_contexts):
            if ctx in peer.environment.contexts:
                peer.add_context_access(alias, ctx, shared=(ctx in local.shared_contexts), activate=(ctx == local.active_context))
        synced.append(alias)
    return {'synced': synced, 'missing': missing}

async def _runtime_execute_distributed_formal_plan_v22b(self: MultiAgentRuntime, peer_name: str, plan_name: str, depends_on: Optional[List[str]] = None) -> DistributedFormalPlanPacket:
    preflight = self.preflight_distributed_plan(peer_name, plan_name, depends_on=depends_on)
    peers = getattr(self, '_runtime_peers', {})
    peer = peers.get(peer_name)
    if peer is None:
        payload = {'preflight': preflight.to_dict(), 'reason': '; '.join(preflight.reasons) or 'preflight failed'}
        return DistributedFormalPlanPacket(packet_id=str(uuid.uuid4()), plan_name=plan_name, target_peer=peer_name, ast={}, result=payload, success=False)
    program = getattr(peer, 'formal_plans', {}).get(plan_name)
    if program is None and hasattr(self, 'formal_plans'):
        program = getattr(self, 'formal_plans', {}).get(plan_name)
        if program is not None:
            peer.formal_plans = getattr(peer, 'formal_plans', {})
            peer.formal_plans[plan_name] = program
    if program is None:
        payload = {'preflight': preflight.to_dict(), 'reason': f'peer {peer_name} has no plan named {plan_name}'}
        return DistributedFormalPlanPacket(packet_id=str(uuid.uuid4()), plan_name=plan_name, target_peer=peer_name, ast={}, result=payload, success=False)
    # synchronize referenced agents before final execution attempt
    sync_report = await self._sync_plan_agents_to_peer(peer, program)
    preflight = self.preflight_distributed_plan(peer_name, plan_name, depends_on=depends_on)
    if not preflight.executable:
        payload = {'preflight': preflight.to_dict(), 'sync': sync_report, 'reason': '; '.join(preflight.reasons) or 'preflight failed'}
        return DistributedFormalPlanPacket(packet_id=str(uuid.uuid4()), plan_name=plan_name, target_peer=peer_name, ast=program.to_dict(), result=payload, success=False)
    dispatch = PlanDispatchPacket(packet_id=str(uuid.uuid4()), plan_name=plan_name, target_peer=peer_name, ast=program.to_dict())
    result = await peer.execute_formal_plan(program)
    result_packet = PlanResultPacket(packet_id=str(uuid.uuid4()), plan_name=plan_name, source_peer=peer_name, success=bool(result.success), result=result.__dict__)
    payload = dict(result.__dict__)
    payload['dispatch'] = dispatch.__dict__
    payload['result_packet'] = result_packet.__dict__
    payload['preflight'] = preflight.to_dict()
    payload['sync'] = sync_report
    return DistributedFormalPlanPacket(packet_id=str(uuid.uuid4()), plan_name=plan_name, target_peer=peer_name, ast=program.to_dict(), result=payload, success=bool(result.success))

MultiAgentRuntime._collect_plan_aliases = _runtime_collect_plan_aliases
MultiAgentRuntime._sync_plan_agents_to_peer = _runtime_sync_plan_agents_to_peer
MultiAgentRuntime.execute_distributed_formal_plan = _runtime_execute_distributed_formal_plan_v22b


def _infer_plan_resources_v22(self: MultiAgentRuntime, program: Any) -> List[str]:
    resources: List[str] = [f'plan:{getattr(program, "name", "unknown")}' ]
    def walk(node: Any) -> None:
        kind = getattr(node, 'kind', '')
        cmd = getattr(node, 'command', None)
        if kind in {'do', 'vote', 'negotiate', 'run.group', 'fanout', 'delegate', 'command'} and cmd is not None:
            action = getattr(cmd, 'action', None)
            payload = getattr(cmd, 'payload', {}) or {}
            if action:
                resources.append(f'action:{action}')
            for key in ('case', 'drone', 'mission', 'target', 'group'):
                if key in payload and payload[key] not in (None, ''):
                    resources.append(f'{key}:{payload[key]}')
        for child in getattr(node, 'children', []) or []:
            walk(child)
        for child in getattr(node, 'then_branch', []) or []:
            walk(child)
        for child in getattr(node, 'else_branch', []) or []:
            walk(child)
    for node in getattr(program, 'root', []) or []:
        walk(node)
    out=[]
    for res in resources:
        if res not in out:
            out.append(res)
    return out

MultiAgentRuntime._infer_plan_resources = _infer_plan_resources_v22


# Ensure release/beta protocol extensions are loaded --------------------------
try:
    from . import release as _release  # noqa: F401
except Exception:
    pass


@dataclass
class RuntimeMergeReport:
    source_environment_id: str
    imported_agents: int = 0
    imported_groups: int = 0
    imported_events: int = 0
    imported_reactions: int = 0
    imported_nodes: int = 0
    imported_edges: int = 0
    imported_locks: int = 0
    replaced_locks: int = 0
    imported_executions: int = 0
    replaced_executions: int = 0
    skipped_events: int = 0
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    local_high_watermark: int = 0

    def to_dict(self) -> Dict[str, Any]:
        data = {
            'source_environment_id': self.source_environment_id,
            'imported_agents': self.imported_agents,
            'imported_groups': self.imported_groups,
            'imported_events': self.imported_events,
            'imported_reactions': self.imported_reactions,
            'imported_nodes': self.imported_nodes,
            'imported_edges': self.imported_edges,
            'imported_locks': self.imported_locks,
            'replaced_locks': self.replaced_locks,
            'imported_executions': self.imported_executions,
            'replaced_executions': self.replaced_executions,
            'skipped_events': self.skipped_events,
            'conflicts': list(self.conflicts),
            'local_high_watermark': self.local_high_watermark,
        }
        # compatibility aliases for older iterations/tests
        data['merged_agents'] = data['imported_agents']
        data['merged_groups'] = data['imported_groups']
        data['merged_events'] = data['imported_events']
        data['merged_reactions'] = data['imported_reactions']
        data['merged_nodes'] = data['imported_nodes']
        data['merged_edges'] = data['imported_edges']
        return data

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

# iteration 25 overrides -----------------------------------------------------
from .persistence import SQLiteRuntimeStore

def _runtime_export_state_v25(self: MultiAgentRuntime) -> RuntimeStatePacket:
    _runtime_coordination_init(self)
    policy = self.gateway.policy_engine.snapshot()
    return RuntimeStatePacket(
        packet_id=str(uuid.uuid4()),
        environment_id=self.environment.environment_id,
        agents=self.describe_agents(),
        groups=self.describe_groups(),
        policy=policy,
        journal=self.environment.memory.event_journal(),
        graph=self.environment.semantic_graph.export(),
        emitted_at=time.time(),
    )

def _runtime_state_payload_v25(self: MultiAgentRuntime) -> Dict[str, Any]:
    pkt = self.export_runtime_state()
    payload = pkt.__dict__.copy()
    payload['runtime_id'] = getattr(self, 'runtime_id', f'runtime:{id(self)}')
    payload['locks'] = self.list_locks()
    payload['executions'] = self.execution_state().executions
    payload['heartbeat'] = self.heartbeat().to_dict()
    payload['peers'] = dict(getattr(self.gateway, 'peers', {}))
    return payload

def _runtime_save_sqlite_v25(self: MultiAgentRuntime, base: str) -> Dict[str, Any]:
    path = str(base) if str(base).endswith('.sqlite') else str(base) + '.runtime.sqlite'
    store = SQLiteRuntimeStore(path)
    store.save_runtime_state(self.runtime_state_payload())
    return {'runtime': path}

def _runtime_load_sqlite_v25(self: MultiAgentRuntime, base: str) -> Dict[str, Any]:
    path = str(base) if str(base).endswith('.sqlite') else str(base) + '.runtime.sqlite'
    store = SQLiteRuntimeStore(path)
    state = store.latest_runtime_state()
    if not state:
        return {'runtime': path, 'loaded': False}
    report = self.merge_runtime_state(RuntimeStatePacket(
        packet_id=str(state.get('packet_id','loaded')),
        environment_id=str(state.get('environment_id', self.environment.environment_id)),
        agents=list(state.get('agents', [])),
        groups=list(state.get('groups', [])),
        policy=dict(state.get('policy', {})),
        journal=list(state.get('journal', [])),
        graph=dict(state.get('graph', {'nodes': {}, 'edges': []})),
        emitted_at=float(state.get('emitted_at', time.time())),
    ))
    # import peers/hints opportunistically
    for peer_name, peer in (state.get('peers') or {}).items():
        self.gateway.peers[peer_name] = peer
    return {'runtime': path, 'loaded': True, 'merge': report.to_dict()}

def _runtime_merge_state_v25(self: MultiAgentRuntime, packet: RuntimeStatePacket) -> RuntimeMergeReport:
    _runtime_coordination_init(self)
    report = RuntimeMergeReport(source_environment_id=packet.environment_id)
    local_ids = {a['alias']: a for a in self.describe_agents()}
    for agent in packet.agents:
        alias = agent.get('alias')
        if alias and alias not in local_ids:
            self.peers_hint(alias, agent)
            report.imported_agents += 1
    for group in packet.groups:
        name = group.get('name')
        if not name:
            continue
        if name not in self.groups:
            self.groups[name] = GroupProfile(name=name, members=list(group.get('members', [])), shared_contexts=list(group.get('shared_contexts', [])), metadata=dict(group.get('metadata', {})))
            report.imported_groups += 1
        else:
            current = self.groups[name]
            before_members = set(current.members)
            current.members = list(dict.fromkeys(current.members + list(group.get('members', []))))
            current.shared_contexts = list(dict.fromkeys(current.shared_contexts + list(group.get('shared_contexts', []))))
            current.metadata.update(group.get('metadata', {}))
            if set(current.members) != before_members:
                report.imported_groups += 1
    local_journal = self.environment.memory.event_journal()
    existing_seq_map = {int(e.get('sequence_number', 0)): e for e in local_journal if int(e.get('sequence_number', 0)) > 0}
    report.local_high_watermark = max(existing_seq_map.keys() or [0])
    accepted = []
    accepted_reactions = []
    reaction_ids = {r.get('reaction_id') for r in self.environment.memory.to_dict().get('reactions', [])}
    for j in sorted([j for j in packet.journal if j.get('sequence_number', 0) > 0], key=lambda x: (x.get('sequence_number', 0), x.get('event', {}).get('occurred_at', 0.0))):
        seq = int(j.get('sequence_number', 0))
        event = j.get('event', j)
        local = existing_seq_map.get(seq)
        if local is not None:
            local_evt = local.get('event', local)
            if local_evt.get('event_id') != event.get('event_id') or local_evt.get('correlation_id') != event.get('correlation_id'):
                report.conflicts.append({'kind': 'sequence_conflict', 'sequence_number': seq, 'local_event_id': local_evt.get('event_id'), 'remote_event_id': event.get('event_id')})
            else:
                report.skipped_events += 1
            continue
        accepted.append(event)
        reaction = j.get('reaction')
        if reaction is not None and reaction.get('reaction_id') not in reaction_ids:
            accepted_reactions.append(reaction)
            reaction_ids.add(reaction.get('reaction_id'))
    if accepted or accepted_reactions:
        mem_report = self.environment.merge_memory(CausalMemory.from_dict({'events': accepted, 'reactions': accepted_reactions, 'interactions': [], 'phenomena': []}))
        report.imported_events = mem_report.get('events', 0)
        report.imported_reactions = mem_report.get('reactions', 0)
    graph_report = self.environment.semantic_graph.merge_export(packet.graph)
    report.imported_nodes = graph_report.get('nodes', 0)
    report.imported_edges = graph_report.get('edges', 0)
    # merge locks/executions/peers if available on packet-like object dict
    state = packet.__dict__ if hasattr(packet, '__dict__') else {}
    for lock in state.get('locks', []) or []:
        resource = lock.get('resource')
        if not resource:
            continue
        incoming_expires = float(lock.get('expires_at', 0.0))
        current = self._leases.get(resource)
        if current is None:
            self._leases[resource] = ExecutionLease(resource=resource, owner=str(lock.get('owner','')), acquired_at=float(lock.get('acquired_at', time.time())), expires_at=incoming_expires)
            report.imported_locks += 1
        else:
            if incoming_expires > current.expires_at:
                self._leases[resource] = ExecutionLease(resource=resource, owner=str(lock.get('owner','')), acquired_at=float(lock.get('acquired_at', time.time())), expires_at=incoming_expires)
                report.replaced_locks += 1
            elif current.owner != str(lock.get('owner','')):
                report.conflicts.append({'kind': 'lock_conflict', 'resource': resource, 'local_owner': current.owner, 'remote_owner': lock.get('owner')})
    for ex in state.get('executions', []) or []:
        exid = str(ex.get('execution_id') or '')
        if not exid:
            continue
        current = self._executions.get(exid)
        if current is None:
            self._executions[exid] = dict(ex)
            report.imported_executions += 1
        else:
            cur_stamp = float(current.get('completed_at', current.get('started_at', 0.0)))
            new_stamp = float(ex.get('completed_at', ex.get('started_at', 0.0)))
            if new_stamp > cur_stamp or (current.get('state') == 'running' and ex.get('state') != 'running'):
                self._executions[exid] = dict(ex)
                report.replaced_executions += 1
    for peer_name, peer in state.get('peers', {}).items():
        if peer_name not in self.gateway.peers:
            self.gateway.peers[peer_name] = peer
    return report

def _gateway_runtime_merge_packet_v25(self: MepGateway, runtime: MultiAgentRuntime, peer_name: str) -> CanonicalPacket:
    report = runtime.merge_peer_state(peer_name)
    body = {
        'packet_id': str(uuid.uuid4()),
        'source_runtime_id': getattr(runtime, 'runtime_id', f'runtime:{id(runtime)}'),
        'target_runtime_id': getattr(getattr(runtime, '_runtime_peers', {}).get(peer_name), 'runtime_id', peer_name),
        'peer_count_delta': int(report.imported_agents),
        'execution_updates': int(report.imported_executions + report.replaced_executions),
        'lock_updates': int(report.imported_locks + report.replaced_locks),
        'merged_at': time.time(),
        'details': report.to_dict(),
    }
    return ProtocolCodec.pack('runtime.merge_state', body)

MepGateway.runtime_merge_packet = _gateway_runtime_merge_packet_v25

try:
    __all__.extend(['RuntimeMergeReport'])
except Exception:
    pass


# iteration 25 final bindings -----------------------------------------------
def _gateway_runtime_merge_packet_v25b(self: MepGateway, runtime: MultiAgentRuntime, peer_name: str) -> CanonicalPacket:
    peers = getattr(runtime, '_runtime_peers', {})
    if peer_name not in peers:
        raise KeyError(f'unknown runtime peer: {peer_name}')
    peer = peers[peer_name]
    packet = peer.export_runtime_state()
    packet.locks = peer.list_locks()
    packet.executions = peer.execution_state().executions
    packet.peers = dict(getattr(peer.gateway, 'peers', {}))
    report = runtime.merge_runtime_state(packet)
    body = {
        'packet_id': str(uuid.uuid4()),
        'source_runtime_id': getattr(peer, 'runtime_id', peer_name),
        'target_runtime_id': getattr(runtime, 'runtime_id', f'runtime:{id(runtime)}'),
        'peer_count_delta': int(report.imported_agents),
        'execution_updates': int(report.imported_executions + report.replaced_executions),
        'lock_updates': int(report.imported_locks + report.replaced_locks),
        'merged_at': time.time(),
        'details': report.to_dict(),
    }
    return ProtocolCodec.pack('runtime.merge_state', body)

MultiAgentRuntime.export_runtime_state = _runtime_export_state_v25
MultiAgentRuntime.runtime_state_payload = _runtime_state_payload_v25
MultiAgentRuntime.save_runtime_sqlite = _runtime_save_sqlite_v25
MultiAgentRuntime.load_runtime_sqlite = _runtime_load_sqlite_v25
MultiAgentRuntime.merge_runtime_state = _runtime_merge_state_v25
MepGateway.runtime_merge_packet = _gateway_runtime_merge_packet_v25b
