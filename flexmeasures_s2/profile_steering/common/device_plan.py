from typing import Optional
from flexmeasures_s2.profile_steering.common.pydantic_base import FlexMeasuresBaseModel

from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.soc_profile import SoCProfile
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_instruction_profile import (
    S2FrbcInstructionProfile,
)


class DevicePlan(FlexMeasuresBaseModel):

    device_id: str
    device_name: str
    connection_id: str
    energy_profile: JouleProfile
    fill_level_profile: Optional[SoCProfile] = None
    instruction_profile: Optional[S2FrbcInstructionProfile] = None
