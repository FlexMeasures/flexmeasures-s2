from typing import Optional, Union
from flexmeasures_s2.profile_steering.common.pydantic_base import FlexMeasuresBaseModel

from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.soc_profile import SoCProfile
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_instruction_profile import (
    S2FrbcInstructionProfile,
)
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_instruction_profile import (
    S2DdbcInstructionProfile,
)


class DevicePlan(FlexMeasuresBaseModel):
    """Represents a plan for a single device.

    A DevicePlan contains:
    - Device identification (device_id, device_name, connection_id)
    - Energy profile: The planned energy consumption/production over time
    - Fill level profile: For storage devices, the planned state of charge
    - Instruction profile: Device-specific instructions (FRBC or DDBC format)

    Device plans are created by device planners and aggregated into cluster plans.
    """

    device_id: str
    device_name: str
    connection_id: str
    energy_profile: JouleProfile
    fill_level_profile: Optional[SoCProfile] = None
    instruction_profile: Optional[
        Union[S2FrbcInstructionProfile, S2DdbcInstructionProfile]
    ] = None
