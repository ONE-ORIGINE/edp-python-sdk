from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time

from .protocol import PROTOCOL_SCHEMAS, ProtocolCodec, CanonicalPacket, MultiAgentRuntime, _runtime_coordination_init

PROJECT_VERSION = "2.0.0"
CHANNEL = "stable"
PROTOCOL_VERSION = "1.0"


@dataclass
class ModuleManifest:
    name: str
    version: str
    description: str
    exports: List[str] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "exports": list(self.exports),
            "commands": list(self.commands),
            "dependencies": list(self.dependencies),
        }


@dataclass
class ReleaseManifest:
    version: str
    channel: str
    protocol_version: str
    generated_at: float
    modules: List[ModuleManifest] = field(default_factory=list)
    schema_count: int = 0
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "channel": self.channel,
            "protocol_version": self.protocol_version,
            "generated_at": self.generated_at,
            "schema_count": self.schema_count,
            "modules": [m.to_dict() for m in self.modules],
            "notes": list(self.notes),
        }


@dataclass
class ProtocolHelloPacket:
    packet_id: str
    runtime_id: str
    protocol_version: str
    supported_schema_versions: Dict[str, List[str]]
    module_versions: Dict[str, str]
    emitted_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "runtime_id": self.runtime_id,
            "protocol_version": self.protocol_version,
            "supported_schema_versions": dict(self.supported_schema_versions),
            "module_versions": dict(self.module_versions),
            "emitted_at": self.emitted_at,
        }


@dataclass
class ProtocolNegotiationPacket:
    packet_id: str
    source_runtime_id: str
    target_runtime_id: str
    compatible: bool
    shared_packets: List[str] = field(default_factory=list)
    protocol_version: str = PROTOCOL_VERSION
    notes: List[str] = field(default_factory=list)
    emitted_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "source_runtime_id": self.source_runtime_id,
            "target_runtime_id": self.target_runtime_id,
            "compatible": self.compatible,
            "shared_packets": list(self.shared_packets),
            "protocol_version": self.protocol_version,
            "notes": list(self.notes),
            "emitted_at": self.emitted_at,
        }


def build_module_manifests() -> Dict[str, ModuleManifest]:
    manifests = {
        "edp_sdk": ModuleManifest(
            name="edp_sdk",
            version=PROJECT_VERSION,
            description="Canonical runtime, semantics, protocol, policy, memory, analytics, persistence and maintenance.",
            exports=[
                "Environment", "Context", "Element", "Action", "Reaction", "MepGateway",
                "MultiAgentRuntime", "EnvironmentCanonicalBody", "Savoir", "Contextualizer",
            ],
            commands=["edp-demo", "edp-cli", "edp-release-check", "edp-build-release"],
            dependencies=["drone_edp", "mep_tools"],
        ),
        "drone_edp": ModuleManifest(
            name="drone_edp",
            version=PROJECT_VERSION,
            description="Drone specialization over EDP + MEP + SAVOIR.",
            exports=["DroneElement", "DroneSwarmSDK", "PoseSE3"],
            commands=[],
            dependencies=["edp_sdk"],
        ),
        "mep_tools": ModuleManifest(
            name="mep_tools",
            version=PROJECT_VERSION,
            description="EnvLang, schema tooling and release metadata/build tooling for MEP environments.",
            exports=["EnvLangParser", "EnvLangCompiler", "EnvLangFormalCompiler", "ProtocolSchemaRegistry"],
            commands=["edp-build-release"],
            dependencies=["edp_sdk"],
        ),
    }
    return manifests


def build_release_manifest() -> ReleaseManifest:
    manifests = build_module_manifests()
    notes = [
        "stable canonical release built from canonical ENVX body",
        "multi-agent runtime, governance, distributed plans and protocol validation included",
        "generation-2 stable line with contextual matrix, learning projection and persistent native stores",
    ]
    return ReleaseManifest(
        version=PROJECT_VERSION,
        channel=CHANNEL,
        protocol_version=PROTOCOL_VERSION,
        generated_at=time.time(),
        modules=list(manifests.values()),
        schema_count=sum(len(v) for v in PROTOCOL_SCHEMAS.export().get("packet_types", {}).values()),
        notes=notes,
    )


def _schema_versions_map() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    exported = PROTOCOL_SCHEMAS.export().get("packet_types", {})
    for packet_type, versions in exported.items():
        out[packet_type] = sorted({str(item.get("version", "1.0")) for item in versions})
    return out


