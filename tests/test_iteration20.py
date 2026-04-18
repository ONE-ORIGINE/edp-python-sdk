from __future__ import annotations

import asyncio

from examples.cli import EnvLangInterpreter, build_ops_runtime
from edp_sdk import EnvironmentDoctor, RuntimeOptimizer


def test_doctor_reports_ok():
    env, gateway, runtime = build_ops_runtime()
    report = EnvironmentDoctor.inspect(env, runtime)
    assert report.ok is True
    assert report.metrics["contexts"] >= 3


def test_optimizer_compacts_duplicates_and_expired_locks():
    env, gateway, runtime = build_ops_runtime()
    # Create duplicate graph edges intentionally
    ctx = env.contexts["Main"]
    actor_id = next(iter(env.contexts.keys()))
    env.semantic_graph.connect(ctx.context_id, ctx.context_id, "self", payload={"a": 1})
    env.semantic_graph.connect(ctx.context_id, ctx.context_id, "self", payload={"a": 1})
    # Expired lock
    runtime.acquire_lock("res:test", "cli", ttl_s=1.0)
    for lease in runtime._leases.values():
        lease.expires_at = 0.0
    report = RuntimeOptimizer.optimize(env, runtime)
    assert report.graph["duplicate_edges_removed"] >= 1
    assert report.runtime["expired_locks_removed"] >= 1


def test_cli_doctor_and_optimize_commands():
    env, gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)

    async def run():
        d = await interp.execute("doctor")
        o = await interp.execute("optimize")
        return d, o

    doctor, optimize = asyncio.run(run())
    assert "doctor" in doctor
    assert doctor["doctor"]["ok"] is True
    assert "optimization" in optimize
