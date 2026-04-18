from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple


@dataclass
class PoseSE3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0

    def translation(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def exp_update(self, xi: Tuple[float, float, float, float, float, float]) -> "PoseSE3":
        dx, dy, dz, droll, dpitch, dyaw = xi
        return PoseSE3(
            x=self.x + dx,
            y=self.y + dy,
            z=self.z + dz,
            roll=self.roll + droll,
            pitch=self.pitch + dpitch,
            yaw=self.yaw + dyaw,
        )

    def distance_to(self, other: "PoseSE3") -> float:
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2)
