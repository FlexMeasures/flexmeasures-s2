from typing import List, Dict


class S2FrbcPlan:
    def __init__(
        self,
        idle: bool,
        energy,
        fill_level,
        operation_mode_id: List[Dict[str, "S2ActuatorConfiguration"]],
        s2_frbc_insights_profile,
    ):
        self.idle = idle
        self.energy = energy
        self.fill_level = fill_level
        self.operation_mode_id = operation_mode_id

    def is_idle(self) -> bool:
        return self.idle

    def get_energy(self):
        return self.energy

    def get_fill_level(self):
        return self.fill_level

    def get_operation_mode_id(self) -> List[Dict[str, "S2ActuatorConfiguration"]]:
        return self.operation_mode_id

    def get_s2_frbc_insights_profile(self):
        return self.s2_frbc_insights_profile
