from __future__ import annotations

import argparse
import asyncio
import json
import shlex
from edp_sdk.pathing import normalize_user_path, ensure_parent_dir
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edp_sdk import (
    Action,
    ActionCategory,
    Circumstance,
    ContextKind,
    Contextualizer,
    Element,
    Environment,
    EnvironmentKind,
    ImpactScope,
    MepGateway,
    MultiAgentRuntime,
    Reaction,
    SenseVector,
    Savoir,
    TaskPlan,
    TaskStep,
    JsonEventStore,
    JsonGraphStore,
    SQLiteEventStore,
    SQLiteGraphStore,
    ProtocolCodec,
    EnvironmentCanonicalBody,
    EnvLangParser,
    EnvLangLinter,
    EnvLangCompiler,
    EnvLangFormalCompiler,
    FormalPlanStaticAnalyzer,
    FormalPlanGraphBuilder,
    formal_plan_reference_report,
    EnvironmentDoctor,
    RuntimeOptimizer,
    build_release_manifest,
    build_module_manifests,
)
from drone_edp import DroneElement, DroneSwarmSDK
from mep_llm.runtime import AgentDecisionEngine


class OpsAgent(Element):
    def __init__(self, name: str, role: str) -> None:
        super().__init__(name=name, kind="ops_agent", basis=SenseVector.social(f"{role} agent", 0.7), properties={"role": role})
        self.inbox: List[Dict[str, Any]] = []
        self.outbox: List[Dict[str, Any]] = []

    async def on_impacted(self, reaction, frame):
        self.dynamic["last_reaction"] = reaction.type
        self.dynamic["last_correlation_id"] = frame.get("correlation_id")

    def deliver(self, message):
        self.inbox.append(message.to_dict())
        self.dynamic["inbox_count"] = len(self.inbox)


