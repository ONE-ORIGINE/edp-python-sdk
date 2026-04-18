from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from .pathing import normalize_user_path
from typing import Any, Dict, List, Optional


def parse_kv(items: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for item in items:
        if '=' not in item:
            continue
        k, v = item.split('=', 1)
        low = v.lower()
        if low in {'true', 'false'}:
            out[k] = low == 'true'
            continue
        try:
            if '.' in v:
                out[k] = float(v)
            else:
                out[k] = int(v)
            continue
        except ValueError:
            out[k] = v
    return out


@dataclass
class CommandNode:
    kind: str
    raw: str
    tokens: List[str] = field(default_factory=list)
    subject: Optional[str] = None
    target: Optional[str] = None
    action: Optional[str] = None
    interface: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'kind': self.kind,
            'raw': self.raw,
            'tokens': list(self.tokens),
            'subject': self.subject,
            'target': self.target,
            'action': self.action,
            'interface': self.interface,
            'payload': dict(self.payload),
            'metadata': dict(self.metadata),
        }


@dataclass
class ScriptNode:
    path: str
    commands: List[CommandNode] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'path': self.path,
            'commands': [c.to_dict() for c in self.commands],
            'errors': list(self.errors),
            'warnings': list(self.warnings),
        }


class EnvLangSyntaxError(ValueError):
    pass


