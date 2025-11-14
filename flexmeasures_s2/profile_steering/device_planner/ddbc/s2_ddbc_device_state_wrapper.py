from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional, Any, TYPE_CHECKING
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_device_state import (
    S2DdbcDeviceState,
)
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_actuator_configuration import (
    S2DdbcActuatorConfiguration,
)
from flexmeasures_s2.profile_steering.device_planner.ddbc.ddbc_operation_mode_wrapper import (
    DdbcOperationModeWrapper,
)

if TYPE_CHECKING:
    from flexmeasures_s2.profile_steering.device_planner.ddbc.ddbc_timestep import (
        DdbcTimestep,
    )


class S2DdbcDeviceStateWrapper:
    """
    Wrapper for S2DdbcDeviceState that adds utility functions and caching.
    """

    EPSILON = 1e-4
    STRATIFICATION_LAYERS = 50

    def __init__(self, device_state: S2DdbcDeviceState):
        self.device_state = device_state

        self.actuator_operation_mode_map_per_timestep: Dict[
            datetime, Dict[str, List[str]]
        ] = {}
        self.all_actions: Dict[
            datetime, List[Dict[str, S2DdbcActuatorConfiguration]]
        ] = {}
        self.operation_mode_uses_factor_map: Dict[str, bool] = {}
        self.operation_modes: Dict[str, DdbcOperationModeWrapper] = {}

    def is_online(self) -> bool:
        return self.device_state.is_device_online()

    def get_power_forecast(self) -> Any:
        return self.device_state.get_power_forecast()

    def get_system_descriptions(self) -> List[Any]:
        return self.device_state.get_system_descriptions()

    def get_demand_forecasts(self) -> List[Any]:
        return self.device_state.get_demand_forecasts()

    def get_energy_in_current_timestep(self) -> float:
        return self.device_state.get_energy_in_current_timestep()

    def get_gas_price_per_m3(self) -> float:
        return self.device_state.get_gas_price_per_m3()

    def get_actuator_statuses(self):
        return self.device_state.get_actuator_statuses()

    def get_actuators(self, target_timestep: "DdbcTimestep") -> Set[str]:
        """Get all actuator IDs for a timestep."""
        actuator_operation_mode_map = self.actuator_operation_mode_map_per_timestep.get(
            target_timestep.get_start_date()
        )
        if actuator_operation_mode_map is None:
            actuator_operation_mode_map = self._create_actuator_operation_mode_map(
                target_timestep
            )
        return set(actuator_operation_mode_map.keys())

    def get_normal_operation_modes_for_actuator(
        self, target_timestep: "DdbcTimestep", actuator_id: str
    ) -> List[str]:
        """Get all normal operation mode IDs for an actuator."""
        actuator_operation_mode_map = self.actuator_operation_mode_map_per_timestep.get(
            target_timestep.get_start_date()
        )
        if actuator_operation_mode_map is None:
            actuator_operation_mode_map = self._create_actuator_operation_mode_map(
                target_timestep
            )
        return actuator_operation_mode_map[actuator_id]

    def _create_actuator_operation_mode_map(
        self, target_timestep: "DdbcTimestep"
    ) -> Dict[str, List[str]]:
        """Create a map from actuator ID to list of normal operation mode IDs."""
        actuator_operation_mode_map: Dict[str, List[str]] = {}

        for actuator in target_timestep.get_system_description().actuators:
            operation_mode_ids = [
                om.id
                for om in actuator.operation_modes
                if not om.abnormal_condition_only
            ]
            actuator_operation_mode_map[actuator.id] = operation_mode_ids

        self.actuator_operation_mode_map_per_timestep[
            target_timestep.get_start_date()
        ] = actuator_operation_mode_map
        return actuator_operation_mode_map

    def get_operation_mode(
        self, target_timestep: "DdbcTimestep", actuator_id: str, operation_mode_id: str
    ) -> DdbcOperationModeWrapper:
        """Get an operation mode wrapper."""
        om_key = f"{actuator_id}-{operation_mode_id}"

        if om_key in self.operation_modes:
            return self.operation_modes[om_key]

        found_actuator_description = None
        for actuator_description in target_timestep.get_system_description().actuators:
            if (
                str(actuator_description.id) == actuator_id
                or actuator_description.id == actuator_id
            ):
                found_actuator_description = actuator_description
                break

        if found_actuator_description is None:
            raise ValueError(f"Actuator {actuator_id} not found")

        for operation_mode in found_actuator_description.operation_modes:
            operation_mode_id_obj = (
                operation_mode.Id
                if hasattr(operation_mode, "Id")
                else operation_mode.id
            )
            if hasattr(operation_mode_id_obj, "root"):
                operation_mode_id_str = str(operation_mode_id_obj.root)
            else:
                operation_mode_id_str = str(operation_mode_id_obj)
            if operation_mode_id_str == str(operation_mode_id):
                found_operation_mode = DdbcOperationModeWrapper(operation_mode)
                self.operation_modes[om_key] = found_operation_mode
                return found_operation_mode

        raise ValueError(
            f"Operation mode {operation_mode_id} not found for actuator {actuator_id}"
        )

    def operation_mode_uses_factor(
        self, target_timestep: "DdbcTimestep", actuator_id: str, operation_mode_id: str
    ) -> bool:
        """Check if an operation mode uses a factor."""
        key = f"{actuator_id}-{operation_mode_id}"
        result_from_map = self.operation_mode_uses_factor_map.get(key)

        if result_from_map is None:
            result = self.get_operation_mode(
                target_timestep, actuator_id, operation_mode_id
            ).uses_factor_method()
            self.operation_mode_uses_factor_map[key] = result
            return result
        else:
            return result_from_map

    def get_all_possible_actuator_configurations(
        self, target_timestep: "DdbcTimestep"
    ) -> List[Dict[str, S2DdbcActuatorConfiguration]]:
        """Get all possible actuator configurations for a timestep."""
        timestep_date = target_timestep.get_start_date()

        if timestep_date in self.all_actions:
            return self.all_actions[timestep_date]

        possible_actuator_configs: Dict[str, List[S2DdbcActuatorConfiguration]] = {}

        for actuator_id in self.get_actuators(target_timestep):
            actuator_list: List[S2DdbcActuatorConfiguration] = []

            for operation_mode_id in self.get_normal_operation_modes_for_actuator(
                target_timestep, actuator_id
            ):
                if self.operation_mode_uses_factor(
                    target_timestep, actuator_id, operation_mode_id
                ):
                    actuator_list.append(
                        S2DdbcActuatorConfiguration(operation_mode_id, None, None, {})
                    )
                else:
                    om = self.get_operation_mode(
                        target_timestep, actuator_id, operation_mode_id
                    )
                    actuator_list.append(om.convert_to_actuator_config(0.0))

            possible_actuator_configs[actuator_id] = actuator_list

        keys = list(possible_actuator_configs.keys())
        operation_mode_configurations: List[Dict[str, S2DdbcActuatorConfiguration]] = []

        combination = [0] * len(keys)
        operation_mode_configurations.append(
            self._combination_to_map(combination, keys, possible_actuator_configs)
        )

        while self._increase(combination, keys, possible_actuator_configs):
            operation_mode_configurations.append(
                self._combination_to_map(combination, keys, possible_actuator_configs)
            )

        finished = False
        while not finished:
            found_multiple = False
            for i in range(len(operation_mode_configurations)):
                c = operation_mode_configurations[i]
                if self._contains_multiple_oms_with_factor(c, target_timestep):
                    operation_mode_configurations.pop(i)
                    operation_mode_configurations.extend(
                        self._apply_stratification_layers(c, target_timestep)
                    )
                    found_multiple = True
                    break
            finished = not found_multiple

        self.all_actions[timestep_date] = operation_mode_configurations
        return operation_mode_configurations

    def _apply_stratification_layers(
        self,
        configurations: Dict[str, S2DdbcActuatorConfiguration],
        target_timestep: "DdbcTimestep",
    ) -> List[Dict[str, S2DdbcActuatorConfiguration]]:
        """Apply stratification layers to configurations with factors."""
        actuator_id = None
        operation_mode_id = None
        copy = dict(configurations)

        for config_actuator_id, config in list(copy.items()):
            if self.operation_mode_uses_factor(
                target_timestep, config_actuator_id, config.get_operation_mode_id()
            ):
                actuator_id = config_actuator_id
                operation_mode_id = config.get_operation_mode_id()
                del copy[config_actuator_id]
                break

        if actuator_id is None or operation_mode_id is None:
            raise ValueError("No actuator with factor found")

        configs: List[Dict[str, S2DdbcActuatorConfiguration]] = []
        om = self.get_operation_mode(target_timestep, actuator_id, operation_mode_id)

        for i in range(self.STRATIFICATION_LAYERS + 1):
            config_actuator_map = dict(copy)
            factor_for_actuator = i * (1.0 / self.STRATIFICATION_LAYERS)
            config_actuator_map[actuator_id] = om.convert_to_actuator_config(
                factor_for_actuator
            )
            configs.append(config_actuator_map)

        return configs

    def _contains_multiple_oms_with_factor(
        self,
        configurations: Dict[str, S2DdbcActuatorConfiguration],
        target_timestep: "DdbcTimestep",
    ) -> bool:
        """Check if configurations contain multiple operation modes with factors."""
        found_one = False
        for actuator_id, config in configurations.items():
            if self.operation_mode_uses_factor(
                target_timestep, actuator_id, config.get_operation_mode_id()
            ):
                if found_one:
                    return True
                else:
                    found_one = True
        return False

    def _combination_to_map(
        self,
        cur: List[int],
        keys: List[str],
        possible_actuator_configs: Dict[str, List[S2DdbcActuatorConfiguration]],
    ) -> Dict[str, S2DdbcActuatorConfiguration]:
        """Convert combination indices to a configuration map."""
        combination: Dict[str, S2DdbcActuatorConfiguration] = {}
        for i in range(len(keys)):
            key = keys[i]
            combination[key] = possible_actuator_configs[key][cur[i]]
        return combination

    def _increase(
        self,
        cur: List[int],
        keys: List[str],
        possible_actuator_configs: Dict[str, List[S2DdbcActuatorConfiguration]],
    ) -> bool:
        """Increase combination indices."""
        cur[0] += 1
        for i in range(len(keys)):
            key = keys[i]
            if cur[i] >= len(possible_actuator_configs[key]):
                if i + 1 >= len(keys):
                    return False
                cur[i] = 0
                cur[i + 1] += 1
        return True

    @staticmethod
    def get_transition(
        target_timestep: "DdbcTimestep",
        actuator_id: str,
        from_operation_mode_id: str,
        to_operation_mode_id: str,
    ) -> Optional[Any]:
        """Get a transition between operation modes."""
        actuator_description = S2DdbcDeviceStateWrapper.get_actuator_description(
            target_timestep, actuator_id
        )

        found_transition = None
        for transition in actuator_description.transitions:
            if (
                getattr(transition, "from", None) == from_operation_mode_id
                and transition.to == to_operation_mode_id
            ):
                found_transition = transition
                break

        return found_transition

    @staticmethod
    def get_timer_duration_milliseconds(
        target_timestep: "DdbcTimestep", actuator_id: str, timer_id: str
    ) -> int:
        """Get timer duration in milliseconds."""
        actuator_description = S2DdbcDeviceStateWrapper.get_actuator_description(
            target_timestep, actuator_id
        )
        timer = next(t for t in actuator_description.timers if t.id == timer_id)
        return timer.duration

    @staticmethod
    def get_timer_duration(
        target_timestep: "DdbcTimestep", actuator_id: str, timer_id: str
    ) -> timedelta:
        """Get timer duration as timedelta."""
        return timedelta(
            milliseconds=S2DdbcDeviceStateWrapper.get_timer_duration_milliseconds(
                target_timestep, actuator_id, timer_id
            )
        )

    @staticmethod
    def get_actuator_description(
        target_timestep: "DdbcTimestep", actuator_id: str
    ) -> Any:
        """Get actuator description by ID."""
        found_actuator_description = None
        for actuator_description in target_timestep.get_system_description().actuators:
            if (
                str(actuator_description.id) == actuator_id
                or actuator_description.id == actuator_id
            ):
                found_actuator_description = actuator_description
                break

        if found_actuator_description is None:
            raise ValueError(f"Actuator {actuator_id} not found")

        return found_actuator_description
