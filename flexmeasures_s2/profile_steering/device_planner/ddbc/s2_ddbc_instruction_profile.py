from typing import List, Dict, Any
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata


class S2DdbcInstructionProfile:
    """Instruction profile for DDBC device."""

    class Element:
        """Single instruction element."""

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
