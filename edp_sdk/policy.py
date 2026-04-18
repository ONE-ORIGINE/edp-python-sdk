from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class PolicyDecision:
    allowed: bool
    reasons: List[str] = field(default_factory=list)
    matched_rules: List[str] = field(default_factory=list)
    evaluated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "matched_rules": list(self.matched_rules),
            "evaluated_at": self.evaluated_at,
        }


@dataclass
class ActionPolicyRule:
    rule_id: str
    effect: str  # allow|deny
    action_type: str
    role: Optional[str] = None
    context_name: Optional[str] = None
    capability: Optional[str] = None
    situation_label: Optional[str] = None
    interface_name: Optional[str] = None
    interface_realm: Optional[str] = None
    description: str = ""
    priority: int = 0

    def matches(self, *, role: str, action_type: str, context_name: str, capabilities: Set[str],
                situation_label: Optional[str] = None, interface_name: Optional[str] = None,
                interface_realm: Optional[str] = None) -> bool:
        if self.action_type not in {"*", action_type}:
            return False
        if self.role is not None and self.role != role:
            return False
        if self.context_name is not None and self.context_name != context_name:
            return False
        if self.capability is not None and self.capability not in capabilities:
            return False
        if self.situation_label is not None and self.situation_label != situation_label:
            return False
        if self.interface_name is not None and self.interface_name != interface_name:
            return False
        if self.interface_realm is not None and self.interface_realm != interface_realm:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "effect": self.effect,
            "action_type": self.action_type,
            "role": self.role,
            "context_name": self.context_name,
            "capability": self.capability,
            "situation_label": self.situation_label,
            "interface_name": self.interface_name,
            "interface_realm": self.interface_realm,
            "description": self.description,
            "priority": self.priority,
        }


class PolicyEngine:
    """Simple but explicit governance layer for multi-agent EDP/MEP."""

    def __init__(self) -> None:
        self._rules: List[ActionPolicyRule] = []
        self._role_caps: Dict[str, Set[str]] = {}

    def set_role_capabilities(self, role: str, capabilities: List[str]) -> None:
        self._role_caps[role] = set(capabilities)

    def grant_capability(self, role: str, capability: str) -> None:
        self._role_caps.setdefault(role, set()).add(capability)

    def revoke_capability(self, role: str, capability: str) -> None:
        self._role_caps.setdefault(role, set()).discard(capability)

    def capabilities_for(self, role: str, extra: Optional[List[str]] = None) -> Set[str]:
        caps = set(self._role_caps.get(role, set()))
        caps.update(extra or [])
        return caps

    def add_rule(self, rule: ActionPolicyRule) -> None:
        self._rules.append(rule)
        self._rules.sort(key=lambda r: (r.priority, r.effect == "allow"), reverse=True)

    def allow(self, rule_id: str, action_type: str, *, role: Optional[str] = None,
              context_name: Optional[str] = None, capability: Optional[str] = None,
              situation_label: Optional[str] = None, interface_name: Optional[str] = None,
              interface_realm: Optional[str] = None, description: str = "", priority: int = 10) -> None:
        self.add_rule(ActionPolicyRule(rule_id, "allow", action_type, role, context_name, capability, situation_label, interface_name, interface_realm, description, priority))

    def deny(self, rule_id: str, action_type: str, *, role: Optional[str] = None,
             context_name: Optional[str] = None, capability: Optional[str] = None,
             situation_label: Optional[str] = None, interface_name: Optional[str] = None,
             interface_realm: Optional[str] = None, description: str = "", priority: int = 100) -> None:
        self.add_rule(ActionPolicyRule(rule_id, "deny", action_type, role, context_name, capability, situation_label, interface_name, interface_realm, description, priority))

    def evaluate(self, *, role: str, action_type: str, context_name: str,
                 explicit_capabilities: Optional[List[str]] = None,
                 situation_label: Optional[str] = None,
                 interface_name: Optional[str] = None,
                 interface_realm: Optional[str] = None) -> PolicyDecision:
        caps = self.capabilities_for(role, explicit_capabilities)
        matched = [r for r in self._rules if r.matches(role=role, action_type=action_type, context_name=context_name, capabilities=caps, situation_label=situation_label, interface_name=interface_name, interface_realm=interface_realm)]
        if matched:
            top = matched[0]
            decision = PolicyDecision(allowed=(top.effect == "allow"))
            decision.matched_rules = [r.rule_id for r in matched]
            if top.effect != "allow":
                decision.reasons.append(top.description or f"policy denied {action_type}")
            return decision
        # default posture: allowed if role has dispatch or action-specific cap
        if "dispatch" in caps or f"action:{action_type}" in caps:
            return PolicyDecision(True, matched_rules=["implicit-capability"])
        return PolicyDecision(False, reasons=[f"role {role} lacks capability for {action_type}"], matched_rules=["implicit-deny"])

    def snapshot(self) -> Dict[str, Any]:
        return {
            "role_capabilities": {k: sorted(v) for k, v in self._role_caps.items()},
            "rules": [r.to_dict() for r in self._rules],
        }
