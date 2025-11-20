from typing import List, Dict, Optional, Any
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata


class S2DdbcInsightsProfile:
    """Insights profile for DDBC device providing additional information about the plan."""

    class Element:
        """Single element in the insights profile."""

        def __init__(
            self,
            demand_rate_forecast: Optional[float],
            supply_rate: float,
            actuator_configurations: Dict[str, Any],
        ):
            self.demand_rate_forecast = demand_rate_forecast
            self.supply_rate = supply_rate
            self.actuator_configurations = actuator_configurations

        def get_demand_rate_forecast(self) -> Optional[float]:
            return self.demand_rate_forecast

        def get_supply_rate(self) -> float:
            return self.supply_rate

        def get_actuator_configurations(self) -> Dict[str, Any]:
            return self.actuator_configurations

    def __init__(
        self, profile_metadata: ProfileMetadata, elements: List[Optional[Element]]
    ):
        self.profile_metadata = profile_metadata
        self.elements = elements

    def get_profile_metadata(self) -> ProfileMetadata:
        return self.profile_metadata

    def get_elements(self) -> List[Optional[Element]]:
        return self.elements
