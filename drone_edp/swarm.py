from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from edp_sdk.contextualizer import ContextualRule, Contextualizer, SignalProfile
from edp_sdk.core import (
    Action,
    ActionCategory,
    Circumstance,
    ContextKind,
    Element,
    Environment,
    EnvironmentKind,
    ImpactScope,
    Reaction,
)
from edp_sdk.protocol import MepGateway
from edp_sdk.savoir import Factor, Savoir
from edp_sdk.semantics import SenseVector

from .se3 import PoseSE3


@dataclass
class DroneState:
    pose: PoseSE3 = field(default_factory=PoseSE3)
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    battery_pct: float = 100.0
    gps_lock: bool = True
    airborne: bool = False
    mode: str = "IDLE"


class DroneElement(Element):
    def __init__(self, name: str, drone_id: str) -> None:
        super().__init__(name=name, kind="drone", basis=SenseVector.spatial("drone body", 1.0), properties={"drone_id": drone_id})
        self.state = DroneState()

    async def on_impacted(self, reaction: Reaction, frame: Dict[str, Any]) -> None:
        if reaction.type == "flight.takeoff":
            self.state.airborne = True
            self.state.mode = "TAKEOFF"
        elif reaction.type == "flight.move":
            dx = float(reaction.result.get("dx", 0.0))
            dy = float(reaction.result.get("dy", 0.0))
            dz = float(reaction.result.get("dz", 0.0))
            self.state.pose = self.state.pose.exp_update((dx, dy, dz, 0.0, 0.0, 0.0))
            self.state.mode = "CRUISE"
        elif reaction.type == "flight.return_home":
            self.state.pose = PoseSE3()
            self.state.mode = "RTL"
        elif reaction.type == "flight.land":
            self.state.airborne = False
            self.state.mode = "LANDED"
        elif reaction.type == "swarm.broadcast_status":
            self.dynamic["last_broadcast"] = reaction.result.get("summary", "broadcast")

    def snapshot(self) -> Dict[str, Any]:
        base = super().snapshot()
        base["state"] = {
            "pose": self.state.pose.__dict__,
            "battery_pct": self.state.battery_pct,
            "gps_lock": self.state.gps_lock,
            "airborne": self.state.airborne,
            "mode": self.state.mode,
        }
        return base


