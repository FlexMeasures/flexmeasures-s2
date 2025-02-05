from typing import List, Optional


class JouleProfile:
    def __init__(
        self, profile_start, timestep_duration, elements: Optional[List[int]] = None
    ):
        self.profile_start = profile_start
        self.timestep_duration = timestep_duration
        self.elements = elements if elements is not None else []

    def avg_power_at(self, date) -> Optional[float]:
        element = self.element_at(date)
        if element is None:
            return None
        return element / self.timestep_duration.total_seconds()

    def element_at(self, date) -> Optional[int]:
        index = int(
            (date - self.profile_start).total_seconds()
            // self.timestep_duration.total_seconds()
        )
        if 0 <= index < len(self.elements):
            return self.elements[index]
        return None

    def add(self, other: "JouleProfile") -> "JouleProfile":
        self.check_compatibility(other)
        summed_elements = [a + b for a, b in zip(self.elements, other.elements)]
        return JouleProfile(self.profile_start, self.timestep_duration, summed_elements)

    def subtract(self, other: "JouleProfile") -> "JouleProfile":
        self.check_compatibility(other)
        diff_elements = [a - b for a, b in zip(self.elements, other.elements)]
        return JouleProfile(self.profile_start, self.timestep_duration, diff_elements)

    def absolute_values(self) -> "JouleProfile":
        abs_elements = [abs(e) for e in self.elements]
        return JouleProfile(self.profile_start, self.timestep_duration, abs_elements)

    def sum_quadratic_distance(self) -> float:
        return sum(e**2 for e in self.elements if e is not None)

    def is_below_or_equal(self, other: "JouleProfile") -> bool:
        self.check_compatibility(other)
        return all(
            a <= b for a, b in zip(self.elements, other.elements) if b is not None
        )

    def is_above_or_equal(self, other: "JouleProfile") -> bool:
        self.check_compatibility(other)
        return all(
            a >= b for a, b in zip(self.elements, other.elements) if b is not None
        )

    def minimum(self, other: "JouleProfile") -> "JouleProfile":
        self.check_compatibility(other)
        min_elements = [min(a, b) for a, b in zip(self.elements, other.elements)]
        return JouleProfile(self.profile_start, self.timestep_duration, min_elements)

    def maximum(self, other: "JouleProfile") -> "JouleProfile":
        self.check_compatibility(other)
        max_elements = [max(a, b) for a, b in zip(self.elements, other.elements)]
        return JouleProfile(self.profile_start, self.timestep_duration, max_elements)

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

    def check_compatibility(self, other: "JouleProfile"):
        if self.timestep_duration != other.timestep_duration or len(
            self.elements
        ) != len(other.elements):
            raise ValueError("Profiles are not compatible")

    def __str__(self) -> str:
        return f"JouleProfile(elements={self.elements}, profile_start={self.profile_start}, timestep_duration={self.timestep_duration})"
