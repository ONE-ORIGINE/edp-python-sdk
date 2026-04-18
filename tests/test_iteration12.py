from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
from edp_sdk import ProtocolCodec, EnvLangParser, EnvLangLinter, EnvLangCompiler
from examples.cli import build_ops_runtime, EnvLangInterpreter


def test_iteration12_protocol_schema_registry():
    schemas = ProtocolCodec.export_schemas()
    assert 'packet_types' in schemas
    assert 'world' in schemas['packet_types']
    pkt = ProtocolCodec.schema_packet()
    raw = pkt.to_json()
    restored = ProtocolCodec.unpack(raw)
    assert restored.header.packet_type == 'schema.registry'


def test_iteration12_envlang_parser_and_compiler(tmp_path: Path):
    script = tmp_path / 'scenario.envl'
    script.write_text('\n'.join([
        'spawn alice:agent role=admin ctx=Main',
        'do alice :: case.open case=INC-12 severity=high',
        'ask alice :: Main',
    ]), encoding='utf-8')
    parsed = EnvLangParser.parse_script(script)
    linted = EnvLangLinter.lint_script(parsed)
    compiled = EnvLangCompiler.compile_script(linted)
    assert compiled['command_count'] == 3
    assert compiled['errors'] == []
    assert compiled['commands'][1]['kind'] == 'do'


async def _cli_parse_and_schema_case(tmp_path: Path):
    _env, _gateway, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    ast = await interp.execute('parse do alice :: case.open case=INC-13 severity=medium')
    assert ast['ast']['kind'] == 'do'
    script = tmp_path / 'lint.envl'
    script.write_text('spawn alice:agent role=admin ctx=Main\nshow card env\n', encoding='utf-8')
    lint = await interp.execute(f'lint {script}')
    assert lint['ok'] is True
    schema = await interp.execute('show schema environment.card')
    assert 'environment.card' in schema['schema']


def test_iteration12_cli_parse_and_schema(tmp_path: Path):
    asyncio.run(_cli_parse_and_schema_case(tmp_path))