class EnvLangParser:
    """Formal parser for a useful EnvLang subset.

    Goal: make the command language introspectable, lintable and compilable
    without replacing the permissive interpreter.
    """
    @classmethod
    def parse_line(cls, line: str) -> CommandNode:
        raw = line.strip()
        if not raw:
            return CommandNode(kind='empty', raw=raw)
        if raw.startswith('#'):
            return CommandNode(kind='comment', raw=raw)
        tokens = shlex.split(raw)
        if not tokens:
            return CommandNode(kind='empty', raw=raw)
        cmd = tokens[0].lower()
        if cmd == 'spawn':
            alias_kind = tokens[1]
            alias, kind = (alias_kind.split(':',1)+['agent'])[:2] if ':' in alias_kind else (alias_kind, 'agent')
            return CommandNode(kind='spawn', raw=raw, tokens=tokens, subject=alias, metadata={'element_kind': kind, 'options': parse_kv(tokens[2:])})
        if cmd == 'role':
            if len(tokens) < 4 or tokens[2] != '=':
                raise EnvLangSyntaxError('role syntax: role <alias> = <role>')
            return CommandNode(kind='role', raw=raw, tokens=tokens, subject=tokens[1], metadata={'role': tokens[3]})
        if cmd == 'focus':
            if len(tokens) < 4 or tokens[2] != '->':
                raise EnvLangSyntaxError('focus syntax: focus <alias> -> <context>')
            return CommandNode(kind='focus', raw=raw, tokens=tokens, subject=tokens[1], target=tokens[3])
        if cmd == 'do':
            idx = 1
            subject = tokens[idx]; idx += 1
            iface = None
            if idx < len(tokens) and tokens[idx].startswith('@'):
                iface = tokens[idx][1:]; idx += 1
            if idx >= len(tokens) or tokens[idx] != '::':
                raise EnvLangSyntaxError('do syntax: do <alias> [@iface] :: <action> [k=v ...]')
            action = tokens[idx+1]
            payload = parse_kv(tokens[idx+2:])
            return CommandNode(kind='do', raw=raw, tokens=tokens, subject=subject, action=action, interface=iface, payload=payload)
        if cmd == 'ask':
            subject = tokens[1]
            iface = None
            context = None
            rest = tokens[2:]
            if rest and rest[0].startswith('@'):
                iface = rest[0][1:]
                rest = rest[1:]
            if len(rest) >= 2 and rest[0] == '::':
                context = rest[1]
            return CommandNode(kind='ask', raw=raw, tokens=tokens, subject=subject, interface=iface, metadata={'context': context})
        if cmd == 'whynot':
            idx = 1
            subject = tokens[idx]; idx += 1
            iface = None
            if idx < len(tokens) and tokens[idx].startswith('@'):
                iface = tokens[idx][1:]; idx += 1
            if idx >= len(tokens) or tokens[idx] != '::':
                raise EnvLangSyntaxError('whynot syntax: whynot <alias> [@iface] :: <action> [k=v ...]')
            action = tokens[idx+1]
            payload = parse_kv(tokens[idx+2:])
            return CommandNode(kind='whynot', raw=raw, tokens=tokens, subject=subject, action=action, interface=iface, payload=payload)
        if cmd == 'msg':
            if len(tokens) < 4 or tokens[2] != '->':
                raise EnvLangSyntaxError('msg syntax: msg <sender> -> <recipient> topic=<t> [k=v ...]')
            return CommandNode(kind='msg', raw=raw, tokens=tokens, subject=tokens[1], target=tokens[3], payload=parse_kv(tokens[4:]))
        if cmd == 'delegate':
            if len(tokens) < 6 or tokens[2] != '->' or tokens[4] != '::':
                raise EnvLangSyntaxError('delegate syntax: delegate <from> -> <to> :: <action> [k=v ...]')
            return CommandNode(kind='delegate', raw=raw, tokens=tokens, subject=tokens[1], target=tokens[3], action=tokens[5], payload=parse_kv(tokens[6:]))
        if cmd == 'vote':
            group = tokens[1]
            idx = 2
            iface = None
            if idx < len(tokens) and tokens[idx].startswith('@'):
                iface = tokens[idx][1:]; idx += 1
            if idx >= len(tokens) or tokens[idx] != '::':
                raise EnvLangSyntaxError('vote syntax: vote <group> [@iface] :: <action> [k=v ...]')
            return CommandNode(kind='vote', raw=raw, tokens=tokens, subject=group, action=tokens[idx+1], interface=iface, payload=parse_kv(tokens[idx+2:]))
        if cmd == 'negotiate':
            group = tokens[1]
            idx = 2
            iface = None
            if idx < len(tokens) and tokens[idx].startswith('@'):
                iface = tokens[idx][1:]; idx += 1
            if idx >= len(tokens) or tokens[idx] != '::':
                raise EnvLangSyntaxError('negotiate syntax: negotiate <group> [@iface] :: <action> [k=v ...]')
            return CommandNode(kind='negotiate', raw=raw, tokens=tokens, subject=group, action=tokens[idx+1], interface=iface, payload=parse_kv(tokens[idx+2:]))
        if cmd == 'run' and len(tokens) > 2 and tokens[1] == 'group':
            group = tokens[2]
            idx = 3
            iface = None
            if idx < len(tokens) and tokens[idx].startswith('@'):
                iface = tokens[idx][1:]; idx += 1
            if idx >= len(tokens) or tokens[idx] != '::':
                raise EnvLangSyntaxError('run group syntax: run group <group> [@iface] :: <action> [k=v ...]')
            return CommandNode(kind='run.group', raw=raw, tokens=tokens, subject=group, action=tokens[idx+1], interface=iface, payload=parse_kv(tokens[idx+2:]))
        if cmd == 'fanout':
            group = tokens[1]
            idx = 2
            iface = None
            if idx < len(tokens) and tokens[idx].startswith('@'):
                iface = tokens[idx][1:]; idx += 1
            if idx >= len(tokens) or tokens[idx] != '::':
                raise EnvLangSyntaxError('fanout syntax: fanout <group> [@iface] :: <action> [k=v ...]')
            return CommandNode(kind='fanout', raw=raw, tokens=tokens, subject=group, action=tokens[idx+1], interface=iface, payload=parse_kv(tokens[idx+2:]))
        if cmd == 'show':
            return CommandNode(kind='show', raw=raw, tokens=tokens, subject=' '.join(tokens[1:]))
        if cmd == 'policy':
            return CommandNode(kind='policy', raw=raw, tokens=tokens, metadata={'subcommand': tokens[1] if len(tokens)>1 else '', 'options': parse_kv(tokens[2:])})
        if cmd == 'group':
            return CommandNode(kind='group', raw=raw, tokens=tokens, metadata={'subcommand': tokens[1] if len(tokens)>1 else '', 'arguments': tokens[2:]})
        if cmd == 'ctx':
            return CommandNode(kind='ctx', raw=raw, tokens=tokens, metadata={'subcommand': tokens[1] if len(tokens)>1 else '', 'arguments': tokens[2:]})
        if cmd == 'iface':
            return CommandNode(kind='iface', raw=raw, tokens=tokens, metadata={'subcommand': tokens[1] if len(tokens)>1 else '', 'arguments': tokens[2:]})
        if cmd == 'plan':
            return CommandNode(kind='plan', raw=raw, tokens=tokens, metadata={'body': raw.split('=',1)[1].strip() if '=' in raw else ''})
        if cmd == 'source':
            return CommandNode(kind='source', raw=raw, tokens=tokens, subject=tokens[1] if len(tokens)>1 else None)
        if cmd in {'quit', 'exit'}:
            return CommandNode(kind='quit', raw=raw, tokens=tokens)
        return CommandNode(kind='generic', raw=raw, tokens=tokens)

    @classmethod
    def parse_script(cls, path: str | Path) -> ScriptNode:
        file = normalize_user_path(path)
        script = ScriptNode(path=str(file))
        for lineno, raw in enumerate(file.read_text(encoding='utf-8').splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            try:
                script.commands.append(cls.parse_line(line))
            except Exception as exc:
                script.errors.append(f'line {lineno}: {exc}')
        return script


class EnvLangLinter:
    @staticmethod
    def lint_script(script: ScriptNode) -> ScriptNode:
        declared = set()
        plan_names = set()
        for idx, cmd in enumerate(script.commands, start=1):
            if cmd.kind == 'spawn' and cmd.subject:
                declared.add(cmd.subject)
            if cmd.kind == 'plan':
                if cmd.tokens and len(cmd.tokens) > 1:
                    plan_names.add(cmd.tokens[1])
            if cmd.kind in {'do', 'ask', 'whynot', 'msg', 'delegate'} and cmd.subject and cmd.subject not in declared:
                script.warnings.append(f'line {idx}: alias {cmd.subject!r} used before spawn')
            if cmd.kind == 'delegate' and cmd.target and cmd.target not in declared:
                script.warnings.append(f'line {idx}: delegate target {cmd.target!r} used before spawn')
            if cmd.kind in {'vote', 'negotiate', 'run.group', 'fanout'} and not cmd.subject:
                script.errors.append(f'line {idx}: group command missing subject')
            if cmd.kind in {'do', 'whynot', 'vote', 'negotiate', 'run.group', 'fanout'} and not cmd.action:
                script.errors.append(f'line {idx}: command missing action')
        return script


class EnvLangCompiler:
    @staticmethod
    def compile_script(script: ScriptNode) -> Dict[str, Any]:
        return {
            'language': 'EnvLang',
            'version': '0.2',
            'command_count': len(script.commands),
            'commands': [c.to_dict() for c in script.commands],
            'errors': list(script.errors),
            'warnings': list(script.warnings),
        }

    @staticmethod
    def to_json(script: ScriptNode) -> str:
        return json.dumps(EnvLangCompiler.compile_script(script), ensure_ascii=False, indent=2, sort_keys=True)


# Deeper formal grammar -------------------------------------------------------

@dataclass
class FormalCondition:
    field: str
    op: str
    value: Any

    def to_dict(self) -> Dict[str, Any]:
        return {'field': self.field, 'op': self.op, 'value': self.value}


@dataclass
class FormalPlanNode:
    kind: str
    label: str = ''
    command: Optional[CommandNode] = None
    condition: Optional[FormalCondition] = None
    then_branch: List['FormalPlanNode'] = field(default_factory=list)
    else_branch: List['FormalPlanNode'] = field(default_factory=list)
    children: List['FormalPlanNode'] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'kind': self.kind,
            'label': self.label,
            'command': None if self.command is None else self.command.to_dict(),
            'condition': None if self.condition is None else self.condition.to_dict(),
            'then_branch': [n.to_dict() for n in self.then_branch],
            'else_branch': [n.to_dict() for n in self.else_branch],
            'children': [n.to_dict() for n in self.children],
        }