def _parse_kv(items: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        low = v.lower()
        if low in {"true", "false"}:
            out[k] = low == "true"
            continue
        try:
            if "." in v:
                out[k] = float(v)
            else:
                out[k] = int(v)
            continue
        except ValueError:
            out[k] = v
    return out


def _role_in(*roles: str) -> Circumstance:
    allowed = set(roles)
    return Circumstance.when(
        name=f"role.in.{'.'.join(sorted(allowed))}",
        description=f"role in {sorted(allowed)}",
        predicate=lambda ctx, frame: frame.get("actor_role") in allowed,
    )


def build_ops_runtime() -> tuple[Environment, MepGateway, MultiAgentRuntime]:
    env = Environment("OpsEnv", EnvironmentKind.REACTIVE, contextualizer=Contextualizer(), savoir=Savoir())
    main = env.create_context("Main", ContextKind.SEMANTIC, SenseVector.normative("operations main", 0.9), [Circumstance.flag("system.open", "System open", "open", True)])
    dispatch = env.create_context("Dispatch", ContextKind.EXECUTION, SenseVector.social("dispatch board", 0.9), [Circumstance.flag("dispatch.ready", "Dispatch ready", "dispatch_ready", True)])
    review = env.create_context("Review", ContextKind.OBSERVATION, SenseVector.normative("review board", 0.95), [Circumstance.flag("review.ready", "Review ready", "review_ready", True)])
    for ctx in (main, dispatch, review):
        ctx.set("open", True)
        ctx.set("dispatch_ready", True)
        ctx.set("review_ready", True)
        ctx.set("cases", {})

    async def ping(actor, payload, ctx, frame):
        return Reaction.ok("system.ping", f"pong:{actor.name}", sense=SenseVector.technical("health check", 0.6), impact_scope=ImpactScope.ON_ACTOR, result={"pong": True})

    async def case_open(actor, payload, ctx, frame):
        case_id = str(payload.get("case", f"CASE-{len(ctx.data['cases'])+1}"))
        severity = str(payload.get("severity", "medium"))
        case = {"case": case_id, "severity": severity, "state": "open", "owner": actor.name}
        ctx.data["cases"][case_id] = case
        dispatch.data["cases"][case_id] = dict(case)
        review.data["cases"][case_id] = dict(case)
        return Reaction.ok("case.opened", f"case {case_id} opened", sense=SenseVector.normative("case opened", 0.85), impact_scope=ImpactScope.ON_ENVIRONMENT, result=case)

    async def case_assign(actor, payload, ctx, frame):
        case_id = str(payload.get("case"))
        target = str(payload.get("target"))
        case = ctx.data["cases"].setdefault(case_id, {"case": case_id, "severity": "unknown", "state": "open"})
        case["assignee"] = target
        case["state"] = "assigned"
        review.data["cases"][case_id] = dict(case)
        return Reaction.ok("case.assigned", f"case {case_id} assigned to {target}", sense=SenseVector.social("assignment", 0.8), impact_scope=ImpactScope.ON_ENVIRONMENT, result=dict(case))

    async def review_escalate(actor, payload, ctx, frame):
        case_id = str(payload.get("case"))
        case = ctx.data["cases"].setdefault(case_id, {"case": case_id, "severity": "unknown", "state": "open"})
        case["state"] = "escalated"
        summary = {"case": case_id, "state": case["state"]}
        return Reaction.ok(
            "review.escalated",
            f"case {case_id} escalated",
            sense=SenseVector.normative("review escalation", 0.9),
            impact_scope=ImpactScope.ON_ENVIRONMENT,
            result=summary,
            chain=[("system.ping", {}, actor.element_id)],
        )

    async def review_resolve(actor, payload, ctx, frame):
        case_id = str(payload.get("case"))
        case = ctx.data["cases"].setdefault(case_id, {"case": case_id, "severity": "unknown", "state": "open"})
        case["state"] = "resolved"
        return Reaction.ok("review.resolved", f"case {case_id} resolved", sense=SenseVector.normative("resolution", 0.85), impact_scope=ImpactScope.ON_ENVIRONMENT, result=dict(case))

    main.reg(Action("system.ping", ActionCategory.QUERY, "Ping the environment", SenseVector.technical("ping", 0.5), ping, circumstances=[Circumstance.always("ping.allowed")]))
    main.reg(Action("case.open", ActionCategory.COMMAND, "Open a case", SenseVector.normative("open case", 0.8), case_open, circumstances=[_role_in("admin", "operator")]))
    dispatch.reg(Action("case.assign", ActionCategory.TRANSITION, "Assign a case", SenseVector.social("assign case", 0.8), case_assign, circumstances=[_role_in("admin", "dispatcher")]))
    review.reg(Action("review.escalate", ActionCategory.TRANSITION, "Escalate a case", SenseVector.normative("escalate case", 0.9), review_escalate, circumstances=[_role_in("admin", "operator", "reviewer")]))
    review.reg(Action("review.resolve", ActionCategory.COMMAND, "Resolve a case", SenseVector.normative("resolve case", 0.8), review_resolve, circumstances=[_role_in("admin", "reviewer", "responder")]))

    gateway = MepGateway(env)
    runtime = MultiAgentRuntime(gateway)
    return env, gateway, runtime


async def build_drone_runtime() -> tuple[DroneSwarmSDK, MultiAgentRuntime]:
    sdk = DroneSwarmSDK()
    scout = DroneElement("Scout-1", "drone-001")
    relay = DroneElement("Relay-1", "drone-002")
    relay.state.pose.x = 5.0
    await sdk.admit(scout)
    await sdk.admit(relay)
    sdk.update_telemetry(scout)
    sdk.update_telemetry(relay)
    runtime = MultiAgentRuntime(sdk.gateway)
    runtime.register_existing("scout", scout, role="pilot", context_name="Flight", capabilities=["dispatch", "recommend", "whynot", "message"])
    runtime.register_existing("relay", relay, role="pilot", context_name="Flight", capabilities=["dispatch", "recommend", "whynot", "message"])
    await runtime.spawn("tower", role="controller", kind="agent", context_name="Emergency")
    return sdk, runtime


class EnvLangInterpreter:
    HELP = """
LANGUAGE
  spawn <alias>[:<kind>] role=<role> ctx=<context>
  role <alias> = <role>
  focus <alias> -> <context>
  ctx add <alias> <context> [shared=true] [activate=true]
  ctx drop <alias> <context>
  ctx show <alias>
  share <context> with <alias1,alias2,...>
  group create <name> with <alias1,alias2,...> [ctx=<context1,context2,...>]
  group add <name> <alias>
  group drop <name> <alias>
  group show [<name>]
  delegate <from> -> <to> :: <action> [k=v ...]
  vote <group> :: <action> [k=v ...] [threshold=<0..1>] [ctx=<context>] [@<iface>] [weighted=true]
  negotiate <group> :: <action> [k=v ...] [threshold=<0..1>] [ctx=<context>] [@<iface>]
  run group <group> :: <action> [k=v ...] [threshold=<0..1>] [ctx=<context>] [@<iface>] [weighted=true]
  fanout <group> :: <action> [k=v ...] [ctx=<context>] [@<iface>]
  group weight <name> <alias> <weight>
  plan <name> = <formal body>
  run plan <name>
  show plan <name>
  iface bind <alias> <iface> realm=<realm> ctx=<context> [mode=<mode>] [shared=true]
  iface drop <alias> <iface>
  iface show <alias>
  do <alias> [@<iface>] :: <action> [k=v ...]
  ask <alias> [:: <context>|*] [@<iface>]
  whynot <alias> [@<iface>] :: <action> [k=v ...]
  why <correlation_id>
  msg <sender> -> <recipient> topic=<topic> [k=v ...]
  cap grant <alias> <capability> | cap revoke <alias> <capability>
  policy show
  policy allow role=<role> action=<type> [ctx=<context>] [cap=<capability>] [sit=<label>] [iface=<name>] [realm=<realm>] [priority=<n>] [desc=<text>]
  policy deny role=<role> action=<type> [ctx=<context>] [cap=<capability>] [sit=<label>] [iface=<name>] [realm=<realm>] [priority=<n>] [desc=<text>]
  show agents|contexts|scope <alias>|interfaces <alias>|env|envx|projection <vector|matrix|graph|annotations>|facts|belief|graph [relation <rel>]|forecast [<context>]|inbox <alias>|memory [actor <alias>|context <name>|correlation <id>]|governance|card env|card agent <alias>|packet <action.request|action.validation> <alias> <action> [ctx=<name>] [@iface]
  peer add <name> <ops|drone> | peer show | peer negotiate <peer> | merge runtime <peer> | run remote <peer> <plan> [after=<execid,...>]
  lock acquire <resource> owner=<owner> [ttl=<seconds>] | lock release <resource> owner=<owner> | lock show
  show exec | heartbeat | plan check <name>
  show packet plan.dispatch <peer> <plan> | show packet plan.preflight <peer> <plan> [after=<execid,...>] | show packet runtime.merge_state <peer> | show packet protocol.hello [<peer>] | show packet protocol.negotiate <peer> | show packet release.manifest
  llm config provider=<demo|ollama|openai|anthropic> model=<name> [inject_memory=true] [inject_situation=true] [retries=<n>] [timeout=<s>]
  llm status
  show llm memory [<alias>] | show chat [<alias>] | show llm bundle [<alias>]
  goal preview <alias> [@<iface>] [ctx=<context>] :: <natural goal>
  goal <alias> [@<iface>] [ctx=<context>] :: <natural goal>
  group goal preview <group> [@<iface>] [ctx=<context>] :: <natural goal>
  group goal <group> [@<iface>] [ctx=<context>] :: <natural goal>
  chat <alias> [@<iface>] [ctx=<context>] :: <natural language>
  /help | /ctx [<alias>] | /switch <alias> <context> | /why <correlation_id> | /whynot <alias> :: <action> [k=v ...] | /env | /history [<alias>] | /impact | /savoir | /export <path> | /quit
  doctor
  optimize
  save sqlite <base>
  save runtime sqlite <base>
  export envx <path>
  load sqlite <base>
  load runtime sqlite <base>
  source <file>
  parse <command>
  validate <alias> [@iface] :: <action> [k=v ...]
  lint <file>
  compile <file>
  show schema [<packet_type>]
  show release | show manifest [<module>] | show protocol
  show projection tensor | show projection dataset | show projection stores | show projection math
  store vector similar anchor=<id> [kind=<kind>] [top=<n>]
  store graph neighbors <node> [relation=<r>]
  store graph path <src> <dst>
  store tensor inspect node <id> | store tensor inspect edge <id>
  store dataset action <type> | store dataset correlation <id> | store dataset phenomenon <category>
  quit
""".strip()

    def __init__(self, runtime: MultiAgentRuntime):
        self.runtime = runtime
        self.gateway = runtime.gateway
        self.environment = runtime.environment
        self.plans: Dict[str, TaskPlan] = {}
        self.formal_plans: Dict[str, Any] = {}
        self.peer_runtimes: Dict[str, MultiAgentRuntime] = {}
        self.agent_engine = AgentDecisionEngine(runtime)

    def _tail_after(self, line: str, prefix: str) -> str:
        lower = line.lower()
        start = len(prefix)
        return line[start:].strip() if lower.startswith(prefix) else ''

    def _path_after(self, line: str, prefix: str) -> str:
        raw = self._tail_after(line, prefix)
        return str(normalize_user_path(raw))

    def _sqlite_paths(self, base: str) -> tuple[str, str]:
        base = str(Path(base))
        return base + ".events.sqlite", base + ".graph.sqlite"

    def _save_sqlite(self, base: str) -> Dict[str, Any]:
        event_path, graph_path = self._sqlite_paths(base)
        SQLiteEventStore(event_path).save_memory(self.environment.memory)
        SQLiteGraphStore(graph_path).save(self.environment.semantic_graph)
        return {"events": event_path, "graph": graph_path}

    def _load_sqlite(self, base: str) -> Dict[str, Any]:
        event_path, graph_path = self._sqlite_paths(base)
        mem_report = SQLiteEventStore(event_path).merge_into(self.environment.memory)
        graph_report = SQLiteGraphStore(graph_path).merge_into(self.environment.semantic_graph)
        return {"memory_merge": mem_report, "graph_merge": graph_report, "events": event_path, "graph": graph_path}

    async def _source_file(self, path: str) -> Dict[str, Any]:
        file = normalize_user_path(path)
        results = []
        for raw in file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            results.append({"command": line, "result": await self.execute(line)})
        return {"script": str(file), "results": results}

    def _parse_command(self, raw: str) -> Dict[str, Any]:
        node = EnvLangParser.parse_line(raw)
        return {"ast": node.to_dict()}

    def _lint_file(self, path: str) -> Dict[str, Any]:
        script = EnvLangParser.parse_script(path)
        script = EnvLangLinter.lint_script(script)
        return {"lint": script.to_dict(), "ok": len(script.errors) == 0}

    def _compile_file(self, path: str) -> Dict[str, Any]:
        script = EnvLangParser.parse_script(path)
        script = EnvLangLinter.lint_script(script)
        compiled = EnvLangCompiler.compile_script(script)
        return {"compiled": compiled}

    def _plan_check(self, name: str) -> Dict[str, Any]:
        if name not in self.formal_plans:
            raise KeyError(f"unknown formal plan: {name}")
        report = FormalPlanStaticAnalyzer.analyze(self.formal_plans[name], known_plans=self.formal_plans)
        return report.to_dict()

    def _lock_request(self, resource: str, owner: str, ttl_s: float = 30.0) -> Dict[str, Any]:
        return self.runtime.acquire_lock(resource, owner, ttl_s=ttl_s).to_dict()

    def _lock_release(self, resource: str, owner: str) -> Dict[str, Any]:
        return self.runtime.release_lock(resource, owner)

    def _lock_show(self) -> Dict[str, Any]:
        return {"locks": self.runtime.list_locks()}

    def _doctor(self) -> Dict[str, Any]:
        return {"doctor": EnvironmentDoctor.inspect(self.environment, self.runtime).to_dict()}

    def _optimize(self) -> Dict[str, Any]:
        return {"optimization": RuntimeOptimizer.optimize(self.environment, self.runtime).to_dict()}

    def _parse_step(self, spec: str) -> TaskStep:
        tokens = shlex.split(spec.strip())
        if not tokens:
            raise ValueError("empty step")
        mode = "single"
        actor = None
        group = None
        iface = None
        ctx = None
        threshold = 0.5
        idx = 0
        if tokens[0] == "do":
            actor = tokens[1]; idx = 2
            if idx < len(tokens) and tokens[idx].startswith("@"):
                iface = tokens[idx][1:]; idx += 1
            if tokens[idx] != "::": raise ValueError("plan step single requires ::")
            action = tokens[idx+1]; payload = _parse_kv(tokens[idx+2:])
        elif tokens[0] in {"vote", "fanout", "negotiate"}:
            mode = {"vote":"group", "fanout":"fanout", "negotiate":"negotiate"}[tokens[0]]
            group = tokens[1]; idx = 2
            if idx < len(tokens) and tokens[idx].startswith("@"):
                iface = tokens[idx][1:]; idx += 1
            if tokens[idx] != "::": raise ValueError("plan group step requires ::")
            action = tokens[idx+1]; payload = _parse_kv(tokens[idx+2:])
            threshold = float(payload.pop("threshold", 0.5))
        else:
            raise ValueError("unsupported plan step")
        ctx = None if "ctx" not in payload else str(payload.pop("ctx"))
        return TaskStep(step_id=f"step-{len(self.plans)+1}-{abs(hash(spec))%10000}", action_type=action, payload=payload, actor=actor, group=group, context_name=ctx, interface_name=iface, threshold=threshold, mode=mode)

    async def execute(self, line: str) -> Any:
        line = line.strip()
        if not line:
            return None
        tokens = shlex.split(line)
        if not tokens:
            return None
        cmd = tokens[0].lower()
        if cmd == "help":
            return self.HELP
        if cmd == "spawn":
            alias_kind = tokens[1]
            alias, kind = (alias_kind.split(":", 1) + ["agent"])[:2] if ":" in alias_kind else (alias_kind, "agent")
            kv = _parse_kv(tokens[2:])
            role = str(kv.get("role", "operator"))
            ctx = str(kv.get("ctx", next(iter(self.environment.contexts.keys()))))
            profile = await self.runtime.spawn(alias, role=role, kind=kind, context_name=ctx)
            return {"spawned": profile.to_dict()}
        if cmd == "role":
            alias = tokens[1]
            role = tokens[3] if len(tokens) >= 4 and tokens[2] == "=" else tokens[2]
            return {"agent": self.runtime.set_role(alias, role).to_dict()}
        if cmd == "focus":
            alias = tokens[1]
            ctx = tokens[3] if len(tokens) >= 4 and tokens[2] == "->" else tokens[2]
            return {"agent": self.runtime.focus(alias, ctx).to_dict()}
        if cmd == "ctx":
            sub = tokens[1]
            if sub == "add":
                alias = tokens[2]; ctx = tokens[3]; kv = _parse_kv(tokens[4:])
                return {"agent": self.runtime.add_context_access(alias, ctx, shared=bool(kv.get("shared", False)), activate=bool(kv.get("activate", False)))}
            if sub == "drop":
                return {"agent": self.runtime.remove_context_access(tokens[2], tokens[3])}
            if sub == "show":
                return {"scope": self.runtime.scope_packet(tokens[2]).__dict__}
            raise ValueError("ctx expects add|drop|show")
        if cmd == "share":
            ctx = tokens[1]
            if tokens[2].lower() != "with":
                raise ValueError("share syntax: share <context> with <a,b>")
            aliases = [a for a in tokens[3].split(",") if a]
            return self.runtime.share_context(ctx, aliases)
        if cmd == "group":
            sub = tokens[1]
            if sub == "create":
                name = tokens[2]
                if tokens[3].lower() != "with":
                    raise ValueError("group create <name> with <a,b>")
                aliases = [a for a in tokens[4].split(",") if a]
                kv = _parse_kv(tokens[5:])
                shared_contexts = [] if "ctx" not in kv else [c for c in str(kv["ctx"]).split(",") if c]
                return {"group": self.runtime.create_group(name, aliases, shared_contexts=shared_contexts, metadata={k:v for k,v in kv.items() if k != "ctx"})}
            if sub == "add":
                return {"group": self.runtime.add_group_member(tokens[2], tokens[3])}
            if sub == "drop":
                return {"group": self.runtime.remove_group_member(tokens[2], tokens[3])}
            if sub == "show":
                if len(tokens) > 2:
                    return {"group": self.runtime.group_scope(tokens[2]).__dict__}
                return {"groups": self.runtime.describe_groups()}
            if sub == "weight":
                return {"group": self.runtime.set_group_weight(tokens[2], tokens[3], float(tokens[4]))}
            raise ValueError("group expects create|add|drop|show|weight")
        if cmd == "delegate":
            sender = tokens[1]
            if tokens[2] != "->":
                raise ValueError("delegate syntax: delegate <from> -> <to> :: <action> ...")
            recipient = tokens[3]
            if tokens[4] != "::":
                raise ValueError("delegate syntax requires ::")
            action = tokens[5]
            payload = _parse_kv(tokens[6:])
            ctx = None if "ctx" not in payload else str(payload.pop("ctx"))
            return self.runtime.delegate(sender, recipient, action, payload, context_name=ctx)
        if cmd == "vote":
            group = tokens[1]
            idx = 2
            iface = None
            if idx < len(tokens) and tokens[idx].startswith("@"):
                iface = tokens[idx][1:]
                idx += 1
            if tokens[idx] != "::":
                raise ValueError("vote syntax requires ::")
            action = tokens[idx+1]
            payload = _parse_kv(tokens[idx+2:])
            threshold = float(payload.pop("threshold", 0.5))
            ctx = None if "ctx" not in payload else str(payload.pop("ctx"))
            weighted = bool(payload.pop("weighted", False))
            return {"consensus": self.runtime.consensus(group, action, payload, context_name=ctx, threshold=threshold, interface_name=iface, weighted=weighted).__dict__}
        if cmd == "negotiate":
            group = tokens[1]
            idx = 2
            iface = None
            if idx < len(tokens) and tokens[idx].startswith("@"): iface = tokens[idx][1:]; idx += 1
            if tokens[idx] != "::": raise ValueError("negotiate syntax requires ::")
            action = tokens[idx+1]
            payload = _parse_kv(tokens[idx+2:])
            threshold = float(payload.pop("threshold", 0.5))
            ctx = None if "ctx" not in payload else str(payload.pop("ctx"))
            return {"negotiation": self.runtime.negotiate(group, action, payload, context_name=ctx, interface_name=iface, threshold=threshold).__dict__}
        if cmd == "run" and len(tokens) > 2 and tokens[1] == "group":
            group = tokens[2]
            idx = 3
            iface = None
            if idx < len(tokens) and tokens[idx].startswith("@"):
                iface = tokens[idx][1:]
                idx += 1
            if tokens[idx] != "::":
                raise ValueError("run group syntax requires ::")
            action = tokens[idx+1]
            payload = _parse_kv(tokens[idx+2:])
            threshold = float(payload.pop("threshold", 0.5))
            ctx = None if "ctx" not in payload else str(payload.pop("ctx"))
            weighted = bool(payload.pop("weighted", False))
            return await self.runtime.group_execute(group, action, payload, context_name=ctx, threshold=threshold, interface_name=iface, weighted=weighted)
        if cmd == "fanout":
            group = tokens[1]
            idx = 2
            iface = None
            if idx < len(tokens) and tokens[idx].startswith("@"):
                iface = tokens[idx][1:]
                idx += 1
            if tokens[idx] != "::":
                raise ValueError("fanout syntax requires ::")
            action = tokens[idx+1]
            payload = _parse_kv(tokens[idx+2:])
            ctx = None if "ctx" not in payload else str(payload.pop("ctx"))
            return await self.runtime.fanout(group, action, payload, context_name=ctx, interface_name=iface)
        if cmd == "plan":
            if len(tokens) > 2 and tokens[2] == "=":
                name = tokens[1]
                raw = line.split("=",1)[1].strip()
                program = EnvLangFormalCompiler.build_program(name, raw)
                self.formal_plans[name] = program
                # keep linear task plan compatibility for simple consumers
                parts = [part.strip() for part in raw.split(";") if part.strip()]
                try:
                    steps = [self._parse_step(part) for part in parts if not part.lower().startswith(("if ", "parallel", "sequence"))]
                    self.plans[name] = TaskPlan(plan_id=name, name=name, steps=steps, metadata={"formal": True})
                except Exception:
                    self.plans[name] = TaskPlan(plan_id=name, name=name, steps=[], metadata={"formal": True})
                return {"plan": program.to_dict()}
            raise ValueError("plan syntax: plan <name> = <formal body>")
        if cmd == "run" and len(tokens) > 2 and tokens[1] == "plan":
            name = tokens[2]
            if name in self.formal_plans:
                packet = (await self.runtime.execute_formal_plan(self.formal_plans[name])).to_dict()
                return {"formal_plan_execution": packet, "plan_execution": packet}
            return {"plan_execution": (await self.runtime.execute_plan(self.plans[name])).__dict__}

        if cmd == "show" and len(tokens) > 3 and tokens[1] == "packet" and tokens[2] == "plan.dispatch":
            if len(tokens) < 5:
                raise ValueError("show packet plan.dispatch <peer> <plan>")
            peer_name, plan_name = tokens[3], tokens[4]
            peer_runtime = self.peer_runtimes.get(peer_name)
            if peer_runtime is None:
                raise KeyError(f"unknown runtime peer: {peer_name}")
            program = getattr(peer_runtime, 'formal_plans', {}).get(plan_name)
            if program is None:
                raise KeyError(f"peer {peer_name} has no plan named {plan_name}")
            from edp_sdk.protocol import PlanDispatchPacket
            return {"packet": PlanDispatchPacket(packet_id="preview", plan_name=plan_name, target_peer=peer_name, ast=program.to_dict()).__dict__}
        if cmd == "show" and len(tokens) > 3 and tokens[1] == "packet" and tokens[2] == "plan.preflight":
            if len(tokens) < 5:
                raise ValueError("show packet plan.preflight <peer> <plan> [after=<execid,...>]")
            peer_name, plan_name = tokens[3], tokens[4]
            kv = _parse_kv(tokens[5:])
            depends_on = [x for x in str(kv.get("after", "")).split(",") if x]
            return {"packet": self.gateway.plan_preflight_packet(self.runtime, peer_name, plan_name, depends_on=depends_on).to_dict()}
        if cmd == "show" and len(tokens) > 1 and tokens[1] == "release":
            return {"release": build_release_manifest().to_dict()}
        if cmd == "show" and len(tokens) > 1 and tokens[1] == "manifest":
            manifests = build_module_manifests()
            if len(tokens) > 2:
                name = tokens[2]
                if name not in manifests:
                    raise KeyError(f"unknown module manifest: {name}")
                return {"manifest": manifests[name].to_dict()}
            return {"manifests": {k: v.to_dict() for k, v in manifests.items()}}
        if cmd == "show" and len(tokens) > 1 and tokens[1] == "protocol":
            hello = self.runtime.protocol_hello().to_dict()
            release = build_release_manifest().to_dict()
            return {"protocol": {"hello": hello, "release": release}}
        if cmd == "show" and len(tokens) > 3 and tokens[1] == "packet" and tokens[2] == "protocol.negotiate":
            peer_name = tokens[3]
            return {"packet": self.gateway.protocol_negotiation_packet(self.runtime, peer_name).to_dict()}
        if cmd == "show" and len(tokens) > 3 and tokens[1] == "packet" and tokens[2] == "runtime.merge_state":
            peer_name = tokens[3]
            return {"packet": self.gateway.runtime_merge_packet(self.runtime, peer_name).to_dict()}
        if cmd == "show" and len(tokens) > 2 and tokens[1] == "packet" and tokens[2] == "protocol.hello":
            if len(tokens) > 3:
                peer_name = tokens[3]
                peer = self.peer_runtimes.get(peer_name)
                if peer is None:
                    raise KeyError(f"unknown runtime peer: {peer_name}")
                return {"packet": peer.gateway.protocol_hello_packet(peer).to_dict()}
            return {"packet": self.gateway.protocol_hello_packet(self.runtime).to_dict()}
        if cmd == "show" and len(tokens) > 2 and tokens[1] == "packet" and tokens[2] == "release.manifest":
            return {"packet": self.gateway.release_manifest_packet().to_dict()}
        if cmd == "peer" and len(tokens) > 1:
            sub = tokens[1]
            if sub == "add":
                if len(tokens) < 4:
                    raise ValueError("peer add <name> <ops|drone>")
                name, kind = tokens[2], tokens[3].lower()
                if kind == "ops":
                    _env, _gateway, peer_runtime = build_ops_runtime()
                elif kind == "drone":
                    _sdk, peer_runtime = await build_drone_runtime()
                else:
                    raise ValueError(f"unknown peer kind: {kind}")
                self.peer_runtimes[name] = peer_runtime
                return {"peer_registered": self.runtime.register_runtime_peer(name, peer_runtime), "runtime_peers": self.runtime.runtime_peers()}
            if sub == "show":
                return {"runtime_peers": self.runtime.runtime_peers()}
            if sub == "negotiate":
                return {"negotiation": self.runtime.negotiate_protocol(tokens[2]).to_dict(), "packet": self.gateway.protocol_negotiation_packet(self.runtime, tokens[2]).to_dict()}
            raise ValueError("peer expects add|show|negotiate")
        if cmd == "merge" and len(tokens) > 2 and tokens[1] == "runtime":
            peer_name = tokens[2]
            report = self.runtime.merge_peer_state(peer_name)
            return {"merge": report.to_dict(), "packet": self.gateway.runtime_merge_packet(self.runtime, peer_name).to_dict()}
        if cmd == "run" and len(tokens) > 2 and tokens[1] == "remote":
            if len(tokens) < 4:
                raise ValueError("run remote <peer> <plan> [after=<execid,...>]")
            peer_name, plan_name = tokens[2], tokens[3]
            kv = _parse_kv(tokens[4:])
            depends_on = [x for x in str(kv.get("after", "")).split(",") if x]
            if plan_name in self.formal_plans and peer_name in self.peer_runtimes:
                peer_runtime = self.peer_runtimes[peer_name]
                peer_runtime.formal_plans = getattr(peer_runtime, 'formal_plans', {})
                peer_runtime.formal_plans[plan_name] = self.formal_plans[plan_name]
            packet = await self.runtime.execute_distributed_formal_plan(peer_name, plan_name, depends_on=depends_on)
            return {"distributed_formal_plan": packet.__dict__}
        if cmd == "lock":
            sub = tokens[1]
            if sub == "acquire":
                resource = tokens[2]
                kv = _parse_kv(tokens[3:])
                owner = str(kv.get("owner", "cli"))
                ttl = float(kv.get("ttl", 30.0))
                return {"lock": self._lock_request(resource, owner, ttl)}
            if sub == "release":
                resource = tokens[2]
                kv = _parse_kv(tokens[3:])
                owner = str(kv.get("owner", "cli"))
                return {"lock": self._lock_release(resource, owner)}
            if sub == "show":
                return self._lock_show()
            raise ValueError("lock expects acquire|release|show")
        if cmd == "heartbeat":
            return {"heartbeat": self.runtime.heartbeat().to_dict()}
        if cmd == "plan" and len(tokens) > 2 and tokens[1] == "check":
            return {"analysis": self._plan_check(tokens[2])}
        if cmd == "iface":
            sub = tokens[1]
            if sub == "bind":
                alias = tokens[2]; iface = tokens[3]; kv = _parse_kv(tokens[4:])
                return {"interface": self.runtime.bind_interface(alias, iface, realm=str(kv.get("realm", "logical")), context_name=None if "ctx" not in kv else str(kv["ctx"]), mode=str(kv.get("mode", "internal")), shared=bool(kv.get("shared", False)), metadata={k:v for k,v in kv.items() if k not in {"realm","ctx","mode","shared"}})}
            if sub == "drop":
                return self.runtime.unbind_interface(tokens[2], tokens[3])
            if sub == "show":
                return {"interfaces": self.runtime.interfaces(tokens[2])}
            raise ValueError("iface expects bind|drop|show")
        if cmd == "validate":
            alias = tokens[1]
            iface = None
            idx = 2
            if idx < len(tokens) and tokens[idx].startswith("@"):
                iface = tokens[idx][1:]
                idx += 1
            if tokens[idx] != "::":
                raise ValueError("validate syntax requires ::")
            action = tokens[idx+1]
            payload = _parse_kv(tokens[idx+2:])
            req = self.runtime.action_request(alias, action, payload, interface_name=iface, context_name=None if 'ctx' not in payload else str(payload.pop('ctx')))
            return {"validation": self.runtime.validate_action_request(req).to_dict()}
        if cmd == "do":
            alias = tokens[1]
            iface = None
            idx = 2
            if idx < len(tokens) and tokens[idx].startswith("@"):
                iface = tokens[idx][1:]
                idx += 1
            if tokens[idx] != "::":
                raise ValueError("expected :: after agent alias")
            action = tokens[idx+1]
            payload = _parse_kv(tokens[idx+2:])
            return await self.runtime.execute(alias, action, payload, interface_name=iface)
        if cmd == "ask":
            alias = tokens[1]
            iface = None
            ctx = None
            rest = tokens[2:]
            if rest and rest[0].startswith("@"):
                iface = rest[0][1:]
                rest = rest[1:]
            if len(rest) >= 2 and rest[0] == "::":
                ctx = rest[1]
            return {"recommendations": self.runtime.recommend(alias, context_name=ctx, interface_name=iface)}
        if cmd == "whynot":
            alias = tokens[1]
            idx = 2
            iface = None
            if idx < len(tokens) and tokens[idx].startswith("@"):
                iface = tokens[idx][1:]
                idx += 1
            if tokens[idx] != "::":
                raise ValueError("expected :: after agent alias")
            action = tokens[idx+1]
            payload = _parse_kv(tokens[idx+2:])
            return self.runtime.whynot(alias, action, interface_name=iface, payload=payload)
        if cmd == "why":
            return self.gateway.why(tokens[1])
        if cmd == "msg":
            sender = tokens[1]
            if tokens[2] != "->":
                raise ValueError("expected -> in message syntax")
            recipient = tokens[3]
            payload = _parse_kv(tokens[4:])
            topic = str(payload.pop("topic", "message"))
            return self.runtime.send(sender, recipient, topic, payload)
        if cmd == "cap":
            mode = tokens[1]
            alias = tokens[2]
            cap = tokens[3]
            if mode == "grant":
                return {"agent": self.runtime.grant_capability(alias, cap)}
            if mode == "revoke":
                return {"agent": self.runtime.revoke_capability(alias, cap)}
            raise ValueError("cap expects grant|revoke")
        if cmd == "policy":
            mode = tokens[1]
            if mode == "show":
                return {"policy": self.runtime.governance()}
            kv = _parse_kv(tokens[2:])
            role = kv.get("role")
            action = kv.get("action")
            ctx = kv.get("ctx")
            cap = kv.get("cap")
            sit = kv.get("sit")
            iface = kv.get("iface")
            realm = kv.get("realm")
            prio = int(kv.get("priority", 10 if mode == "allow" else 100))
            desc = str(kv.get("desc", f"{mode} {action} for {role}"))
            if not action:
                raise ValueError("policy action=<type> required")
            if mode == "allow":
                return {"policy": self.runtime.allow_action(rule_id=f"allow:{role or '*'}:{action}:{ctx or '*'}", role=role, action_type=str(action), context_name=None if ctx is None else str(ctx), capability=None if cap is None else str(cap), situation_label=None if sit is None else str(sit), interface_name=None if iface is None else str(iface), interface_realm=None if realm is None else str(realm), description=desc, priority=prio)}
            if mode == "deny":
                return {"policy": self.runtime.deny_action(rule_id=f"deny:{role or '*'}:{action}:{ctx or '*'}", role=role, action_type=str(action), context_name=None if ctx is None else str(ctx), capability=None if cap is None else str(cap), situation_label=None if sit is None else str(sit), interface_name=None if iface is None else str(iface), interface_realm=None if realm is None else str(realm), description=desc, priority=prio)}
            raise ValueError("policy expects show|allow|deny")
        if cmd == "merge" and len(tokens) > 1 and tokens[1] == "runtime":
            return {"merge": self.runtime.merge_runtime_state(self.runtime.export_runtime_state())}
        if cmd == "export" and len(tokens) > 1 and tokens[1] == "envx":
            body = EnvironmentCanonicalBody.from_environment(self.environment)
            return {"envx": body.save(self._path_after(line, 'export envx '))}
        if cmd == "save" and len(tokens) > 1 and tokens[1] == "sqlite":
            return {"sqlite": self._save_sqlite(self._path_after(line, 'save sqlite '))}
        if cmd == "load" and len(tokens) > 1 and tokens[1] == "sqlite":
            return {"sqlite": self._load_sqlite(self._path_after(line, 'load sqlite '))}
        if cmd == "doctor":
            return self._doctor()
        if cmd == "optimize":
            return self._optimize()
        if cmd == "source" and len(tokens) > 1:
            return await self._source_file(self._path_after(line, 'source '))
        if cmd == "parse":
            raw = line.split(' ', 1)[1] if ' ' in line else ''
            return self._parse_command(raw)
        if cmd == "lint" and len(tokens) > 1:
            return self._lint_file(self._path_after(line, 'lint '))
        if cmd == "compile" and len(tokens) > 1:
            return self._compile_file(self._path_after(line, 'compile '))
        if cmd == "show":
            subject = tokens[1].lower()
            if subject == "agents":
                return {"agents": self.runtime.describe_agents()}
            if subject == "groups":
                return {"groups": self.runtime.describe_groups()}
            if subject == "contexts":
                return {"contexts": {name: ctx.topology() for name, ctx in self.environment.contexts.items()}}
            if subject == "scope":
                return {"scope": self.runtime.scope_packet(tokens[2]).__dict__}
            if subject == "group":
                return {"group": self.runtime.group_scope(tokens[2]).__dict__}
            if subject == "interfaces":
                return {"interfaces": self.runtime.interfaces(tokens[2])}
            if subject == "env":
                return self.environment.snapshot()
            if subject == "envx":
                body = EnvironmentCanonicalBody.from_environment(self.environment)
                return {"envx": body.to_dict(), "packet": self.gateway.envx_packet().to_dict()}
            if subject == "projection":
                kind = tokens[2] if len(tokens) > 2 else "matrix"
                body = EnvironmentCanonicalBody.from_environment(self.environment)
                if kind == "vector":
                    return {"projection": body.vector_projection()}
                if kind == "matrix":
                    return {"projection": body.matrix_projection()}
                if kind == "graph":
                    return {"projection": body.graph_projection()}
                if kind == "annotations":
                    return {"projection": body.annotation_projection()}
                if kind == "tensor":
                    return {"projection": body.tensor_graph_projection()}
                if kind == "dataset":
                    return {"projection": body.causal_dataset_projection()}
                if kind == "stores":
                    bundle = body.store_bundle_projection()
                    return {"projection": bundle, "projection_stores": bundle}
                raise ValueError("show projection vector|matrix|graph|annotations|tensor|dataset|stores")
            if subject == "facts":
                return {"facts": self.environment.savoir.snapshot().get("facts", {})}
            if subject == "belief":
                return {"belief": self.environment.savoir.snapshot().get("belief", {})}
            if subject == "graph":
                if len(tokens) > 3 and tokens[2] == "relation":
                    return {"edges": self.environment.semantic_graph.query_edges(relation=tokens[3])}
                return self.environment.semantic_graph.export()
            if subject == "forecast":
                ctx = tokens[2] if len(tokens) > 2 else None
                return {"forecast": self.gateway.forecast_phenomena(ctx)}
            if subject == "inbox":
                alias = tokens[2]
                return {"inbox": self.runtime.inbox(alias)}
            if subject == "governance":
                return {"governance": self.runtime.governance()}
            if subject == "card":
                if tokens[2] == "env":
                    card = self.gateway.environment_card()
                    packet = ProtocolCodec.pack("environment.card", card.to_dict())
                    return {"card": card.to_dict(), "packet": packet.to_dict()}
                if tokens[2] == "agent":
                    card = self.runtime.agent_card(tokens[3])
                    packet = ProtocolCodec.pack("agent.card", card.to_dict())
                    return {"card": card.to_dict(), "packet": packet.to_dict()}
                raise ValueError("show card env|agent <alias>")
            if subject == "schema":
                schemas = ProtocolCodec.export_schemas()
                if len(tokens) > 2:
                    ptype = tokens[2]
                    return {"schema": {ptype: schemas.get('packet_types', {}).get(ptype, [])}}
                return {"schema": schemas, "packet": ProtocolCodec.schema_packet().to_dict()}
            if subject == "plans":
                return {"plans": [p.to_dict() for p in self.plans.values()], "formal_plans": {k:v.to_dict() for k,v in self.formal_plans.items()}}
            if subject.startswith("plan "):
                name = subject.split(" ",1)[1]
                return {"plan": None if name not in self.formal_plans else self.formal_plans[name].to_dict()}
            if subject == "runtime":
                return {"runtime": self.runtime.export_runtime_state().__dict__}
            if subject == "exec":
                return {"execution_state": self.runtime.execution_state().to_dict()}
            if subject == "packet":
                packet_kind = tokens[2]
                alias = tokens[3]
                action = tokens[4]
                iface = None
                extra = [] if len(tokens) <= 5 else tokens[5:]
                if extra and extra[0].startswith("@"):
                    iface = extra[0][1:]
                    extra = extra[1:]
                kv = _parse_kv(extra)
                ctx = None if "ctx" not in kv else str(kv.pop("ctx"))
                if packet_kind == "action.request":
                    return {"packet": self.gateway.action_request_packet(self.runtime, alias, action, kv, context_name=ctx, interface_name=iface).to_dict()}
                if packet_kind == "action.validation":
                    return {"packet": self.gateway.action_validation_packet(self.runtime, alias, action, kv, context_name=ctx, interface_name=iface).to_dict()}
                if packet_kind == "lock.request":
                    owner = alias
                    ttl = float(kv.get("ttl", 30.0))
                    return {"packet": self.gateway.lock_request_packet(action, owner, ttl).to_dict()}
                if packet_kind == "lock.decision":
                    owner = alias
                    ttl = float(kv.get("ttl", 30.0))
                    return {"packet": self.gateway.lock_decision_packet(self.runtime, action, owner, ttl).to_dict()}
                if packet_kind == "runtime.heartbeat":
                    return {"packet": self.gateway.runtime_heartbeat_packet(self.runtime).to_dict()}
                if packet_kind == "runtime.execution_state":
                    return {"packet": self.gateway.runtime_execution_state_packet(self.runtime).to_dict()}
                raise ValueError("unknown packet kind")
            if subject == "memory":
                if len(tokens) == 2:
                    return {"summary": self.environment.memory.summary()}
                mode = tokens[2]
                if mode == "actor":
                    alias = tokens[3]
                    profile = self.runtime.agents[alias]
                    return {"timeline": [e.to_dict() for e in self.environment.memory.actor_timeline(profile.element_id)]}
                if mode == "context":
                    return {"timeline": [e.to_dict() for e in self.environment.memory.context_timeline(tokens[3])]}
                if mode == "correlation":
                    return {"trace": self.gateway.why(tokens[3])}
            raise ValueError(f"unknown show target: {subject}")
        if cmd in {"quit", "exit"}:
            return {"quit": True}
        raise ValueError(f"unknown command: {cmd}")


async def run_interactive(mode: str) -> None:
    if mode == "drone":
        sdk, runtime = await build_drone_runtime()
        _ = sdk
    else:
        env, gateway, runtime = build_ops_runtime()
        _ = (env, gateway)
    interp = EnvLangInterpreter(runtime)
    print("ENVLANG READY")
    print(interp.HELP)
    while True:
        try:
            line = input("env> ")
        except EOFError:
            break
        try:
            result = await interp.execute(line)
            if result is None:
                continue
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if isinstance(result, dict) and result.get("quit"):
                break
        except Exception as exc:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="EDP/MEP multi-agent CLI")
    parser.add_argument("--mode", choices=["ops", "drone"], default="ops")
    args = parser.parse_args()
    asyncio.run(run_interactive(args.mode))


