from datetime import datetime, timedelta
from typing import List, Optional, Any

from flexmeasures_s2.profile_steering.device_planner.frbc.frbc_timestep import FrbcTimestep
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state_wrapper import (
    S2FrbcDeviceStateWrapper,
)

from flexmeasures_s2.profile_steering.device_planner.frbc.frbc_state import FrbcState
from flexmeasures_s2.profile_steering.device_planner.frbc.fill_level_target_util import (
    FillLevelTargetUtil,
)
from flexmeasures_s2.profile_steering.device_planner.frbc.usage_forecast_util import UsageForecastUtil
from flexmeasures_s2.profile_steering.s2_utils.number_range_wrapper import (
    NumberRangeWrapper,
)
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_plan import S2FrbcPlan
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.soc_profile import SoCProfile
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state import S2FrbcDeviceState
from pint import UnitRegistry

SI = UnitRegistry()

# TODO: Add S2FrbcInsightsProfile?->Update 08-02-2025: Not needed for now


class OperationModeProfileTree:
    def __init__(
        self,
        device_state: S2FrbcDeviceState,
        profile_metadata: ProfileMetadata,
        plan_due_by_date: datetime,
    ):
        self.device_state = S2FrbcDeviceStateWrapper(device_state)
        self.profile_metadata = profile_metadata
        self.plan_due_by_date = plan_due_by_date
        self.timestep_duration_seconds = int(profile_metadata.get_timestep_duration().total_seconds())
        self.timesteps: List[FrbcTimestep] = []
        self.generate_timesteps()

    def generate_timesteps(self) -> None:
        time_step_start = self.profile_metadata.get_profile_start()
        for i in range(self.profile_metadata.get_nr_of_timesteps()):
            time_step_end = time_step_start + self.profile_metadata.get_timestep_duration()
            if i == 0:
                time_step_start = self.plan_due_by_date
            time_step_start_dt = time_step_start
            current_system_description = self.get_latest_before(
                time_step_start_dt,
                self.device_state.get_system_descriptions(),
                lambda sd: sd.get_valid_from(),
            )
            current_leakage_behaviour = self.get_latest_before(
                time_step_start_dt,
                self.device_state.get_leakage_behaviours(),
                lambda lb: lb.get_valid_from(),
            )
            current_fill_level = self.get_latest_before(
                time_step_start_dt,
                self.device_state.get_fill_level_target_profiles(),
                lambda fl: fl.get_start_time(),
            )
            current_fill_level_target = None
            if current_fill_level:
                current_fill_level_target = FillLevelTargetUtil.from_fill_level_target_profile(current_fill_level)
            fill_level_target = self.get_fill_level_target_for_timestep(
                current_fill_level_target, time_step_start, time_step_end
            )
            current_usage_forecast = self.get_latest_before(
                time_step_start_dt,
                self.device_state.get_usage_forecasts(),
                lambda uf: uf.get_start_time(),
            )
            current_usage_forecast_profile = None
            if current_usage_forecast:
                current_usage_forecast_profile = UsageForecastUtil.from_storage_usage_profile(current_usage_forecast)
            usage_forecast = self.get_usage_forecast_for_timestep(
                current_usage_forecast_profile, time_step_start, time_step_end
            )
            self.timesteps.append(
                FrbcTimestep(
                    time_step_start,
                    time_step_end,
                    current_system_description,
                    current_leakage_behaviour,
                    fill_level_target,
                    usage_forecast,
                    self.device_state.get_computational_parameters(),
                )
            )
            time_step_start = time_step_end

    @staticmethod
    def get_latest_before(before: datetime, select_from: List[Any], get_date_time: Any) -> Optional[Any]:
        latest_before = None
        latest_before_date_time = None
        if select_from:
            for current in select_from:
                if current:
                    current_date_time = get_date_time(current)
                    if current_date_time <= before and (
                        latest_before is None or current_date_time > latest_before_date_time
                    ):
                        latest_before = current
                        latest_before_date_time = current_date_time
        return latest_before

    @staticmethod
    def get_fill_level_target_for_timestep(
        fill_level_target_profile: Optional[Any],
        time_step_start: datetime,
        time_step_end: datetime,
    ) -> Optional[NumberRangeWrapper]:
        if not fill_level_target_profile:
            return None
        time_step_end -= timedelta(milliseconds=1)
        lower, upper = None, None
        for e in fill_level_target_profile.get_elements_in_range(time_step_start, time_step_end):
            if e.get_lower_limit() is not None and (lower is None or e.get_lower_limit() > lower):
                lower = e.get_lower_limit()
            if e.get_upper_limit() is not None and (upper is None or e.get_upper_limit() < upper):
                upper = e.get_upper_limit()
        if lower is None and upper is None:
            return None
        return NumberRangeWrapper(lower, upper)

    @staticmethod
    def get_usage_forecast_for_timestep(
        usage_forecast: Optional[Any],
        time_step_start: datetime,
        time_step_end: datetime,
    ) -> float:
        if not usage_forecast:
            return 0
        time_step_end -= timedelta(milliseconds=1)
        usage = 0
        sub_profile = usage_forecast.sub_profile(time_step_start, time_step_end)
        for element in sub_profile.get_elements():
            usage += element.get_usage()
        return usage

    def find_best_plan(self, target_profile: Any, diff_to_min_profile: Any, diff_to_max_profile: Any) -> S2FrbcPlan:
        for i, ts in enumerate(self.timesteps):
            ts.clear()
            ts.set_targets(
                target_profile.get_elements()[i],
                diff_to_min_profile.get_elements()[i],
                diff_to_max_profile.get_elements()[i],
            )
        first_timestep_index = next(
            (i for i, ts in enumerate(self.timesteps) if ts.get_system_description()),
            -1,
        )
        first_timestep = self.timesteps[first_timestep_index]
        last_timestep = self.timesteps[-1]
        state_zero = FrbcState(self.device_state, first_timestep)
        state_zero.generate_next_timestep_states(first_timestep)
        for i in range(first_timestep_index, len(self.timesteps) - 1):
            current_timestep = self.timesteps[i]
            next_timestep = self.timesteps[i + 1]
            final_states = current_timestep.get_final_states_within_fill_level_target()
            for frbc_state in final_states:
                frbc_state.generate_next_timestep_states(next_timestep)
        end_state = self.find_best_end_state(last_timestep.get_final_states_within_fill_level_target())
        return self.convert_to_plan(first_timestep_index, end_state)

    @staticmethod
    def find_best_end_state(states: List[FrbcState]) -> FrbcState:
        best_state = states[0]
        for state in states[1:]:
            if state.is_preferable_than(best_state).result:
                best_state = state
        return best_state

    def convert_to_plan(self, first_timestep_index_with_state: int, end_state: FrbcState) -> S2FrbcPlan:
        energy: List[int] = [0] * self.profile_metadata.get_nr_of_timesteps()
        fill_level: List[float] = [0.0] * self.profile_metadata.get_nr_of_timesteps()
        actuators: List[dict] = [{}] * self.profile_metadata.get_nr_of_timesteps()
        insight_elements = [None] * self.profile_metadata.get_nr_of_timesteps()
        state_selection_reasons: List[str] = [""] * self.profile_metadata.get_nr_of_timesteps()
        state = end_state
        for i in range(self.profile_metadata.get_nr_of_timesteps() - 1, -1, -1):
            if i >= first_timestep_index_with_state:
                energy[i] = int(state.get_timestep_energy())
                fill_level[i] = state.get_fill_level()
                actuators[i] = state.get_actuator_configurations()
                state_selection_reasons[i] = state.get_selection_reason().abbr  # type: ignore
                state = state.get_previous_state()
            else:
                energy[i] = 0
                fill_level[i] = 0.0
                actuators[i] = {}
                insight_elements[i] = None
        energy[0] += self.device_state.get_energy_in_current_timestep().to(SI.joule).magnitude
        return S2FrbcPlan(
            False,
            JouleProfile(
                self.profile_metadata.get_profile_start(), self.profile_metadata.get_timestep_duration(), energy
            ),
            SoCProfile(
                self.profile_metadata.get_profile_start(), self.profile_metadata.get_timestep_duration(), fill_level
            ),
            actuators,
        )

    def get_timestep_duration_seconds(self) -> int:
        return self.timestep_duration_seconds