class EnvLangFormalParser:
    @staticmethod
    def parse_condition(spec: str) -> FormalCondition:
        spec = spec.strip()
        for op in ('>=', '<=', '!=', '=', '>', '<'):
            if op in spec:
                left, right = spec.split(op, 1)
                return FormalCondition(left.strip(), op, parse_kv([f'x={right.strip()}']).get('x', right.strip()))
        raise EnvLangSyntaxError(f'unsupported condition: {spec}')

    @classmethod
    def parse_command_node(cls, spec: str) -> FormalPlanNode:
        return FormalPlanNode(kind='command', command=EnvLangParser.parse_line(spec.strip()))

    @classmethod
    def parse_plan_body(cls, body: str) -> List[FormalPlanNode]:
        nodes: List[FormalPlanNode] = []
        parts = [part.strip() for part in body.split(';') if part.strip()]
        for part in parts:
            low = part.lower()
            if low.startswith('parallel{') and part.endswith('}'):
                inner = part[len('parallel{'):-1]
                children = [cls.parse_command_node(seg.strip()) for seg in inner.split('|') if seg.strip()]
                nodes.append(FormalPlanNode(kind='parallel', children=children))
                continue
            if low.startswith('if ') and ' then ' in low:
                # Simple form: if <cond> then <cmd> [else <cmd>]
                m = re.match(r'^if\s+(.+?)\s+then\s+(.+?)(?:\s+else\s+(.+))?$', part, flags=re.IGNORECASE)
                if not m:
                    raise EnvLangSyntaxError(f'invalid conditional plan fragment: {part}')
                cond = cls.parse_condition(m.group(1))
                then_node = cls.parse_command_node(m.group(2))
                else_branch = [cls.parse_command_node(m.group(3))] if m.group(3) else []
                nodes.append(FormalPlanNode(kind='if', condition=cond, then_branch=[then_node], else_branch=else_branch))
                continue
            nodes.append(cls.parse_command_node(part))
        return nodes


# Enhance linter/compiler with formal plan support
_old_lint_script = EnvLangLinter.lint_script

def _lint_script_with_plans(script: ScriptNode) -> ScriptNode:
    script = _old_lint_script(script)
    for idx, cmd in enumerate(script.commands, start=1):
        if cmd.kind == 'plan' and cmd.metadata.get('body'):
            try:
                EnvLangFormalParser.parse_plan_body(cmd.metadata['body'])
            except Exception as exc:
                script.errors.append(f'line {idx}: invalid plan body: {exc}')
    return script

EnvLangLinter.lint_script = staticmethod(_lint_script_with_plans)

_old_compile_script = EnvLangCompiler.compile_script

def _compile_script_with_plans(script: ScriptNode) -> Dict[str, Any]:
    base = _old_compile_script(script)
    plans: Dict[str, Any] = {}
    for cmd in script.commands:
        if cmd.kind == 'plan' and cmd.tokens and len(cmd.tokens) > 1:
            name = cmd.tokens[1]
            body = cmd.metadata.get('body', '')
            try:
                ast = [node.to_dict() for node in EnvLangFormalParser.parse_plan_body(body)]
            except Exception as exc:
                ast = {'error': str(exc)}
            plans[name] = {'body': body, 'ast': ast}
    base['formal_plans'] = plans
    base['version'] = '0.3'
    return base

EnvLangCompiler.compile_script = staticmethod(_compile_script_with_plans)

# Iteration 15 — deeper formal grammar and executable programs -----------------

@dataclass
class FormalPlanProgram:
    name: str
    root: List[FormalPlanNode] = field(default_factory=list)
    source: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'source': self.source,
            'root': [n.to_dict() for n in self.root],
        }


def _split_top_level(text: str, sep: str) -> List[str]:
    parts: List[str] = []
    buf: List[str] = []
    brace = bracket = paren = 0
    quote: Optional[str] = None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in {'"', "'"}:
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch == '{':
            brace += 1
        elif ch == '}':
            brace = max(0, brace - 1)
        elif ch == '[':
            bracket += 1
        elif ch == ']':
            bracket = max(0, bracket - 1)
        elif ch == '(':
            paren += 1
        elif ch == ')':
            paren = max(0, paren - 1)
        if ch == sep and brace == 0 and bracket == 0 and paren == 0:
            part = ''.join(buf).strip()
            if part:
                parts.append(part)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = ''.join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _strip_outer_braces(text: str) -> str:
    text = text.strip()
    if text.startswith('{') and text.endswith('}'):
        return text[1:-1].strip()
    return text


