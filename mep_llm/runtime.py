from __future__ import annotations

import asyncio
import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

from edp_sdk.intelligence import ActionRanker
from edp_sdk.semantics import SenseVector, nearest_by_cosine


class CircuitState(Enum):
    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 4, recovery_seconds: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self.failures = 0
        self.last_failure = 0.0
        self._state = CircuitState.CLOSED

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and time.time() - self.last_failure >= self.recovery_seconds:
            self._state = CircuitState.HALF_OPEN
        return self._state

    def allow(self) -> bool:
        return self.state in {CircuitState.CLOSED, CircuitState.HALF_OPEN}

    def record_success(self) -> None:
        self.failures = 0
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failures += 1
        self.last_failure = time.time()
        if self.failures >= self.failure_threshold:
            self._state = CircuitState.OPEN


@dataclass
class ErrorBudget:
    max_failures: int = 5
    failures: int = 0

    def fail(self) -> None:
        self.failures += 1

    def ok(self) -> None:
        self.failures = max(0, self.failures - 1)

    @property
    def degraded(self) -> bool:
        return self.failures >= self.max_failures


class LlmProvider(Protocol):
    async def complete(self, prompt: str, *, model: str, timeout_s: float = 45.0) -> str: ...


class DemoProvider:
    async def complete(self, prompt: str, *, model: str, timeout_s: float = 45.0) -> str:
        return json.dumps({"action_type": "", "confidence": 0.0, "payload": {}, "provider": "demo"})


class _JsonHttpProvider:
    def __init__(self, *, api_key_env: Optional[str] = None, endpoint: str = "") -> None:
        self.api_key_env = api_key_env
        self.endpoint = endpoint

    def _request(self, payload: Dict[str, Any], headers: Dict[str, str], timeout_s: float) -> str:
        req = urllib.request.Request(self.endpoint, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.read().decode('utf-8')


class OllamaProvider(_JsonHttpProvider):
    def __init__(self, endpoint: str = 'http://localhost:11434/api/generate') -> None:
        super().__init__(endpoint=endpoint)

    async def complete(self, prompt: str, *, model: str, timeout_s: float = 45.0) -> str:
        def _call() -> str:
            body = {"model": model, "prompt": prompt, "stream": False}
            raw = self._request(body, {"Content-Type": "application/json"}, timeout_s)
            data = json.loads(raw)
            return str(data.get('response', ''))
        return await asyncio.to_thread(_call)


class OpenAIProvider(_JsonHttpProvider):
    def __init__(self, endpoint: str = 'https://api.openai.com/v1/chat/completions', api_key_env: str = 'OPENAI_API_KEY') -> None:
        super().__init__(api_key_env=api_key_env, endpoint=endpoint)

    async def complete(self, prompt: str, *, model: str, timeout_s: float = 45.0) -> str:
        key = os.getenv(self.api_key_env or '')
        if not key:
            raise RuntimeError(f'missing API key env: {self.api_key_env}')
        def _call() -> str:
            body = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2}
            raw = self._request(body, {"Content-Type": "application/json", "Authorization": f'Bearer {key}'}, timeout_s)
            data = json.loads(raw)
            return str(((data.get('choices') or [{}])[0].get('message') or {}).get('content', ''))
        return await asyncio.to_thread(_call)


class AnthropicProvider(_JsonHttpProvider):
    def __init__(self, endpoint: str = 'https://api.anthropic.com/v1/messages', api_key_env: str = 'ANTHROPIC_API_KEY') -> None:
        super().__init__(api_key_env=api_key_env, endpoint=endpoint)

    async def complete(self, prompt: str, *, model: str, timeout_s: float = 45.0) -> str:
        key = os.getenv(self.api_key_env or '')
        if not key:
            raise RuntimeError(f'missing API key env: {self.api_key_env}')
        def _call() -> str:
            body = {"model": model, "max_tokens": 256, "messages": [{"role": "user", "content": prompt}]}
            raw = self._request(body, {"Content-Type": "application/json", "x-api-key": key, "anthropic-version": '2023-06-01'}, timeout_s)
            data = json.loads(raw)
            content = data.get('content') or []
            if content and isinstance(content[0], dict):
                return str(content[0].get('text', ''))
            return ''
        return await asyncio.to_thread(_call)


def make_provider(name: str) -> LlmProvider:
    lowered = (name or 'demo').lower()
    if lowered == 'ollama':
        return OllamaProvider()
    if lowered == 'openai':
        return OpenAIProvider()
    if lowered == 'anthropic':
        return AnthropicProvider()
    return DemoProvider()


@dataclass
class DecisionCandidate:
    action_type: str
    confidence: float = 0.0
    payload: Dict[str, Any] = field(default_factory=dict)
    raw: str = ''


class RobustDecisionParser:
    PREFIX_RE = re.compile(r'^\[[^\]]+\]\s*')

    @classmethod
    def parse(cls, raw: str) -> DecisionCandidate:
        cleaned = cls.PREFIX_RE.sub('', (raw or '').strip())
        try:
            data = json.loads(cleaned)
            action_type = str(data.get('action_type') or data.get('action') or '')
            confidence = float(data.get('confidence', 0.0) or 0.0)
            payload = data.get('payload', {}) or {}
            if action_type:
                return DecisionCandidate(action_type=action_type, confidence=confidence, payload=payload, raw=raw)
        except Exception:
            pass
        m = re.search(r'([a-zA-Z_][\w.-]+)', cleaned)
        return DecisionCandidate(action_type=m.group(1) if m else '', confidence=0.0, payload={}, raw=raw)