if __name__ == "__main__":
    main()


# Iteration 21 — extra plan introspection commands ----------------------------
_old_execute_iteration20 = EnvLangInterpreter.execute

def _plan_graph(self, name: str) -> Dict[str, Any]:
    if name not in self.formal_plans:
        raise KeyError(f"unknown formal plan: {name}")
    graph = FormalPlanGraphBuilder.build(self.formal_plans[name])
    return {"graph": graph.to_dict(), "dot": graph.to_dot()}


def _plan_refs(self, name: str) -> Dict[str, Any]:
    if name not in self.formal_plans:
        raise KeyError(f"unknown formal plan: {name}")
    return {"references": formal_plan_reference_report(self.formal_plans[name]).to_dict()}

EnvLangInterpreter._plan_graph = _plan_graph
EnvLangInterpreter._plan_refs = _plan_refs

async def _execute_iteration21(self, line: str) -> Any:
    line = line.strip()
    if not line:
        return None
    tokens = shlex.split(line)
    if not tokens:
        return None
    if tokens[0].lower() == 'plan' and len(tokens) > 2:
        if tokens[1] == 'graph':
            return self._plan_graph(tokens[2])
        if tokens[1] == 'refs':
            return self._plan_refs(tokens[2])
    if tokens[0].lower() == 'show' and len(tokens) > 3 and tokens[1].lower() == 'plan' and tokens[2].lower() == 'graph':
        return self._plan_graph(tokens[3])
    return await _old_execute_iteration20(self, line)