def _parse_label(spec: str) -> tuple[str, str]:
    spec = spec.strip()
    brace = bracket = paren = 0
    quote: Optional[str] = None
    for i, ch in enumerate(spec):
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in {'"', "'"}:
            quote = ch
            continue
        if ch == '{':
            brace += 1
            continue
        if ch == '}':
            brace = max(0, brace - 1)
            continue
        if ch == '[':
            bracket += 1
            continue
        if ch == ']':
            bracket = max(0, bracket - 1)
            continue
        if ch == '(':
            paren += 1
            continue
        if ch == ')':
            paren = max(0, paren - 1)
            continue
        if ch == ':' and brace == 0 and bracket == 0 and paren == 0:
            if i + 1 < len(spec) and spec[i + 1] == ':':
                continue
            label = spec[:i].strip()
            remainder = spec[i + 1:].strip()
            if label and ' ' not in label:
                return label, remainder
            return '', spec
    return '', spec


class EnvLangFormalCompiler:
    @classmethod
    def parse_node(cls, spec: str) -> FormalPlanNode:
        spec = spec.strip()
        label, core = _parse_label(spec)
        low = core.lower()
        if low.startswith('parallel'):
            inner = core[len('parallel'):].strip()
            inner = _strip_outer_braces(inner)
            children = [cls.parse_node(seg) for seg in _split_top_level(inner, '|')]
            return FormalPlanNode(kind='parallel', label=label, children=children)
        if low.startswith('sequence'):
            inner = core[len('sequence'):].strip()
            inner = _strip_outer_braces(inner)
            children = [cls.parse_node(seg) for seg in _split_top_level(inner, ';')]
            return FormalPlanNode(kind='sequence', label=label, children=children)
        if low.startswith('if '):
            m = re.match(r'^if\s+(.+?)\s+then\s+(.+?)(?:\s+else\s+(.+))?$', core, flags=re.IGNORECASE | re.DOTALL)
            if not m:
                raise EnvLangSyntaxError(f'invalid conditional form: {core}')
            cond = EnvLangFormalParser.parse_condition(m.group(1).strip())
            then_src = _strip_outer_braces(m.group(2).strip())
            else_src = _strip_outer_braces(m.group(3).strip()) if m.group(3) else ''
            then_branch = [cls.parse_node(seg) for seg in _split_top_level(then_src, ';')] if then_src else []
            else_branch = [cls.parse_node(seg) for seg in _split_top_level(else_src, ';')] if else_src else []
            return FormalPlanNode(kind='if', label=label, condition=cond, then_branch=then_branch, else_branch=else_branch)
        return FormalPlanNode(kind='command', label=label, command=EnvLangParser.parse_line(core))

    @classmethod
    def build_program(cls, name: str, body: str) -> FormalPlanProgram:
        root = [cls.parse_node(seg) for seg in _split_top_level(body, ';')]
        return FormalPlanProgram(name=name, root=root, source=body)


_old_compile_script_v03 = EnvLangCompiler.compile_script

def _compile_script_with_programs(script: ScriptNode) -> Dict[str, Any]:
    base = _old_compile_script_v03(script)
    programs: Dict[str, Any] = {}
    for cmd in script.commands:
        if cmd.kind == 'plan' and cmd.tokens and len(cmd.tokens) > 1:
            name = cmd.tokens[1]
            body = cmd.metadata.get('body', '')
            try:
                programs[name] = EnvLangFormalCompiler.build_program(name, body).to_dict()
            except Exception as exc:
                programs[name] = {'error': str(exc), 'body': body}
    base['formal_programs'] = programs
    base['version'] = '0.4'
    return base

EnvLangCompiler.compile_script = staticmethod(_compile_script_with_programs)


# Iteration 16 — variables, named bindings and template interpolation ---------

@dataclass
class FormalValueBinding:
    name: str
    expr: Any

    def to_dict(self) -> Dict[str, Any]:
        return {'name': self.name, 'expr': self.expr}


def _split_top_level_token(text: str, token: str):
    brace = bracket = paren = 0
    quote: Optional[str] = None
    i = 0
    while i <= len(text) - len(token):
        ch = text[i]
        if quote:
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in {'"', "'"}:
            quote = ch
            i += 1
            continue
        if ch == '{':
            brace += 1
        elif ch == '}':
            brace = max(0, brace - 1)
        elif ch == '[':
            bracket += 1
        elif ch == ']':
            bracket = max(0, bracket - 1)
        elif ch == '(':
            paren += 1
        elif ch == ')':
            paren = max(0, paren - 1)
        if brace == 0 and bracket == 0 and paren == 0 and text[i:i+len(token)] == token:
            return text[:i].strip(), text[i+len(token):].strip()
        i += 1
    return None, None


def _parse_scalar_literal(spec: str) -> Any:
    spec = spec.strip()
    if not spec:
        return ''
    low = spec.lower()
    if low in {'true', 'false'}:
        return low == 'true'
    if (spec.startswith('"') and spec.endswith('"')) or (spec.startswith("'") and spec.endswith("'")):
        return spec[1:-1]
    try:
        if '.' in spec:
            return float(spec)
        return int(spec)
    except ValueError:
        return spec


def _extract_template_refs(value: Any) -> List[str]:
    if isinstance(value, str):
        return re.findall(r'\$\{([^}]+)\}', value)
    if isinstance(value, dict):
        out: List[str] = []
        for v in value.values():
            out.extend(_extract_template_refs(v))
        return out
    if isinstance(value, list):
        out: List[str] = []
        for v in value:
            out.extend(_extract_template_refs(v))
        return out
    return []


_old_parse_node_v15 = EnvLangFormalCompiler.parse_node

