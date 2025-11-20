from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import ClassVar, List, Optional, Union

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
    NULL: ClassVar[Optional["Element"]] = None  # Will be set after class definition

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
                if timestep_duration is None:
                    raise ValueError(
                        "Timestep duration is required when elements are provided"
                    )
                metadata = ProfileMetadata(
                    profile_start, timestep_duration, len(elements)
                )
            elif nr_of_timesteps is not None:
                if timestep_duration is None:
                    raise ValueError(
                        "Timestep duration is required when nr_of_timesteps is provided"
                    )
                metadata = ProfileMetadata(
                    profile_start, timestep_duration, nr_of_timesteps
                )
                elements = self._create_element_array(
                    nr_of_timesteps, min_value, max_value
                )
            else:
                if timestep_duration is None:
                    raise ValueError(
                        "Timestep duration is required when no elements or nr_of_timesteps are provided"
                    )
                metadata = ProfileMetadata(profile_start, timestep_duration, 0)
                elements = []

        super().__init__(metadata, elements)

    @staticmethod
    def _create_element_array(
        nr_of_elements: int, min_value: Optional[int], max_value: Optional[int]
    ) -> List[Element]:
        """Create an array of elements with the given min and max values."""
        return [Element(min_value, max_value) for _ in range(nr_of_elements)]

    def default_value(self) -> Element:
        return Element(None, None)

    def validate(self, profile_metadata: ProfileMetadata, elements: List[Element]):
        """Validate the elements and metadata for this profile."""
        super().validate(profile_metadata, elements)
        # Add any JouleRangeProfile-specific validation here if needed

    def is_within_range(self, other: JouleProfile) -> bool:
        """
        Check if the given JouleProfile is within the range defined by this profile.

        Args:
            other: JouleProfile to check

        Returns:
            True if other is within the range, False otherwise
        """
        if not self.is_compatible(other):
            raise ValueError("Profiles are not compatible")

        for i in range(self.metadata.nr_of_timesteps):
            element = self.elements[i]
            other_value = other.get_energy_for_timestep(i)

            if (
                element.min_joule is not None
                and other_value is not None
                and other_value < element.min_joule
            ):
                return False

            if (
                element.max_joule is not None
                and other_value is not None
                and other_value > element.max_joule
            ):
                return False

        return True

    def difference_with_max_value(self, other: JouleProfile) -> JouleProfile:
        """
        Calculate the difference between this profile's max values and the other profile.

        Args:
            other: JouleProfile to compare against

        Returns:
            JouleProfile containing the differences
        """
        if not self.is_compatible(other):
            raise ValueError("Profiles are not compatible")

        return_values: List[Optional[int]] = []

        for i in range(self.metadata.nr_of_timesteps):
            other_energy = other.get_energy_for_timestep(i)
            element_max_joule = self.elements[i].max_joule
            if element_max_joule is None or other_energy is None:
                return_values.append(None)
            else:
                return_values.append(element_max_joule - other_energy)

        return JouleProfile(metadata=self.metadata, elements=return_values)

    def difference_with_min_value(self, other: JouleProfile) -> JouleProfile:
        """
        Calculate the difference between this profile's min values and the other profile.

        Args:
            other: JouleProfile to compare against

        Returns:
            JouleProfile containing the differences
        """
        if not self.is_compatible(other):
            raise ValueError("Profiles are not compatible")

        return_values: List[Optional[int]] = []

        for i in range(self.metadata.nr_of_timesteps):
            element_min_joule = self.elements[i].min_joule
            other_energy = other.get_energy_for_timestep(i)
            if element_min_joule is None or other_energy is None:
                return_values.append(None)
            else:
                return_values.append(element_min_joule - other_energy)

        return JouleProfile(metadata=self.metadata, elements=return_values)

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
        return JouleRangeProfile(
            new_start_date, self.metadata.timestep_duration, new_elements
        )

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
            # Ignore type error because Element.NULL is not None
            new_elements = self.elements + [Element.NULL] * (  # type: ignore[list-item]
                nr_of_elements - len(self.elements)
            )

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
        return self.metadata == other.metadata

    def __str__(self) -> str:
        """Return a string representation of this profile."""
        return (
            f"JouleRangeProfile(elements={self.elements}, "
            f"profile_start={self.metadata.profile_start}, "
            f"timestep_duration={self.metadata.timestep_duration})"
        )
