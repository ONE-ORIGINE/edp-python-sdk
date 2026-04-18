from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
from edp_sdk import EnvironmentCanonicalBody, ProtocolCodec
from examples.cli import build_ops_runtime, EnvLangInterpreter


def test_iteration13_envx_body_and_packet():
    env, gateway, _runtime = build_ops_runtime()
    body = EnvironmentCanonicalBody.from_environment(env)
    payload = body.to_dict()
    assert payload["version"] == "1.0"
    assert "vector" in payload["exports"]
    packet = gateway.envx_packet()
    restored = ProtocolCodec.unpack(packet.to_json())
    assert restored.header.packet_type == "envx.body"


async def _cli_envx_case(tmp_path: Path):
    env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    show = await interp.execute('show envx')
    assert 'envx' in show
    proj = await interp.execute('show projection vector')
    assert 'environment_vector' in proj['projection']
    out = tmp_path / 'sample.envx.json'
    saved = await interp.execute(f'export envx {out}')
    assert out.exists()
    assert str(out) == saved['envx']


def test_iteration13_cli_envx(tmp_path: Path):
    asyncio.run(_cli_envx_case(tmp_path))