@classmethod
def _parse_node_with_variables(cls, spec: str) -> FormalPlanNode:
    spec = spec.strip()
    label, core = _parse_label(spec)
    low = core.lower()
    if low.startswith('let '):
        m = re.match(r'^let\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$', core, flags=re.IGNORECASE | re.DOTALL)
        if not m:
            raise EnvLangSyntaxError(f'invalid let form: {core}')
        name = m.group(1)
        expr = _parse_scalar_literal(m.group(2))
        node = FormalPlanNode(kind='let', label=label)
        node.metadata = {'binding': FormalValueBinding(name=name, expr=expr).to_dict()}  # type: ignore[attr-defined]
        return node
    bind_left, bind_right = _split_top_level_token(core, '=>')
    if bind_left is not None and bind_right is not None:
        node = _old_parse_node_v15.__func__(cls, bind_left)
        meta = getattr(node, 'metadata', {}) or {}
        meta['bind'] = bind_right
        node.metadata = meta  # type: ignore[attr-defined]
        if label and not getattr(node, 'label', ''):
            node.label = label
        return node
    node = _old_parse_node_v15.__func__(cls, spec)
    if not hasattr(node, 'metadata'):
        node.metadata = {}  # type: ignore[attr-defined]
    return node

EnvLangFormalCompiler.parse_node = _parse_node_with_variables

_old_compile_script_v04 = EnvLangCompiler.compile_script

def _compile_script_with_variables(script: ScriptNode) -> Dict[str, Any]:
    base = _old_compile_script_v04(script)
    plans: Dict[str, Any] = {}
    for cmd in script.commands:
        if cmd.kind == 'plan' and cmd.tokens and len(cmd.tokens) > 1:
            name = cmd.tokens[1]
            body = cmd.metadata.get('body', '')
            try:
                plans[name] = EnvLangFormalCompiler.build_program(name, body).to_dict()
            except Exception as exc:
                plans[name] = {'error': str(exc), 'body': body}
    base['formal_programs'] = plans
    base['version'] = '0.5'
    return base

EnvLangCompiler.compile_script = staticmethod(_compile_script_with_variables)

_old_lint_script_v15 = EnvLangLinter.lint_script

def _lint_script_iteration16(script: ScriptNode) -> ScriptNode:
    script = _old_lint_script_v15(script)
    for idx, cmd in enumerate(script.commands, start=1):
        if cmd.kind == 'plan' and cmd.metadata.get('body'):
            try:
                program = EnvLangFormalCompiler.build_program(cmd.tokens[1], cmd.metadata['body']) if cmd.tokens and len(cmd.tokens) > 1 else None
                if program is not None:
                    refs: List[str] = []
                    def visit(nodes):
                        for node in nodes:
                            if node.kind == 'command' and node.command is not None:
                                refs.extend(_extract_template_refs(node.command.payload))
                            for branch in (getattr(node, 'children', []), getattr(node, 'then_branch', []), getattr(node, 'else_branch', [])):
                                visit(branch)
                    visit(program.root)
                    for ref in refs:
                        if ref.startswith('var.'):
                            script.warnings.append(f'line {idx}: template reference {ref!r} requires runtime variable resolution')
            except Exception:
                pass
    return script

EnvLangLinter.lint_script = staticmethod(_lint_script_iteration16)


# Iteration 17 — typed variables, scoped execution helpers, and built-in functions ---

@dataclass
class TypedFormalValueBinding(FormalValueBinding):
    declared_type: str = 'auto'

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data['declared_type'] = self.declared_type
        return data


def _coerce_typed_value_v17(value: Any, declared_type: str) -> Any:
    dtype = (declared_type or 'auto').lower()
    if dtype in {'', 'auto', 'any'}:
        return value
    if dtype in {'str', 'string'}:
        return '' if value is None else str(value)
    if dtype in {'int', 'integer'}:
        return 0 if value is None else int(float(value))
    if dtype in {'float', 'number'}:
        return 0.0 if value is None else float(value)
    if dtype in {'bool', 'boolean'}:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {'1', 'true', 'yes', 'on'}
        return bool(value)
    if dtype == 'json':
        if isinstance(value, str):
            return json.loads(value)
        return value
    if dtype == 'list':
        if isinstance(value, list):
            return value
        if value is None:
            return []
        if isinstance(value, str):
            s = value.strip()
            if s.startswith('[') and s.endswith(']'):
                return json.loads(s)
            return [seg.strip() for seg in s.split(',') if seg.strip()]
        return [value]
    return value


