from datetime import datetime, timedelta
from typing import List, Optional
from flexmeasures_s2.profile_steering.common.abstract_profile import AbstractProfile
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata


class JouleProfile(AbstractProfile[int, "JouleProfile"]):
    def __init__(
        self,
        profile_start: datetime,
        timestep_duration: timedelta,
        elements: Optional[List[int]] = None,
    ):
        metadata = ProfileMetadata(
            profile_start,
            timestep_duration,
            nr_of_timesteps=len(elements) if elements else 0,
        )
        super().__init__(metadata, elements if elements is not None else [])

    def validate(self, profile_metadata: ProfileMetadata, elements: List[int]):
        super().validate(profile_metadata, elements)
        # Add any JouleProfile-specific validation here if needed

    def subprofile(self, new_start_date: datetime) -> "JouleProfile":
        index = self.index_at(new_start_date)
        if index < 0:
            raise ValueError("New start date is outside profile range")
        new_elements = self.elements[index:]
        return JouleProfile(
            new_start_date, self.metadata.get_timestep_duration(), new_elements
        )

    def adjust_nr_of_elements(self, nr_of_elements: int) -> "JouleProfile":
        if nr_of_elements < len(self.elements):
            new_elements = self.elements[:nr_of_elements]
        else:
            new_elements = self.elements + [0] * (nr_of_elements - len(self.elements))
        return JouleProfile(
            self.metadata.get_profile_start(),
            self.metadata.get_timestep_duration(),
            new_elements,
        )

    def is_compatible(self, other: AbstractProfile) -> bool:
        return (
            self.metadata.get_timestep_duration()
            == other.get_profile_metadata().get_timestep_duration()
            and len(self.elements) == len(other.get_elements())
        )

    def avg_power_at(self, date: datetime) -> Optional[float]:
        element = self.element_at(date)
        return element / self.metadata.get_timestep_duration().total_seconds()

    def add(self, other: "JouleProfile") -> "JouleProfile":
        if not self.is_compatible(other):
            raise ValueError("Profiles are not compatible")
        summed_elements = [a + b for a, b in zip(self.elements, other.elements)]
        return JouleProfile(
            self.metadata.get_profile_start(),
            self.metadata.get_timestep_duration(),
            summed_elements,
        )

    def subtract(self, other: "JouleProfile") -> "JouleProfile":
        if not self.is_compatible(other):
            raise ValueError("Profiles are not compatible")
        diff_elements = [a - b for a, b in zip(self.elements, other.elements)]
        return JouleProfile(
            self.metadata.get_profile_start(),
            self.metadata.get_timestep_duration(),
            diff_elements,
        )

    def absolute_values(self) -> "JouleProfile":
        abs_elements = [abs(e) for e in self.elements]
        return JouleProfile(
            self.metadata.get_profile_start(),
            self.metadata.get_timestep_duration(),
            abs_elements,
        )

    def sum_quadratic_distance(self) -> float:
        return sum(e ** 2 for e in self.elements if e is not None)

    def is_below_or_equal(self, other: "JouleProfile") -> bool:
        if not self.is_compatible(other):
            raise ValueError("Profiles are not compatible")
        return all(
            a <= b for a, b in zip(self.elements, other.elements) if b is not None
        )

    def is_above_or_equal(self, other: "JouleProfile") -> bool:
        if not self.is_compatible(other):
            raise ValueError("Profiles are not compatible")
        return all(
            a >= b for a, b in zip(self.elements, other.elements) if b is not None
        )

    def minimum(self, other: "JouleProfile") -> "JouleProfile":
        if not self.is_compatible(other):
            raise ValueError("Profiles are not compatible")
        min_elements = [min(a, b) for a, b in zip(self.elements, other.elements)]
        return JouleProfile(
            self.metadata.get_profile_start(),
            self.metadata.get_timestep_duration(),
            min_elements,
        )

    def maximum(self, other: "JouleProfile") -> "JouleProfile":
        if not self.is_compatible(other):
            raise ValueError("Profiles are not compatible")
        max_elements = [max(a, b) for a, b in zip(self.elements, other.elements)]
        return JouleProfile(
            self.metadata.get_profile_start(),
            self.metadata.get_timestep_duration(),
            max_elements,
        )

    def get_total_energy(self) -> int:
        return sum(self.elements)

    def get_total_energy_production(self) -> int:
        return sum(min(0, e) for e in self.elements)

    def get_total_energy_consumption(self) -> int:
        return sum(max(0, e) for e in self.elements)

    def get_energy_for_timestep(self, index: int) -> Optional[int]:
        if 0 <= index < len(self.elements):
            return self.elements[index]
        return None

    def __str__(self) -> str:
        return f"JouleProfile(elements={self.elements}, profile_start={self.metadata.get_profile_start()}, timestep_duration={self.metadata.get_timestep_duration()})"
