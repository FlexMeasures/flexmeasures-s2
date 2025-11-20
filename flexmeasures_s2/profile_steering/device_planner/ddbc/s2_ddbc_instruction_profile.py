from typing import List, Dict, Any
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata


class S2DdbcInstructionProfile:
    """Instruction profile for DDBC device control.

    Contains instructions that tell the device which operation modes to use
    at each timestep. Instructions are derived from the optimized plan and
    specify actuator configurations.

    Attributes:
        profile_metadata: Metadata describing the profile timing
        elements: List of instruction elements, one per timestep
    """

    class Element:
        """Single instruction element for one timestep.

        Contains actuator configurations specifying which operation modes
        to use for each actuator at this timestep.

        Attributes:
            is_empty: Whether this element represents an empty/idle state
            actuator_configurations: Dictionary mapping actuator IDs to
                their operation mode configurations
        """

        def __init__(self, is_empty: bool, actuator_configurations: Dict[str, Any]):
            self.is_empty = is_empty
            self.actuator_configurations = actuator_configurations

        def is_element_empty(self) -> bool:
            return self.is_empty

        def get_actuator_configurations(self) -> Dict[str, Any]:
            return self.actuator_configurations

    def __init__(self, profile_metadata: ProfileMetadata, elements: List[Element]):
        self.profile_metadata = profile_metadata
        self.elements = elements

    def get_profile_metadata(self) -> ProfileMetadata:
        return self.profile_metadata

    def get_elements(self) -> List[Element]:
        return self.elements