def _parse_typed_let_binding_v17(core: str) -> TypedFormalValueBinding:
    m = re.match(r'^let\s+([A-Za-z_][A-Za-z0-9_]*)(?::([A-Za-z_][A-Za-z0-9_]*))?\s*=\s*(.+)$', core, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        raise EnvLangSyntaxError(f'invalid typed let form: {core}')
    name = m.group(1)
    declared_type = m.group(2) or 'auto'
    expr = _parse_scalar_literal(m.group(3))
    return TypedFormalValueBinding(name=name, expr=expr, declared_type=declared_type)


_old_parse_node_v16 = EnvLangFormalCompiler.parse_node

@classmethod
def _parse_node_iteration17(cls, spec: str) -> FormalPlanNode:
    spec = spec.strip()
    label, core = _parse_label(spec)
    low = core.lower()
    if low.startswith('let '):
        binding = _parse_typed_let_binding_v17(core)
        node = FormalPlanNode(kind='let', label=label)
        node.metadata = {'binding': binding.to_dict()}  # type: ignore[attr-defined]
        return node
    return _old_parse_node_v16.__func__(cls, spec)

EnvLangFormalCompiler.parse_node = _parse_node_iteration17


def _function_apply_v17(name: str, args: List[Any]) -> Any:
    lname = name.lower()
    if lname == 'upper':
        return '' if not args or args[0] is None else str(args[0]).upper()
    if lname == 'lower':
        return '' if not args or args[0] is None else str(args[0]).lower()
    if lname == 'title':
        return '' if not args or args[0] is None else str(args[0]).title()
    if lname == 'len':
        return len(args[0]) if args else 0
    if lname == 'int':
        return _coerce_typed_value_v17(args[0] if args else 0, 'int')
    if lname == 'float':
        return _coerce_typed_value_v17(args[0] if args else 0.0, 'float')
    if lname == 'bool':
        return _coerce_typed_value_v17(args[0] if args else False, 'bool')
    if lname == 'str':
        return _coerce_typed_value_v17(args[0] if args else '', 'str')
    if lname == 'json':
        target = args[0] if args else None
        return json.dumps(target, ensure_ascii=False, sort_keys=True)
    if lname == 'default':
        if not args:
            return None
        return args[0] if args[0] not in (None, '', []) else (args[1] if len(args) > 1 else None)
    if lname == 'coalesce':
        for arg in args:
            if arg not in (None, '', []):
                return arg
        return None
    raise KeyError(f'unknown EnvLang function: {name}')


# Iteration 18 — reusable plan calls and remote blocks -------------------------

def _make_call_node_v18(label: str, plan_name: str) -> FormalPlanNode:
    cmd = CommandNode(kind='call', raw=f'call {plan_name}', tokens=['call', plan_name], subject=plan_name)
    return FormalPlanNode(kind='call', label=label, command=cmd)


def _make_remote_node_v18(label: str, peer_name: str, body: str) -> FormalPlanNode:
    children = [EnvLangFormalCompiler.parse_node(seg) for seg in _split_top_level(body, ';')] if body else []
    node = FormalPlanNode(kind='remote', label=label, children=children)
    node.metadata = {'peer': peer_name}  # type: ignore[attr-defined]
    return node


_old_parse_node_v17 = EnvLangFormalCompiler.parse_node

@classmethod
def _parse_node_iteration18(cls, spec: str) -> FormalPlanNode:
    spec = spec.strip()
    label, core = _parse_label(spec)
    low = core.lower()
    if low.startswith('call '):
        plan_name = core.split(None, 1)[1].strip()
        return _make_call_node_v18(label, plan_name)
    if low.startswith('remote '):
        m = re.match(r'^remote\s+([A-Za-z_][A-Za-z0-9_.-]*)\s*(.+)$', core, flags=re.IGNORECASE | re.DOTALL)
        if not m:
            raise EnvLangSyntaxError(f'invalid remote block: {core}')
        peer_name = m.group(1)
        body = _strip_outer_braces(m.group(2).strip())
        return _make_remote_node_v18(label, peer_name, body)
    return _old_parse_node_v17.__func__(cls, spec)

EnvLangFormalCompiler.parse_node = _parse_node_iteration18

_old_lint_script_iteration16 = EnvLangLinter.lint_script

def _lint_script_iteration18(script: ScriptNode) -> ScriptNode:
    script = _old_lint_script_iteration16(script)
    for idx, cmd in enumerate(script.commands, start=1):
        if cmd.kind == 'plan' and cmd.metadata.get('body'):
            body = cmd.metadata['body']
            if 'call ' in body:
                script.warnings.append(f'line {idx}: call nodes require runtime plan registry')
            if 'remote ' in body:
                script.warnings.append(f'line {idx}: remote nodes require registered runtime peers')
    return script

EnvLangLinter.lint_script = staticmethod(_lint_script_iteration18)


# Iteration 19 — static analysis for formal plans -----------------------------

@dataclass
class FormalPlanStaticIssue:
    severity: str
    code: str
    message: str
    label: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'severity': self.severity,
            'code': self.code,
            'message': self.message,
            'label': self.label,
        }


@dataclass
class FormalPlanStaticReport:
    plan_name: str
    issues: List[FormalPlanStaticIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity == 'error' for i in self.issues)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'plan_name': self.plan_name,
            'ok': self.ok,
            'issues': [i.to_dict() for i in self.issues],
        }


class FormalPlanStaticAnalyzer:
    @staticmethod
    def _command_resources(node: FormalPlanNode) -> List[str]:
        cmd = getattr(node, 'command', None)
        if cmd is None:
            return []
        payload = getattr(cmd, 'payload', {}) or {}
        resources: List[str] = []
        action = getattr(cmd, 'action', None)
        if action:
            resources.append(f'action:{action}')
        for key in ('case', 'drone', 'mission', 'target', 'group'):
            if key in payload and payload[key] not in (None, ''):
                resources.append(f'{key}:{payload[key]}')
        return resources

    @classmethod
    def _walk(cls, node: FormalPlanNode, report: FormalPlanStaticReport, known_plans: Optional[Dict[str, Any]] = None) -> set[str]:
        kind = getattr(node, 'kind', '')
        label = getattr(node, 'label', '') or ''
        resources: set[str] = set()
        if kind in {'do', 'vote', 'negotiate', 'run.group', 'fanout', 'delegate', 'command'}:
            resources.update(cls._command_resources(node))
        elif kind == 'call':
            plan_name = getattr(getattr(node, 'command', None), 'subject', None)
            if known_plans is not None and plan_name not in known_plans:
                report.issues.append(FormalPlanStaticIssue('error', 'unknown-plan', f'call references unknown plan {plan_name}', label))
            if plan_name == report.plan_name:
                report.issues.append(FormalPlanStaticIssue('error', 'recursive-call', f'plan {report.plan_name} directly calls itself', label))
        elif kind == 'remote':
            metadata = getattr(node, 'metadata', {}) or {}
            if not metadata.get('peer'):
                report.issues.append(FormalPlanStaticIssue('error', 'remote-peer-missing', 'remote block has no peer target', label))
        if kind == 'parallel':
            child_resources = []
            for child in getattr(node, 'children', []) or []:
                cres = cls._walk(child, report, known_plans)
                child_resources.append((child, cres))
                resources.update(cres)
            seen: Dict[str, str] = {}
            for child, cres in child_resources:
                child_label = getattr(child, 'label', '') or getattr(child, 'kind', '')
                for res in cres:
                    if res in seen:
                        report.issues.append(FormalPlanStaticIssue('warning', 'parallel-resource-conflict', f'parallel branches both touch {res} ({seen[res]} vs {child_label})', label or 'parallel'))
                    else:
                        seen[res] = child_label
            return resources
        for child in getattr(node, 'children', []) or []:
            resources.update(cls._walk(child, report, known_plans))
        return resources

    @classmethod
    def analyze(cls, program: FormalPlanProgram, known_plans: Optional[Dict[str, Any]] = None) -> FormalPlanStaticReport:
        report = FormalPlanStaticReport(plan_name=getattr(program, 'name', 'unknown'))
        for node in getattr(program, 'root', []) or []:
            cls._walk(node, report, known_plans)
        return report


