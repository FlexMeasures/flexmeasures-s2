from typing import List, Union, cast
from datetime import datetime, timedelta
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.abstract_profile import AbstractProfile
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata


class TargetProfile(AbstractProfile[Union["TargetProfile.Element", None], "TargetProfile"]):
    class Element:
        pass

    class JouleElement(Element):
        def __init__(self, joules: int):
            self.joules = joules

    class TariffElement(Element):
        def __init__(self, tariff: float):
            self.tariff = tariff

    class NullElement(Element):
        pass

    NULL_ELEMENT: "TargetProfile.Element" = NullElement()

    def __init__(
        self,
        profile_start: datetime,
        timestep_duration: timedelta,
        elements: Union[List[int], List[Union["TargetProfile.Element", None]]],
    ):
        metadata = ProfileMetadata(profile_start, timestep_duration, len(elements))
        # if elements is a list of ints, convert it to a list of JouleElement
        if isinstance(elements, list) and all(isinstance(e, int) for e in elements):
            new_elements = [TargetProfile.JouleElement(e) for e in cast(List[int], elements)]
            super().__init__(metadata, cast(List[Union["TargetProfile.Element", None]], new_elements))
        else:
            super().__init__(metadata, cast(List[Union["TargetProfile.Element", None]], elements))

    def validate(
        self,
        profile_metadata: ProfileMetadata,
        elements: List[Union["TargetProfile.Element", None]],
    ):
        super().validate(profile_metadata, elements)
        # Add any TargetProfile-specific validation if needed
        if not elements:
            return

        for i in range(len(elements) - 1):
            current_element = elements[i]
            next_element = elements[i + 1]

            if current_element is None:
                raise ValueError("An element cannot be null")

            if isinstance(current_element, TargetProfile.TariffElement) and isinstance(
                next_element, TargetProfile.JouleElement
            ):
                raise ValueError("A TariffElement can only be followed by another TariffElement or a NullElement")

            if isinstance(current_element, TargetProfile.NullElement) and not isinstance(
                next_element, TargetProfile.NullElement
            ):
                raise ValueError("A NullElement can only be followed by another NullElement")

    def default_value(self) -> "TargetProfile.Element":
        return TargetProfile.NULL_ELEMENT

    def subprofile(self, new_start_date: datetime) -> "TargetProfile":
        index = self.index_at(new_start_date)
        if index < 0:
            raise ValueError("New start date is outside profile range")
        new_elements = self.elements[index:]
        return TargetProfile(new_start_date, self.metadata.timestep_duration, new_elements)

    def adjust_nr_of_elements(self, nr_of_elements: int) -> "TargetProfile":
        if nr_of_elements < len(self.elements):
            new_elements = self.elements[:nr_of_elements]
        else:
            new_elements = self.elements + [self.NULL_ELEMENT] * (nr_of_elements - len(self.elements))
        return TargetProfile(
            self.metadata.profile_start,
            self.metadata.timestep_duration,
            new_elements,
        )

    def is_compatible(self, other: AbstractProfile) -> bool:
        return self.metadata.timestep_duration == other.metadata.timestep_duration and len(self.elements) == len(
            other.elements
        )

    def get_total_energy(self) -> int:
        return sum(e.joules for e in self.elements if isinstance(e, TargetProfile.JouleElement))

    def target_elements_to_joule_profile(self) -> JouleProfile:
        joules = [e.joules for e in self.elements if isinstance(e, TargetProfile.JouleElement)]
        return JouleProfile(
            self.metadata.profile_start,
            self.metadata.timestep_duration,
            joules,
        )

    def nr_of_joule_target_elements(self) -> int:
        return len([e for e in self.elements if isinstance(e, TargetProfile.JouleElement)])

    def subtract(self, other: JouleProfile) -> "TargetProfile":
        if not self.is_compatible(other):
            raise ValueError("Profiles are not compatible")
        diff_elements: List["TargetProfile.Element | None"] = []
        for i, element in enumerate(self.elements):
            if isinstance(element, TargetProfile.JouleElement) and other.get_energy_for_timestep(i) is not None:
                diff_elements.append(TargetProfile.JouleElement(element.joules - other.get_energy_for_timestep(i)))
            elif isinstance(element, TargetProfile.TariffElement):
                diff_elements.append(element)
            else:
                diff_elements.append(self.NULL_ELEMENT)
        return TargetProfile(
            self.metadata.profile_start,
            self.metadata.timestep_duration,
            diff_elements,
        )

    def add(self, other: JouleProfile) -> "TargetProfile":
        if not self.is_compatible(other):
            raise ValueError("Profiles are not compatible")
        sum_elements: List["TargetProfile.Element | None"] = []
        for i, element in enumerate(self.elements):
            if isinstance(element, TargetProfile.JouleElement):
                other_energy = other.get_energy_for_timestep(i)
                if other_energy is not None:
                    sum_elements.append(TargetProfile.JouleElement(element.joules + other_energy))
                else:
                    sum_elements.append(self.NULL_ELEMENT)
            else:
                sum_elements.append(self.NULL_ELEMENT)
        return TargetProfile(
            self.metadata.profile_start,
            self.metadata.timestep_duration,
            sum_elements,
        )

    def sum_quadratic_distance(self) -> float:
        return sum(e.joules**2 for e in self.elements if isinstance(e, TargetProfile.JouleElement))

    def __str__(self) -> str:
        return f"TargetProfile(elements={self.elements}, profile_start={self.metadata.profile_start}, timestep_duration={self.metadata.timestep_duration})"

    @property
    def get_elements(self) -> List[Union["TargetProfile.Element", None]]:
        return self.elements

    @staticmethod
    def null_profile(metadata: ProfileMetadata) -> "TargetProfile":
        return TargetProfile(
            metadata.profile_start,
            metadata.timestep_duration,
            [TargetProfile.NULL_ELEMENT] * metadata.nr_of_timesteps,  # type: ignore
        )

    @staticmethod
    def from_joule_profile(joule_profile: JouleProfile) -> "TargetProfile":
        return TargetProfile(
            joule_profile.metadata.profile_start,
            joule_profile.metadata.timestep_duration,
            [TargetProfile.JouleElement(e) for e in joule_profile.elements],  # type: ignore
        )
