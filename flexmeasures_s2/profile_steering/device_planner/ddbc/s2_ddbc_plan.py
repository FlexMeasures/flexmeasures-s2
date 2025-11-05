from typing import List, Dict, Optional, Any
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile


class S2DdbcActuatorConfiguration:
    """Configuration for a DDBC actuator at a specific timestep."""

    def __init__(self, operation_mode_id: str, factor: float):
        self.operation_mode_id = operation_mode_id
        self.factor = factor


class S2DdbcPlan:
    """
    Plan for a DDBC device.
    Contains energy profile and actuator configurations per timestep.
    """

    def __init__(
        self,
        idle: bool,
        energy: JouleProfile,
        operation_mode_id: Optional[List[Dict[str, S2DdbcActuatorConfiguration]]],
        insights_profile: Optional[Any] = None,
    ):
        self.idle = idle
        self.energy = energy
        self.operation_mode_id = operation_mode_id
        self.insights_profile = insights_profile

    def is_idle(self) -> bool:
        return self.idle

    def get_energy(self) -> JouleProfile:
        return self.energy

    def get_operation_mode_id(
        self,
    ) -> Optional[List[Dict[str, S2DdbcActuatorConfiguration]]]:
        return self.operation_mode_id

    def get_s2_ddbc_insights_profile(self) -> Optional[Any]:
        return self.insights_profile
