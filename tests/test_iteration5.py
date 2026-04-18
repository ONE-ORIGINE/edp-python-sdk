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
    MepGateway,
    Reaction,
    SenseVector,
    Savoir,
)


class User(Element):
    def __init__(self, name: str):
        super().__init__(name, "user", SenseVector.social("user", 0.7), {"role": "user"})


async def _distributed_merge_case():
    env1 = Environment("Env1", EnvironmentKind.REACTIVE, contextualizer=Contextualizer(), savoir=Savoir())
    ctx1 = env1.create_context("Main", ContextKind.SEMANTIC, SenseVector.normative("main", 0.9), [Circumstance.always("system.active")])

    async def greet(actor, payload, context, frame):
        return Reaction.ok("hello.done", "ok", sense=SenseVector.social("done", 0.6), impact_scope=ImpactScope.ON_ACTOR)

    ctx1.reg(Action("hello", ActionCategory.COMMAND, "hello", SenseVector.social("hello", 0.6), greet))
    alice = User("Alice")
    await env1.admit(alice)
    ctx1.include(alice.snapshot())
    gw1 = MepGateway(env1)
    await gw1.dispatch(alice, "Main", "hello", {})
    corr = env1.memory.events[-1].correlation_id

    env2 = Environment("Env2", EnvironmentKind.REACTIVE, contextualizer=Contextualizer(), savoir=Savoir())
    env2.create_context("Main", ContextKind.SEMANTIC, SenseVector.normative("main", 0.9), [Circumstance.always("system.active")])
    gw2 = MepGateway(env2)
    req = gw2.build_resync_request("peer-2", want_memory_since=0, include_graph=True)
    rsp = gw1.respond_resync(req)
    report = gw2.merge_resync(rsp)
    assert report.merged_events >= 1
    assert env2.memory.events
    assert env2.memory.replay(corr)

    with TemporaryDirectory() as tmp:
        persisted = gw2.persist_state(str(Path(tmp) / "memory.json"), str(Path(tmp) / "graph.json"))
        assert persisted["memory_summary"]["events"] >= 1
        assert persisted["graph_index"]["node_ids"]


def test_iteration5():
    asyncio.run(_distributed_merge_case())
