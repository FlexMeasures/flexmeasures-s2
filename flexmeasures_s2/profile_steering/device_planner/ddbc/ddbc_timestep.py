from datetime import datetime
from typing import Optional
from s2python.ddbc import DDBCSystemDescription
from s2python.ddbc.ddbc_average_demand_rate_forecast import (
    DDBCAverageDemandRateForecast,
)


class DdbcTimestep:
    """
    Represents a timestep in DDBC planning.
    Similar to FrbcTimestep but for DDBC devices.
    """

    def __init__(
        self,
        start_date: datetime,
        timestep_duration_seconds: float,
        system_description: DDBCSystemDescription,
        demand_forecast: Optional[DDBCAverageDemandRateForecast] = None,
    ):
        self.start_date = start_date
        self.timestep_duration_seconds = timestep_duration_seconds
        self.system_description = system_description
        self.demand_forecast = demand_forecast

        # Cache the expected demand rate if available
        self.expected_demand_rate = 0.0
        if demand_forecast and len(demand_forecast.elements) > 0:
            # Use the first element's demand rate
            self.expected_demand_rate = demand_forecast.elements[0].demand_rate_expected

    def get_start_date(self) -> datetime:
        return self.start_date

    def get_timestep_duration_seconds(self) -> float:
        return self.timestep_duration_seconds

    def get_system_description(self) -> DDBCSystemDescription:
        return self.system_description

    def get_demand_forecast(self) -> Optional[DDBCAverageDemandRateForecast]:
        return self.demand_forecast

    def get_expected_demand_rate(self) -> float:
        """Get the expected demand rate for this timestep."""
        return self.expected_demand_rate
