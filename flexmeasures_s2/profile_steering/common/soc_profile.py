from typing import List, Optional
from flexmeasures_s2.profile_steering.common.abstract_profile import AbstractProfile


class SoCProfile(AbstractProfile[float, "SoCProfile"]):
    def __init__(
        self, profile_start, timestep_duration, elements: Optional[List[float]] = None
    ):
        self.profile_start = profile_start
        self.timestep_duration = timestep_duration
        super().__init__(profile_start, elements if elements is not None else [])

    def default_value(self) -> Optional[float]:
        return None

    def __str__(self) -> str:
        return f"SoCProfile(elements={self.elements}, profile_start={self.profile_start}, timestep_duration={self.timestep_duration})"