@dataclass
class ContrastiveMemoryRecord:
    goal: str
    context_name: str
    action_type: str
    success: bool
    score: float
    created_at: float = field(default_factory=time.time)


@dataclass
class ReactiveAttentionMap:
    anchors: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"anchors": list(self.anchors)}


@dataclass
class GoalPreview:
    alias: str
    goal: str
    selected_context: str
    goal_sense: Dict[str, Any]
    context_scores: List[Dict[str, Any]]
    candidates: List[Dict[str, Any]]
    attention: Dict[str, Any]
    prompt: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alias": self.alias,
            "goal": self.goal,
            "selected_context": self.selected_context,
            "goal_sense": dict(self.goal_sense),
            "context_scores": list(self.context_scores),
            "candidates": list(self.candidates),
            "attention": dict(self.attention),
            "prompt": self.prompt,
        }


@dataclass
class GoalDecision:
    alias: str
    goal: str
    context_name: str
    action_type: str
    payload: Dict[str, Any]
    confidence: float
    strategy: str
    preview: Dict[str, Any]
    execution: Optional[Dict[str, Any]] = None
    provider_raw: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alias": self.alias,
            "goal": self.goal,
            "context_name": self.context_name,
            "action_type": self.action_type,
            "payload": dict(self.payload),
            "confidence": self.confidence,
            "strategy": self.strategy,
            "preview": dict(self.preview),
            "execution": None if self.execution is None else dict(self.execution),
            "provider_raw": self.provider_raw,
        }




@dataclass
class AgentPersona:
    role: str
    title: str
    voice: str
    policy: str


@dataclass
class ChatTurn:
    alias: str
    role: str
    message: str
    response: str
    context_name: str
    action_type: str = ''
    executed: bool = False
    success: Optional[bool] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alias": self.alias,
            "role": self.role,
            "message": self.message,
            "response": self.response,
            "context_name": self.context_name,
            "action_type": self.action_type,
            "executed": self.executed,
            "success": self.success,
            "created_at": self.created_at,
        }


class SemanticIntelligenceLayer:
    KEYWORDS: Dict[str, List[Tuple[SenseVector, float]]] = {
        'open': [(SenseVector.normative('open', 0.9), 1.0)],
        'assign': [(SenseVector.social('assign', 0.9), 1.0)],
        'resolve': [(SenseVector.normative('resolve', 0.9), 1.0)],
        'escalate': [(SenseVector.causal('escalate', 0.9), 1.0), (SenseVector.normative('escalate', 0.7), 0.7)],
        'ping': [(SenseVector.technical('ping', 0.9), 1.0)],
        'scan': [(SenseVector.spatial('scan', 0.9), 1.0)],
        'return': [(SenseVector.temporal('return', 0.7), 0.8)],
        'land': [(SenseVector.spatial('land', 0.8), 1.0)],
        'battery': [(SenseVector.technical('battery', 0.8), 1.0)],
        'incident': [(SenseVector.normative('incident', 0.7), 1.0)],
        'case': [(SenseVector.normative('case', 0.7), 1.0)],
        'review': [(SenseVector.normative('review', 0.7), 1.0)],
        'dispatch': [(SenseVector.social('dispatch', 0.7), 1.0)],
        'drone': [(SenseVector.spatial('drone', 0.8), 1.0)],
        'emergency': [(SenseVector.causal('emergency', 1.0), 1.0)],
        'high': [(SenseVector.causal('high severity', 0.8), 0.6)],
        'critical': [(SenseVector.causal('critical', 1.0), 1.0)],
    }

    def __init__(self) -> None:
        self.memory: List[ContrastiveMemoryRecord] = []

    def remember(self, goal: str, context_name: str, action_type: str, success: bool, score: float) -> None:
        self.memory.append(ContrastiveMemoryRecord(goal, context_name, action_type, success, score))
        self.memory = self.memory[-128:]

    def score_prior(self, goal: str, context_name: str, action_type: str) -> float:
        matches = [m for m in self.memory if m.context_name == context_name and m.action_type == action_type]
        if not matches:
            return 0.0
        successes = sum(1 for m in matches if m.success)
        return successes / len(matches)

    def translate_goal_to_sense(self, goal: str) -> SenseVector:
        words = re.findall(r'[a-zA-Z][\w-]*', goal.lower())
        parts: List[Tuple[SenseVector, float]] = []
        for word in words:
            for vec, weight in self.KEYWORDS.get(word, []):
                parts.append((vec, weight))
        if not parts:
            parts = [(SenseVector.normative('generic goal', 0.5), 1.0)]
        return SenseVector.combine('goal', goal[:80], parts)

    def situation_as_sense(self, envelope: Any) -> SenseVector:
        basis = ((getattr(envelope, 'situation', None) or {}).get('basis') or {})
        if basis:
            return SenseVector.from_dict(basis)
        return SenseVector.zeros('situation')

    def attention_from_envelope(self, envelope: Any) -> ReactiveAttentionMap:
        anchors: List[Dict[str, Any]] = []
        for item in (getattr(envelope, 'phenomena', None) or [])[:5]:
            anchors.append({"kind": "phenomenon", "label": item.get('category', 'unknown'), "weight": float(item.get('intensity', 0.7) or 0.7)})
        for item in (getattr(envelope, 'circumstances', None) or [])[:5]:
            if item.get('holds'):
                anchors.append({"kind": "circumstance", "label": item.get('name', 'unknown'), "weight": 0.6 if item.get('role') == 'enabler' else 0.8})
        for item in (getattr(envelope, 'available_actions', None) or [])[:5]:
            anchors.append({"kind": "action", "label": item.get('action_type', 'unknown'), "weight": float(item.get('score', 0.0) or 0.0)})
        anchors.sort(key=lambda a: float(a.get('weight', 0.0)), reverse=True)
        return ReactiveAttentionMap(anchors=anchors[:8])


