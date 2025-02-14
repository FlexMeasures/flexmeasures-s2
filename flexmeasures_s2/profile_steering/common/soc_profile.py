from typing import List, Optional
from flexmeasures_s2.profile_steering.common.abstract_profile import AbstractProfile
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata
from datetime import datetime


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

    def is_compatible(self, other: AbstractProfile) -> bool:
        return (
            self.metadata.get_timestep_duration()
            == other.get_profile_metadata().get_timestep_duration()
            and len(self.elements) == len(other.get_elements())
        )

    def validate(self, profile_metadata: ProfileMetadata, elements: List[float]):
        super().validate(profile_metadata, elements)

    def subprofile(self, new_start_date: datetime) -> "SoCProfile":
        index = self.index_at(new_start_date)
        if index < 0:
            raise ValueError("New start date is outside profile range")
        new_elements = self.elements[index:]
        return SoCProfile(
            new_start_date, self.metadata.get_timestep_duration(), new_elements
        )

    def adjust_nr_of_elements(self, nr_of_elements: int) -> "SoCProfile":
        if nr_of_elements < len(self.elements):
            new_elements = self.elements[:nr_of_elements]
        else:
            new_elements = self.elements + [0.0] * (nr_of_elements - len(self.elements))
        return SoCProfile(
            self.metadata.get_profile_start(),
            self.metadata.get_timestep_duration(),
            new_elements,
        )
