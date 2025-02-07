import logging
from datetime import datetime, timedelta
from s2python.frbc import (
    FRBCSystemDescription,
)
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from flexmeasures_s2.profile_steering.frbc.s2_frbc_device_state_wrapper import (
    S2FrbcDeviceStateWrapper,
)
from flexmeasures_s2.profile_steering.frbc.s2_frbc_actuator_configuration import S2ActuatorConfiguration
from flexmeasures_s2.profile_steering.frbc.frbc_timestep import FrbcTimestep
from flexmeasures_s2.profile_steering.frbc.selection_reason_result import SelectionResult, SelectionReason
from typing import Dict, Optional


class FrbcState:
    constraint_epsilon = 1e-4
    tariff_epsilon = 0.5

    def __init__(
        self,
        device_state: S2FrbcDeviceStateWrapper,
        timestep: FrbcTimestep,
        previous_state: Optional["FrbcState"] = None,
        actuator_configurations: Optional[Dict[str, S2ActuatorConfiguration]] = None,
    ):
        self.device_state = device_state
        self.timestep = timestep
        self.previous_state = previous_state
        self.system_description = timestep.get_system_description()
        self.fill_level = (
            self.system_description.get_storage().get_status().get_present_fill_level()
        )
        self.bucket = 0
        self.timestep_energy = 0
        self.sum_squared_distance = 0
        self.sum_squared_constraint_violation = 0
        self.sum_energy_cost = 0
        self.sum_squared_energy = 0
        self.selection_reason = None
        self.actuator_configurations = actuator_configurations or {}
        self.timer_elapse_map = (
            self.get_initial_timer_elapse_map_for_system_description(
                self.system_description
            )
        )

        if previous_state is None:
            for actuator in self.system_description.get_actuators():
                actuator_status = actuator.get_status()
                actuator_config = S2ActuatorConfiguration(
                    actuator_status.get_active_operation_mode_id(),
                    actuator_status.get_operation_mode_factor(),
                )
                self.actuator_configurations[actuator.get_id()] = actuator_config
        else:
            self.calculate_state_values(previous_state, actuator_configurations)

    @staticmethod
    def get_initial_timer_elapse_map_for_system_description(
        system_description: FRBCSystemDescription,
    ) -> Dict[str, datetime]:
        timer_elapse_map = {}
        for actuator in system_description.get_actuators():
            for timer in actuator.get_timers():
                timer_elapse_map[
                    FrbcState.timer_key(actuator.get_id(), timer.get_id())
                ] = timer.get_finished_at()
        return timer_elapse_map

    def calculate_state_values(
        self,
        previous_state: "FrbcState",
        actuator_configurations: Dict[str, S2ActuatorConfiguration],
    ):
        self.timestep_energy = 0
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
            S2FrbcDeviceStateWrapper.get_leakage_rate(self.timestep, self.fill_level)
            * seconds
        )
        self.fill_level += self.timestep.get_forecasted_usage()
        self.bucket = S2FrbcDeviceStateWrapper.calculate_bucket(
            self.timestep, self.fill_level
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
                    transition = S2FrbcDeviceStateWrapper.get_transition(
                        self.timestep,
                        actuator_id,
                        previous_operation_mode_id,
                        new_operation_mode_id,
                    )
                    for timer_id in transition.get_start_timers():
                        duration = S2FrbcDeviceStateWrapper.get_timer_duration(
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
        elif isinstance(target, TargetProfile.TariffElement):
            self.sum_squared_distance = previous_state.get_sum_squared_distance()
            self.sum_energy_cost = (
                previous_state.get_sum_energy_cost()
                + target.get_tariff() * (self.timestep_energy / 3_600_000)
            )
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
            previous_state.get_sum_squared_energy() + self.timestep_energy**2
        )

    @staticmethod
    def timer_key(actuator_id: str, timer_id: str) -> str:
        return f"{actuator_id}-{timer_id}"

    def generate_next_timestep_states(self, target_timestep: FrbcTimestep):
        all_actions = self.device_state.get_all_possible_actuator_configurations(
            target_timestep
        )
        for action in all_actions:
            FrbcState.try_create_next_state(self, target_timestep, action)

    @staticmethod
    def try_create_next_state(
        previous_state: "FrbcState",
        target_timestep: FrbcTimestep,
        actuator_configs_for_target_timestep: Dict[str, S2ActuatorConfiguration],
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
                    transition = S2FrbcDeviceStateWrapper.get_transition(
                        target_timestep,
                        actuator_id,
                        previous_operation_mode_id,
                        new_operation_mode_id,
                    )
                    if transition is None:
                        return False
                    for timer_id in transition.get_blocking_timers():
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
                self.sum_squared_constraint_violation
                < other_state.get_sum_squared_constraint_violation(),
                SelectionReason.CONGESTION_CONSTRAINT,
            )
        elif (
            abs(self.sum_squared_distance - other_state.get_sum_squared_distance())
            >= self.constraint_epsilon
        ):
            return SelectionResult(
                self.sum_squared_distance < other_state.get_sum_squared_distance(),
                SelectionReason.ENERGY_TARGET,
            )
        elif (
            abs(self.sum_energy_cost - other_state.get_sum_energy_cost())
            >= self.tariff_epsilon
        ):
            return SelectionResult(
                self.sum_energy_cost < other_state.get_sum_energy_cost(),
                SelectionReason.TARIFF_TARGET,
            )
        else:
            return SelectionResult(
                self.sum_squared_energy < other_state.get_sum_squared_energy(),
                SelectionReason.MIN_ENERGY,
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

    def get_fill_level(self):
        return self.fill_level

    def get_bucket(self):
        return self.bucket

    def get_timestep_energy(self):
        return self.timestep_energy

    def get_sum_squared_distance(self):
        return self.sum_squared_distance

    def get_sum_squared_constraint_violation(self):
        return self.sum_squared_constraint_violation

    def get_sum_energy_cost(self):
        return self.sum_energy_cost

    def get_sum_squared_energy(self):
        return self.sum_squared_energy

    def get_timer_elapse_map(self):
        return self.timer_elapse_map

    def set_selection_reason(self, selection_reason: SelectionReason):
        self.selection_reason = selection_reason

    def get_selection_reason(self):
        return self.selection_reason
