from typing import List, Dict
from flexmeasures_s2.profile_steering.common.s2_actuator_configuration import (
    S2ActuatorConfiguration,
)
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile


class S2FrbcPlan:
    """Plan for an FRBC device.

    Represents a complete plan for an FRBC storage device, including:
    - Energy profile: Planned energy consumption/production over time
    - Fill level profile: Planned state of charge over time
    - Operation mode IDs: Actuator configurations for each timestep
    - Idle flag: Whether the device is in idle state

    Plans are created by the OperationModeProfileTree state tree search and
    converted to instruction profiles for device control. The fill level profile
    ensures that storage constraints (min/max fill levels) are respected.
    """

    def __init__(
        self,
        idle: bool,
        energy: JouleProfile,
        fill_level,
        operation_mode_id: List[Dict[str, S2ActuatorConfiguration]],
    ):
        self.idle = idle
        self.energy = energy
        self.fill_level = fill_level
        self.operation_mode_id = operation_mode_id

    def is_idle(self) -> bool:
        return self.idle

    def get_energy(self):
        return self.energy

    def get_operation_mode_id(self) -> List[Dict[str, S2ActuatorConfiguration]]:
        return self.operation_mode_id
