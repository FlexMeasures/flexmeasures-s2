from datetime import datetime
from typing import Optional, Dict, TYPE_CHECKING
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_actuator_configuration import (
    S2DdbcActuatorConfiguration,
)

if TYPE_CHECKING:
    from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_device_state_wrapper import (
        S2DdbcDeviceStateWrapper,
    )
    from flexmeasures_s2.profile_steering.device_planner.ddbc.ddbc_timestep import (
        DdbcTimestep,
    )


class DdbcState:
    """Represents a state in the DDBC planning algorithm."""

    CONSTRAINT_EPSILON = 1e-4

    def __init__(
        self,
        device_state_wrapper: "S2DdbcDeviceStateWrapper",
        timestep: "DdbcTimestep",
        previous_state: Optional["DdbcState"] = None,
        actuator_configurations: Optional[
            Dict[str, S2DdbcActuatorConfiguration]
        ] = None,
    ):
        """Initialize state. If previous_state is None, this is state zero."""
        self.device_state_wrapper = device_state_wrapper
        self.timestep = timestep
        self.previous_state = previous_state

        if previous_state is None:
            self._init_state_zero()
        else:
            assert (
                actuator_configurations is not None
            ), "actuator_configurations must not be None when previous_state is provided"
            self._init_from_previous_state(actuator_configurations)

    def _init_state_zero(self):
        """Initialize as state zero (initial state)."""
        self.supply_rate = 0.0
        self.timestep_energy = 0.0
        self.sum_squared_distance = 0.0
        self.sum_squared_constraint_violation = 0.0
        self.sum_energy_cost = 0.0
        self.sum_natural_gas_cost = 0.0
        self.sum_squared_energy = 0.0

        self.actuator_configurations: Dict[str, S2DdbcActuatorConfiguration] = {}

        actuator_statuses = self.device_state_wrapper.get_actuator_statuses()

        for actuator in self.timestep.get_system_description().actuators:
            actuator_id_str = str(actuator.id)
            actuator_status = actuator_statuses.get(actuator_id_str)

            if actuator_status is None:
                continue

            # Convert active_operation_mode_id to string to handle UUID objects
            active_om_id = actuator_status.active_operation_mode_id
            if hasattr(active_om_id, "root"):
                active_om_id_str = str(active_om_id.root)
            else:
                active_om_id_str = str(active_om_id)

            om = self.device_state_wrapper.get_operation_mode(
                self.timestep, actuator_id_str, active_om_id_str
            )

            factor = float(actuator_status.operation_mode_factor)
            actuator_config = om.convert_to_actuator_config(factor)
            self.actuator_configurations[actuator_id_str] = actuator_config

        self.timer_elapse_map = (
            self._get_initial_timer_elapse_map_for_system_description(
                self.timestep.get_system_description()
            )
        )
        self.gas_price_per_liter = (
            self.device_state_wrapper.get_gas_price_per_m3() / 1000.0
        )

    def _init_from_previous_state(
        self, actuator_configurations: Dict[str, S2DdbcActuatorConfiguration]
    ):
        """Initialize from a previous state."""
        assert self.previous_state is not None, "previous_state must not be None"
        self.gas_price_per_liter = self.previous_state.gas_price_per_liter

        self.actuator_configurations = self._calculate_missing_factor(
            actuator_configurations, self.timestep.get_avg_demand_rate_forecast()
        )

        timestep_energy = 0.0
        timestep_natural_gas_liters = 0.0
        timestep_supply_rate = 0.0
        seconds = self.timestep.get_duration_seconds()

        for actuator_id, actuator_configuration in self.actuator_configurations.items():
            om = self.device_state_wrapper.get_operation_mode(
                self.timestep,
                actuator_id,
                actuator_configuration.get_operation_mode_id(),
            )
            timestep_supply_rate += om.get_operation_mode_supply_rate(
                actuator_configuration.get_factor()
            )
            timestep_energy += (
                om.get_operation_mode_electrical_power(
                    actuator_configuration.get_factor()
                )
                * seconds
            )
            timestep_natural_gas_liters += (
                om.get_operation_mode_gas_consumption(
                    actuator_configuration.get_factor()
                )
                * seconds
            )

        self.timestep_energy = timestep_energy
        self.supply_rate = timestep_supply_rate

        self._update_timer_elapse_map()
        self._calculate_scores(timestep_natural_gas_liters)

        self.timestep.add_state(self)

    def _update_timer_elapse_map(self):
        """Update timers based on transitions."""
        if (
            self.previous_state.get_system_description().valid_from
            == self.get_system_description().valid_from
        ):
            self.timer_elapse_map = dict(self.previous_state.timer_elapse_map)

            for actuator_id, actuator_config in self.actuator_configurations.items():
                previous_operation_mode_id = (
                    self.previous_state.actuator_configurations[
                        actuator_id
                    ].get_operation_mode_id()
                )
                new_operation_mode_id = actuator_config.get_operation_mode_id()

                if previous_operation_mode_id != new_operation_mode_id:
                    from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_device_state_wrapper import (
                        S2DdbcDeviceStateWrapper,
                    )

                    transition = S2DdbcDeviceStateWrapper.get_transition(
                        self.timestep,
                        actuator_id,
                        previous_operation_mode_id,
                        new_operation_mode_id,
                    )

                    for timer_id in transition.start_timers:
                        duration = S2DdbcDeviceStateWrapper.get_timer_duration(
                            self.timestep, actuator_id, timer_id
                        )
                        new_finished_at = self.timestep.get_start_date() + duration
                        self.timer_elapse_map[
                            self._timer_key(actuator_id, timer_id)
                        ] = new_finished_at
        else:
            self.timer_elapse_map = (
                self._get_initial_timer_elapse_map_for_system_description(
                    self.get_system_description()
                )
            )

    def _calculate_scores(self, timestep_natural_gas_liters: float):
        """Calculate scoring metrics for this state."""
        assert self.previous_state is not None, "previous_state must not be None"
        target = self.timestep.get_target()

        if isinstance(target, TargetProfile.JouleElement):
            self.sum_squared_distance = (
                self.previous_state.sum_squared_distance
                + (target.joules - self.timestep_energy) ** 2
            )
            self.sum_energy_cost = self.previous_state.sum_energy_cost
        elif isinstance(target, TargetProfile.TariffElement):
            self.sum_squared_distance = self.previous_state.sum_squared_distance
            self.sum_energy_cost = (
                self.previous_state.sum_energy_cost
                + target.tariff * (self.timestep_energy / 3_600_000.0)
            )
        else:
            self.sum_squared_distance = self.previous_state.sum_squared_distance
            self.sum_energy_cost = self.previous_state.sum_energy_cost

        squared_constraint_violation = (
            self.previous_state.sum_squared_constraint_violation
        )

        if self.timestep.get_max_constraint() is not None:
            if self.timestep_energy > self.timestep.get_max_constraint():
                squared_constraint_violation += (
                    self.timestep_energy - self.timestep.get_max_constraint()
                ) ** 2

        if self.timestep.get_min_constraint() is not None:
            if self.timestep_energy < self.timestep.get_min_constraint():
                squared_constraint_violation += (
                    self.timestep.get_min_constraint() - self.timestep_energy
                ) ** 2

        self.sum_natural_gas_cost = self.previous_state.sum_natural_gas_cost + (
            timestep_natural_gas_liters * self.gas_price_per_liter
        )
        self.sum_squared_constraint_violation = squared_constraint_violation
        self.sum_squared_energy = (
            self.previous_state.sum_squared_energy + self.timestep_energy**2
        )

    def _calculate_missing_factor(
        self,
        actuator_configurations: Dict[str, S2DdbcActuatorConfiguration],
        desired_supply_rate: Optional[float],
    ) -> Dict[str, S2DdbcActuatorConfiguration]:
        """Calculate the missing factor (if any) and return a new map with the factor filled in."""
        if desired_supply_rate is None:
            return actuator_configurations

        missing_factor_actuator_id = None

        for actuator_id, config in actuator_configurations.items():
            if (
                config.get_factor() is None
                and self.device_state_wrapper.operation_mode_uses_factor(
                    self.timestep, actuator_id, config.get_operation_mode_id()
                )
            ):
                missing_factor_actuator_id = actuator_id
                break

        if missing_factor_actuator_id is None:
            return actuator_configurations

        supply_rate = 0.0
        for actuator_id, actuator_configuration in actuator_configurations.items():
            if actuator_id != missing_factor_actuator_id:
                om = self.device_state_wrapper.get_operation_mode(
                    self.timestep,
                    actuator_id,
                    actuator_configuration.get_operation_mode_id(),
                )
                supply_rate += om.get_operation_mode_supply_rate(
                    actuator_configuration.get_factor()
                )

        missing_supply_rate = desired_supply_rate - supply_rate
        om = self.device_state_wrapper.get_operation_mode(
            self.timestep,
            missing_factor_actuator_id,
            actuator_configurations[missing_factor_actuator_id].get_operation_mode_id(),
        )
        supply_range = om.supply_range
        calculated_factor = (
            missing_supply_rate - supply_range.get_start_of_range()
        ) / (supply_range.get_end_of_range() - supply_range.get_start_of_range())

        calculated_factor = min(1.0, max(0.0, calculated_factor))

        result = dict(actuator_configurations)
        result[missing_factor_actuator_id] = om.convert_to_actuator_config(
            calculated_factor
        )
        return result

    @staticmethod
    def _timer_key(actuator_id: str, timer_id: str) -> str:
        """Generate a key for timer elapse map."""
        return f"{actuator_id}-{timer_id}"

    @staticmethod
    def _get_initial_timer_elapse_map_for_system_description(
        system_description,
    ) -> Dict[str, datetime]:
        """Get initial timer elapse map for a system description."""
        timer_elapse_map = {}

        for actuator in system_description.actuators:
            for timer in actuator.timers:
                timer_elapse_map[
                    DdbcState._timer_key(actuator.id, timer.id)
                ] = timer.finished_at

        return timer_elapse_map

    @staticmethod
    def try_create_next_state(
        previous_state: "DdbcState",
        target_timestep: "DdbcTimestep",
        actuator_configs_for_target_timestep: Dict[str, S2DdbcActuatorConfiguration],
    ) -> bool:
        """Try to create a next state. Returns True if successful, False if constraints are violated."""
        from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_device_state_wrapper import (
            S2DdbcDeviceStateWrapper,
        )

        if (
            previous_state.get_system_description().valid_from
            == target_timestep.get_system_description().valid_from
        ):
            for actuator_id, config in actuator_configs_for_target_timestep.items():
                previous_operation_mode_id = previous_state.actuator_configurations[
                    actuator_id
                ].get_operation_mode_id()
                new_operation_mode_id = config.get_operation_mode_id()

                if previous_operation_mode_id != new_operation_mode_id:
                    transition = S2DdbcDeviceStateWrapper.get_transition(
                        target_timestep,
                        actuator_id,
                        previous_operation_mode_id,
                        new_operation_mode_id,
                    )

                    if transition is None:
                        return False

                    for timer_id in transition.blocking_timers:
                        timer_is_finished_at = previous_state.timer_elapse_map.get(
                            DdbcState._timer_key(actuator_id, timer_id)
                        )
                        if (
                            timer_is_finished_at is not None
                            and target_timestep.get_start_date() < timer_is_finished_at
                        ):
                            return False

        DdbcState(
            previous_state.device_state_wrapper,
            target_timestep,
            previous_state,
            actuator_configs_for_target_timestep,
        )
        return True

    def generate_next_timestep_states(self, target_timestep: "DdbcTimestep"):
        """Generate all possible states for the next timestep."""
        all_actions = (
            self.device_state_wrapper.get_all_possible_actuator_configurations(
                target_timestep
            )
        )
        for action_map in all_actions:
            self.try_create_next_state(self, target_timestep, action_map)

    def is_preferable_than(self, other: "DdbcState") -> bool:
        """Determine if this state is better than another state."""
        if (
            abs(
                self.sum_squared_constraint_violation
                - other.sum_squared_constraint_violation
            )
            >= self.CONSTRAINT_EPSILON
        ):
            return (
                self.sum_squared_constraint_violation
                < other.sum_squared_constraint_violation
            )
        else:
            if self.sum_squared_distance != 0:
                raise RuntimeError("Expect distance 0 as only tariff elements")

            if (
                abs(self.sum_squared_distance - other.sum_squared_distance)
                >= self.CONSTRAINT_EPSILON
            ):
                return self.sum_squared_distance < other.sum_squared_distance
            else:
                total_cost = self.sum_energy_cost + self.sum_natural_gas_cost
                other_total_cost = other.sum_energy_cost + other.sum_natural_gas_cost

                if abs(total_cost - other_total_cost) >= self.CONSTRAINT_EPSILON:
                    return total_cost < other_total_cost
                else:
                    return self.sum_squared_energy > other.sum_squared_energy

    def supply_demand_distance(self) -> float:
        """Calculate distance between supply and demand."""
        return abs(self.supply_rate - self.timestep.get_avg_demand_rate_forecast())

    def get_timestep(self) -> "DdbcTimestep":
        return self.timestep

    def get_system_description(self):
        return self.timestep.get_system_description()

    def get_device_state_wrapper(self) -> "S2DdbcDeviceStateWrapper":
        return self.device_state_wrapper

    def get_previous_state(self) -> Optional["DdbcState"]:
        return self.previous_state

    def get_actuator_configurations(self) -> Dict[str, S2DdbcActuatorConfiguration]:
        return self.actuator_configurations

    def get_supply_rate(self) -> float:
        return self.supply_rate

    def get_timestep_energy(self) -> float:
        return self.timestep_energy

    def get_timer_elapse_map(self) -> Dict[str, datetime]:
        return self.timer_elapse_map