EnvLangInterpreter.execute = _execute_iteration21


# Generation 2 iteration 2 — natural goal + resilient provider layer --------
_old_execute_generation2_a1 = EnvLangInterpreter.execute

def _parse_goal_command(line: str) -> tuple[bool, str, str | None, str | None, str]:
    raw = line.strip()
    lowered = raw.lower()
    preview = False
    if lowered.startswith('goal preview '):
        preview = True
        tail = raw[len('goal preview '):].strip()
    elif lowered.startswith('goal '):
        tail = raw[len('goal '):].strip()
    else:
        raise ValueError('not a goal command')
    if '::' not in tail:
        raise ValueError('goal syntax requires :: <natural goal>')
    head, goal = tail.split('::', 1)
    tokens = shlex.split(head.strip())
    if not tokens:
        raise ValueError('goal requires an alias')
    alias = tokens[0]
    iface = None
    ctx = None
    for tok in tokens[1:]:
        if tok.startswith('@'):
            iface = tok[1:]
        elif tok.startswith('ctx='):
            ctx = tok.split('=', 1)[1]
    return preview, alias, iface, ctx, goal.strip()


def _parse_group_goal_command(line: str) -> tuple[bool, str, str | None, str | None, str]:
    raw = line.strip()
    lowered = raw.lower()
    preview = False
    if lowered.startswith('group goal preview '):
        preview = True
        tail = raw[len('group goal preview '):].strip()
    elif lowered.startswith('group goal '):
        tail = raw[len('group goal '):].strip()
    else:
        raise ValueError('not a group goal command')
    if '::' not in tail:
        raise ValueError('group goal syntax requires :: <natural goal>')
    head, goal = tail.split('::', 1)
    tokens = shlex.split(head.strip())
    if not tokens:
        raise ValueError('group goal requires a group name')
    group = tokens[0]
    iface = None
    ctx = None
    for tok in tokens[1:]:
        if tok.startswith('@'):
            iface = tok[1:]
        elif tok.startswith('ctx='):
            ctx = tok.split('=', 1)[1]
    return preview, group, iface, ctx, goal.strip()

