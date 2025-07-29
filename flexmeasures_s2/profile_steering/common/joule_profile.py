from datetime import datetime, timedelta
from typing import List, Optional
from flexmeasures_s2.profile_steering.common.abstract_profile import AbstractProfile
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata


class JouleProfile(AbstractProfile[int, "JouleProfile"]):
    def __init__(
        self,
        profile_start: Optional[datetime] = None,
        timestep_duration: Optional[timedelta] = None,
        elements: Optional[List[int]] = None,
        metadata: Optional[ProfileMetadata] = None,
        value: Optional[int] = None,
        profile_length: Optional[int] = None,
        other_profile: Optional["JouleProfile"] = None,
    ):
        """
        Initialize a JouleProfile with various parameter combinations.

        Args:
            profile_start: Start time of the profile
            timestep_duration: Duration of each timestep
            elements: List of energy values
            metadata: ProfileMetadata object containing start time and duration
            value: Single value to fill the entire profile
            profile_length: Length of the profile when using a single value
            other_profile: Another JouleProfile to copy from
        """
        # Case 1: Copy from another profile
        if other_profile is not None:
            super().__init__(
                profile_metadata=other_profile.metadata,
                elements=other_profile.elements,
            )
            return

        # Case 2: Initialize from metadata
        if metadata is not None:
            if elements is not None:
                super().__init__(profile_metadata=metadata, elements=elements)
            elif value is not None:
                elements = [value] * metadata.nr_of_timesteps
                super().__init__(profile_metadata=metadata, elements=elements)
            else:
                super().__init__(profile_metadata=metadata, elements=[])
            return

        # Case 3: Initialize with single value and profile length
        if value is not None and profile_length is not None:
            elements = [value] * profile_length
            super().__init__(
                profile_start=profile_start,
                timestep_duration=timestep_duration,
                elements=elements,
            )
            return

        # Case 4: Basic initialization
        if profile_start is not None and timestep_duration is not None:
            super().__init__(
                profile_start=profile_start,
                timestep_duration=timestep_duration,
                elements=elements if elements is not None else [],
            )
            return

        # Case 5: Empty initialization (for serialization)
        super().__init__()

    def validate(self, profile_metadata: ProfileMetadata, elements: List[int]):
        super().validate(profile_metadata, elements)
        # Add any JouleProfile-specific validation here if needed

    def default_value(self) -> None:
        return None

    def subprofile(self, new_start_date: datetime) -> "JouleProfile":
        index = self.index_at(new_start_date)
        if index < 0:
            raise ValueError("New start date is outside profile range")
        new_elements = self.elements[index:]
        return JouleProfile(
            new_start_date,
            self.metadata.timestep_duration,
            new_elements,
        )

    def adjust_nr_of_elements(self, nr_of_elements: int) -> "JouleProfile":
        if nr_of_elements < len(self.elements):
            new_elements = self.elements[:nr_of_elements]
        else:
            new_elements = self.elements + [0] * (nr_of_elements - len(self.elements))
        return JouleProfile(
            self.metadata.profile_start,
            self.metadata.timestep_duration,
            new_elements,
        )

    def is_compatible(self, other: AbstractProfile) -> bool:
        return self.metadata == other.metadata

    def avg_power_at(self, date: datetime) -> Optional[float]:
        element = self.element_at(date)
        return element / self.metadata.timestep_duration.total_seconds()

    def add(self, other: "JouleProfile") -> "JouleProfile":
        if not self.is_compatible(other):
            raise ValueError("Profiles are not compatible")
        summed_elements = [0] * len(self.elements)
        for i in range(len(self.elements)):
            if self.elements[i] is None or other.elements[i] is None:
                summed_elements[i] = self.default_value()
            else:
                summed_elements[i] = self.elements[i] + other.elements[i]
        return JouleProfile(
            self.metadata.profile_start,
            self.metadata.timestep_duration,
            summed_elements,
        )

    def subtract(self, other: "JouleProfile") -> "JouleProfile":
        if not self.is_compatible(other):
            raise ValueError("Profiles are not compatible")
        diff_elements = [0] * len(self.elements)
        for i in range(len(self.elements)):
            if self.elements[i] is None or other.elements[i] is None:
                diff_elements[i] = self.default_value()
            else:
                diff_elements[i] = self.elements[i] - other.elements[i]
        return JouleProfile(
            self.metadata.profile_start,
            self.metadata.timestep_duration,
            diff_elements,
        )

    def absolute_values(self) -> "JouleProfile":
        abs_elements = [abs(e) for e in self.elements]
        return JouleProfile(
            self.metadata.profile_start,
            self.metadata.timestep_duration,
            abs_elements,
        )

    def sum_quadratic_distance(self) -> float:
        return sum(e**2 for e in self.elements if e is not None)

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
        # skip None values
        min_elements = [
            min(a, b)
            for a, b in zip(self.elements, other.elements)
            if a is not None and b is not None
        ]
        return JouleProfile(
            self.metadata.profile_start,
            self.metadata.timestep_duration,
            min_elements,
        )

    def maximum(self, other: "JouleProfile") -> "JouleProfile":
        if not self.is_compatible(other):
            raise ValueError("Profiles are not compatible")
        # skip None values
        max_elements = [
            max(a, b)
            for a, b in zip(self.elements, other.elements)
            if a is not None and b is not None
        ]
        return JouleProfile(
            self.metadata.profile_start,
            self.metadata.timestep_duration,
            max_elements,
        )

    @property
    def get_total_energy(self) -> int:
        return sum(self.elements)

    @property
    def get_total_energy_production(self) -> int:
        return sum(min(0, e) for e in self.elements)

    @property
    def get_total_energy_consumption(self) -> int:
        return sum(max(0, e) for e in self.elements)

    def get_energy_for_timestep(self, index: int) -> Optional[int]:
        if 0 <= index < len(self.elements):
            return self.elements[index]
        return None

    def __str__(self) -> str:
        return f"JouleProfile(elements={self.elements}, profile_start={self.metadata.profile_start}, timestep_duration={self.metadata.timestep_duration})"
