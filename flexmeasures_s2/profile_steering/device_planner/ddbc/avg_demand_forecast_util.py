from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Any, Optional


@dataclass
class AvgDemandForecastElement:
    """Element representing average demand forecast for a time period."""

    start: datetime
    end: datetime
    avg_demand: float

    def get_duration(self) -> timedelta:
        return self.end - self.start


@dataclass
class AvgDemandForecastProfile:
    """Profile of average demand forecast elements."""

    elements: List[AvgDemandForecastElement]

    @property
    def start(self) -> Optional[datetime]:
        return self.elements[0].start if self.elements else None

    @property
    def end(self) -> Optional[datetime]:
        return self.elements[-1].end if self.elements else None

    def sub_profile(self, start: datetime, end: datetime) -> "AvgDemandForecastProfile":
        """Get a sub-profile between start and end times."""
        sub_elements = []

        for element in self.elements:
            element_start = max(element.start, start)
            element_end = min(element.end, end)

            if element_start < element_end:
                sub_elements.append(
                    AvgDemandForecastElement(
                        element_start, element_end, element.avg_demand
                    )
                )

        return AvgDemandForecastProfile(sub_elements)


class AvgDemandForecastUtil:
    """Utility class for converting DDBC average demand forecasts."""

    @staticmethod
    def from_avg_demand_rate_forecast(demand_forecast: Any) -> AvgDemandForecastProfile:
        """Convert a DDBC average demand rate forecast to a profile."""
        elements: List[AvgDemandForecastElement] = []

        start = demand_forecast.start_time

        for element in demand_forecast.elements:
            if isinstance(element.duration, (int, float)):
                duration_seconds = element.duration
            elif hasattr(element.duration, "root"):
                duration_seconds = element.duration.root
            else:
                duration_seconds = int(element.duration)
            end = start + timedelta(seconds=duration_seconds)
            elements.append(
                AvgDemandForecastElement(
                    start, end, float(element.demand_rate_expected)
                )
            )
            start = end + timedelta(milliseconds=1)

        return AvgDemandForecastProfile(elements)

    @staticmethod
    def get_avg_demand_forecast_for_timestep(
        avg_demand_forecast: AvgDemandForecastProfile,
        timestep_start: datetime,
        timestep_end: datetime,
    ) -> Optional[float]:
        """Get weighted average demand forecast for a timestep."""
        if avg_demand_forecast is None:
            return None

        timestep_end_adjusted = timestep_end - timedelta(milliseconds=1)

        sub_profile = avg_demand_forecast.sub_profile(
            timestep_start, timestep_end_adjusted
        )

        if not sub_profile.elements:
            return None

        demand = 0.0
        for element in sub_profile.elements:
            duration_ms = element.get_duration().total_seconds() * 1000
            demand += element.avg_demand * duration_ms

        start = sub_profile.start
        end = sub_profile.end
        if start is None or end is None:
            return None

        total_duration_ms = (end - start).total_seconds() * 1000

        if total_duration_ms == 0:
            return None

        return demand / total_duration_ms