async def _execute_generation2_a2(self, line: str) -> Any:
    line = line.strip()
    if not line:
        return None
    lowered = line.lower()
    if lowered.startswith('llm config '):
        kv = _parse_kv(shlex.split(line[len('llm config '):]))
        if 'retries' in kv:
            kv['retries'] = int(kv['retries'])
        if 'timeout' in kv and 'timeout_s' not in kv:
            kv['timeout_s'] = float(kv.pop('timeout'))
        return {'llm': self.agent_engine.configure(**kv)}
    if lowered == 'llm status':
        return {'llm': self.agent_engine.status()}
    if lowered.startswith('goal '):
        preview, alias, iface, ctx, goal = _parse_goal_command(line)
        if preview:
            return {'goal_preview': self.agent_engine.preview(alias, goal, context_name=ctx, interface_name=iface).to_dict()}
        return {'goal_decision': (await self.agent_engine.decide(alias, goal, context_name=ctx, interface_name=iface, execute=True)).to_dict()}
    return await _old_execute_generation2_a1(self, line)

EnvLangInterpreter.execute = _execute_generation2_a2


# Generation 2 iteration 3 — conversational natural mode + slash aliases ---
_old_execute_generation2_a2 = EnvLangInterpreter.execute

def _parse_chat_command(line: str) -> tuple[str, str | None, str | None, str]:
    raw = line.strip()
    lowered = raw.lower()
    if lowered.startswith('chat '):
        tail = raw[len('chat '):].strip()
    elif lowered.startswith('say '):
        tail = raw[len('say '):].strip()
    else:
        raise ValueError('not a chat command')
    if '::' not in tail:
        raise ValueError('chat syntax requires :: <text>')
    head, text = tail.split('::', 1)
    tokens = shlex.split(head.strip())
    if not tokens:
        raise ValueError('chat requires an alias')
    alias = tokens[0]
    iface = None
    ctx = None
    for tok in tokens[1:]:
        if tok.startswith('@'):
            iface = tok[1:]
        elif tok.startswith('ctx='):
            ctx = tok.split('=', 1)[1]
    return alias, iface, ctx, text.strip()

