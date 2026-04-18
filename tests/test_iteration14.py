from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
from edp_sdk import ProtocolCodec
from edp_sdk.envlang import EnvLangParser, EnvLangLinter, EnvLangCompiler
from examples.cli import build_ops_runtime, EnvLangInterpreter
from mep_tools import ProtocolCodec as ToolsCodec


def test_iteration14_formal_plan_compile():
    src = Path('/tmp/iter14.envl')
    src.write_text('spawn alice:agent role=admin ctx=Main\nplan triage = do alice :: case.open case=INC-1 severity=high ; parallel{ do alice :: system.ping | do alice :: system.ping } ; if role=admin then do alice :: system.ping else do alice :: system.ping\n', encoding='utf-8')
    script = EnvLangParser.parse_script(src)
    linted = EnvLangLinter.lint_script(script)
    compiled = EnvLangCompiler.compile_script(linted)
    assert 'triage' in compiled['formal_plans']
    ast = compiled['formal_plans']['triage']['ast']
    assert any(node['kind'] == 'parallel' for node in ast)
    assert any(node['kind'] == 'if' for node in ast)


async def _validate_case():
    env, gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=reviewer ctx=Review')
    packet = await interp.execute('show packet action.validation alice review.resolve')
    assert packet['packet']['header']['packet_type'] == 'action.validation'
    decoded = ToolsCodec.unpack(packet['packet'])
    assert decoded.header.packet_type == 'action.validation'
    denied = await interp.execute('validate alice :: case.open case=INC-2 severity=low')
    assert denied['validation']['allowed'] is False


def test_iteration14_protocol_validation():
    asyncio.run(_validate_case())
