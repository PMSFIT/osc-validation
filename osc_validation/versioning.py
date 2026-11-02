"""Explicit OpenSCENARIO XML contracts shared by generators and test runners."""

from dataclasses import dataclass
from enum import Enum


class OscVersion(str, Enum):
    V1_3_0 = "1.3.0"
    V1_3_1 = "1.3.1"
    V1_4_0 = "1.4.0"

    # Keep the existing enum names as aliases for API callers.
    V1_3 = V1_3_0
    V1_4 = V1_4_0

    def __str__(self) -> str:
        return self.value

    @property
    def major(self) -> int:
        return int(self.value.split(".")[0])

    @property
    def minor(self) -> int:
        return int(self.value.split(".")[1])

    @property
    def patch(self) -> int:
        return int(self.value.split(".")[2])


@dataclass(frozen=True)
class ScenarioContract:
    osc_version: OscVersion

    def __post_init__(self) -> None:
        object.__setattr__(self, "osc_version", OscVersion(self.osc_version))
