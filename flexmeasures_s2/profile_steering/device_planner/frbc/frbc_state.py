from datetime import datetime
from s2python.frbc import (
    FRBCSystemDescription,
)
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from s2python.frbc.frbc_actuator_status import FRBCActuatorStatus
import \
    flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state_wrapper as s2_frbc_device_state_wrapper

from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_actuator_configuration import (
    S2ActuatorConfiguration,
)
import \
    flexmeasures_s2.profile_steering.device_planner.frbc.frbc_timestep as frbc_timestep
from flexmeasures_s2.profile_steering.device_planner.frbc.selection_reason_result import (
    SelectionResult,
    SelectionReason,
)
from typing import Dict, Optional


class FrbcState:
    constraint_epsilon = 1e-4
    tariff_epsilon = 0.5

    def __init__(
            self,
            device_state,
            timestep,
            present_fill_level,
            previous_state: Optional["FrbcState"] = None,
            actuator_configurations: Optional[
                Dict[str, S2ActuatorConfiguration]] = None,
            actuator_statuses: Optional[
                Dict[str, FRBCActuatorStatus]] = None,
    ):
        self.device_state = device_state
        self.timestep = timestep
        self.previous_state = previous_state
        self.system_description = timestep.get_system_description()
        # TODO:  The Java code for s2 contains a status field for storage.
        #       This is not present in the S2FRBCSystemDescription.
        #       We should add it to the S2FRBCSystemDescription.
        self.fill_level = present_fill_level
        self.bucket = 0
        self.timestep_energy = 0.0
        self.sum_squared_distance = 0.0
        self.sum_squared_constraint_violation = 0.0
        self.sum_energy_cost = 0.0
        self.sum_squared_energy = 0.0
        self.selection_reason: Optional[SelectionReason] = None
        self.actuator_configurations = actuator_configurations or {}
        self.timer_elapse_map = (
            self.get_initial_timer_elapse_map_for_system_description(
                self.system_description
            )
        )
        self.actuator_statuses = actuator_statuses or {}
        # TODO: Same problem as the Storage message. There is no way to store the status
        if previous_state is None:
            for actuator_status in self.actuator_statuses.values():
                actuator_config = S2ActuatorConfiguration(
                    actuator_status.active_operation_mode_id,
                    actuator_status.operation_mode_factor,
                )
                self.actuator_configurations[str(actuator_status.actuator_id)] = actuator_config
        else:
            self.calculate_state_values(previous_state,
                                        self.actuator_configurations)

    @staticmethod
    def get_initial_timer_elapse_map_for_system_description(
            system_description: FRBCSystemDescription,
    ) -> Dict[str, datetime]:
        timer_elapse_map = {}
        for actuator in system_description.actuators:
            for timer in actuator.timers:
                timer_elapse_map[
                    FrbcState.timer_key(str(actuator.id), str(timer.id))
                ] = datetime.min  # arbitrary day in the past
                # TODO: Add the finished_at time to the timer class?
        return timer_elapse_map

    def calculate_state_values(
            self,
            previous_state: "FrbcState",
            actuator_configurations: Dict[str, S2ActuatorConfiguration],
    ):
        self.timestep_energy = 0.0
        self.fill_level = previous_state.get_fill_level()
        seconds = self.timestep.get_duration_seconds()
        for actuator_id, actuator_configuration in actuator_configurations.items():
            om = self.device_state.get_operation_mode(
                self.timestep,
                actuator_id,
                actuator_configuration.get_operation_mode_id(),
            )
            self.timestep_energy += (
                    self.device_state.get_operation_mode_power(
                        om,
                        previous_state.get_fill_level(),
                        actuator_configuration.get_factor(),
                    )
                    * seconds
            )
            self.fill_level += (
                    self.device_state.get_operation_mode_fill_rate(
                        om,
                        previous_state.get_fill_level(),
                        actuator_configuration.get_factor(),
                    )
                    * seconds
            )
        self.fill_level -= (
                s2_frbc_device_state_wrapper.S2FrbcDeviceStateWrapper.get_leakage_rate(
                    self.timestep, self.fill_level
                )
                * seconds
        )
        self.fill_level += self.timestep.get_forecasted_usage()
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
                previous_state.system_description.get_valid_from()
                == self.system_description.get_valid_from()
        ):
            self.timer_elapse_map = previous_state.get_timer_elapse_map().copy()
            for actuator_id, actuator_configuration in actuator_configurations.items():
                previous_operation_mode_id = (
                    previous_state.get_actuator_configurations()[
                        actuator_id
                    ].get_operation_mode_id()
                )
                new_operation_mode_id = actuator_configuration.get_operation_mode_id()
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
                            self.timestep, actuator_id, timer_id
                        )
                        new_finished_at = self.timestep.get_start_date() + duration
                        self.timer_elapse_map[
                            FrbcState.timer_key(actuator_id, timer_id)
                        ] = new_finished_at
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
                    previous_state.get_sum_squared_distance()
                    + (target.get_joules() - self.timestep_energy) ** 2
            )
            self.sum_energy_cost = previous_state.get_sum_energy_cost()

        else:
            self.sum_squared_distance = previous_state.get_sum_squared_distance()
            self.sum_energy_cost = previous_state.get_sum_energy_cost()
        squared_constraint_violation = (
            previous_state.get_sum_squared_constraint_violation()
        )
        if (
                self.timestep.get_max_constraint() is not None
                and self.timestep_energy > self.timestep.get_max_constraint()
        ):
            squared_constraint_violation += (
                                                    self.timestep_energy - self.timestep.get_max_constraint()
                                            ) ** 2
        if (
                self.timestep.get_min_constraint() is not None
                and self.timestep_energy < self.timestep.get_min_constraint()
        ):
            squared_constraint_violation += (
                                                    self.timestep.get_min_constraint() - self.timestep_energy
                                            ) ** 2
        self.sum_squared_constraint_violation = (
                previous_state.get_sum_squared_constraint_violation()
                + squared_constraint_violation
        )
        self.sum_squared_energy = (
                previous_state.get_sum_squared_energy() + self.timestep_energy ** 2
        )

    @staticmethod
    def timer_key(actuator_id: str, timer_id: str) -> str:
        return f"{actuator_id}-{timer_id}"

    def generate_next_timestep_states(self, target_timestep):
        all_actions = self.device_state.get_all_possible_actuator_configurations(
            target_timestep
        )
        for action in all_actions:
            FrbcState.try_create_next_state(self, target_timestep, action)

    @staticmethod
    def try_create_next_state(
            previous_state: "FrbcState",
            target_timestep,
            actuator_configs_for_target_timestep: Dict[
                str, S2ActuatorConfiguration],
    ):
        if (
                previous_state.get_system_description().get_valid_from()
                == target_timestep.get_system_description().get_valid_from()
        ):
            for (
                    actuator_id,
                    actuator_configuration,
            ) in actuator_configs_for_target_timestep.items():
                previous_operation_mode_id = (
                    previous_state.get_actuator_configurations()[
                        actuator_id
                    ].get_operation_mode_id()
                )
                new_operation_mode_id = actuator_configuration.get_operation_mode_id()
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
                        timer_is_finished_at = (
                            previous_state.get_timer_elapse_map().get(
                                FrbcState.timer_key(actuator_id, timer_id)
                            )
                        )
                        if (
                                timer_is_finished_at
                                and target_timestep.get_start_date() < timer_is_finished_at
                        ):
                            return False
        FrbcState(
            previous_state.device_state,
            target_timestep,
            previous_state,
            actuator_configs_for_target_timestep,
        )
        return True

    def is_preferable_than(self, other_state: "FrbcState") -> SelectionResult:
        if (
                abs(
                    self.sum_squared_constraint_violation
                    - other_state.get_sum_squared_constraint_violation()
                )
                >= self.constraint_epsilon
        ):
            return SelectionResult(
                result=self.sum_squared_constraint_violation
                       < other_state.get_sum_squared_constraint_violation(),
                reason=SelectionReason.CONGESTION_CONSTRAINT,
            )
        elif (
                abs(self.sum_squared_distance - other_state.get_sum_squared_distance())
                >= self.constraint_epsilon
        ):
            return SelectionResult(
                result=self.sum_squared_distance
                       < other_state.get_sum_squared_distance(),
                reason=SelectionReason.ENERGY_TARGET,
            )
        elif (
                abs(self.sum_energy_cost - other_state.get_sum_energy_cost())
                >= self.tariff_epsilon
        ):
            return SelectionResult(
                result=self.sum_energy_cost < other_state.get_sum_energy_cost(),
                reason=SelectionReason.TARIFF_TARGET,
            )
        else:
            return SelectionResult(
                result=self.sum_squared_energy < other_state.get_sum_squared_energy(),
                reason=SelectionReason.MIN_ENERGY,
            )

    def is_within_fill_level_range(self):
        fill_level_range = self.system_description.get_storage().get_fill_level_range()
        return (
                self.fill_level >= fill_level_range.get_start_of_range()
                and self.fill_level <= fill_level_range.get_end_of_range()
        )

    def get_fill_level_distance(self):
        fill_level_range = self.system_description.get_storage().get_fill_level_range()
        if self.fill_level < fill_level_range.get_start_of_range():
            return fill_level_range.get_start_of_range() - self.fill_level
        else:
            return self.fill_level - fill_level_range.get_end_of_range()

    def get_device_state(self):
        return self.device_state

    def get_previous_state(self):
        return self.previous_state

    def get_actuator_configurations(self):
        return self.actuator_configurations

    def get_fill_level(self) -> float:
        return self.fill_level

    def get_bucket(self) -> int:
        return self.bucket

    def get_timestep_energy(self) -> float:
        return self.timestep_energy

    def get_sum_squared_distance(self) -> float:
        return self.sum_squared_distance

    def get_sum_squared_constraint_violation(self) -> float:
        return self.sum_squared_constraint_violation

    def get_sum_energy_cost(self) -> float:
        return self.sum_energy_cost

    def get_sum_squared_energy(self) -> float:
        return self.sum_squared_energy

    def get_timer_elapse_map(self) -> Dict[str, datetime]:
        return self.timer_elapse_map

    def set_selection_reason(self, selection_reason):
        self.selection_reason = selection_reason

    def get_selection_reason(self) -> Optional[SelectionReason]:
        return self.selection_reason

    def get_system_description(self) -> FRBCSystemDescription:
        return self.system_description

    def get_timestep(self):
        return self.timestep
