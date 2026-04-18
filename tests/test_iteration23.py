from __future__ import annotations

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

from examples.cli import EnvLangInterpreter, build_ops_runtime
from edp_sdk import build_release_manifest, build_module_manifests
from edp_sdk.release import CHANNEL


def test_release_manifest_has_modules_and_schema_count():
    manifest = build_release_manifest().to_dict()
    names = {m['name'] for m in manifest['modules']}
    assert manifest['channel'] == CHANNEL
    assert manifest['schema_count'] > 0
    assert {'edp_sdk', 'drone_edp', 'mep_tools'}.issubset(names)


def test_cli_show_release_and_manifest():
    env, gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)

    async def run():
        release = await interp.execute('show release')
        manifest = await interp.execute('show manifest edp_sdk')
        return release, manifest

    release, manifest = asyncio.run(run())
    assert release['release']['channel'] == CHANNEL
    assert manifest['manifest']['name'] == 'edp_sdk'


def test_peer_protocol_negotiation_and_packets():
    env, gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)

    async def run():
        await interp.execute('peer add mirror ops')
        negotiated = await interp.execute('peer negotiate mirror')
        hello = await interp.execute('show packet protocol.hello mirror')
        packet = await interp.execute('show packet protocol.negotiate mirror')
        return negotiated, hello, packet

    negotiated, hello, packet = asyncio.run(run())
    assert negotiated['negotiation']['compatible'] is True
    assert negotiated['negotiation']['shared_packets']
    assert hello['packet']['header']['packet_type'] == 'protocol.hello'
    assert packet['packet']['header']['packet_type'] == 'protocol.negotiate'
