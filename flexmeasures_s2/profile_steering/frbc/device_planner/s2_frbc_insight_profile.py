from typing import List, Dict


class S2FrbcInsightsProfile:
    def __init__(
        self, profile_metadata, elements: List["S2FrbcInsightsProfile.Element"]
    ):
        self.profile_metadata = profile_metadata
        self.elements = elements

    def default_value(self):
        return None

    def build_profile_type(self, profile_metadata, elements):
        return S2FrbcInsightsProfile(profile_metadata, elements)

    def to_insights_map(self) -> Dict[str, List[float]]:
        insights_map = {
            "fill_level_end_of_step": [
                e.get_fill_level_end_of_step() if e else None for e in self.elements
            ]
        }
        return insights_map

    class Element:
        def __init__(self, fill_level_end_of_step: float):
            self.fill_level_end_of_step = fill_level_end_of_step

        def get_fill_level_end_of_step(self) -> float:
            return self.fill_level_end_of_step
