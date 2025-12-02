from datetime import datetime
from typing import List, Optional, Callable, TypeVar, Any, Dict, TYPE_CHECKING, cast
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_device_state import (
    S2DdbcDeviceState,
)
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_device_state_wrapper import (
    S2DdbcDeviceStateWrapper,
)
from flexmeasures_s2.profile_steering.device_planner.ddbc.ddbc_timestep import (
    DdbcTimestep,
)
from flexmeasures_s2.profile_steering.device_planner.ddbc.ddbc_state import DdbcState
from flexmeasures_s2.profile_steering.device_planner.ddbc.avg_demand_forecast_util import (
    AvgDemandForecastUtil,
    AvgDemandForecastProfile,
)
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_insights_profile import (
    S2DdbcInsightsProfile,
)
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_plan import S2DdbcPlan

if TYPE_CHECKING:
    pass

T = TypeVar("T")


class DdbcPlanningWindow:
    """Planning window for DDBC device planning.

    This class represents a state tree that explores possible device states
    over the planning window. It:
    1. Generates timesteps based on system descriptions and demand forecasts
    2. Searches for optimal operation mode sequences
    3. Evaluates plans against targets (energy, cost, congestion constraints)

    The planning window handles:
    - Multiple system descriptions that may change over time
    - Average demand rate forecasts indicating expected demand
    - Actuator operation modes with different cost characteristics
    - Constraints from congestion points and global targets

    The search algorithm finds the best plan that balances meeting demand,
    minimizing cost, and respecting constraints.
    """

    def __init__(
        self,
        device_state: S2DdbcDeviceState,
        profile_metadata: ProfileMetadata,
        plan_due_by_date: datetime,
        stratification_layers: int,
    ):
        self.device_state = S2DdbcDeviceStateWrapper(
            device_state, stratification_layers=stratification_layers
        )
        self.profile_metadata = profile_metadata
        self.plan_due_by_date = plan_due_by_date
        self.timestep_duration_seconds = int(
            profile_metadata.timestep_duration.total_seconds()
        )

        self.timesteps: List[DdbcTimestep] = []
        self._generate_timesteps()

    def _generate_timesteps(self):
        """Generate timesteps for the planning window."""
        timestep_start = self.profile_metadata.profile_start

        for i in range(self.profile_metadata.nr_of_timesteps):
            timestep_end = timestep_start + self.profile_metadata.timestep_duration

            if i == 0 and timestep_start < self.plan_due_by_date < timestep_end:
                timestep_start = self.plan_due_by_date

            current_system_description = self.get_latest_before(
                timestep_start,
                self.device_state.get_system_descriptions(),
                lambda sd: sd.valid_from,
            )

            current_avg_demand_forecast_obj = self.get_latest_before(
                timestep_start,
                self.device_state.get_demand_forecasts(),
                lambda df: df.start_time,
            )

            current_demand_profile: Optional[AvgDemandForecastProfile] = None
            if current_avg_demand_forecast_obj is not None:
                current_demand_profile = (
                    AvgDemandForecastUtil.from_avg_demand_rate_forecast(
                        current_avg_demand_forecast_obj
                    )
                )

            avg_demand_rate_forecast = self.get_avg_demand_forecast_for_timestep(
                current_demand_profile, timestep_start, timestep_end
            )

            self.timesteps.append(
                DdbcTimestep(
                    timestep_start,
                    timestep_end,
                    current_system_description,
                    avg_demand_rate_forecast,
                )
            )

            timestep_start = timestep_end

    @staticmethod
    def get_latest_before(
        before: datetime, select_from: List[T], get_datetime: Callable[[T], datetime]
    ) -> Optional[T]:
        """Get the latest item from a list that occurs before a given datetime."""
        latest_before: Optional[T] = None
        latest_before_datetime: Optional[datetime] = None

        if select_from is not None:
            for current in select_from:
                if current is not None:
                    current_datetime = get_datetime(current)

                    if current_datetime <= before:
                        if latest_before is None or (
                            latest_before_datetime is not None
                            and current_datetime > latest_before_datetime
                        ):
                            latest_before = current
                            latest_before_datetime = current_datetime

        return latest_before

    @staticmethod
    def get_avg_demand_forecast_for_timestep(
        avg_demand_forecast: Optional[AvgDemandForecastProfile],
        timestep_start: datetime,
        timestep_end: datetime,
    ) -> Optional[float]:
        """Get the average demand forecast for a timestep."""
        if avg_demand_forecast is None:
            return None

        return AvgDemandForecastUtil.get_avg_demand_forecast_for_timestep(
            avg_demand_forecast, timestep_start, timestep_end
        )

    def find_best_plan(
        self,
        target_profile: TargetProfile,
        diff_to_min_profile: JouleProfile,
        diff_to_max_profile: JouleProfile,
    ) -> "S2DdbcPlan":
        """Find the best plan for the device."""
        for i in range(len(self.timesteps)):
            ts = self.timesteps[i]
            ts.clear()
            target_element = target_profile.elements[i]
            if target_element is not None:
                ts.set_targets(
                    target_element,
                    diff_to_min_profile.elements[i],
                    diff_to_max_profile.elements[i],
                )

        first_timestep_index = -1
        for i in range(len(self.timesteps)):
            if self.timesteps[i].system_description is not None:
                first_timestep_index = i
                break

        if first_timestep_index == -1:
            first_timestep_index = self.profile_metadata.nr_of_timesteps
        else:
            first_timestep = self.timesteps[first_timestep_index]

            state_zero = DdbcState(self.device_state, first_timestep)
            state_zero.generate_next_timestep_states(first_timestep)

            for i in range(first_timestep_index, len(self.timesteps) - 1):
                current_timestep = self.timesteps[i]
                next_timestep = self.timesteps[i + 1]

                best_state = current_timestep.get_best_state()
                if best_state is not None:
                    best_state.generate_next_timestep_states(next_timestep)

        return self._convert_to_plan(first_timestep_index)

    def _convert_to_plan(self, first_timestep_index_with_state: int) -> "S2DdbcPlan":
        """Convert the planning window to a plan."""
        energy: List[int] = []
        actuators: List[Dict[str, Any]] = []
        insight_elements: List[Any] = []

        for i in range(self.profile_metadata.nr_of_timesteps):
            if i >= first_timestep_index_with_state:
                timestep = self.timesteps[i]
                state = timestep.get_best_state()

                if state is not None:
                    energy.append(int(state.timestep_energy))
                    actuators.append(state.actuator_configurations)
                    insight_elements.append(
                        S2DdbcInsightsProfile.Element(
                            timestep.avg_demand_rate_forecast,
                            state.supply_rate,
                            state.actuator_configurations,
                        )
                    )
                else:
                    energy.append(0)
                    actuators.append({})
                    insight_elements.append(None)
            else:
                energy.append(0)
                actuators.append({})
                insight_elements.append(None)

        energy[0] = energy[0] + int(self.device_state.get_energy_in_current_timestep())

        energy_profile = JouleProfile(
            self.profile_metadata.profile_start,
            self.profile_metadata.timestep_duration,
            cast(List[Optional[int]], energy),
        )

        return S2DdbcPlan(
            idle=False,
            energy=energy_profile,
            operation_mode_id=actuators,
            s2_ddbc_insights_profile=S2DdbcInsightsProfile(
                self.profile_metadata, insight_elements
            ),
        )

    def get_timestep_duration_seconds(self) -> int:
        return self.timestep_duration_seconds
