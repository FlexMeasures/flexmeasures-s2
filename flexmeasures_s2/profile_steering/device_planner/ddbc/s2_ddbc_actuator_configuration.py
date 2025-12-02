from dataclasses import dataclass
from typing import Optional
from flexmeasures_s2.profile_steering.common.s2_actuator_configuration import (
    S2ActuatorConfiguration,
)


@dataclass
class S2DdbcActuatorConfiguration(S2ActuatorConfiguration):
    supply_rate: Optional[float]
    power_per_commodity_quantity: dict[str, float]
