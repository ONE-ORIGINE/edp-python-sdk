from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

from examples.cli import EnvLangInterpreter, build_ops_runtime


async def _chat_case():
    _env, _gw, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=admin ctx=Main')
    out = await interp.execute('chat alice :: open a high severity case INC-300')
    chat = out['chat']
    assert chat['alias'] == 'alice'
    assert chat['decision'] is not None
    assert chat['decision']['action_type'] == 'case.open'
    assert chat['decision']['execution']['status'] == 'success'
    assert 'Administrator' in chat['reply']


def test_chat_case():
    asyncio.run(_chat_case())


async def _slash_alias_case(tmp_path: Path):
    _env, _gw, runtime = build_ops_runtime()
    interp = EnvLangInterpreter(runtime)
    await interp.execute('spawn alice:agent role=admin ctx=Main')
    ctx = await interp.execute('/ctx alice')
    assert ctx['scope']['agent']['alias'] == 'alice'
    switched = await interp.execute('/switch alice Dispatch')
    assert switched['agent']['active_context'] == 'Dispatch'
    hist = await interp.execute('/history alice')
    assert 'history' in hist and 'chat_history' in hist
    export_path = tmp_path / 'slash.envx.json'
    exported = await interp.execute(f'/export {export_path}')
    assert Path(exported['envx']).exists()


def test_slash_alias_case(tmp_path: Path):
    asyncio.run(_slash_alias_case(tmp_path))
