from typing import List, Dict, Optional, Any, TYPE_CHECKING
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile

if TYPE_CHECKING:
    from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_insights_profile import (
        S2DdbcInsightsProfile,
    )


class S2DdbcPlan:
    """Plan for a DDBC device."""

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
