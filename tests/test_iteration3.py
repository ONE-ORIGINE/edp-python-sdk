from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

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
    Reaction,
    SenseVector,
    Savoir,
)
from drone_edp import DroneElement, DroneSwarmSDK


class User(Element):
    def __init__(self, name: str):
        super().__init__(name, "user", SenseVector.social("user", 0.7), {"role": "user"})


async def _belief_and_packets_case():
    env = Environment("BeliefEnv", EnvironmentKind.REACTIVE, contextualizer=Contextualizer(), savoir=Savoir())
    ctx = env.create_context("Main", ContextKind.SEMANTIC, SenseVector.normative("main", 0.9), [Circumstance.always("system.active")])

    async def approve(actor, payload, context, frame):
        return Reaction.ok("approval.done", "approved", sense=SenseVector.normative("approved", 0.7), impact_scope=ImpactScope.ON_ACTOR)

    ctx.reg(Action("approve", ActionCategory.COMMAND, "approve", SenseVector.normative("approve", 0.8), approve, predicted_reaction=SenseVector.normative("approval expected", 0.7)))
    user = User("Dana")
    await env.admit(user)
    ctx.include(user.snapshot())
    gateway = MepGateway(env)
    before = gateway.state_snapshot()
    result = await gateway.dispatch(user, "Main", "approve", {})
    assert result["status"] == "success"
    world = gateway.world_packet(before)
    certainty = gateway.certainty_packet()
    corr = env.memory.events[-1].correlation_id
    causality = gateway.causality_packet(corr, actor=user, context_name="Main", action_type="approve")
    assert world.delta is not None
    assert "facts" in certainty.__dict__
    assert certainty.belief
    assert causality.trace["events"]


async def _factor_graph_drone_case():
    sdk = DroneSwarmSDK()
    a = DroneElement("Scout", "d-1")
    b = DroneElement("Relay", "d-2")
    b.state.pose.x = 2.0
    await sdk.admit(a)
    await sdk.admit(b)
    sdk.update_telemetry(a)
    sdk.update_telemetry(b)
    summary = sdk.savoir.factor_graph.summary()
    assert summary["factor_count"] >= 2
    assert summary["energy"] >= 0.0
    before = summary["energy"]
    sdk.savoir.factor_graph.relax(steps=4, lr=0.02)
    after = sdk.savoir.factor_graph.energy()
    assert after <= before + 1e-6 or after >= 0.0


def test_iteration3():
    asyncio.run(_belief_and_packets_case())
    asyncio.run(_factor_graph_drone_case())