DEFAULT_PERSONAS: Dict[str, AgentPersona] = {
    "admin": AgentPersona("admin", "Administrator", "precise", "act decisively within policy"),
    "operator": AgentPersona("operator", "Operator", "focused", "stabilize the environment"),
    "dispatcher": AgentPersona("dispatcher", "Dispatcher", "coordinated", "route work to the right target"),
    "reviewer": AgentPersona("reviewer", "Reviewer", "deliberate", "verify before resolving"),
    "responder": AgentPersona("responder", "Responder", "direct", "mitigate and close loops"),
    "pilot": AgentPersona("pilot", "Pilot", "situational", "keep mission integrity and safety"),
    "controller": AgentPersona("controller", "Controller", "commanding", "protect shared airspace and coordination"),
    "agent": AgentPersona("agent", "Agent", "neutral", "operate inside the structured environment"),
}

def persona_for_role(role: str) -> AgentPersona:
    return DEFAULT_PERSONAS.get(role, AgentPersona(role, role.title(), "neutral", "operate inside the structured environment"))


@dataclass
class AgentEngineConfig:
    provider: str = 'demo'
    model: str = 'semantic-demo'
    timeout_s: float = 45.0
    retries: int = 3
    inject_memory: bool = False
    inject_situation: bool = False
    memory_size: int = 4


