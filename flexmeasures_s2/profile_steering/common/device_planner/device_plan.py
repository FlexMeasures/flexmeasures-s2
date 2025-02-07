from typing import Optional, List
from datetime import datetime
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.frbc.s2_frbc_instruction_profile import S2FrbcInstructionProfile

class DevicePlan:
    def __init__(
        self,
        device_id: str,
        device_name: str,
        connection_id: str,
        energy_profile: JouleProfile,
        fill_level_profile: Optional[JouleProfile],
        instruction_profile: S2FrbcInstructionProfile,
    ):
        self.device_id = device_id
        self.device_name = device_name
        self.connection_id = connection_id
        self.energy_profile = energy_profile
        self.fill_level_profile = fill_level_profile
        self.instruction_profile = instruction_profile

    def get_device_id(self) -> str:
        return self.device_id

    def get_device_name(self) -> str:
        return self.device_name

    def get_connection_id(self) -> str:
        return self.connection_id

    def get_energy_profile(self) -> JouleProfile:
        return self.energy_profile

    def get_fill_level_profile(self) -> Optional[JouleProfile]:
        return self.fill_level_profile

    def get_instruction_profile(self) -> S2FrbcInstructionProfile:
        return self.instruction_profile


    def __str__(self) -> str:
        return (
            f"DevicePlan(device_id={self.device_id}, device_name={self.device_name}, "
            f"connection_id={self.connection_id}, energy_profile={self.energy_profile}, "
            f"fill_level_profile={self.fill_level_profile}, instruction_profile={self.instruction_profile}, "
            f"insights_profile={self.insights_profile})"
        ) 