async def _execute_generation2_a3(self, line: str) -> Any:
    line = line.strip()
    if not line:
        return None
    lowered = line.lower()
    if lowered.startswith('show llm memory'):
        parts = shlex.split(line)
        alias = parts[3] if len(parts) > 3 else None
        return {'llm_memory': self.agent_engine.history(alias)}
    if lowered.startswith('show chat'):
        parts = shlex.split(line)
        alias = parts[2] if len(parts) > 2 else None
        return {'chat_history': self.agent_engine.chat_history(alias)}
    if lowered.startswith('show llm bundle'):
        return {'llm_bundle': self.agent_engine.export_learning_bundle()}
    if lowered.startswith('group goal '):
        preview, group, iface, ctx, goal = _parse_group_goal_command(line)
        if preview:
            return {'group_goal_preview': self.agent_engine.preview_group(group, goal, context_name=ctx, interface_name=iface).to_dict()}
        return {'group_goal_decision': (await self.agent_engine.decide_group(group, goal, context_name=ctx, interface_name=iface, execute=True)).to_dict()}
    if lowered.startswith('chat ') or lowered.startswith('say '):
        alias, iface, ctx, text = _parse_chat_command(line)
        return {'chat': await self.agent_engine.chat(alias, text, context_name=ctx, interface_name=iface)}
    if line.startswith('/'):
        parts = shlex.split(line)
        cmd = parts[0].lower()
        if cmd == '/help':
            return {'help': self.HELP}
        if cmd == '/ctx':
            alias = parts[1] if len(parts) > 1 else (next(iter(self.runtime.agents.keys())) if self.runtime.agents else None)
            if alias is None:
                return {'scope': None}
            scope = self.runtime.scope_packet(alias)
            return {'scope': {
                'agent': scope.agent,
                'active_context': scope.active_context,
                'accessible_contexts': scope.accessible_contexts,
                'shared_contexts': scope.shared_contexts,
                'interfaces': scope.interfaces,
                'situation_map': scope.situation_map,
                'topology': scope.topology,
            }, 'recommendations': self.runtime.recommend(alias)}
        if cmd == '/switch' and len(parts) >= 3:
            return await _old_execute_generation2_a2(self, f'focus {parts[1]} -> {parts[2]}')
        if cmd == '/why' and len(parts) >= 2:
            return await _old_execute_generation2_a2(self, f'why {parts[1]}')
        if cmd == '/whynot':
            rest = line[len('/whynot'):].strip()
            return await _old_execute_generation2_a2(self, f'whynot {rest}')
        if cmd == '/env':
            return await _old_execute_generation2_a2(self, 'show env')
        if cmd == '/history':
            alias = parts[1] if len(parts) > 1 else None
            return {'history': self.agent_engine.history(alias), 'chat_history': self.agent_engine.chat_history(alias)}
        if cmd == '/impact':
            return {'impact': self.environment.impact.summary()}
        if cmd == '/savoir':
            return await _old_execute_generation2_a2(self, 'show facts')
        if cmd == '/export' and len(parts) >= 2:
            return await _old_execute_generation2_a2(self, f'export envx {line[len(parts[0]):].strip()}')
        if cmd == '/quit':
            return {'quit': True}
    return await _old_execute_generation2_a2(self, line)

