from typing import List, Optional


class SoCProfile:
    def __init__(
        self, profile_start, timestep_duration, elements: Optional[List[float]] = None
    ):
        self.profile_start = profile_start
        self.timestep_duration = timestep_duration
        self.elements = elements if elements is not None else []

    def default_value(self) -> Optional[float]:
        return None

    def __str__(self) -> str:
        return f"SoCProfile(elements={self.elements}, profile_start={self.profile_start}, timestep_duration={self.timestep_duration})"