def _runtime_protocol_hello(self: MultiAgentRuntime) -> ProtocolHelloPacket:
    import uuid
    _runtime_coordination_init(self)
    return ProtocolHelloPacket(
        packet_id=str(uuid.uuid4()),
        runtime_id=self.runtime_id,
        protocol_version=PROTOCOL_VERSION,
        supported_schema_versions=_schema_versions_map(),
        module_versions={k: v.version for k, v in build_module_manifests().items()},
    )


def _runtime_negotiate_protocol(self: MultiAgentRuntime, peer_name: str) -> ProtocolNegotiationPacket:
    import uuid
    peers = getattr(self, '_runtime_peers', {})
    if peer_name not in peers:
        raise KeyError(f'unknown runtime peer: {peer_name}')
    peer = peers[peer_name]
    local = self.protocol_hello()
    remote = peer.protocol_hello()
    shared_packets: List[str] = []
    local_map = local.supported_schema_versions
    remote_map = remote.supported_schema_versions
    for packet_type, versions in local_map.items():
        overlap = sorted(set(versions).intersection(remote_map.get(packet_type, [])))
        if overlap:
            shared_packets.append(f"{packet_type}@{overlap[-1]}")
    compatible = local.protocol_version == remote.protocol_version and len(shared_packets) > 0
    notes: List[str] = []
    if local.protocol_version != remote.protocol_version:
        notes.append(f"protocol version mismatch: {local.protocol_version} vs {remote.protocol_version}")
    if not shared_packets:
        notes.append("no shared packet schemas")
    return ProtocolNegotiationPacket(
        packet_id=str(uuid.uuid4()),
        source_runtime_id=self.runtime_id,
        target_runtime_id=getattr(peer, 'runtime_id', peer_name),
        compatible=compatible,
        shared_packets=shared_packets,
        notes=notes,
    )


def _gateway_protocol_hello_packet(self, runtime: MultiAgentRuntime) -> CanonicalPacket:
    return ProtocolCodec.pack('protocol.hello', runtime.protocol_hello().to_dict())


def _gateway_protocol_negotiation_packet(self, runtime: MultiAgentRuntime, peer_name: str) -> CanonicalPacket:
    return ProtocolCodec.pack('protocol.negotiate', runtime.negotiate_protocol(peer_name).to_dict())


def _register_release_protocol_schemas() -> None:
    from .protocol import PacketSchema
    packets = {
        'protocol.hello': {
            'required': ('packet_id', 'runtime_id', 'protocol_version', 'supported_schema_versions', 'module_versions'),
            'optional': ('emitted_at',),
            'description': 'protocol capability hello packet',
        },
        'protocol.negotiate': {
            'required': ('packet_id', 'source_runtime_id', 'target_runtime_id', 'compatible', 'shared_packets', 'protocol_version'),
            'optional': ('notes', 'emitted_at'),
            'description': 'protocol compatibility negotiation packet',
        },
        'release.manifest': {
            'required': ('version', 'channel', 'protocol_version', 'generated_at', 'modules', 'schema_count'),
            'optional': ('notes',),
            'description': 'release manifest packet',
        },
    }
    for ptype, spec in packets.items():
        if PROTOCOL_SCHEMAS.get(ptype, '1.0') is None:
            PROTOCOL_SCHEMAS.register(PacketSchema(packet_type=ptype, version='1.0', required_body=tuple(spec['required']), optional_body=tuple(spec['optional']), description=spec['description']))


_register_release_protocol_schemas()
MultiAgentRuntime.protocol_hello = _runtime_protocol_hello
MultiAgentRuntime.negotiate_protocol = _runtime_negotiate_protocol


def _runtime_release_manifest(self: MultiAgentRuntime) -> ReleaseManifest:
    return build_release_manifest()


MultiAgentRuntime.release_manifest = _runtime_release_manifest


def _gateway_release_manifest_packet(self) -> CanonicalPacket:
    return ProtocolCodec.pack('release.manifest', build_release_manifest().to_dict())


# monkeypatch gateway lazily to avoid circular type complaints
try:
    from .protocol import MepGateway
    MepGateway.protocol_hello_packet = _gateway_protocol_hello_packet
    MepGateway.protocol_negotiation_packet = _gateway_protocol_negotiation_packet
    MepGateway.release_manifest_packet = _gateway_release_manifest_packet
except Exception:
    pass


__all__ = [
    'PROJECT_VERSION', 'CHANNEL', 'PROTOCOL_VERSION',
    'ModuleManifest', 'ReleaseManifest', 'ProtocolHelloPacket', 'ProtocolNegotiationPacket',
    'build_module_manifests', 'build_release_manifest',
]
