from typing import List, Dict
from s2_frbc_actuator_configuration import S2FrbcActuatorConfiguration
from common.joule_profile import JouleProfile
from common.soc_profile import SoCProfile
    
class S2FrbcPlan:
    def __init__(
        self,
        idle: bool,
        energy,
        fill_level,
        operation_mode_id: List[Dict[str, S2FrbcActuatorConfiguration]],
        s2_frbc_insights_profile,
    ):
        self.idle = idle
        self.energy = energy
        self.fill_level = fill_level
        self.operation_mode_id = operation_mode_id

    def is_idle(self) -> bool:
        return self.idle

    def get_energy(self) -> JouleProfile:
        return self.energy

    def get_fill_level(self) -> SoCProfile:
        return self.fill_level

    def get_operation_mode_id(self) -> List[Dict[str, S2FrbcActuatorConfiguration]]:
        return self.operation_mode_id