class DroneSwarmSDK:
    def __init__(self, name: str = "DroneSwarm") -> None:
        self.savoir = Savoir()
        self.contextualizer = Contextualizer()
        self.environment = Environment(name, EnvironmentKind.DYNAMIC, contextualizer=self.contextualizer, savoir=self.savoir)
        self.gateway = MepGateway(self.environment)
        self._factor_names: set[str] = set()
        self.flight = self.environment.create_context("Flight", ContextKind.NAVIGATION, SenseVector.spatial("flight corridor", 1.0))
        self.emergency = self.environment.create_context("Emergency", ContextKind.EMERGENCY, SenseVector.causal("emergency handling", 1.0))
        self.swarm = self.environment.create_context("Swarm", ContextKind.SWARM, SenseVector.social("swarm coordination", 0.95))
        self._configure_contextualizer()
        self._configure_factors()
        self._configure_actions()
    def _add_factor_once(self, name: str, variables: tuple[str, ...], evaluator, *, weight: float = 1.0, kind: str = "constraint") -> None:
        if name in self._factor_names:
            return
        self._factor_names.add(name)
        self.savoir.factor_graph.add_factor(Factor(name=name, variables=variables, evaluator=evaluator, weight=weight, kind=kind))

    def _configure_contextualizer(self) -> None:
        self.contextualizer.register_profile(SignalProfile("battery", SenseVector.temporal("battery endurance", 0.9), min_val=0.0, max_val=100.0, thresholds={"critical": 15.0}))
        self.contextualizer.register_profile(SignalProfile("gps_hdop", SenseVector.technical("gps quality", 0.8), min_val=0.0, max_val=5.0))
        self.contextualizer.register_rule(ContextualRule(
            signal_tag="battery",
            context_kind=ContextKind.NAVIGATION.value,
            sense_fn=lambda signal, ctx: SenseVector.temporal("battery low" if signal.numeric() < 20 else "battery nominal", 0.9),
            relevance_fn=lambda signal, ctx: 1.0 - (signal.numeric() / 100.0),
            label_fn=lambda signal, ctx: "battery critical" if signal.numeric() < 15 else "battery observation",
            actionable_fn=lambda signal, ctx, relevance: signal.numeric() < 20,
            priority=10,
        ))

    def _configure_factors(self) -> None:
        self.savoir.factor_graph.add_factor(Factor(
            name="gps_quality",
            variables=("gps_hdop",),
            weight=1.0,
            evaluator=lambda vals: max(0.0, float(vals.get("gps_hdop") or 0.0) - 2.0),
        ))
        self.savoir.factor_graph.add_factor(Factor(
            name="battery_safety",
            variables=("battery",),
            weight=1.5,
            evaluator=lambda vals: max(0.0, 15.0 - float(vals.get("battery") or 100.0)),
        ))
        self.savoir.factor_graph.add_factor(Factor(
            name="swarm_separation",
            variables=("nearest_neighbor_distance",),
            weight=1.3,
            evaluator=lambda vals: max(0.0, 2.0 - float(vals.get("nearest_neighbor_distance") or 99.0)),
        ))

    def _configure_actions(self) -> None:
        can_takeoff = Circumstance.when("drone.ready.takeoff", "GPS lock and battery > 15%", lambda ctx, frame: ctx.data.get("gps_lock", True) and ctx.data.get("battery", 100.0) > 15.0)
        can_move = Circumstance.when("drone.can.move", "Airborne and no emergency", lambda ctx, frame: ctx.data.get("airborne", False) and not ctx.data.get("collision_alert", False))
        low_battery = Circumstance.when("drone.low.battery", "Battery below 20%", lambda ctx, frame: ctx.data.get("battery", 100.0) < 20.0)
        swarm_safe = Circumstance.when("swarm.separation.ok", "Nearest neighbor distance above minimum", lambda ctx, frame: ctx.data.get("nearest_neighbor_distance", 99.0) >= 2.0)

        async def takeoff(actor: DroneElement, payload: Dict[str, Any], ctx, frame):
            return Reaction.ok("flight.takeoff", "Drone airborne", sense=SenseVector.causal("thrust to lift", 0.9), impact_scope=ImpactScope.ON_ACTOR)

        async def move(actor: DroneElement, payload: Dict[str, Any], ctx, frame):
            dx = float(payload.get("dx", 0.0))
            dy = float(payload.get("dy", 0.0))
            dz = float(payload.get("dz", 0.0))
            return Reaction.ok("flight.move", "Drone moved", sense=SenseVector.spatial("displacement", 0.9), impact_scope=ImpactScope.ON_ACTOR, result={"dx": dx, "dy": dy, "dz": dz})

        async def return_home(actor: DroneElement, payload: Dict[str, Any], ctx, frame):
            return Reaction.ok("flight.return_home", "Returning to home", sense=SenseVector.temporal("recovery trajectory", 0.8), impact_scope=ImpactScope.ON_ACTOR, chain=[("flight.land", {}, actor.element_id)])

        async def land(actor: DroneElement, payload: Dict[str, Any], ctx, frame):
            return Reaction.ok("flight.land", "Drone landed", sense=SenseVector.normative("safe termination", 0.9), impact_scope=ImpactScope.ON_ACTOR)

        async def broadcast_status(actor: DroneElement, payload: Dict[str, Any], ctx, frame):
            summary = payload.get("summary") or f"{actor.name}:{actor.state.mode}:{actor.state.battery_pct:.0f}%"
            targets = [eid for eid in self.environment.elements.keys() if eid != actor.element_id]
            return Reaction.ok(
                "swarm.broadcast_status",
                "Swarm status broadcasted",
                sense=SenseVector.social("swarm coordination", 0.85),
                impact_scope=ImpactScope.BROADCAST,
                target_ids=targets,
                result={"summary": summary, "target_count": len(targets)},
            )

        self.flight.reg(Action("flight.takeoff", ActionCategory.COMMAND, "Takeoff", SenseVector.causal("takeoff action", 0.8), handler=takeoff, circumstances=[can_takeoff], predicted_reaction=SenseVector.causal("lift confirmed", 0.8)))
        self.flight.reg(Action("flight.move", ActionCategory.TRANSITION, "Move in SE(3)", SenseVector.spatial("motion command", 0.9), handler=move, circumstances=[can_move, swarm_safe], predicted_reaction=SenseVector.spatial("position updated", 0.9)))
        self.emergency.reg(Action("flight.return_home", ActionCategory.COMMAND, "Return to home", SenseVector.temporal("return home", 0.9), handler=return_home, circumstances=[low_battery], predicted_reaction=SenseVector.temporal("recovery path", 0.8)))
        self.emergency.reg(Action("flight.land", ActionCategory.COMMAND, "Land immediately", SenseVector.normative("land", 0.9), handler=land, circumstances=[Circumstance.always("landing.allowed")], predicted_reaction=SenseVector.normative("drone safe", 0.8)))
        self.swarm.reg(Action("swarm.broadcast_status", ActionCategory.SIGNAL, "Broadcast swarm status", SenseVector.social("broadcast status", 0.8), handler=broadcast_status, circumstances=[Circumstance.always("swarm.broadcast.allowed")], predicted_reaction=SenseVector.social("swarm synchronized", 0.75)))

    async def admit(self, drone: DroneElement) -> None:
        await self.environment.admit(drone)
        self.flight.include(drone.snapshot())
        self.emergency.include(drone.snapshot())
        self.swarm.include(drone.snapshot())
        self._refresh_swarm_relations()

    def _refresh_swarm_relations(self) -> None:
        drones = [e for e in self.environment.elements.values() if isinstance(e, DroneElement)]
        for drone in drones:
            nearest = min((drone.state.pose.distance_to(other.state.pose) for other in drones if other is not drone), default=99.0)
            self.swarm.set("nearest_neighbor_distance", nearest)
            self.savoir.factor_graph.set("nearest_neighbor_distance", nearest)
            self.savoir.factor_graph.set(f"{drone.name}.nearest_neighbor_distance", nearest)
            self._add_factor_once(
                name=f"{drone.name}.swarm_separation",
                variables=(f"{drone.name}.nearest_neighbor_distance",),
                evaluator=lambda a, key=f"{drone.name}.nearest_neighbor_distance": max(0.0, 5.0 - float(a.get(key, 99.0))),
                weight=1.2,
                kind="separation",
            )
            self.environment.semantic_graph.connect(drone.element_id, self.swarm.context_id, "participates_in", sense=self.swarm.basis, precision=1.0, payload={"nearest_neighbor_distance": nearest})

    def update_telemetry(self, drone: DroneElement) -> None:
        battery = drone.state.battery_pct
        gps_hdop = 1.0 if drone.state.gps_lock else 4.0
        self.savoir.observe(f"{drone.name}.battery", battery, "telemetry", certainty=1.0, sense=SenseVector.temporal("battery measure", 0.8))
        self.savoir.factor_graph.set("battery", battery)
        self.savoir.observe(f"{drone.name}.gps_hdop", gps_hdop, "gps", certainty=0.95, sense=SenseVector.technical("gps quality", 0.8))
        self.savoir.factor_graph.set("gps_hdop", gps_hdop)
        self.savoir.observe(f"{drone.name}.airborne", drone.state.airborne, "controller", certainty=0.95, sense=SenseVector.causal("flight state", 0.7))
        self._add_factor_once(
            name=f"{drone.name}.battery_margin",
            variables=(f"{drone.name}.battery",),
            evaluator=lambda a, key=f"{drone.name}.battery": max(0.0, 20.0 - float(a.get(key, 100.0))) / 20.0,
            weight=1.0,
            kind="battery_margin",
        )
        self.flight.set("battery", battery)
        self.flight.set("gps_lock", drone.state.gps_lock)
        self.flight.set("airborne", drone.state.airborne)
        self.emergency.set("battery", battery)
        self._refresh_swarm_relations()


__all__ = ["PoseSE3", "DroneState", "DroneElement", "DroneSwarmSDK"]
