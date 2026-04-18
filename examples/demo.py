from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
from tempfile import TemporaryDirectory

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
    JsonEventStore,
    JsonGraphStore,
    MepGateway,
    Reaction,
    SenseVector,
    Savoir,
)
from drone_edp import DroneElement, DroneSwarmSDK


class User(Element):
    def __init__(self, name: str):
        super().__init__(name, "user", SenseVector.social("operator", 0.7), {"role": "operator"})

    async def on_impacted(self, reaction, frame):
        self.dynamic["last_reaction"] = reaction.type


async def software_demo() -> None:
    env = Environment("HelloEnv", EnvironmentKind.REACTIVE, contextualizer=Contextualizer(), savoir=Savoir())
    ctx = env.create_context("Main", ContextKind.SEMANTIC, SenseVector.normative("administrative space", 0.9), [Circumstance.flag("system.open", "System open", "open", True)])
    review = env.create_context("Review", ContextKind.OBSERVATION, SenseVector.technical("review board", 0.8))
    ctx.set("open", True)

    async def greet(actor, payload, context, frame):
        return Reaction.ok(
            "say.hello",
            f"Hello {payload.get('name','World')}",
            sense=SenseVector.social("greeting", 0.8),
            impact_scope=ImpactScope.ON_ACTOR,
            result={"greeting": f"Hello {payload.get('name','World')}"},
        )

    async def escalate(actor, payload, context, frame):
        return Reaction.ok(
            "review.escalated",
            "Escalated for review",
            sense=SenseVector.normative("review escalation", 0.9),
            impact_scope=ImpactScope.ON_ACTOR,
            chain=[("say.hello", {"name": payload.get("name", actor.name)}, actor.element_id)],
        )

    ctx.reg(Action("say.hello", ActionCategory.COMMAND, "Say hello", SenseVector.social("greet", 0.7), greet, predicted_reaction=SenseVector.social("hello acknowledged", 0.7)))
    review.reg(Action("review.escalate", ActionCategory.TRANSITION, "Escalate to review", SenseVector.normative("review", 0.8), escalate, predicted_reaction=SenseVector.normative("review opened", 0.8)))
    alice = User("Alice")
    await env.admit(alice)
    ctx.include(alice.snapshot())
    review.include(alice.snapshot())
    gateway = MepGateway(env)
    print("AVAILABLE:", [a["action_type"] for a in gateway.recommend_actions(alice, "Main")])
    before = gateway.state_snapshot()
    result = await gateway.dispatch(alice, "Main", "say.hello", {"name": "Alice"})
    print("REACTION:", result)
    result2 = await gateway.dispatch(alice, "Review", "review.escalate", {"name": "Alice"})
    corr = env.memory.events[-1].correlation_id
    print("CHAIN REACTION:", result2)
    print("DELTA:", gateway.state_delta(before, gateway.state_snapshot()).delta)
    print("FORECAST:", gateway.forecast_phenomena("Review"))
    print("REPLAY:", gateway.replay_packet(corr).to_json())
    print("SYNC:", gateway.distributed_sync().to_json())
    req = gateway.build_resync_request("demo-peer", want_memory_since=0, include_graph=True)
    rsp = gateway.respond_resync(req)
    print("RESYNC RESPONSE EVENTS:", len(rsp.journal))
    with TemporaryDirectory() as tmp:
        persisted = gateway.persist_state(str(Path(tmp) / "memory.json"), str(Path(tmp) / "graph.json"))
        print("MEMORY SUMMARY:", persisted["memory_summary"])
        print("GRAPH INDEX:", persisted["graph_index"])


async def drone_demo() -> None:
    sdk = DroneSwarmSDK()
    scout = DroneElement("Scout-1", "drone-001")
    relay = DroneElement("Relay-1", "drone-002")
    relay.state.pose.x = 3.5
    await sdk.admit(scout)
    await sdk.admit(relay)
    sdk.update_telemetry(scout)
    sdk.update_telemetry(relay)
    print("DRONE CARD:")
    print(sdk.gateway.describe().to_json())
    print("AGENT HELLO:", sdk.gateway.register_peer("planner-1", ["world", "certainty", "causality", "recommend", "resync"]).to_json())
    print("TAKEOFF:", await sdk.gateway.dispatch(scout, "Flight", "flight.takeoff", {}))
    sdk.update_telemetry(scout)
    print("WHY NOT MOVE?", sdk.gateway.whynot(scout, "Flight", "flight.move", {"dx": 0.5, "dy": 0.0, "dz": 0.0}))
    scout.state.pose.x = 0.0
    relay.state.pose.x = 8.0
    sdk.update_telemetry(scout)
    sdk.update_telemetry(relay)
    print("MOVE:", await sdk.gateway.dispatch(scout, "Flight", "flight.move", {"dx": 3, "dy": 1, "dz": 2}))
    print("RECOMMENDATIONS:", sdk.gateway.recommend_actions(scout, "Emergency"))
    print("BROADCAST:", await sdk.gateway.dispatch(scout, "Swarm", "swarm.broadcast_status", {"summary": "mission nominal"}))
    scout.state.battery_pct = 10.0
    sdk.update_telemetry(scout)
    print("RTH:", await sdk.gateway.dispatch(scout, "Emergency", "flight.return_home", {}))
    print("FORECAST:", sdk.gateway.forecast_phenomena("Emergency"))
    print("CERTAINTY PACKET:", sdk.gateway.certainty_packet().to_json())
    req = sdk.gateway.build_resync_request("drone-peer", want_memory_since=0, include_graph=True)
    rsp = sdk.gateway.respond_resync(req)
    print("DRONE RESYNC SUMMARY:", rsp.summary)


async def main() -> None:
    await software_demo()
    await drone_demo()


if __name__ == "__main__":
    asyncio.run(main())
