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

    async def greet(actor, payload, context, frame):
        return Reaction.ok("hello.done", "ok", sense=SenseVector.social("done", 0.6), impact_scope=ImpactScope.ON_ACTOR)

    ctx.reg(Action("hello", ActionCategory.COMMAND, "hello", SenseVector.social("hello", 0.6), greet))
    user = User("Bob")
    await env.admit(user)
    ctx.include(user.snapshot())
    gateway = MepGateway(env)
    result = await gateway.dispatch(user, "Main", "hello", {})
    assert result["status"] == "success"
    assert len(env.memory.events) == 1


async def _drone_case():
    sdk = DroneSwarmSDK()
    drone = DroneElement("Scout", "d-1")
    await sdk.admit(drone)
    sdk.update_telemetry(drone)
    result = await sdk.gateway.dispatch(drone, "Flight", "flight.takeoff", {})
    assert result["status"] == "success"
    assert drone.state.airborne is True


def test_iteration1():
    asyncio.run(_software_case())
    asyncio.run(_drone_case())