EnvLangInterpreter.execute = _execute_generation2_a3


# Generation 2 iteration 6 — store adapters + mathematical projection ---
_old_execute_generation2_a5 = EnvLangInterpreter.execute

def _parse_kv_tokens(tokens):
    out = {}
    for tok in tokens:
        if '=' in tok:
            k, v = tok.split('=', 1)
            out[k] = v
    return out

async def _execute_generation2_a6(self, line: str) -> Any:
    from edp_sdk import EnvironmentCanonicalBody, StoreProjectionSuite
    line = line.strip()
    if not line:
        return None
    lowered = line.lower()
    if lowered == 'show projection math':
        body = EnvironmentCanonicalBody.from_environment(self.environment)
        return {'projection_math': body.mathematical_projection()}
    if lowered.startswith('store vector similar '):
        toks = shlex.split(line)
        kv = _parse_kv_tokens(toks[3:])
        anchor = kv.get('anchor')
        if not anchor:
            return {'error': 'anchor=<id> is required'}
        kind = kv.get('kind')
        top = int(kv.get('top', '5'))
        suite = StoreProjectionSuite.from_envx(EnvironmentCanonicalBody.from_environment(self.environment))
        return {'vector_similar': suite.vector.similar_to_anchor(anchor, kind=kind, top_k=top)}
    if lowered.startswith('store graph neighbors '):
        toks = shlex.split(line)
        node = toks[3] if len(toks) > 3 else ''
        kv = _parse_kv_tokens(toks[4:])
        relation = kv.get('relation')
        suite = StoreProjectionSuite.from_envx(EnvironmentCanonicalBody.from_environment(self.environment))
        return {'graph_neighbors': suite.graph.neighbors(node, relation=relation)}
    if lowered.startswith('store graph path '):
        toks = shlex.split(line)
        if len(toks) < 5:
            return {'error': 'store graph path <src> <dst>'}
        suite = StoreProjectionSuite.from_envx(EnvironmentCanonicalBody.from_environment(self.environment))
        return {'graph_path': suite.graph.path(toks[3], toks[4])}
    if lowered.startswith('store tensor inspect node '):
        toks = shlex.split(line)
        suite = StoreProjectionSuite.from_envx(EnvironmentCanonicalBody.from_environment(self.environment))
        return {'tensor_node': suite.tensor.inspect_node(toks[4])}
    if lowered.startswith('store tensor inspect edge '):
        toks = shlex.split(line)
        suite = StoreProjectionSuite.from_envx(EnvironmentCanonicalBody.from_environment(self.environment))
        return {'tensor_edge': suite.tensor.inspect_edge(toks[4])}
    if lowered.startswith('store dataset action '):
        toks = shlex.split(line)
        suite = StoreProjectionSuite.from_envx(EnvironmentCanonicalBody.from_environment(self.environment))
        return {'dataset_action': suite.dataset.by_action(toks[3])}
    if lowered.startswith('store dataset correlation '):
        toks = shlex.split(line)
        suite = StoreProjectionSuite.from_envx(EnvironmentCanonicalBody.from_environment(self.environment))
        return {'dataset_correlation': suite.dataset.by_correlation(toks[3])}
    if lowered.startswith('store dataset phenomenon '):
        toks = shlex.split(line)
        suite = StoreProjectionSuite.from_envx(EnvironmentCanonicalBody.from_environment(self.environment))
        return {'dataset_phenomenon': suite.dataset.by_phenomenon(toks[3])}
    return await _old_execute_generation2_a5(self, line)

