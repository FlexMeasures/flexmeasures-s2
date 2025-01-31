from typing import List, Union
from common.joule_profile import JouleProfile


class TargetProfile:
    class Element:
        pass

    class JouleElement(Element):
        def __init__(self, joules: int):
            self.joules = joules

        def get_joules(self) -> int:
            return self.joules

    class NullElement(Element):
        pass

    NULL_ELEMENT = NullElement()

    def __init__(self, profile_start, timestep_duration, elements: List[Element]):
        self.profile_start = profile_start
        self.timestep_duration = timestep_duration
        self.elements = elements

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
        return JouleProfile(self.profile_start, self.timestep_duration, joules)

    def nr_of_joule_target_elements(self) -> int:
        return len(
            [e for e in self.elements if isinstance(e, TargetProfile.JouleElement)]
        )

    def subtract(self, other: JouleProfile) -> "TargetProfile":
        diff_elements = []
        for i, element in enumerate(self.elements):
            if (
                isinstance(element, TargetProfile.JouleElement)
                and other.get_energy_for_timestep(i) is not None
            ):
                diff_elements.append(
                    TargetProfile.JouleElement(
                        element.get_joules() - other.get_energy_for_timestep(i)
                    )
                )
            elif isinstance(element, TargetProfile.TariffElement):
                diff_elements.append(element)
            else:
                diff_elements.append(TargetProfile.NULL_ELEMENT)
        return TargetProfile(self.profile_start, self.timestep_duration, diff_elements)

    def add(self, other: JouleProfile) -> "TargetProfile":
        sum_elements = []
        for i, element in enumerate(self.elements):
            if (
                isinstance(element, TargetProfile.JouleElement)
                and other.get_energy_for_timestep(i) is not None
            ):
                sum_elements.append(
                    TargetProfile.JouleElement(
                        element.get_joules() + other.get_energy_for_timestep(i)
                    )
                )
            elif isinstance(element, TargetProfile.TariffElement):
                sum_elements.append(element)
            else:
                sum_elements.append(TargetProfile.NULL_ELEMENT)
        return TargetProfile(self.profile_start, self.timestep_duration, sum_elements)

    def sum_quadratic_distance(self) -> float:
        return sum(
            e.get_joules() ** 2
            for e in self.elements
            if isinstance(e, TargetProfile.JouleElement)
        )

    def __str__(self) -> str:
        return f"TargetProfile(elements={self.elements}, profile_start={self.profile_start}, timestep_duration={self.timestep_duration})"