class AgentDecisionEngine:
    def __init__(self, runtime: Any, *, provider: Optional[LlmProvider] = None, config: Optional[AgentEngineConfig] = None, semantic: Optional[SemanticIntelligenceLayer] = None) -> None:
        self.runtime = runtime
        self.config = config or AgentEngineConfig()
        self.provider = provider or make_provider(self.config.provider)
        self.semantic = semantic or SemanticIntelligenceLayer()
        self.breaker = CircuitBreaker()
        self.error_budget = ErrorBudget()
        self._history: List[Dict[str, Any]] = []
        self._chat_history: Dict[str, List[ChatTurn]] = {}

    def configure(self, **updates: Any) -> Dict[str, Any]:
        for key, value in updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self.provider = make_provider(self.config.provider)
        return self.status()

    def status(self) -> Dict[str, Any]:
        return {
            "provider": self.config.provider,
            "model": self.config.model,
            "timeout_s": self.config.timeout_s,
            "retries": self.config.retries,
            "inject_memory": self.config.inject_memory,
            "inject_situation": self.config.inject_situation,
            "memory_size": self.config.memory_size,
            "circuit": self.breaker.state.name.lower(),
            "failures": self.breaker.failures,
            "degraded": self.error_budget.degraded,
            "memory_items": len(self.semantic.memory),
            "chat_sessions": len(self._chat_history),
            "chat_turns": sum(len(v) for v in self._chat_history.values()),
        }

    def _extract_payload_hints(self, goal: str, action_type: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        m = re.search(r'\b(INC-[A-Za-z0-9_-]+|CASE-[A-Za-z0-9_-]+)\b', goal, re.I)
        if m:
            payload['case'] = m.group(1).upper()
        sev = re.search(r'\b(low|medium|high|critical)\b', goal, re.I)
        if sev:
            payload['severity'] = sev.group(1).lower()
        target = re.search(r'\bto\s+([A-Za-z][\w-]*)\b', goal)
        if target and any(tok in action_type for tok in ('assign', 'delegate')):
            payload['target'] = target.group(1)
        return payload

    def _candidate_boost(self, goal: str, action_type: str, description: str) -> float:
        text = f"{action_type} {description}".lower()
        goal_words = set(re.findall(r'[a-zA-Z][\w-]*', goal.lower()))
        if not goal_words:
            return 0.0
        overlap = sum(1 for w in goal_words if w in text)
        return min(0.2, overlap * 0.04)

    def _attention_weight(self, preview: GoalPreview, action_type: str) -> float:
        weight = 0.0
        for anchor in preview.attention.get('anchors', []):
            label = str(anchor.get('label', '')).lower()
            if label and (label in action_type.lower() or action_type.lower() in label):
                weight += float(anchor.get('weight', 0.0)) * 0.05
        return min(0.25, weight)

    def _negotiated_score(self, preview: GoalPreview, candidate: Dict[str, Any], *, action_basis: Optional[SenseVector] = None, context_basis: Optional[SenseVector] = None) -> float:
        score = float(candidate.get('score', 0.0))
        score += float(candidate.get('contrastive_prior', 0.0)) * 0.25
        score += self._attention_weight(preview, str(candidate.get('action_type', '')))
        if action_basis is not None:
            score += self.semantic.attention_alignment(action_basis, ReactiveAttentionMap(anchors=list(preview.attention.get('anchors', [])))) * 0.12
        if action_basis is not None and context_basis is not None:
            score += action_basis.apply_context_operator(context_basis).cosine(SenseVector.from_dict(preview.goal_sense)) * 0.08
        return score

    def _build_prompt(self, alias: str, goal: str, preview: GoalPreview) -> str:
        memory_block = []
        if self.config.inject_memory:
            for rec in self.semantic.memory[-self.config.memory_size:]:
                memory_block.append({"goal": rec.goal, "context": rec.context_name, "action": rec.action_type, "success": rec.success, "score": rec.score})
        tone = "neutral"
        if self.config.inject_situation:
            tone = "urgent" if any(a.get('kind') == 'phenomenon' and a.get('weight', 0) >= 0.8 for a in preview.attention['anchors']) else 'controlled'
        envelope_summary = {
            "context": preview.selected_context,
            "goal": goal,
            "attention": preview.attention,
            "candidates": preview.candidates,
            "tone": tone,
            "memory": memory_block,
        }
        return (
            "You are operating inside a structured causal environment. "
            "Choose exactly one action from the candidate list. Return strict JSON with keys action_type, confidence, payload.\n"
            + json.dumps(envelope_summary, ensure_ascii=False)
        )

    def history(self, alias: Optional[str] = None) -> List[Dict[str, Any]]:
        if alias is None:
            return list(self._history)
        return [h for h in self._history if h.get("alias") == alias]

    def chat_history(self, alias: Optional[str] = None) -> List[Dict[str, Any]]:
        if alias is None:
            out: List[Dict[str, Any]] = []
            for items in self._chat_history.values():
                out.extend(t.to_dict() for t in items)
            return out
        return [t.to_dict() for t in self._chat_history.get(alias, [])]

    def export_learning_bundle(self) -> Dict[str, Any]:
        return {
            "contrastive_memory": [m.__dict__ for m in self.semantic.memory],
            "decision_history": list(self._history),
            "chat_history": self.chat_history(),
            "status": self.status(),
        }

    def _imperative_goal(self, text: str) -> bool:
        lowered = text.strip().lower()
        if lowered.endswith('?'):
            return False
        starters = ("open", "assign", "resolve", "escalate", "scan", "land", "return", "ping", "move", "takeoff", "start", "stop")
        return lowered.startswith(starters) or "please " in lowered or " case " in lowered or " incident " in lowered

    def _build_chat_prompt(self, alias: str, utterance: str, preview: GoalPreview, *, executed: bool) -> str:
        profile = getattr(self.runtime, 'agents', {}).get(alias)
        persona = persona_for_role(getattr(profile, 'role', 'agent'))
        history = [t.to_dict() for t in self._chat_history.get(alias, [])[-4:]]
        body = {
            "alias": alias,
            "persona": {"title": persona.title, "voice": persona.voice, "policy": persona.policy},
            "utterance": utterance,
            "selected_context": preview.selected_context,
            "candidates": preview.candidates[:4],
            "attention": preview.attention,
            "executed": executed,
            "history": history,
        }
        return (
            "You are an agent inside a structured causal environment. Respond in concise JSON with keys reply, action_type, execute, confidence, payload. "
            "Do not invent unavailable actions.\n" + json.dumps(body, ensure_ascii=False)
        )

    def _fallback_reply(self, alias: str, utterance: str, preview: GoalPreview, decision: Optional[GoalDecision] = None) -> str:
        profile = getattr(self.runtime, 'agents', {}).get(alias)
        persona = persona_for_role(getattr(profile, 'role', 'agent'))
        if decision and decision.execution:
            status = decision.execution.get('status', 'unknown')
            msg = decision.execution.get('message', '')
            return f"{persona.title}: executed {decision.action_type} in {decision.context_name} with status={status}. {msg}".strip()
        top = preview.candidates[0] if preview.candidates else None
        if utterance.strip().endswith('?'):
            if top:
                return f"{persona.title}: in {preview.selected_context}, the strongest admissible action is {top['action_type']} (score={top.get('negotiated_score', 0.0):.3f})."
            return f"{persona.title}: no admissible action is currently available in {preview.selected_context}."
        if top:
            return f"{persona.title}: I can act in {preview.selected_context}. Best candidate is {top['action_type']} (score={top.get('negotiated_score', 0.0):.3f})."
        return f"{persona.title}: I cannot derive a valid action from the current environment."

    async def chat(self, alias: str, utterance: str, *, context_name: Optional[str] = None, interface_name: Optional[str] = None, auto_execute: Optional[bool] = None) -> Dict[str, Any]:
        preview = self.preview(alias, utterance, context_name=context_name, interface_name=interface_name)
        should_execute = self._imperative_goal(utterance) if auto_execute is None else bool(auto_execute)
        decision: Optional[GoalDecision] = None
        provider_raw = ''
        reply = ''
        parsed = DecisionCandidate(action_type='', confidence=0.0, payload={})
        if self.config.provider != 'demo' and not self.error_budget.degraded and self.breaker.allow():
            prompt = self._build_chat_prompt(alias, utterance, preview, executed=should_execute)
            for attempt in range(1, self.config.retries + 1):
                try:
                    provider_raw = await self.provider.complete(prompt, model=self.config.model, timeout_s=self.config.timeout_s)
                    parsed = RobustDecisionParser.parse(provider_raw)
                    self.breaker.record_success()
                    self.error_budget.ok()
                    break
                except Exception:
                    self.breaker.record_failure()
                    self.error_budget.fail()
                    await asyncio.sleep(min(0.25 * attempt, 1.0))
        if should_execute:
            decision = await self.decide(alias, utterance, context_name=context_name, interface_name=interface_name, execute=True)
        reply = self._fallback_reply(alias, utterance, preview, decision)
        turn = ChatTurn(alias=alias, role=getattr(getattr(self.runtime, 'agents', {}).get(alias), 'role', 'agent'), message=utterance, response=reply, context_name=preview.selected_context, action_type=(decision.action_type if decision else ''), executed=bool(decision and decision.execution), success=(decision.execution.get('status') == 'success' if decision and decision.execution else None))
        self._chat_history.setdefault(alias, []).append(turn)
        self._chat_history[alias] = self._chat_history[alias][-32:]
        return {
            "reply": reply,
            "alias": alias,
            "context_name": preview.selected_context,
            "preview": preview.to_dict(),
            "decision": None if decision is None else decision.to_dict(),
            "provider_raw": provider_raw,
        }

    def preview(self, alias: str, goal: str, *, context_name: Optional[str] = None, interface_name: Optional[str] = None) -> GoalPreview:
        goal_sense = self.semantic.translate_goal_to_sense(goal)
        accessible = [context_name] if context_name else self.runtime.accessible_contexts(alias)
        scored_contexts: List[Dict[str, Any]] = []
        best_name = accessible[0]
        best_score = -1.0
        for name in accessible:
            ctx = self.runtime.environment.contexts[name]
            score = goal_sense.cosine(ctx.basis)
            scored_contexts.append({"context_name": name, "score": score, "basis": ctx.basis.to_dict()})
            if score > best_score:
                best_name, best_score = name, score
        envelope = self.runtime.envelope(alias, context_name=best_name, interface_name=interface_name)
        attention = self.semantic.attention_from_envelope(envelope)
        situation_sense = self.semantic.situation_as_sense(envelope)
        ranked = self.runtime.recommend(alias, context_name=best_name, interface_name=interface_name, payload={})
        candidates: List[Dict[str, Any]] = []
        for rec in ranked[:8]:
            ctx = self.runtime.environment.contexts[best_name]
            action = ctx._actions.get(rec['action_type']) or next((c._actions[rec['action_type']] for c in self.runtime.environment.contexts.values() if rec['action_type'] in c._actions), None)
            action_basis = action.basis if action is not None else SenseVector.zeros(rec['action_type'])
            similarity = goal_sense.cosine(action_basis.apply_context_operator(ctx.basis))
            prior = self.semantic.score_prior(goal, best_name, rec['action_type'])
            boost = self._candidate_boost(goal, rec['action_type'], rec.get('description', ''))
            item = dict(rec)
            item['goal_similarity'] = similarity
            item['contrastive_prior'] = prior
            item['lexical_boost'] = boost
            item['attention_alignment'] = self.semantic.attention_alignment(action_basis, attention)
            final = 0.48 * float(rec.get('total_score', rec.get('score', 0.0))) + 0.20 * similarity + boost
            final += self._negotiated_score(GoalPreview(alias, goal, best_name, goal_sense.to_dict(), scored_contexts, [], attention.to_dict()), item, action_basis=action_basis, context_basis=ctx.basis)
            item['negotiated_score'] = final
            candidates.append(item)
        candidates.sort(key=lambda x: x.get('negotiated_score', 0.0), reverse=True)
        prompt = self._build_prompt(alias, goal, GoalPreview(alias, goal, best_name, goal_sense.to_dict(), scored_contexts, candidates, attention.to_dict()))
        return GoalPreview(alias=alias, goal=goal, selected_context=best_name, goal_sense=goal_sense.to_dict(), context_scores=scored_contexts, candidates=candidates, attention=attention.to_dict(), prompt=prompt)

    async def decide(self, alias: str, goal: str, *, context_name: Optional[str] = None, interface_name: Optional[str] = None, execute: bool = False) -> GoalDecision:
        preview = self.preview(alias, goal, context_name=context_name, interface_name=interface_name)
        chosen = preview.candidates[0] if preview.candidates else {"action_type": "", "negotiated_score": 0.0}
        provider_raw = ''
        strategy = 'semantic-fallback'
        parsed = DecisionCandidate(action_type='', confidence=0.0, payload={})
        if self.config.provider != 'demo' and not self.error_budget.degraded and self.breaker.allow():
            for attempt in range(1, self.config.retries + 1):
                try:
                    provider_raw = await self.provider.complete(preview.prompt or '', model=self.config.model, timeout_s=self.config.timeout_s)
                    parsed = RobustDecisionParser.parse(provider_raw)
                    if parsed.action_type:
                        self.breaker.record_success()
                        self.error_budget.ok()
                        strategy = f'{self.config.provider}-negotiated'
                        break
                    raise ValueError('empty llm decision')
                except Exception:
                    self.breaker.record_failure()
                    self.error_budget.fail()
                    await asyncio.sleep(min(0.25 * attempt, 1.0))
        if parsed.action_type:
            # fuzzy map to candidate catalog
            cand_names = [c['action_type'] for c in preview.candidates]
            if parsed.action_type not in cand_names:
                m = nearest_by_cosine(self.semantic.translate_goal_to_sense(parsed.action_type), [(c['action_type'], self.semantic.translate_goal_to_sense(c['action_type'])) for c in preview.candidates], top_k=1)
                if m:
                    parsed.action_type = m[0][0]
            match = next((c for c in preview.candidates if c['action_type'] == parsed.action_type), None)
            if match is not None:
                chosen = match
        action_type = str(chosen.get('action_type', ''))
        payload = self._extract_payload_hints(goal, action_type)
        payload.update(parsed.payload)
        execution = None
        confidence = max(float(parsed.confidence or 0.0), float(chosen.get('negotiated_score', 0.0)))
        if execute and action_type:
            execution = await self.runtime.execute(alias, action_type, payload, context_name=preview.selected_context, interface_name=interface_name)
            success = execution.get('status') == 'success'
            self.semantic.remember(goal, preview.selected_context, action_type, success, float(chosen.get('negotiated_score', 0.0)))
            self._history.append({"alias": alias, "goal": goal, "action_type": action_type, "context_name": preview.selected_context, "success": success, "time": time.time()})
            self._history = self._history[-64:]
        return GoalDecision(alias=alias, goal=goal, context_name=preview.selected_context, action_type=action_type, payload=payload, confidence=confidence, strategy=strategy, preview=preview.to_dict(), execution=execution, provider_raw=provider_raw)


@dataclass
class GroupGoalPreview:
    group: str
    goal: str
    selected_context: str
    candidate_actions: List[Dict[str, Any]]
    member_previews: List[Dict[str, Any]]
    negotiation_basis: Dict[str, Any]
    def to_dict(self) -> Dict[str, Any]:
        return {
            "group": self.group,
            "goal": self.goal,
            "selected_context": self.selected_context,
            "candidate_actions": list(self.candidate_actions),
            "member_previews": list(self.member_previews),
            "negotiation_basis": dict(self.negotiation_basis),
        }


@dataclass
class GroupGoalDecision:
    group: str
    goal: str
    action_type: str
    context_name: str
    selected_actor: Optional[str]
    negotiated: Dict[str, Any]
    execution: Optional[Dict[str, Any]]
    preview: Dict[str, Any]
    def to_dict(self) -> Dict[str, Any]:
        return {
            "group": self.group,
            "goal": self.goal,
            "action_type": self.action_type,
            "context_name": self.context_name,
            "selected_actor": self.selected_actor,
            "negotiated": dict(self.negotiated),
            "execution": None if self.execution is None else dict(self.execution),
            "preview": dict(self.preview),
        }


def _semantic_attention_vector(self, attention: ReactiveAttentionMap) -> SenseVector:
    parts: List[Tuple[SenseVector, float]] = []
    for anchor in attention.anchors:
        label = str(anchor.get('label', ''))
        weight = float(anchor.get('weight', 0.0) or 0.0)
        if label and weight > 0.0:
            parts.append((self.translate_goal_to_sense(label), min(1.0, max(0.05, weight))))
    if not parts:
        return SenseVector.zeros('attention')
    return SenseVector.combine('attention', 'reactive attention', parts)


def _semantic_attention_alignment(self, action_basis: SenseVector, attention: ReactiveAttentionMap) -> float:
    return action_basis.cosine(self.attention_vector(attention))


def _engine_preview_group(self, group_name: str, goal: str, *, context_name: Optional[str] = None, interface_name: Optional[str] = None) -> GroupGoalPreview:
    group = self.runtime.groups[group_name]
    member_previews: List[Dict[str, Any]] = []
    aggregate: Dict[Tuple[str, str], Dict[str, Any]] = {}
    context_counter: Dict[str, float] = {}
    for alias in group.members:
        pv = self.preview(alias, goal, context_name=context_name, interface_name=interface_name)
        member_previews.append(pv.to_dict())
        context_counter[pv.selected_context] = context_counter.get(pv.selected_context, 0.0) + 1.0
        for cand in pv.candidates[:6]:
            key = (cand['context_name'], cand['action_type'])
            bucket = aggregate.setdefault(key, {"context_name": cand['context_name'], "action_type": cand['action_type'], "score": 0.0, "support": 0.0, "members": []})
            bucket['score'] += float(cand.get('negotiated_score', cand.get('score', 0.0))) * max(0.1, self.runtime._group_weight(group_name, alias))
            bucket['support'] += 1.0
            bucket['members'].append(alias)
    selected_context = max(context_counter.items(), key=lambda kv: kv[1])[0] if context_counter else (context_name or '*')
    candidates = list(aggregate.values())
    candidates.sort(key=lambda x: ((x['context_name'] == selected_context), x['score'], x['support']), reverse=True)
    negotiation_basis = {"group": group_name, "selected_context": selected_context, "member_count": len(group.members), "context_votes": context_counter}
    return GroupGoalPreview(group=group_name, goal=goal, selected_context=selected_context, candidate_actions=candidates[:8], member_previews=member_previews, negotiation_basis=negotiation_basis)


async def _engine_decide_group(self, group_name: str, goal: str, *, context_name: Optional[str] = None, interface_name: Optional[str] = None, execute: bool = False, threshold: float = 0.5) -> GroupGoalDecision:
    preview = self.preview_group(group_name, goal, context_name=context_name, interface_name=interface_name)
    top = preview.candidate_actions[0] if preview.candidate_actions else {"action_type": "", "context_name": preview.selected_context}
    action_type = str(top.get('action_type', ''))
    ctx_name = str(top.get('context_name', preview.selected_context))
    payload = self._extract_payload_hints(goal, action_type)
    negotiated = self.runtime.negotiate(group_name, action_type, payload, context_name=ctx_name, interface_name=interface_name, threshold=threshold).__dict__ if action_type else {"agreed": False, "selected_actor": None, "proposals": []}
    execution = None
    selected_actor = negotiated.get('selected_actor')
    if execute and negotiated.get('agreed') and selected_actor and action_type:
        execution = await self.runtime.execute(selected_actor, action_type, payload, context_name=ctx_name, interface_name=interface_name)
    return GroupGoalDecision(group=group_name, goal=goal, action_type=action_type, context_name=ctx_name, selected_actor=selected_actor, negotiated=negotiated, execution=execution, preview=preview.to_dict())


# generation 2 iteration 5 monkey-patches
SemanticIntelligenceLayer.attention_vector = _semantic_attention_vector
SemanticIntelligenceLayer.attention_alignment = _semantic_attention_alignment
AgentDecisionEngine.preview_group = _engine_preview_group
AgentDecisionEngine.decide_group = _engine_decide_group


# Generation 2 iteration 8 — deeper group negotiation + phenomenon/attention ---

def _semantic_aggregate_attention(self, previews: Sequence[GoalPreview]) -> ReactiveAttentionMap:
    merged: Dict[tuple[str, str], float] = {}
    for preview in previews:
        for anchor in preview.attention.get('anchors', []):
            kind = str(anchor.get('kind', 'unknown'))
            label = str(anchor.get('label', 'unknown'))
            weight = float(anchor.get('weight', 0.0) or 0.0)
            merged[(kind, label)] = merged.get((kind, label), 0.0) + weight
    anchors = [
        {"kind": kind, "label": label, "weight": weight / max(1, len(previews))}
        for (kind, label), weight in merged.items()
    ]
    anchors.sort(key=lambda a: float(a.get('weight', 0.0)), reverse=True)
    return ReactiveAttentionMap(anchors=anchors[:12])


def _semantic_phenomenon_pressure(self, envelope: Any, target: SenseVector) -> float:
    pressure = 0.0
    for item in (getattr(envelope, 'phenomena', None) or []):
        basis = item.get('basis') or item.get('sense') or {}
        try:
            vec = SenseVector.from_dict(basis) if basis else self.translate_goal_to_sense(str(item.get('category', 'phenomenon')))
        except Exception:
            vec = self.translate_goal_to_sense(str(item.get('category', 'phenomenon')))
        intensity = float(item.get('intensity', 0.0) or 0.0)
        pressure += vec.cosine(target) * intensity
    return pressure


def _semantic_circumstance_pressure(self, envelope: Any, target: SenseVector) -> float:
    pressure = 0.0
    for item in (getattr(envelope, 'circumstances', None) or []):
        label = str(item.get('name', ''))
        if not item.get('holds'):
            continue
        vec = self.translate_goal_to_sense(label or 'circumstance')
        role = str(item.get('role', 'enabler'))
        polarity = 1.0 if role == 'enabler' else -0.35
        pressure += vec.cosine(target) * polarity * 0.45
    return pressure


def _semantic_attention_profile(self, envelope: Any, goal_sense: SenseVector) -> Dict[str, Any]:
    attention = self.attention_from_envelope(envelope)
    vector = self.attention_vector(attention)
    return {
        "anchors": attention.to_dict().get('anchors', []),
        "vector": vector.to_dict(),
        "goal_alignment": vector.cosine(goal_sense),
        "phenomenon_pressure": self.phenomenon_pressure(envelope, goal_sense),
        "circumstance_pressure": self.circumstance_pressure(envelope, goal_sense),
    }


def _engine_preview_group_v2(self, group_name: str, goal: str, *, context_name: Optional[str] = None, interface_name: Optional[str] = None) -> GroupGoalPreview:
    group = self.runtime.groups[group_name]
    member_previews: List[GoalPreview] = []
    aggregate: Dict[tuple[str, str], Dict[str, Any]] = {}
    context_counter: Dict[str, float] = {}
    member_alignment: Dict[str, float] = {}
    for alias in group.members:
        pv = self.preview(alias, goal, context_name=context_name, interface_name=interface_name)
        member_previews.append(pv)
        goal_vec = SenseVector.from_dict(pv.goal_sense)
        att_vec = self.semantic.attention_vector(ReactiveAttentionMap(anchors=list(pv.attention.get('anchors', []))))
        member_alignment[alias] = goal_vec.cosine(att_vec)
        context_counter[pv.selected_context] = context_counter.get(pv.selected_context, 0.0) + max(0.1, self.runtime._group_weight(group_name, alias))
        env_ctx = self.runtime.environment.contexts[pv.selected_context]
        envelope = self.runtime.envelope(alias, context_name=pv.selected_context, interface_name=interface_name)
        for cand in pv.candidates[:8]:
            key = (cand['context_name'], cand['action_type'])
            bucket = aggregate.setdefault(key, {
                "context_name": cand['context_name'],
                "action_type": cand['action_type'],
                "score": 0.0,
                "support": 0.0,
                "members": [],
                "member_scores": {},
                "phenomenon_pressure": 0.0,
                "circumstance_pressure": 0.0,
                "attention_alignment": 0.0,
            })
            weight = max(0.1, self.runtime._group_weight(group_name, alias))
            action = env_ctx._actions.get(cand['action_type']) or next((c._actions[cand['action_type']] for c in self.runtime.environment.contexts.values() if cand['action_type'] in c._actions), None)
            action_basis = action.basis if action is not None else SenseVector.zeros(cand['action_type'])
            phen = self.semantic.phenomenon_pressure(envelope, action_basis)
            circ = self.semantic.circumstance_pressure(envelope, action_basis)
            att = self.semantic.attention_alignment(action_basis, ReactiveAttentionMap(anchors=list(pv.attention.get('anchors', []))))
            score = float(cand.get('negotiated_score', cand.get('score', 0.0))) * weight
            score += phen * 0.18 + circ * 0.10 + att * 0.08
            bucket['score'] += score
            bucket['support'] += weight
            bucket['members'].append(alias)
            bucket['member_scores'][alias] = score
            bucket['phenomenon_pressure'] += phen
            bucket['circumstance_pressure'] += circ
            bucket['attention_alignment'] += att
    selected_context = max(context_counter.items(), key=lambda kv: kv[1])[0] if context_counter else (context_name or '*')
    collective_attention = self.semantic.aggregate_attention(member_previews)
    candidate_actions = []
    for item in aggregate.values():
        count = max(1, len(item['members']))
        item['avg_score'] = item['score'] / count
        item['avg_phenomenon_pressure'] = item['phenomenon_pressure'] / count
        item['avg_circumstance_pressure'] = item['circumstance_pressure'] / count
        item['avg_attention_alignment'] = item['attention_alignment'] / count
        item['consensus_strength'] = item['support'] / max(1.0, sum(max(0.1, self.runtime._group_weight(group_name, a)) for a in group.members))
        candidate_actions.append(item)
    candidate_actions.sort(key=lambda x: ((x['context_name'] == selected_context), x['avg_score'], x['consensus_strength']), reverse=True)
    negotiation_basis = {
        "group": group_name,
        "selected_context": selected_context,
        "member_count": len(group.members),
        "context_votes": context_counter,
        "member_alignment": member_alignment,
        "collective_attention": collective_attention.to_dict(),
    }
    return GroupGoalPreview(
        group=group_name,
        goal=goal,
        selected_context=selected_context,
        candidate_actions=candidate_actions[:10],
        member_previews=[pv.to_dict() for pv in member_previews],
        negotiation_basis=negotiation_basis,
    )


async def _engine_decide_group_v2(self, group_name: str, goal: str, *, context_name: Optional[str] = None, interface_name: Optional[str] = None, execute: bool = False, threshold: float = 0.5) -> GroupGoalDecision:
    preview = self.preview_group(group_name, goal, context_name=context_name, interface_name=interface_name)
    top = preview.candidate_actions[0] if preview.candidate_actions else {"action_type": "", "context_name": preview.selected_context}
    action_type = str(top.get('action_type', ''))
    ctx_name = str(top.get('context_name', preview.selected_context))
    payload = self._extract_payload_hints(goal, action_type)
    negotiated_packet = self.runtime.negotiate(group_name, action_type, payload, context_name=ctx_name, interface_name=interface_name, threshold=threshold) if action_type else None
    negotiated = negotiated_packet.__dict__ if negotiated_packet is not None else {"agreed": False, "selected_actor": None, "proposals": []}
    if negotiated_packet is not None:
        proposals = []
        for proposal in negotiated.get('proposals', []):
            alias = proposal.get('agent')
            local = top.get('member_scores', {}).get(alias, 0.0)
            proposal = dict(proposal)
            proposal['semantic_score'] = local
            proposals.append(proposal)
        negotiated['proposals'] = proposals
        negotiated['collective_attention'] = preview.negotiation_basis.get('collective_attention', {})
        negotiated['member_alignment'] = preview.negotiation_basis.get('member_alignment', {})
        negotiated['phenomenon_pressure'] = top.get('avg_phenomenon_pressure', 0.0)
        negotiated['circumstance_pressure'] = top.get('avg_circumstance_pressure', 0.0)
        negotiated['consensus_strength'] = top.get('consensus_strength', 0.0)
    execution = None
    selected_actor = negotiated.get('selected_actor')
    if execute and negotiated.get('agreed') and selected_actor and action_type:
        execution = await self.runtime.execute(selected_actor, action_type, payload, context_name=ctx_name, interface_name=interface_name)
    return GroupGoalDecision(group=group_name, goal=goal, action_type=action_type, context_name=ctx_name, selected_actor=selected_actor, negotiated=negotiated, execution=execution, preview=preview.to_dict())


SemanticIntelligenceLayer.aggregate_attention = _semantic_aggregate_attention
SemanticIntelligenceLayer.phenomenon_pressure = _semantic_phenomenon_pressure
SemanticIntelligenceLayer.circumstance_pressure = _semantic_circumstance_pressure
SemanticIntelligenceLayer.attention_profile = _semantic_attention_profile
AgentDecisionEngine.preview_group = _engine_preview_group_v2
AgentDecisionEngine.decide_group = _engine_decide_group_v2