EnvLangInterpreter.execute = _execute_generation2_a6


# Generation 2 iteration 7 — concrete store exports + deeper tensor/graph queries ---
_old_execute_generation2_a6 = EnvLangInterpreter.execute

async def _execute_generation2_a7(self, line: str) -> Any:
    from edp_sdk import EnvironmentCanonicalBody, StoreProjectionSuite
    line = line.strip()
    if not line:
        return None
    lowered = line.lower()
    if lowered.startswith('store export '):
        target = self._path_after(line, 'store export ')
        suite = StoreProjectionSuite.from_envx(EnvironmentCanonicalBody.from_environment(self.environment))
        return {'store_export': suite.save(target)}
    if lowered.startswith('store graph relation '):
        toks = shlex.split(line)
        suite = StoreProjectionSuite.from_envx(EnvironmentCanonicalBody.from_environment(self.environment))
        return {'graph_relation': suite.graph.relations(toks[3])}
    if lowered.startswith('store tensor affinity '):
        toks = shlex.split(line)
        if len(toks) < 5:
            return {'error': 'store tensor affinity <edge_a> <edge_b>'}
        suite = StoreProjectionSuite.from_envx(EnvironmentCanonicalBody.from_environment(self.environment))
        return {'tensor_affinity': {'edge_a': toks[3], 'edge_b': toks[4], 'score': suite.tensor.edge_affinity(toks[3], toks[4])}}
    if lowered.startswith('store tensor compose '):
        toks = shlex.split(line)
        suite = StoreProjectionSuite.from_envx(EnvironmentCanonicalBody.from_environment(self.environment))
        return {'tensor_compose': {'edges': toks[3:], 'operator': suite.tensor.compose_operators(toks[3:])}}
    return await _old_execute_generation2_a6(self, line)

EnvLangInterpreter.execute = _execute_generation2_a7


# Generation 2 iteration 8 — deeper group negotiation + attention views ------
_old_execute_generation2_a7 = EnvLangInterpreter.execute

async def _execute_generation2_a8(self, line: str) -> Any:
    line = line.strip()
    if not line:
        return None
    lowered = line.lower()
    if lowered.startswith('show attention group '):
        group = shlex.split(line)[3]
        previews = []
        for alias in self.runtime.groups[group].members:
            pv = self.agent_engine.preview(alias, f'group:{group}:attention')
            previews.append(pv)
        att = self.agent_engine.semantic.aggregate_attention(previews)
        return {'attention': {'group': group, **att.to_dict()}}
    if lowered.startswith('show attention '):
        alias = shlex.split(line)[2]
        pv = self.agent_engine.preview(alias, f'agent:{alias}:attention')
        profile = self.agent_engine.semantic.attention_profile(self.runtime.envelope(alias, context_name=pv.selected_context), self.agent_engine.semantic.translate_goal_to_sense(f'agent:{alias}:attention'))
        return {'attention': {'alias': alias, **profile}}
    if lowered.startswith('group goal explain '):
        _, group, iface, ctx, goal = _parse_group_goal_command('group goal preview ' + line[len('group goal explain '):])
        preview = self.agent_engine.preview_group(group, goal, context_name=ctx, interface_name=iface)
        decision = await self.agent_engine.decide_group(group, goal, context_name=ctx, interface_name=iface, execute=False)
        return {'group_goal_explain': {'preview': preview.to_dict(), 'decision': decision.to_dict()}}
    return await _old_execute_generation2_a7(self, line)

EnvLangInterpreter.execute = _execute_generation2_a8


# Generation 2 iteration 9 — enriched math body + learning projections ------
_old_execute_generation2_a8 = EnvLangInterpreter.execute

async def _execute_generation2_a9(self, line: str) -> Any:
    from edp_sdk import DataSignal, EnvironmentCanonicalBody
    line = line.strip()
    if not line:
        return None
    lowered = line.lower()
    if lowered == 'show context matrix':
        return {'context_matrix': self.environment.contextualizer.context_matrix_export()}
    if lowered == 'show learning':
        return {'learning': self.environment.impact.learning_projection().to_dict()}
    if lowered.startswith('show learning action '):
        action = line[len('show learning action '):].strip()
        return {'learning_action': self.environment.impact.profile_for(action)}
    if lowered.startswith('show contextualize '):
        toks = shlex.split(line)
        if len(toks) < 5:
            return {'error': 'show contextualize <context> <signal> <value> [unit=<u>]'}
        ctx_name, tag, raw_value = toks[2], toks[3], toks[4]
        try:
            value: Any = float(raw_value) if '.' in raw_value else int(raw_value)
        except ValueError:
            value = raw_value
        unit = ''
        for tok in toks[5:]:
            if tok.startswith('unit='):
                unit = tok.split('=', 1)[1]
        if ctx_name not in self.environment.contexts:
            return {'error': f'unknown context: {ctx_name}'}
        explanation = self.environment.contextualizer.explain(DataSignal(tag=tag, value=value, unit=unit), self.environment.contexts[ctx_name])
        return {'contextualized': explanation}
    if lowered == 'show math body':
        body = EnvironmentCanonicalBody.from_environment(self.environment)
        return {'math_body': body.mathematical_projection(), 'learning': body.learning_projection()}
    return await _old_execute_generation2_a8(self, line)

EnvLangInterpreter.execute = _execute_generation2_a9


# Generation 2 iteration 10 — persistent specialized stores + causal scoring --
_old_execute_generation2_a9 = EnvLangInterpreter.execute

async def _execute_generation2_a10(self, line: str) -> Any:
    from edp_sdk import EnvironmentCanonicalBody, NativeSpecializedStoreSuite
    line = line.strip()
    if not line:
        return None
    lowered = line.lower()
    if lowered.startswith('persist stores '):
        base = self._path_after(line, 'persist stores ')
        suite = NativeSpecializedStoreSuite(base)
        self.environment.attach_native_store_suite(suite)
        return {'stores': suite.save_environment(self.environment, runtime_state=self.runtime.runtime_state_payload())}
    if lowered.startswith('load stores '):
        base = self._path_after(line, 'load stores ')
        suite = NativeSpecializedStoreSuite(base)
        self.environment.attach_native_store_suite(suite)
        merged = suite.merge_into(self.environment)
        return {'stores': suite.summary(), 'merge': merged}
    if lowered == 'show stores':
        return {'stores': self.environment.native_store_summary() if hasattr(self.environment, 'native_store_summary') else {}}
    if lowered == 'show learning backend':
        if getattr(self.environment, 'native_store_suite', None) is not None:
            return {'learning_backend': self.environment.native_store_suite.learning.backend_state()}
        return {'learning_backend': self.environment.impact.learning_backend_state()}
    if lowered.startswith('show score '):
        tail = line[len('show score '):]
        if '::' not in tail:
            return {'error': 'show score <alias> :: <goal>'}
        alias, goal = [part.strip() for part in tail.split('::', 1)]
        preview = self.agent_engine.preview(alias, goal)
        return {'score': {'alias': alias, 'goal': goal, 'context': preview.selected_context, 'candidates': [{
            'action_type': item.get('action_type'),
            'negotiated_score': item.get('negotiated_score', 0.0),
            'total_score': item.get('total_score', 0.0),
            'causal_score_card': dict((item.get('details') or {}).get('causal_score_card', {})),
            'causal_prior': dict((item.get('details') or {}).get('causal_prior', {})),
        } for item in preview.candidates]}}
    if lowered == 'show projection persistent':
        body = EnvironmentCanonicalBody.from_environment(self.environment)
        return {'projection': body.to_dict().get('exports', {}).get('persistent_backends', {})}
    return await _old_execute_generation2_a9(self, line)

EnvLangInterpreter.execute = _execute_generation2_a10
