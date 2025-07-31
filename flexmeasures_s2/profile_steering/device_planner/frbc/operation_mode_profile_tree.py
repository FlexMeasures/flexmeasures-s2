from datetime import datetime, timedelta
from typing import List, Optional, Any, Tuple
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from flexmeasures_s2.profile_steering.device_planner.frbc.frbc_timestep import (
    FrbcTimestep,
)
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state_wrapper import (
    S2FrbcDeviceStateWrapper,
)

from flexmeasures_s2.profile_steering.device_planner.frbc.frbc_state import FrbcState
from flexmeasures_s2.profile_steering.device_planner.frbc.fill_level_target_util import (
    FillLevelTargetUtil,
)
from flexmeasures_s2.profile_steering.device_planner.frbc.usage_forecast_util import (
    UsageForecastUtil,
)
from flexmeasures_s2.profile_steering.s2_utils.number_range_wrapper import (
    NumberRangeWrapper,
)
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_plan import S2FrbcPlan
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.soc_profile import SoCProfile
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state import (
    S2FrbcDeviceState,
)
from pint import UnitRegistry

SI = UnitRegistry()


# TODO: Add S2FrbcInsightsProfile?->Update 08-02-2025: Not needed for now


def plot_planning_results(
    timestep_start_times, energy_elements, fill_level_elements, operation_mode_ids, ids
):
    """
    Plots the energy, fill level, actuator usage, and operation mode ID lists using matplotlib.

    :param timestep_start_times: List of datetime objects representing the start time of each timestep.
    :param energy_elements: List of energy values.
    :param fill_level_elements: List of fill level values.
    :param operation_mode_ids: List of dictionaries with actuator configurations.
    :param ids: List of tuples (id, name) for debugging.
    """
    # Create a figure and a set of subplots
    fig, axs = plt.subplots(4, 1, figsize=(12, 16), sharex=True)

    # Plot energy elements
    axs[0].plot(timestep_start_times, energy_elements, label="Energy", color="blue")
    axs[0].set_ylabel("Energy (Joules)")
    axs[0].legend(loc="upper right")
    axs[0].grid(True)

    # Plot fill level elements
    axs[1].plot(
        timestep_start_times, fill_level_elements, label="Fill Level", color="green"
    )
    axs[1].set_ylabel("Fill Level (%)")
    axs[1].legend(loc="upper right")
    axs[1].grid(True)

    # Create a dictionary from the list of tuples for easier lookup
    id_to_name = {id_val: name for id_val, name in ids}

    # Create a color mapping for names
    unique_names = set(name for _, name in ids)
    actuator_colors = {name: f"C{i}" for i, name in enumerate(unique_names)}

    # Plot actuator usage
    for i, (time, config) in enumerate(zip(timestep_start_times, operation_mode_ids)):
        for actuator_id, config in config.items():
            actuator_name = id_to_name.get(str(actuator_id), str(actuator_id))
            axs[2].scatter(
                time,
                actuator_name,
                color=actuator_colors.get(actuator_name, "black"),
                label=actuator_name if i == 0 else "",
            )
    axs[2].set_ylabel("Actuator Name")
    handles, labels = axs[2].get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    axs[2].legend(by_label.values(), by_label.keys(), loc="upper right")
    axs[2].grid(True)

    # Plot operation modes
    for i, (time, config) in enumerate(zip(timestep_start_times, operation_mode_ids)):
        for actuator_id, config in config.items():
            operation_mode_id = getattr(config, "operation_mode_id", None)
            if operation_mode_id:
                operation_mode_name = id_to_name.get(
                    str(operation_mode_id), str(operation_mode_id)
                )
                axs[3].scatter(
                    time,
                    operation_mode_name,
                    color=actuator_colors.get(operation_mode_name, "black"),
                    label=operation_mode_name if i == 0 else "",
                )
    axs[3].set_ylabel("Operation Mode Name")
    handles, labels = axs[3].get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    axs[3].legend(by_label.values(), by_label.keys(), loc="upper right")
    axs[3].grid(True)

    # Format the x-axis to show time and set ticks every 30 minutes
    axs[3].xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
    axs[3].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    fig.autofmt_xdate()

    # Adjust layout
    plt.tight_layout()
    plt.show()


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
        self.timestep_duration_seconds = int(
            profile_metadata.timestep_duration.total_seconds()
        )
        self.timesteps: List[FrbcTimestep] = []
        self.generate_timesteps()

    def generate_timesteps(self) -> None:
        time_step_start = self.profile_metadata.profile_start
        for i in range(self.profile_metadata.nr_of_timesteps):
            if i == 187:
                print("here")
            time_step_end = time_step_start + self.profile_metadata.timestep_duration

            if i == 0:
                time_step_start = self.plan_due_by_date
            system_default_timezone = time_step_start.astimezone().tzinfo
            time_step_start_dt = time_step_start.astimezone(system_default_timezone)
            current_system_description = self.get_latest_before(
                time_step_start_dt,
                self.device_state.get_system_descriptions(),
                lambda sd: sd.valid_from,
            )
            current_leakage_behaviour = self.get_latest_before(
                time_step_start_dt,
                self.device_state.get_leakage_behaviours(),
                lambda lb: lb.valid_from,
            )
            current_fill_level = self.get_latest_before(
                time_step_start_dt,
                self.device_state.fill_level_target_profiles,
                lambda fl: fl.start_time,
            )
            current_fill_level_target = None
            if current_fill_level:
                current_fill_level_target = (
                    FillLevelTargetUtil.from_fill_level_target_profile(
                        current_fill_level
                    )
                )
            fill_level_target = self.get_fill_level_target_for_timestep(
                current_fill_level_target, time_step_start, time_step_end
            )
            current_usage_forecast = self.get_latest_before(
                time_step_start_dt,
                self.device_state.usage_forecasts,
                lambda uf: uf.start_time,
            )
            current_usage_forecast_profile = None
            if current_usage_forecast:
                current_usage_forecast_profile = (
                    UsageForecastUtil.from_storage_usage_profile(current_usage_forecast)
                )

            usage_forecast = self.get_usage_forecast_for_timestep(
                current_usage_forecast_profile, time_step_start, time_step_end
            )
            self.timesteps.append(
                FrbcTimestep(
                    time_step_start.astimezone(system_default_timezone),
                    time_step_end.astimezone(system_default_timezone),
                    current_system_description,
                    current_leakage_behaviour,
                    fill_level_target,
                    usage_forecast,
                    self.device_state.get_computational_parameters(),
                )
            )
            time_step_start = time_step_end

    @staticmethod
    def get_latest_before(before, select_from, get_date_time):
        latest_before = None
        latest_before_date_time = None
        if select_from:
            for current in select_from:
                if current:
                    current_date_time = get_date_time(current).replace(tzinfo=None)
                    before = before.replace(tzinfo=None)
                    if current_date_time <= before and (
                        latest_before is None
                        or current_date_time > latest_before_date_time
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
        for e in FillLevelTargetUtil.get_elements_in_range(
            fill_level_target_profile, time_step_start, time_step_end
        ):
            if e.lower_limit is not None and (lower is None or e.lower_limit > lower):
                lower = e.lower_limit
            if e.upper_limit is not None and (upper is None or e.upper_limit < upper):
                upper = e.upper_limit
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
        usage = UsageForecastUtil.sub_profile(
            usage_forecast=usage_forecast,
            time_step_start=time_step_start,
            time_step_end=time_step_end,
        )

        return usage

    def find_best_plan(
        self,
        target_profile: Any,
        diff_to_min_profile: Any,
        diff_to_max_profile: Any,
        ids: Optional[dict] = None,
    ) -> S2FrbcPlan:
        for i, ts in enumerate(self.timesteps):
            ts.clear()
            ts.set_targets(
                target_profile.elements[i],
                diff_to_min_profile.elements[i],
                diff_to_max_profile.elements[i],
            )
        first_timestep_index = next(
            (i for i, ts in enumerate(self.timesteps) if ts.system_description),
            -1,
        )
        first_timestep = self.timesteps[first_timestep_index]
        last_timestep = self.timesteps[-1]
        state_zero = FrbcState(
            device_state=self.device_state.device_state,
            timestep=first_timestep,
            present_fill_level=0,
        )
        state_zero.generate_next_timestep_states(first_timestep)

        for i in range(first_timestep_index, len(self.timesteps) - 1):
            # print(f"Generating next timestep states for timestep: {i}")
            # if i == 187:
            # print("here")
            current_timestep = self.timesteps[i]
            next_timestep = self.timesteps[i + 1]
            final_states = current_timestep.get_final_states_within_fill_level_target()
            # print(f"There are {len(final_states)} final states")
            for frbc_state in final_states:
                frbc_state.generate_next_timestep_states(next_timestep)
        end_state = self.find_best_end_state(
            last_timestep.get_final_states_within_fill_level_target()
        )
        plan = self.convert_to_plan(first_timestep_index, end_state)
        # Extract only the time component from each datetime object
        # timestep_start_times = [ts.start_date for ts in self.timesteps]

        # Now use this list in the plot function
        # plot_planning_results(timestep_start_times, plan.get_energy().elements, plan.fill_level.elements, plan.get_operation_mode_id(), ids)

        return plan

    @staticmethod
    def find_best_end_state(states: List[FrbcState]) -> FrbcState:
        best_state = states[0]
        for state in states[1:]:
            if state.is_preferable_than(best_state).result:
                best_state = state
        return best_state

    def convert_to_plan(
        self, first_timestep_index_with_state: int, end_state: FrbcState
    ) -> S2FrbcPlan:
        energy: List[int] = [0] * self.profile_metadata.nr_of_timesteps
        fill_level: List[float] = [0.0] * self.profile_metadata.nr_of_timesteps
        actuators: List[dict] = [{}] * self.profile_metadata.nr_of_timesteps
        insight_elements = [None] * self.profile_metadata.nr_of_timesteps
        state_selection_reasons: List[str] = [
            ""
        ] * self.profile_metadata.nr_of_timesteps
        state = end_state
        for i in range(self.profile_metadata.nr_of_timesteps - 1, -1, -1):
            if i >= first_timestep_index_with_state:
                energy[i] = int(state.timestep_energy)
                fill_level[i] = state.fill_level
                actuators[i] = state.actuator_configurations
                state_selection_reasons[i] = state.selection_reason  # type: ignore
                state = state.previous_state
            else:
                energy[i] = 0
                fill_level[i] = 0.0
                actuators[i] = {}
                insight_elements[i] = None
        energy[0] += self.device_state.get_energy_in_current_timestep().value
        return S2FrbcPlan(
            False,
            JouleProfile(
                self.profile_metadata.profile_start,
                self.profile_metadata.timestep_duration,
                energy,
            ),
            SoCProfile(
                self.profile_metadata,
                fill_level,
            ),
            actuators,
        )
