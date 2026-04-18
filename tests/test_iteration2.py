from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

from edp_sdk import Action, ActionCategory, Circumstance, ContextKind, Contextualizer, Element, Environment, EnvironmentKind, ImpactScope, MepGateway, Reaction, SenseVector, Savoir
from drone_edp import DroneElement, DroneSwarmSDK


class User(Element):
    def __init__(self, name: str):
        super().__init__(name, "user", SenseVector.social("user", 0.7), {"role": "user"})


async def _software_case():
    env = Environment("TestEnv", EnvironmentKind.REACTIVE, contextualizer=Contextualizer(), savoir=Savoir())
    ctx = env.create_context("Main", ContextKind.SEMANTIC, SenseVector.normative("main", 0.9), [Circumstance.always("system.active")])
    env.create_context("Review", ContextKind.OBSERVATION, SenseVector.technical("review", 0.7))

    async def greet(actor, payload, context, frame):
        return Reaction.ok("hello.done", "ok", sense=SenseVector.social("done", 0.6), impact_scope=ImpactScope.ON_ACTOR)

    ctx.reg(Action("hello", ActionCategory.COMMAND, "hello", SenseVector.social("hello", 0.6), greet))
    user = User("Bob")
    await env.admit(user)
    ctx.include(user.snapshot())
    gateway = MepGateway(env)
    before = gateway.state_snapshot()
    result = await gateway.dispatch(user, "Main", "hello", {})
    after = gateway.state_snapshot()
    assert result["status"] == "success"
    assert len(env.memory.events) == 1
    delta = gateway.state_delta(before, after).delta
    assert delta["elements"] or delta["contexts"] or delta["savoir"]
    trace = gateway.why(env.memory.events[-1].correlation_id)
    assert len(trace["events"]) == 1
    assert "Review" in gateway.describe().to_json()
    assert env.operational_state().G_t["nodes"]


async def _drone_case():
    sdk = DroneSwarmSDK()
    a = DroneElement("Scout", "d-1")
    b = DroneElement("Relay", "d-2")
    b.state.pose.x = 1.0
    await sdk.admit(a)
    await sdk.admit(b)
    sdk.update_telemetry(a)
    sdk.update_telemetry(b)
    whynot = sdk.gateway.whynot(a, "Flight", "flight.move", {"dx": 1, "dy": 0, "dz": 0})
    assert whynot["blocked"] is True
    b.state.pose.x = 10.0
    a.state.airborne = True
    sdk.update_telemetry(a)
    sdk.update_telemetry(b)
    result = await sdk.gateway.dispatch(a, "Swarm", "swarm.broadcast_status", {"summary": "ok"})
    assert result["status"] == "success"
    assert any(i.category == "broadcast" for i in sdk.environment.memory.interactions) or any(p.category == "broadcast_coordination" for p in sdk.environment.memory.phenomena)


def test_iteration2():
    asyncio.run(_software_case())
    asyncio.run(_drone_case())