# Iteration 21 — deeper static analysis and plan graph export -----------------

@dataclass
class FormalPlanReferenceReport:
    plan_name: str
    variables_declared: List[str] = field(default_factory=list)
    labels_declared: List[str] = field(default_factory=list)
    variable_references: List[str] = field(default_factory=list)
    result_references: List[str] = field(default_factory=list)
    function_references: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'plan_name': self.plan_name,
            'variables_declared': sorted(set(self.variables_declared)),
            'labels_declared': sorted(set(self.labels_declared)),
            'variable_references': sorted(set(self.variable_references)),
            'result_references': sorted(set(self.result_references)),
            'function_references': sorted(set(self.function_references)),
        }


@dataclass
class FormalPlanGraph:
    plan_name: str
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'plan_name': self.plan_name,
            'nodes': list(self.nodes),
            'edges': list(self.edges),
        }

    def to_dot(self) -> str:
        lines = [f'digraph "{self.plan_name}" {{']
        for node in self.nodes:
            nid = node['id'].replace('"', '_')
            label = node.get('label', nid).replace('"', '\\"')
            kind = node.get('kind', 'node')
            lines.append(f'  "{nid}" [label="{label}\\n[{kind}]"];')
        for edge in self.edges:
            src = edge['source'].replace('"', '_')
            dst = edge['target'].replace('"', '_')
            label = edge.get('label', '').replace('"', '\\"')
            lines.append(f'  "{src}" -> "{dst}" [label="{label}"];')
        lines.append('}')
        return '\n'.join(lines)


def _iter_plan_children(node: FormalPlanNode):
    for attr in ('children', 'then_branch', 'else_branch'):
        for child in getattr(node, attr, []) or []:
            yield child


def _extract_symbol_refs(expr: str) -> Dict[str, List[str]]:
    if not isinstance(expr, str):
        return {'var': [], 'result': [], 'fn': []}
    return {
        'var': re.findall(r'\bvar\.([A-Za-z_][A-Za-z0-9_]*)', expr),
        'result': re.findall(r'\bresult\.([A-Za-z_][A-Za-z0-9_]*)', expr),
        'fn': re.findall(r'\bfn\.([A-Za-z_][A-Za-z0-9_]*)\s*\(', expr),
    }


class FormalPlanGraphBuilder:
    @classmethod
    def build(cls, program: FormalPlanProgram) -> FormalPlanGraph:
        graph = FormalPlanGraph(plan_name=getattr(program, 'name', 'unknown'))
        counter = {'n': 0}

        def nid(prefix: str) -> str:
            counter['n'] += 1
            return f'{prefix}-{counter["n"]}'

        def visit(node: FormalPlanNode, parent: Optional[str] = None, edge_label: str = 'next'):
            node_id = getattr(node, 'label', '') or nid(getattr(node, 'kind', 'node'))
            graph.nodes.append({'id': node_id, 'label': getattr(node, 'label', '') or getattr(node, 'kind', 'node'), 'kind': getattr(node, 'kind', 'node')})
            if parent is not None:
                graph.edges.append({'source': parent, 'target': node_id, 'label': edge_label})
            kind = getattr(node, 'kind', '')
            if kind == 'if':
                for child in getattr(node, 'then_branch', []) or []:
                    visit(child, node_id, 'then')
                for child in getattr(node, 'else_branch', []) or []:
                    visit(child, node_id, 'else')
                return node_id
            for child in getattr(node, 'children', []) or []:
                visit(child, node_id, 'contains' if kind in {'parallel', 'sequence', 'remote'} else 'next')
            return node_id

        prev = None
        for node in getattr(program, 'root', []) or []:
            current = visit(node)
            if prev is not None:
                graph.edges.append({'source': prev, 'target': current, 'label': 'flow'})
            prev = current
        return graph


_old_static_analyze_v20 = FormalPlanStaticAnalyzer.analyze

