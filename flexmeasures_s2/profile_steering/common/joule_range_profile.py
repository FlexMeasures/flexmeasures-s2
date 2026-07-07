from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, TypeVar, Union, Tuple

from flexmeasures_s2.profile_steering.common.abstract_profile import AbstractProfile
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile


@dataclass
class Element:
    """
    Represents an element in a JouleRangeProfile with min and max joule values.
    Both values can be None, representing unbounded values.
    """

    min_joule: Optional[int] = None
    max_joule: Optional[int] = None

    # Class constant for NULL element
    NULL = None  # Will be set after class definition

    def __eq__(self, other):
        if not isinstance(other, Element):
            return False
        return self.min_joule == other.min_joule and self.max_joule == other.max_joule

    def __str__(self):
        return f"Element(min_joule={self.min_joule}, max_joule={self.max_joule})"


# Set the NULL element after class definition
Element.NULL = Element(None, None)


class JouleRangeProfile(AbstractProfile[Element, "JouleRangeProfile"]):
    """
    A profile containing elements with minimum and maximum joule values.
    This is the Python implementation of the Java JouleRangeProfile class.
    """

    def __init__(
        self,
        profile_start: Union[datetime, ProfileMetadata],
        timestep_duration: Optional[timedelta] = None,
        elements: Optional[List[Element]] = None,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        nr_of_timesteps: Optional[int] = None,
    ):
        """
        Initialize a JouleRangeProfile with various constructor options.

        Args:
            profile_start: Either a datetime representing profile start or a ProfileMetadata
            timestep_duration: Duration of each timestep (if profile_start is datetime)
            elements: List of Element objects with min/max joule values
            min_value: Optional default min value for all elements
            max_value: Optional default max value for all elements
            nr_of_timesteps: Number of timesteps for the profile
        """
        if isinstance(profile_start, ProfileMetadata):
            metadata = profile_start
            if nr_of_timesteps is None:
                nr_of_timesteps = metadata.nr_of_timesteps

            elements = self._create_element_array(nr_of_timesteps, min_value, max_value)

        else:
            if elements is not None:
                metadata = ProfileMetadata(profile_start, timestep_duration or timedelta(), len(elements))
            elif nr_of_timesteps is not None:
                metadata = ProfileMetadata(profile_start, timestep_duration or timedelta(), nr_of_timesteps)
                elements = self._create_element_array(nr_of_timesteps, min_value, max_value)
            else:
                metadata = ProfileMetadata(profile_start, timestep_duration or timedelta(), 0)
                elements = []

        super().__init__(metadata, elements)

    def _create_element_array(
        self, nr_of_timesteps: int, min_value: Optional[int], max_value: Optional[int]
    ) -> List[Element]:
        if min_value is None and max_value is None:
            return [Element(None, None)] * nr_of_timesteps
        return [Element(min_value, max_value)] * nr_of_timesteps

    def validate(self, profile_metadata: ProfileMetadata, elements: List[Element]):
        """Validate the elements and metadata for this profile."""
        super().validate(profile_metadata, elements)
        # Add any JouleRangeProfile-specific validation here if needed

    def default_value(self) -> Element:
        return Element(None, None)

    def subprofile(self, new_start_date: datetime) -> "JouleRangeProfile":
        """
        Create a subprofile starting from the given date.

        Args:
            new_start_date: Start date for the new profile

        Returns:
            New JouleRangeProfile starting from the given date
        """
        index = self.index_at(new_start_date)
        if index < 0:
            raise ValueError("New start date is outside profile range")
        new_elements = self.elements[index:]
        return JouleRangeProfile(new_start_date, self.metadata.timestep_duration, new_elements)

    def adjust_nr_of_elements(self, nr_of_elements: int) -> "JouleRangeProfile":
        """
        Adjust the number of elements in this profile.

        Args:
            nr_of_elements: New number of elements

        Returns:
            New JouleRangeProfile with adjusted number of elements
        """
        if nr_of_elements < len(self.elements):
            new_elements = self.elements[:nr_of_elements]
        else:
            new_elements = self.elements + [Element(None, None)] * (nr_of_elements - len(self.elements))
        return JouleRangeProfile(
            self.metadata.profile_start,
            self.metadata.timestep_duration,
            new_elements,
        )

    def is_compatible(self, other: AbstractProfile) -> bool:
        """
        Check if this profile is compatible with another profile.

        Args:
            other: Another profile to check compatibility with

        Returns:
            True if compatible, False otherwise

        """
        return self.metadata.timestep_duration == other.metadata.timestep_duration and len(self.elements) == len(
            other.elements
        )

    def get_energy_for_timestep(self, index: int) -> Optional[int]:
        if 0 <= index < len(self.elements):
            return self.elements[index].max_joule
        return None

    def get_min_energy_for_timestep(self, index: int) -> Optional[int]:
        if 0 <= index < len(self.elements):
            return self.elements[index].min_joule
        return None

    def get_max_energy_for_timestep(self, index: int) -> Optional[int]:
        if 0 <= index < len(self.elements):
            return self.elements[index].max_joule
        return None

    def add(self, other: "JouleRangeProfile") -> "JouleRangeProfile":
        if not self.is_compatible(other):
            raise ValueError("Profiles are not compatible")
        summed_elements = [Element(None, None)] * len(self.elements)
        for i in range(len(self.elements)):
            if self.elements[i].min_joule is None or other.elements[i].min_joule is None:
                summed_elements[i] = Element(None, None)
            else:
                summed_elements[i] = Element(
                    self.elements[i].min_joule + other.elements[i].min_joule,
                    self.elements[i].max_joule + other.elements[i].max_joule,
                )
        return JouleRangeProfile(
            self.metadata.profile_start,
            self.metadata.timestep_duration,
            summed_elements,
        )

    def subtract(self, other: "JouleRangeProfile") -> "JouleRangeProfile":
        if not self.is_compatible(other):
            raise ValueError("Profiles are not compatible")
        diff_elements = [Element(None, None)] * len(self.elements)
        for i in range(len(self.elements)):
            if self.elements[i].min_joule is None or other.elements[i].min_joule is None:
                diff_elements[i] = Element(None, None)
            else:
                diff_elements[i] = Element(
                    self.elements[i].min_joule - other.elements[i].max_joule,
                    self.elements[i].max_joule - other.elements[i].min_joule,
                )
        return JouleRangeProfile(
            self.metadata.profile_start,
            self.metadata.timestep_duration,
            diff_elements,
        )

    def __str__(self) -> str:
        """Return a string representation of this profile."""
        return (
            f"JouleRangeProfile(elements={self.elements}, "
            f"profile_start={self.metadata.profile_start}, "
            f"timestep_duration={self.metadata.timestep_duration})"
        )
