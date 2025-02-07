from typing import Dict, List
from datetime import datetime, Duration
from s2_frbc_actuator_configuration import S2ActuatorConfiguration


class S2FrbcInstructionProfile:
    class Element:
        def __init__(
            self, idle: bool, actuator_configuration: Dict[str, S2ActuatorConfiguration]
        ):
            self.idle = idle
            self.actuator_configuration = actuator_configuration

        def is_idle(self) -> bool:
            return self.idle

        def get_actuator_configuration(self) -> Dict[str, S2ActuatorConfiguration]:
            return self.actuator_configuration

    def __init__(
        self,
        profile_start: datetime,
        timestep_duration: Duration,
        elements: List[Element],
    ):
        self.profile_start = profile_start
        self.timestep_duration = timestep_duration
        self.elements = elements

    def default_value(self) -> "S2FrbcInstructionProfile.Element":
        return S2FrbcInstructionProfile.Element(True, {})

    def __str__(self) -> str:
        return f"S2FrbcInstructionProfile(elements={self.elements})"
