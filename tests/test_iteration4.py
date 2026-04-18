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
    CausalMemory,
)
from drone_edp import DroneElement, DroneSwarmSDK


class User(Element):
    def __init__(self, name: str):
        super().__init__(name, "user", SenseVector.social("user", 0.7), {"role": "user"})


async def _recommend_and_persist_case():
    env = Environment("RankEnv", EnvironmentKind.REACTIVE, contextualizer=Contextualizer(), savoir=Savoir())
    ctx = env.create_context("Main", ContextKind.SEMANTIC, SenseVector.normative("main", 0.9), [Circumstance.always("system.active")])

    async def greet(actor, payload, context, frame):
        return Reaction.ok("hello.done", "ok", sense=SenseVector.social("done", 0.6), impact_scope=ImpactScope.ON_ACTOR)

    async def recover(actor, payload, context, frame):
        return Reaction.ok("recover.done", "ok", sense=SenseVector.causal("recovered", 0.8), impact_scope=ImpactScope.ON_ACTOR)

    ctx.reg(Action("hello", ActionCategory.COMMAND, "hello", SenseVector.social("hello", 0.6), greet))
    ctx.reg(Action("recover", ActionCategory.COMMAND, "recover", SenseVector.causal("recover", 0.9), recover))
    user = User("Bob")
    await env.admit(user)
    ctx.include(user.snapshot())
    gateway = MepGateway(env)
    await gateway.dispatch(user, "Main", "hello", {})
    recs = gateway.recommend_actions(user, "Main")
    assert recs and recs[0]["action_type"] in {"hello", "recover"}
    sync = gateway.distributed_sync()
    assert sync.memory_summary["events"] >= 1
    corr = env.memory.events[-1].correlation_id
    replay = gateway.replay_packet(corr)
    assert replay.replay
    with TemporaryDirectory() as tmp:
        gfile = JsonGraphStore(Path(tmp) / "g.json")
        mfile = JsonEventStore(Path(tmp) / "m.json")
        gfile.save(env.semantic_graph)
        mfile.save_memory(env.memory)
        loaded = CausalMemory.from_dict(mfile.load_memory())
        assert loaded.events
        assert gfile.load()["graph"]["nodes"]


async def _forecast_drone_case():
    sdk = DroneSwarmSDK()
    a = DroneElement("Scout", "d-1")
    b = DroneElement("Relay", "d-2")
    b.state.pose.x = 6.0
    await sdk.admit(a)
    await sdk.admit(b)
    sdk.update_telemetry(a)
    sdk.update_telemetry(b)
    await sdk.gateway.dispatch(a, "Flight", "flight.takeoff", {})
    a.state.battery_pct = 10.0
    sdk.update_telemetry(a)
    await sdk.gateway.dispatch(a, "Emergency", "flight.return_home", {})
    forecast = sdk.gateway.forecast_phenomena("Emergency")
    assert isinstance(forecast, list)
    hello = sdk.gateway.register_peer("agent-1")
    assert hello.agent_id == "agent-1"


def test_iteration4():
    asyncio.run(_recommend_and_persist_case())
    asyncio.run(_forecast_drone_case())
