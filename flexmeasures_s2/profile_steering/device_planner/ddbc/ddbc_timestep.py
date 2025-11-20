from datetime import datetime, timedelta
from typing import Optional, Any, List, TYPE_CHECKING
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile

if TYPE_CHECKING:
    from flexmeasures_s2.profile_steering.device_planner.ddbc.ddbc_state import (
        DdbcState,
    )


class DdbcTimestep:
    """Represents a single timestep in DDBC planning."""

    DISTANCE_EPSILON = 500.0  # 500 W tolerance (5% of 10kW typical system)

    def __init__(
        self,
        start_date: datetime,
        end_date: datetime,
        system_description: Any,
        avg_demand_rate_forecast: Optional[float],
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.system_description = system_description
        self.avg_demand_rate_forecast = avg_demand_rate_forecast

        self.target: Optional[TargetProfile.Element] = None
        self.min_constraint: Optional[int] = None
        self.max_constraint: Optional[int] = None

        self.best_state: Optional["DdbcState"] = None
        self.emergency_state: Optional["DdbcState"] = None

    def set_targets(
        self,
        target: TargetProfile.Element,
        min_constraint: Optional[int],
        max_constraint: Optional[int],
    ):
        """Set the target and constraints for this timestep."""
        self.target = target
        self.min_constraint = min_constraint
        self.max_constraint = max_constraint

    def add_state(self, state: "DdbcState"):
        """Add a state to this timestep and track the best state."""
        distance = state.supply_demand_distance()

        if distance < self.DISTANCE_EPSILON:
            if self.best_state is None:
                self.best_state = state
            elif state.is_preferable_than(self.best_state):
                self.best_state = state
        else:
            if (
                self.emergency_state is None
                or distance < self.emergency_state.supply_demand_distance()
            ):
                self.emergency_state = state

    def add_all_states(self, states: List["DdbcState"]):
        """Add multiple states to this timestep."""
        for state in states:
            self.add_state(state)

    def get_best_state(self) -> Optional["DdbcState"]:
        """Get the best state for this timestep, or emergency state if no best state exists."""
        if self.best_state is None:
            return self.emergency_state
        else:
            return self.best_state

    def get_start_date(self) -> datetime:
        return self.start_date

    def get_end_date(self) -> datetime:
        return self.end_date

    def get_system_description(self) -> Any:
        return self.system_description

    def get_duration(self) -> timedelta:
        return self.end_date - self.start_date

    def get_duration_seconds(self) -> int:
        return int(self.get_duration().total_seconds())

    def get_target(self) -> Optional[TargetProfile.Element]:
        return self.target

    def get_min_constraint(self) -> Optional[int]:
        return self.min_constraint

    def get_max_constraint(self) -> Optional[int]:
        return self.max_constraint

    def get_avg_demand_rate_forecast(self) -> Optional[float]:
        return self.avg_demand_rate_forecast

    def clear(self):
        """Clear the states for this timestep."""
        self.best_state = None
        self.emergency_state = None
