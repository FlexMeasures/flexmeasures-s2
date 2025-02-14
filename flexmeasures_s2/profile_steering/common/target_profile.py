from typing import List, Union
from datetime import datetime, timedelta
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.abstract_profile import AbstractProfile
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata


class TargetProfile(
    AbstractProfile[Union["TargetProfile.Element", None], "TargetProfile"]
):
    class Element:
        pass

    class JouleElement(Element):
        def __init__(self, joules: int):
            self.joules = joules

        def get_joules(self) -> int:
            return self.joules

    class NullElement(Element):
        pass

    NULL_ELEMENT: "TargetProfile.Element" = NullElement()

    def __init__(
        self,
        profile_start: datetime,
        timestep_duration: timedelta,
        elements: List["TargetProfile.Element | None"],
    ):
        metadata = ProfileMetadata(profile_start, timestep_duration, len(elements))
        super().__init__(metadata, elements)

    def validate(
        self,
        profile_metadata: ProfileMetadata,
        elements: List["TargetProfile.Element | None"],
    ):
        super().validate(profile_metadata, elements)
        # Add any TargetProfile-specific validation if needed

    def subprofile(self, new_start_date: datetime) -> "TargetProfile":
        index = self.index_at(new_start_date)
        if index < 0:
            raise ValueError("New start date is outside profile range")
        new_elements = self.elements[index:]
        return TargetProfile(
            new_start_date, self.metadata.get_timestep_duration(), new_elements
        )

    def adjust_nr_of_elements(self, nr_of_elements: int) -> "TargetProfile":
        if nr_of_elements < len(self.elements):
            new_elements = self.elements[:nr_of_elements]
        else:
            new_elements = self.elements + [self.NULL_ELEMENT] * (
                nr_of_elements - len(self.elements)
            )
        return TargetProfile(
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

    def get_total_energy(self) -> int:
        return sum(
            e.get_joules()
            for e in self.elements
            if isinstance(e, TargetProfile.JouleElement)
        )

    def target_elements_to_joule_profile(self) -> JouleProfile:
        joules = [
            e.get_joules()
            for e in self.elements
            if isinstance(e, TargetProfile.JouleElement)
        ]
        return JouleProfile(
            self.metadata.get_profile_start(),
            self.metadata.get_timestep_duration(),
            joules,
        )

    def nr_of_joule_target_elements(self) -> int:
        return len(
            [e for e in self.elements if isinstance(e, TargetProfile.JouleElement)]
        )

    def subtract(self, other: JouleProfile) -> "TargetProfile":
        if not self.is_compatible(other):
            raise ValueError("Profiles are not compatible")
        diff_elements: List["TargetProfile.Element | None"] = []
        for i, element in enumerate(self.elements):
            if isinstance(element, TargetProfile.JouleElement):
                other_energy = other.get_energy_for_timestep(i)
                if other_energy is not None:
                    diff_elements.append(
                        TargetProfile.JouleElement(element.get_joules() - other_energy)
                    )
                else:
                    diff_elements.append(self.NULL_ELEMENT)
            else:
                diff_elements.append(self.NULL_ELEMENT)
        return TargetProfile(
            self.metadata.get_profile_start(),
            self.metadata.get_timestep_duration(),
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
                    sum_elements.append(
                        TargetProfile.JouleElement(element.get_joules() + other_energy)
                    )
                else:
                    sum_elements.append(self.NULL_ELEMENT)
            else:
                sum_elements.append(self.NULL_ELEMENT)
        return TargetProfile(
            self.metadata.get_profile_start(),
            self.metadata.get_timestep_duration(),
            sum_elements,
        )

    def sum_quadratic_distance(self) -> float:
        return sum(
            e.get_joules() ** 2
            for e in self.elements
            if isinstance(e, TargetProfile.JouleElement)
        )

    def __str__(self) -> str:
        return f"TargetProfile(elements={self.elements}, profile_start={self.metadata.get_profile_start()}, timestep_duration={self.metadata.get_timestep_duration()})"

    def get_profile_metadata(self) -> ProfileMetadata:
        return self.metadata

    def get_elements(self) -> List["TargetProfile.Element | None"]:
        return self.elements

    @staticmethod
    def null_profile(metadata: ProfileMetadata) -> "TargetProfile":
        return TargetProfile(
            metadata.get_profile_start(),
            metadata.get_timestep_duration(),
            [TargetProfile.NULL_ELEMENT] * metadata.get_nr_of_timesteps(),
        )
