from datetime import datetime, timedelta
from typing import List, Optional, Any
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import logging

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
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from pint import UnitRegistry

SI = UnitRegistry()
logger = logging.getLogger(__name__)


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
        self.device_state = S2FrbcDeviceStateWrapper(**device_state.__dict__)
        self.profile_metadata = profile_metadata
        self.plan_due_by_date = plan_due_by_date
        self.timestep_duration_seconds = int(
            profile_metadata.timestep_duration.total_seconds()
        )
        self.timesteps: List[FrbcTimestep] = []
        self.generate_timesteps()

    def generate_timesteps(self) -> None:
        # logger.info("=" * 80)
        # logger.info("GENERATING TIMESTEPS")
        # logger.info("=" * 80)
        # logger.info(f"Profile start: {self.profile_metadata.profile_start}")
        # logger.info(f"Number of timesteps: {self.profile_metadata.nr_of_timesteps}")
        # logger.info(f"Timestep duration: {self.profile_metadata.timestep_duration}")
        # logger.info(f"Plan due by date: {self.plan_due_by_date}")

        time_step_start = self.profile_metadata.profile_start
        for i in range(self.profile_metadata.nr_of_timesteps):
            time_step_end = time_step_start + self.profile_metadata.timestep_duration

            if i == 0:
                time_step_start = self.plan_due_by_date
                # logger.debug(
                #     f"Timestep {i}: Adjusted start to plan_due_by_date: {time_step_start}"
                # )

            system_default_timezone = time_step_start.astimezone().tzinfo
            time_step_start_dt = time_step_start.astimezone(system_default_timezone)
            current_system_description = self.get_latest_before(
                time_step_start_dt,
                self.device_state.system_descriptions,
                lambda sd: sd.valid_from,
            )
            current_leakage_behaviour = self.get_latest_before(
                time_step_start_dt,
                self.device_state.leakage_behaviours,
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

            # Log timestep details every 10 timesteps and first/last
            if i % 10 == 0 or i == 0 or i == self.profile_metadata.nr_of_timesteps - 1:
                # logger.info(
                #     f"Timestep {i}: {time_step_start.strftime('%H:%M:%S')} -> {time_step_end.strftime('%H:%M:%S')}"
                # )
                # if fill_level_target:
                #     logger.info(
                #         f"  Fill level target: [{fill_level_target.start_of_range}, {fill_level_target.end_of_range}]"
                #     )
                # else:
                #     logger.info("  Fill level target: None")
                # logger.info(f"  Usage forecast: {usage_forecast}")
                # if current_leakage_behaviour:
                #     logger.info("  Leakage behaviour: present")
                # else:
                #     logger.info("  Leakage behaviour: None")
                pass

            self.timesteps.append(
                FrbcTimestep(
                    time_step_start.astimezone(system_default_timezone),
                    time_step_end.astimezone(system_default_timezone),
                    current_system_description,
                    current_leakage_behaviour,
                    fill_level_target,
                    usage_forecast,
                    self.device_state.computational_parameters,
                )
            )
            time_step_start = time_step_end

        # logger.info(f"Generated {len(self.timesteps)} timesteps")
        # logger.info("=" * 80)

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
        target_profile: TargetProfile,
        diff_to_min_profile: Any,
        diff_to_max_profile: Any,
        ids: Optional[dict] = None,
    ) -> S2FrbcPlan:
        # logger.info("=" * 80)
        # logger.info("FINDING BEST PLAN")
        # logger.info("=" * 80)

        # Set targets for each timestep
        for i, ts in enumerate(self.timesteps):
            ts.clear()
            target_element = target_profile.elements[i]
            if target_element is not None:
                ts.set_targets(
                    target_element,
                    diff_to_min_profile.elements[i],
                    diff_to_max_profile.elements[i],
                )
                if i % 10 == 0 or i == 0 or i == len(self.timesteps) - 1:
                    # logger.debug(
                    #     f"Timestep {i} target: {target_element}, diff_min: {diff_to_min_profile.elements[i]}, diff_max: {diff_to_max_profile.elements[i]}"
                    # )
                    pass

        first_timestep_index = next(
            (i for i, ts in enumerate(self.timesteps) if ts.system_description),
            -1,
        )
        # logger.info(f"First timestep with system description: {first_timestep_index}")

        first_timestep = self.timesteps[first_timestep_index]
        last_timestep = self.timesteps[-1]

        initial_fill_level = self.device_state.storage_status.present_fill_level
        # logger.info(f"Initial fill level: {initial_fill_level}")

        state_zero = FrbcState(
            device_state=self.device_state,
            timestep=first_timestep,
            initial_fill_level=initial_fill_level,
        )

        # logger.info(f"Generating states for initial timestep {first_timestep_index}...")
        state_zero.generate_next_timestep_states(first_timestep)
        initial_states = first_timestep.get_final_states_within_fill_level_target()
        # logger.info(f"Generated {len(initial_states)} initial states")

        # Sample some initial states to log
        if initial_states:
            for idx, state in enumerate(initial_states[:3]):  # Log first 3 states
                # logger.debug(
                #     f"  Initial state {idx}: fill_level={state.fill_level:.2f}, energy={state.timestep_energy}, cost={getattr(state, 'cost', 'N/A')}"
                # )
                pass

        # Generate states for each timestep
        for i in range(first_timestep_index, len(self.timesteps) - 1):
            current_timestep = self.timesteps[i]
            next_timestep = self.timesteps[i + 1]
            final_states = current_timestep.get_final_states_within_fill_level_target()

            # Log progress every 10 timesteps
            if i % 10 == 0 or i == first_timestep_index:
                # logger.info(
                #     f"Timestep {i}: Processing {len(final_states)} states -> generating states for timestep {i+1}"
                # )
                # if final_states:
                #     # Log sample states
                #     for idx, state in enumerate(final_states[:2]):  # Log first 2 states
                #         logger.debug(
                #             f"  State {idx}: fill_level={state.fill_level:.2f}, energy={state.timestep_energy}, bucket={getattr(state, 'bucket_index', 'N/A')}"
                #         )
                pass

            for frbc_state in final_states:
                frbc_state.generate_next_timestep_states(next_timestep)

        # Find best end state
        final_states = last_timestep.get_final_states_within_fill_level_target()
        # logger.info(f"Final timestep has {len(final_states)} states")

        if final_states:
            for idx, state in enumerate(final_states[:5]):  # Log first 5 final states
                # cost = getattr(state, "sum_energy_cost", "N/A")
                # constraint_violation = getattr(
                #     state, "sum_squared_constraint_violation", "N/A"
                # )
                # logger.info(
                #     f"  Final state {idx}: fill_level={state.fill_level:.2f}, energy={state.timestep_energy:.0f}, cost={cost}, constraint_violation={constraint_violation}"
                # )
                pass

        end_state = self.find_best_end_state(final_states)
        # logger.info(
        #     f"Best end state selected: fill_level={end_state.fill_level:.2f}, energy={end_state.timestep_energy:.0f}"
        # )
        # logger.info(
        #     f"  Selection reason: {getattr(end_state, 'selection_reason', 'N/A')}"
        # )
        # logger.info(
        #     f"  Best state cost: {getattr(end_state, 'sum_energy_cost', 'N/A')}"
        # )
        # logger.info(
        #     f"  Best state constraint_violation: {getattr(end_state, 'sum_squared_constraint_violation', 'N/A')}"
        # )

        plan = self.convert_to_plan(first_timestep_index, end_state)

        # logger.info("=" * 80)
        # logger.info("PLAN GENERATION COMPLETE")
        # logger.info("=" * 80)

        return plan

    @staticmethod
    def find_best_end_state(states: List[FrbcState]) -> FrbcState:
        # logger.info(f"Comparing {len(states)} end states to find best...")
        best_state = states[0]
        comparisons = 0

        # best_cost = getattr(best_state, "sum_energy_cost", 0)
        # best_violation = getattr(best_state, "sum_squared_constraint_violation", 0)
        # logger.info(
        #     f"  Initial best state: fill_level={best_state.fill_level:.2f}, energy={best_state.timestep_energy:.0f}, cost={best_cost:.4f}, violation={best_violation:.4f}"
        # )

        for idx, state in enumerate(states[1:], 1):
            # state_cost = getattr(state, "sum_energy_cost", 0)
            # state_violation = getattr(state, "sum_squared_constraint_violation", 0)
            comparison_result = state.is_preferable_than(best_state)

            if idx <= 5:  # Log first 5 comparisons
                # logger.info(
                #     f"  Comparing state {idx}: fill_level={state.fill_level:.2f}, energy={state.timestep_energy:.0f}, cost={state_cost:.4f}, violation={state_violation:.4f}"
                # )
                # logger.info(
                #     f"    Comparison result: {comparison_result.result}, reason: {comparison_result.reason if hasattr(comparison_result, 'reason') else 'N/A'}"
                # )
                # logger.info(
                #     f"    Cost difference: {abs(state_cost - best_cost):.4f}, tariff_epsilon: {FrbcState.tariff_epsilon}"
                # )
                pass

            if comparison_result.result:
                # logger.info(
                #     f"  State {idx} is BETTER: fill_level={state.fill_level:.2f} vs {best_state.fill_level:.2f}"
                # )
                # logger.info(
                #     f"    Reason: {comparison_result.reason if hasattr(comparison_result, 'reason') else 'N/A'}"
                # )
                best_state = state
                # best_cost = state_cost
                # best_violation = state_violation
                comparisons += 1

        # logger.info(f"Best state found after {comparisons} preference changes")
        # logger.info(
        #     f"  Final best: fill_level={best_state.fill_level:.2f}, energy={best_state.timestep_energy:.0f}, cost={best_cost:.4f}"
        # )
        return best_state

    def convert_to_plan(
        self, first_timestep_index_with_state: int, end_state: FrbcState
    ) -> S2FrbcPlan:
        # logger.info("Converting end state to plan...")
        # logger.info(f"  First timestep index: {first_timestep_index_with_state}")

        energy: List[int] = [0] * self.profile_metadata.nr_of_timesteps
        fill_level: List[float] = [0.0] * self.profile_metadata.nr_of_timesteps
        actuators: List[dict] = [{}] * self.profile_metadata.nr_of_timesteps
        insight_elements = [None] * self.profile_metadata.nr_of_timesteps
        state_selection_reasons: List[str] = [
            ""
        ] * self.profile_metadata.nr_of_timesteps

        state = end_state
        states_traced = 0

        # Trace back through states
        for i in range(self.profile_metadata.nr_of_timesteps - 1, -1, -1):
            if i >= first_timestep_index_with_state:
                energy[i] = int(state.timestep_energy)
                fill_level[i] = state.fill_level
                actuators[i] = state.actuator_configurations
                state_selection_reasons[i] = state.selection_reason  # type: ignore

                # Log every 10 states
                if i % 10 == 0 or i == first_timestep_index_with_state:
                    # logger.debug(
                    #     f"  Timestep {i}: energy={energy[i]}, fill_level={fill_level[i]:.2f}, actuator_configs={len(actuators[i])} actuator(s)"
                    # )
                    # if actuators[i]:
                    #     for actuator_id, config in actuators[i].items():
                    #         mode_id = getattr(config, "operation_mode_id", "N/A")
                    #         logger.debug(
                    #             f"    Actuator {str(actuator_id)[:8]}...: mode {str(mode_id)[:8]}..."
                    #         )
                    pass

                state = state.previous_state
                states_traced += 1
            else:
                energy[i] = 0
                fill_level[i] = 0.0
                actuators[i] = {}
                insight_elements[i] = None

        # logger.info(f"Traced back through {states_traced} states")

        # Add current energy
        current_energy = self.device_state.energy_in_current_timestep.value
        # logger.info(f"Adding current timestep energy: {current_energy}")
        energy[0] += current_energy

        # Calculate plan statistics
        # total_energy = sum(energy)
        # avg_fill_level = sum(fill_level) / len(fill_level) if fill_level else 0
        # mode_changes = 0
        # prev_mode = None
        # for actuator_config in actuators:
        #     for actuator_id, config in actuator_config.items():
        #         mode_id = getattr(config, "operation_mode_id", None)
        #         if mode_id and mode_id != prev_mode:
        #             mode_changes += 1
        #             prev_mode = mode_id

        # logger.info("Plan statistics:")
        # logger.info(
        #     f"  Total energy: {total_energy} J ({total_energy/3600000:.2f} kWh)"
        # )
        # logger.info(f"  Average fill level: {avg_fill_level:.2f}")
        # logger.info(f"  Operation mode changes: {mode_changes}")

        return S2FrbcPlan(
            False,
            JouleProfile(
                profile_start=self.profile_metadata.profile_start,
                timestep_duration=self.profile_metadata.timestep_duration,
                elements=energy,  # type: ignore[arg-type]
            ),
            SoCProfile(
                self.profile_metadata,
                fill_level,
            ),
            actuators,
        )