@classmethod
def _analyze_iteration21(cls, program: FormalPlanProgram, known_plans: Optional[Dict[str, Any]] = None) -> FormalPlanStaticReport:
    report = _old_static_analyze_v20.__func__(cls, program, known_plans)
    declared_vars: set[str] = set()
    declared_labels: set[str] = set()
    available_fns = {'upper','lower','title','len','int','float','bool','str','json','default','coalesce'}

    def scan_nodes(nodes: List[FormalPlanNode], scope_vars: set[str], scope_labels: set[str]):
        local_vars = set(scope_vars)
        local_labels = set(scope_labels)
        for node in nodes or []:
            label = getattr(node, 'label', '') or ''
            if label:
                if label in local_labels:
                    report.issues.append(FormalPlanStaticIssue('error', 'duplicate-label', f'duplicate label {label}', label))
                local_labels.add(label)
                declared_labels.add(label)
            metadata = getattr(node, 'metadata', {}) or {}
            kind = getattr(node, 'kind', '')
            refs: List[str] = []
            if kind == 'let':
                binding = metadata.get('binding', {}) or {}
                name = binding.get('name')
                if name:
                    if name in local_vars:
                        report.issues.append(FormalPlanStaticIssue('warning', 'shadowed-variable', f'variable {name} redefined in same scope', label))
                    local_vars.add(name)
                    declared_vars.add(name)
                expr = str(binding.get('expr', ''))
                sym = _extract_symbol_refs(expr)
                for ref in sym['var']:
                    if ref not in local_vars:
                        report.issues.append(FormalPlanStaticIssue('error', 'undefined-variable', f'let expression references undefined variable {ref}', label))
                for ref in sym['result']:
                    if ref not in local_labels:
                        report.issues.append(FormalPlanStaticIssue('error', 'undefined-result', f'let expression references undefined result label {ref}', label))
                for fn in sym['fn']:
                    if fn not in available_fns:
                        report.issues.append(FormalPlanStaticIssue('warning', 'unknown-function', f'function fn.{fn} is not a known built-in', label))
            if kind == 'command' and getattr(node, 'command', None) is not None:
                cmd = node.command
                refs.extend(_extract_template_refs(getattr(cmd, 'payload', {}) or {}))
                if getattr(cmd, 'subject', None):
                    refs.extend(_extract_template_refs(cmd.subject))
                if getattr(cmd, 'target', None):
                    refs.extend(_extract_template_refs(cmd.target))
            if kind == 'if' and getattr(node, 'condition', None) is not None:
                cond = node.condition
                refs.append(str(cond.field))
                refs.append(str(cond.value))
            if kind in {'call','remote'}:
                refs.extend(_extract_template_refs(metadata))
            for refexpr in refs:
                sym = _extract_symbol_refs(str(refexpr))
                for ref in sym['var']:
                    if ref not in local_vars:
                        report.issues.append(FormalPlanStaticIssue('error', 'undefined-variable', f'reference to undefined variable {ref}', label))
                for ref in sym['result']:
                    if ref not in local_labels:
                        report.issues.append(FormalPlanStaticIssue('error', 'undefined-result', f'reference to undefined result label {ref}', label))
                for fn in sym['fn']:
                    if fn not in available_fns:
                        report.issues.append(FormalPlanStaticIssue('warning', 'unknown-function', f'function fn.{fn} is not a known built-in', label))
            if kind == 'parallel':
                for child in getattr(node, 'children', []) or []:
                    scan_nodes([child], set(local_vars), set(local_labels))
            elif kind == 'if':
                scan_nodes(getattr(node, 'then_branch', []) or [], set(local_vars), set(local_labels))
                scan_nodes(getattr(node, 'else_branch', []) or [], set(local_vars), set(local_labels))
            else:
                scan_nodes(getattr(node, 'children', []) or [], local_vars, local_labels)
                # post-sequential updates for this node
                if kind == 'command' and metadata.get('bind'):
                    bind_name = str(metadata.get('bind'))
                    local_vars.add(bind_name)
                    declared_vars.add(bind_name)
        return local_vars, local_labels

    scan_nodes(getattr(program, 'root', []) or [], set(), set())
    report.metadata = FormalPlanReferenceReport(  # type: ignore[attr-defined]
        plan_name=getattr(program, 'name', 'unknown'),
        variables_declared=sorted(declared_vars),
        labels_declared=sorted(declared_labels),
        variable_references=[],
        result_references=[],
        function_references=[],
    )
    return report

FormalPlanStaticAnalyzer.analyze = _analyze_iteration21


def formal_plan_reference_report(program: FormalPlanProgram) -> FormalPlanReferenceReport:
    rep = FormalPlanReferenceReport(plan_name=getattr(program, 'name', 'unknown'))

    def walk(nodes: List[FormalPlanNode]):
        for node in nodes or []:
            label = getattr(node, 'label', '') or ''
            if label:
                rep.labels_declared.append(label)
            metadata = getattr(node, 'metadata', {}) or {}
            if getattr(node, 'kind', '') == 'let':
                binding = metadata.get('binding', {}) or {}
                if binding.get('name'):
                    rep.variables_declared.append(str(binding.get('name')))
                expr = str(binding.get('expr', ''))
                sym = _extract_symbol_refs(expr)
                rep.variable_references.extend(sym['var'])
                rep.result_references.extend(sym['result'])
                rep.function_references.extend(sym['fn'])
            if getattr(node, 'kind', '') == 'command' and getattr(node, 'command', None) is not None:
                refs = _extract_template_refs(getattr(node.command, 'payload', {}) or {})
                for refexpr in refs:
                    sym = _extract_symbol_refs(str(refexpr))
                    rep.variable_references.extend(sym['var'])
                    rep.result_references.extend(sym['result'])
                    rep.function_references.extend(sym['fn'])
            if getattr(node, 'kind', '') == 'if' and getattr(node, 'condition', None) is not None:
                sym = _extract_symbol_refs(str(node.condition.field))
                rep.variable_references.extend(sym['var'])
                rep.result_references.extend(sym['result'])
                rep.function_references.extend(sym['fn'])
                sym = _extract_symbol_refs(str(node.condition.value))
                rep.variable_references.extend(sym['var'])
                rep.result_references.extend(sym['result'])
                rep.function_references.extend(sym['fn'])
            for branch in (getattr(node, 'children', []), getattr(node, 'then_branch', []), getattr(node, 'else_branch', [])):
                walk(branch)

    walk(getattr(program, 'root', []) or [])
    return rep
