from pydantic import BaseModel
from pydantic.config import ConfigDict

from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.soc_profile import SoCProfile
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_instruction_profile import (
    S2FrbcInstructionProfile,
)


class DevicePlan(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    device_id: str
    device_name: str
    connection_id: str
    energy_profile: JouleProfile
    fill_level_profile: SoCProfile
    instruction_profile: S2FrbcInstructionProfile
