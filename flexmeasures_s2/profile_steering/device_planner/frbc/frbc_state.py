from datetime import datetime
from s2python.frbc import (
    FRBCSystemDescription,
)
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
import flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state_wrapper as s2_frbc_device_state_wrapper

from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_actuator_configuration import (
    S2ActuatorConfiguration,
)
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state import (
    S2FrbcDeviceState,
)
from flexmeasures_s2.profile_steering.device_planner.frbc.selection_reason_result import (
    SelectionResult,
    SelectionReason,
)

from typing import Dict, Optional, Any, Tuple


class FrbcState:
    constraint_epsilon = 1e-4
    tariff_epsilon = 0.5
    transition_cache: Dict[Any, Any] = {}

    def __init__(  # noqa: C901
        self,
        timestep,
        present_fill_level: float,
        device_state: Optional[S2FrbcDeviceState] = None,
        previous_state: Optional["FrbcState"] = None,
        actuator_configurations: Optional[Dict[str, S2ActuatorConfiguration]] = None,
    ):
        self.timer_elapse_map: Dict[tuple, datetime]
        self.actuator_configurations: Dict[str, S2ActuatorConfiguration]
        self.sum_squared_distance: float
        self.sum_energy_cost: float
        self.sum_squared_constraint_violation: float
        self.sum_squared_energy: float
        if previous_state:
            if device_state:
                self.device_state = (
                    s2_frbc_device_state_wrapper.S2FrbcDeviceStateWrapper(device_state)
                )
            else:
                self.device_state = previous_state.device_state
            self.timestep = timestep
            self.previous_state = previous_state
            self.system_description = timestep.system_description
            self.fill_level = present_fill_level
            self.bucket = 0
            self.timestep_energy = 0.0
            self.fill_level = previous_state.fill_level
            seconds = self.timestep.get_duration_seconds()
            for actuator_id, actuator_configuration in (
                actuator_configurations or {}
            ).items():
                power, fill_rate = self._calculate_and_cache_op_mode_values(
                    previous_state,
                    actuator_id,
                    actuator_configuration,
                )

                self.timestep_energy += power * seconds
                self.fill_level += fill_rate * seconds

            self.fill_level -= (
                s2_frbc_device_state_wrapper.S2FrbcDeviceStateWrapper.get_leakage_rate(
                    self.timestep, self.fill_level
                )
                * seconds
            )
            self.fill_level += self.timestep.forecasted_fill_level_usage
            self.bucket = (
                s2_frbc_device_state_wrapper.S2FrbcDeviceStateWrapper.calculate_bucket(
                    self.timestep, self.fill_level
                )
            )
            if (
                previous_state.system_description.valid_from
                == self.system_description.valid_from
            ):
                self.timer_elapse_map = previous_state.timer_elapse_map.copy()
                for (
                    actuator_id,
                    actuator_configuration,
                ) in (actuator_configurations or {}).items():
                    previous_operation_mode_id = previous_state.actuator_configurations[
                        actuator_id
                    ].operation_mode_id
                    new_operation_mode_id = actuator_configuration.operation_mode_id
                    if previous_operation_mode_id != new_operation_mode_id:
                        transition = s2_frbc_device_state_wrapper.S2FrbcDeviceStateWrapper.get_transition(
                            self.timestep,
                            actuator_id,
                            previous_operation_mode_id,
                            new_operation_mode_id,
                        )
                        last_timer_id = None
                        new_finished_at: datetime = datetime.min
                        if transition is not None:
                            for timer_id in transition.start_timers:
                                duration = s2_frbc_device_state_wrapper.S2FrbcDeviceStateWrapper.get_timer_duration(
                                    self.timestep, actuator_id, str(timer_id)
                                )
                                new_finished_at = self.timestep.start_date + duration
                                last_timer_id = timer_id
                            if last_timer_id is not None:
                                key = FrbcState.timer_key(
                                    actuator_id, str(last_timer_id)
                                )
                                self.timer_elapse_map[key] = new_finished_at
            else:
                self.timer_elapse_map = (
                    self.get_initial_timer_elapse_map_for_system_description(
                        self.system_description
                    )
                )
            # calculate scores
            target = self.timestep.get_target()
            if isinstance(target, TargetProfile.JouleElement):
                self.sum_squared_distance = (
                    previous_state.sum_squared_distance
                    + (target.joules - self.timestep_energy) ** 2
                )
                self.sum_energy_cost = previous_state.sum_energy_cost
            else:
                self.sum_squared_distance = previous_state.sum_squared_distance
                self.sum_energy_cost = previous_state.sum_energy_cost
            squared_constraint_violation = (
                previous_state.sum_squared_constraint_violation
            )
            if self.timestep.max_constraint is not None:
                if self.timestep_energy > self.timestep.max_constraint:
                    squared_constraint_violation += (
                        self.timestep_energy - self.timestep.max_constraint
                    ) ** 2
            if self.timestep.min_constraint is not None:
                if self.timestep_energy < self.timestep.min_constraint:
                    squared_constraint_violation += (
                        self.timestep.min_constraint - self.timestep_energy
                    ) ** 2
            self.sum_squared_constraint_violation = (
                previous_state.sum_squared_constraint_violation
                + squared_constraint_violation
            )
            self.sum_squared_energy = (
                previous_state.sum_squared_energy + self.timestep_energy**2
            )

            self.selection_reason: Optional[SelectionReason] = None
            self.actuator_configurations = actuator_configurations or {}
            for k in list(self.actuator_configurations.keys()):
                if isinstance(k, str):
                    self.actuator_configurations[k] = self.actuator_configurations.pop(
                        k
                    )

            self.timestep.add_state(self)

        else:
            FrbcState.transition_cache.clear()
            if device_state is not None:
                self.device_state = (
                    s2_frbc_device_state_wrapper.S2FrbcDeviceStateWrapper(device_state)
                )
            else:
                self.device_state = None  # type: ignore[assignment]
            self.timestep = timestep
            self.previous_state = None  # type: ignore[assignment]
            self.system_description = timestep.system_description
            self.fill_level = present_fill_level
            self.bucket = 0
            self.timestep_energy = 0.0
            self.sum_squared_distance = 0.0
            self.sum_squared_constraint_violation = 0.0
            self.sum_energy_cost = 0.0
            self.sum_squared_energy = 0.0
            self.selection_reason: Optional[SelectionReason] = None  # type: ignore[no-redef]
            self.actuator_configurations = {}
            self.timer_elapse_map = (
                self.get_initial_timer_elapse_map_for_system_description(
                    self.system_description
                )
            )
            for a in self.device_state.actuator_statuses:
                actuator_status = a
                actuators = self.system_description.actuators
                for actuator in actuators:
                    if actuator.id == a.actuator_id:
                        self.actuator_configurations[
                            str(a.actuator_id)
                        ] = S2ActuatorConfiguration(
                            str(actuator_status.active_operation_mode_id),
                            actuator_status.operation_mode_factor,
                        )

    @staticmethod
    def get_initial_timer_elapse_map_for_system_description(
        system_description: FRBCSystemDescription,
    ) -> Dict[tuple, datetime]:
        timer_elapse_map = {}
        for actuator in system_description.actuators:
            for timer in actuator.timers:
                key = FrbcState.timer_key(str(actuator.id), str(timer.id))
                timer_elapse_map[key] = datetime.min  # arbitrary day in the past
        return timer_elapse_map

    def calculate_state_values(
        self,
        previous_state: "FrbcState",
        actuator_configurations: Dict[str, S2ActuatorConfiguration],
    ):
        self.timestep_energy = 0.0
        self.fill_level = previous_state.fill_level
        seconds = self.timestep.get_duration_seconds()
        for actuator_id, actuator_configuration in actuator_configurations.items():
            om = self.device_state.get_operation_mode(
                self.timestep,
                actuator_id,
                actuator_configuration.operation_mode_id,
            )
            self.timestep_energy += (
                self.device_state.get_operation_mode_power(
                    om,
                    previous_state.fill_level,
                    actuator_configuration.factor,
                )
                * seconds
            )
            self.fill_level += (
                self.device_state.get_operation_mode_fill_rate(
                    om,
                    previous_state.fill_level,
                    actuator_configuration.factor,
                )
                * seconds
            )
        self.fill_level -= (
            s2_frbc_device_state_wrapper.S2FrbcDeviceStateWrapper.get_leakage_rate(
                self.timestep, self.fill_level
            )
            * seconds
        )
        self.fill_level += self.timestep.forecasted_fill_level_usage
        self.bucket = (
            s2_frbc_device_state_wrapper.S2FrbcDeviceStateWrapper.calculate_bucket(
                self.timestep, self.fill_level
            )
        )
        self.update_timers(previous_state, actuator_configurations)
        self.calculate_scores(previous_state)
        self.timestep.add_state(self)

    def update_timers(
        self,
        previous_state: "FrbcState",
        actuator_configurations: Dict[str, S2ActuatorConfiguration],
    ):
        if (
            previous_state.system_description.valid_from
            == self.system_description.valid_from
        ):
            self.timer_elapse_map = previous_state.timer_elapse_map.copy()
            for actuator_id, actuator_configuration in actuator_configurations.items():
                previous_operation_mode_id = previous_state.actuator_configurations[
                    actuator_id
                ].operation_mode_id
                new_operation_mode_id = actuator_configuration.operation_mode_id
                if previous_operation_mode_id != new_operation_mode_id:
                    transition = s2_frbc_device_state_wrapper.S2FrbcDeviceStateWrapper.get_transition(
                        self.timestep,
                        actuator_id,
                        previous_operation_mode_id,
                        new_operation_mode_id,
                    )
                    if transition is None:
                        continue
                    for timer_id in transition.start_timers:
                        duration = s2_frbc_device_state_wrapper.S2FrbcDeviceStateWrapper.get_timer_duration(
                            self.timestep, actuator_id, str(timer_id)
                        )
                        new_finished_at = self.timestep.start_date + duration
                        key = FrbcState.timer_key(actuator_id, str(timer_id))
                        self.timer_elapse_map[key] = new_finished_at
        else:
            self.timer_elapse_map = (
                self.get_initial_timer_elapse_map_for_system_description(
                    self.system_description
                )
            )

    def calculate_scores(self, previous_state: "FrbcState"):
        target = self.timestep.get_target()
        if isinstance(target, TargetProfile.JouleElement):
            self.sum_squared_distance = (
                previous_state.sum_squared_distance
                + (target.joules - self.timestep_energy) ** 2
            )
            self.sum_energy_cost = previous_state.sum_energy_cost

        else:
            self.sum_squared_distance = previous_state.sum_squared_distance
            self.sum_energy_cost = previous_state.sum_energy_cost
        squared_constraint_violation = previous_state.sum_squared_constraint_violation
        if (
            self.timestep.max_constraint is not None
            and self.timestep_energy > self.timestep.max_constraint
        ):
            squared_constraint_violation += (
                self.timestep_energy - self.timestep.max_constraint
            ) ** 2
        if (
            self.timestep.min_constraint is not None
            and self.timestep_energy < self.timestep.min_constraint
        ):
            squared_constraint_violation += (
                self.timestep.min_constraint - self.timestep_energy
            ) ** 2
        self.sum_squared_constraint_violation = (
            previous_state.sum_squared_constraint_violation
            + squared_constraint_violation
        )
        self.sum_squared_energy = (
            previous_state.sum_squared_energy + self.timestep_energy**2
        )

    @staticmethod
    def timer_key(actuator_id: str, timer_id: str) -> tuple:
        return (actuator_id, timer_id)

    def generate_next_timestep_states(self, target_timestep):
        all_actions = self.device_state.get_all_possible_actuator_configurations(
            target_timestep
        )
        # todo: try vectorizing this
        for action in all_actions:
            self.try_create_next_state(self, target_timestep, action)

    def _calculate_and_cache_op_mode_values(
        self,
        previous_state: "FrbcState",
        actuator_id: str,
        actuator_configuration: S2ActuatorConfiguration,
    ) -> Tuple[float, float]:
        discretized_fill_level = round(previous_state.fill_level, 4)
        cache_key = (
            actuator_id,
            actuator_configuration.operation_mode_id,
            actuator_configuration.factor,
            discretized_fill_level,
        )
        if cache_key in FrbcState.transition_cache:
            return FrbcState.transition_cache[cache_key]

        om = self.device_state.get_operation_mode(
            self.timestep,
            actuator_id,
            actuator_configuration.operation_mode_id,
        )
        power = self.device_state.get_operation_mode_power(
            om,
            previous_state.fill_level,
            actuator_configuration.factor,
        )
        fill_rate = self.device_state.get_operation_mode_fill_rate(
            om,
            previous_state.fill_level,
            actuator_configuration.factor,
        )

        FrbcState.transition_cache[cache_key] = (power, fill_rate)
        return power, fill_rate

    @staticmethod
    def try_create_next_state(
        previous_state: "FrbcState",
        target_timestep,
        actuator_configs_for_target_timestep: Dict[str, S2ActuatorConfiguration],
    ):
        if (
            previous_state.system_description.valid_from
            == target_timestep.system_description.valid_from
        ):
            for (
                actuator_id,
                actuator_configuration,
            ) in actuator_configs_for_target_timestep.items():

                # print all the keys in the previous_state.actuator_configurations
                # print(previous_state.actuator_configurations.keys())
                try:
                    previous_operation_mode_id = previous_state.actuator_configurations[
                        actuator_id
                    ].operation_mode_id
                except KeyError:
                    raise KeyError(f"UUID {actuator_id} not in actuator configurations")

                new_operation_mode_id = actuator_configuration.operation_mode_id
                if previous_operation_mode_id != new_operation_mode_id:
                    transition = s2_frbc_device_state_wrapper.S2FrbcDeviceStateWrapper.get_transition(
                        target_timestep,
                        actuator_id,
                        previous_operation_mode_id,
                        new_operation_mode_id,
                    )
                    if transition is None:
                        return False
                    for timer_id in transition.blocking_timers:
                        timer_is_finished_at = previous_state.timer_elapse_map.get(
                            FrbcState.timer_key(actuator_id, str(timer_id))
                        )
                        if (
                            timer_is_finished_at
                            and timer_is_finished_at.year != 1
                            and target_timestep.start_date
                            < timer_is_finished_at.astimezone(
                                target_timestep.start_date.tzinfo
                            )
                        ):
                            return False
        FrbcState(
            timestep=target_timestep,
            previous_state=previous_state,
            actuator_configurations=actuator_configs_for_target_timestep,
            present_fill_level=0,
        )
        return True

    def is_preferable_than(self, other_state: "FrbcState") -> SelectionResult:
        other_violation = other_state.sum_squared_constraint_violation
        other_distance = other_state.sum_squared_distance
        other_cost = other_state.sum_energy_cost
        other_energy = other_state.sum_squared_energy

        if (
            abs(self.sum_squared_constraint_violation - other_violation)
            >= self.constraint_epsilon
        ):
            return SelectionResult(
                result=self.sum_squared_constraint_violation < other_violation,
                reason=SelectionReason.CONGESTION_CONSTRAINT,
            )
        elif abs(self.sum_squared_distance - other_distance) >= self.constraint_epsilon:
            return SelectionResult(
                result=self.sum_squared_distance < other_distance,
                reason=SelectionReason.ENERGY_TARGET,
            )
        elif abs(self.sum_energy_cost - other_cost) >= self.tariff_epsilon:
            return SelectionResult(
                result=self.sum_energy_cost < other_cost,
                reason=SelectionReason.TARIFF_TARGET,
            )
        else:
            return SelectionResult(
                result=self.sum_squared_energy < other_energy,
                reason=SelectionReason.MIN_ENERGY,
            )

    def is_within_fill_level_range(self):
        fill_level_range = self.system_description.storage.fill_level_range
        return (
            self.fill_level >= fill_level_range.start_of_range
            and self.fill_level <= fill_level_range.end_of_range
        )

    def get_fill_level_distance(self):
        fill_level_range = self.system_description.storage.fill_level_range
        if self.fill_level < fill_level_range.start_of_range:
            return fill_level_range.start_of_range - self.fill_level
        else:
            return self.fill_level - fill_level_range.end_of_range

    def set_selection_reason(self, selection_reason):
        self.selection_reason = selection_reason
