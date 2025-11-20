from typing import List, Dict, Optional, Any, TYPE_CHECKING
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile

if TYPE_CHECKING:
    from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_insights_profile import (
        S2DdbcInsightsProfile,
    )


class S2DdbcPlan:
    """Plan for a DDBC device.

    Represents a complete plan for a DDBC device, including:
    - Energy profile: Planned energy consumption/production over time
    - Operation mode IDs: Actuator configurations for each timestep
    - Insights profile: Additional information about demand and supply rates
    - Idle flag: Whether the device is in idle state

    Plans are created by the DdbcPlanningWindow state tree search and
    converted to instruction profiles for device control.
    """

    def __init__(
        self,
        idle: bool,
        energy: JouleProfile,
        operation_mode_id: Optional[List[Dict[str, Any]]],
        s2_ddbc_insights_profile: Optional["S2DdbcInsightsProfile"],
    ):
        self.idle = idle
        self.energy = energy
        self.operation_mode_id = operation_mode_id
        self.s2_ddbc_insights_profile = s2_ddbc_insights_profile

    def is_idle(self) -> bool:
        return self.idle

    def get_energy(self) -> JouleProfile:
        return self.energy

    def get_operation_mode_id(self) -> Optional[List[Dict[str, Any]]]:
        return self.operation_mode_id

    def get_s2_ddbc_insights_profile(self) -> Optional["S2DdbcInsightsProfile"]:
        return self.s2_ddbc_insights_profile
