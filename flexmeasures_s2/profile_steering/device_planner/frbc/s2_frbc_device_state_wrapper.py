from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from functools import lru_cache
import numpy as np

from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_actuator_configuration import (
    S2ActuatorConfiguration,
)
from s2python.common import CommodityQuantity
from flexmeasures_s2.profile_steering.device_planner.frbc.frbc_operation_mode_wrapper import (
    FrbcOperationModeWrapper,
)

if TYPE_CHECKING:
    from flexmeasures_s2.profile_steering.device_planner.frbc.frbc_timestep import (
        FrbcTimestep,
    )

from s2python.common.transition import Transition
from s2python.frbc import (
    FRBCLeakageBehaviour,
    FRBCLeakageBehaviourElement,
    FRBCActuatorDescription,
    FRBCActuatorStatus,
    FRBCStorageStatus,
)
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state import (
    S2FrbcDeviceState,
)


class S2FrbcDeviceStateWrapper:
    epsilon = 1e-4

    def __init__(self, device_state: S2FrbcDeviceState):
        self.device_state: S2FrbcDeviceState = device_state
        computational_params = self.device_state.get_computational_parameters()
        self.nr_of_buckets: int = computational_params.get_nr_of_buckets()
        self.nr_of_stratification_layers: int = (
            computational_params.get_stratification_layers()
        )
        self.actuator_operation_mode_map_per_timestep: Dict[
            datetime, Dict[str, List[str]]
        ] = {}
        self.all_actions: Dict[datetime, List[Dict[str, S2ActuatorConfiguration]]] = {}
        self.operation_mode_uses_factor_map: Dict[str, bool] = {}
        self.operation_modes: Dict[str, FrbcOperationModeWrapper] = {}

    @property
    def is_online(self) -> bool:
        return self.device_state.is_online

    def get_power_forecast(self) -> Any:
        return self.device_state.get_power_forecast()

    def get_system_descriptions(self) -> Any:
        return self.device_state.get_system_descriptions()

    def get_leakage_behaviours(self) -> Any:
        return self.device_state.get_leakage_behaviours()

    @property
    def usage_forecasts(self) -> Any:
        return self.device_state.usage_forecasts

    @property
    def fill_level_target_profiles(self) -> Any:
        return self.device_state.fill_level_target_profiles

    def get_computational_parameters(self) -> Any:
        return self.device_state.get_computational_parameters()

    @lru_cache(maxsize=None)
    def get_actuators(self, target_timestep: "FrbcTimestep") -> List[str]:
        return list(self.create_actuator_operation_mode_map(target_timestep).keys())

    @lru_cache(maxsize=None)
    def get_normal_operation_modes_for_actuator(
        self, target_timestep: "FrbcTimestep", actuator_id: str
    ) -> List[str]:
        actuator_operation_mode_map = self.create_actuator_operation_mode_map(
            target_timestep
        )
        return actuator_operation_mode_map.get(actuator_id, [])

    @lru_cache(maxsize=None)
    def create_actuator_operation_mode_map(
        self, target_timestep: "FrbcTimestep"
    ) -> Dict[str, List[str]]:
        actuator_operation_mode_map = {}
        for a in target_timestep.system_description.actuators:
            actuator_operation_mode_map[str(a.id)] = [
                str(om.id) for om in a.operation_modes if not om.abnormal_condition_only
            ]
        return actuator_operation_mode_map

    @lru_cache(maxsize=None)
    def get_operation_mode(
        self, target_timestep, actuator_id: str, operation_mode_id: str
    ):
        om_key = f"{actuator_id}-{operation_mode_id}"
        if om_key in self.operation_modes:
            return self.operation_modes[om_key]

        actuator_description = self.get_actuator_description(
            target_timestep, actuator_id
        )
        if actuator_description:
            for operation_mode in actuator_description.operation_modes:
                if str(operation_mode.id) == operation_mode_id:
                    found_operation_mode = FrbcOperationModeWrapper(operation_mode)
                    self.operation_modes[om_key] = found_operation_mode
                    return found_operation_mode
        return None

    @lru_cache(maxsize=None)
    def operation_mode_uses_factor(
        self,
        target_timestep: "FrbcTimestep",
        actuator_id: str,
        operation_mode_id: str,
    ) -> bool:
        return self.get_operation_mode(
            target_timestep, actuator_id, operation_mode_id
        ).is_uses_factor()

    @lru_cache(maxsize=None)
    def get_all_possible_actuator_configurations(
        self, target_timestep: "FrbcTimestep"
    ) -> List[Dict[Any, S2ActuatorConfiguration]]:
        possible_actuator_configs = {}
        for actuator_id in self.get_actuators(target_timestep):
            actuator_list = []
            for op_mode_id in self.get_normal_operation_modes_for_actuator(
                target_timestep, actuator_id
            ):
                if self.operation_mode_uses_factor(
                    target_timestep, actuator_id, op_mode_id
                ):
                    factors = np.linspace(
                        0.0, 1.0, self.nr_of_stratification_layers + 1
                    )
                    actuator_list.extend(
                        [
                            S2ActuatorConfiguration(op_mode_id, factor)
                            for factor in factors
                        ]
                    )
                else:
                    actuator_list.append(S2ActuatorConfiguration(op_mode_id, 0.0))
            possible_actuator_configs[actuator_id] = actuator_list

        keys = list(possible_actuator_configs.keys())
        import itertools

        combinations = itertools.product(
            *(possible_actuator_configs[key] for key in keys)
        )

        return [dict(zip(keys, combo)) for combo in combinations]

    @staticmethod
    @lru_cache(maxsize=None)
    def get_transition(
        target_timestep,
        actuator_id: str,
        from_operation_mode_id: str,
        to_operation_mode_id: str,
    ) -> Optional[Transition]:
        actuator_description = S2FrbcDeviceStateWrapper.get_actuator_description(
            target_timestep, actuator_id
        )
        if actuator_description is None:
            return None

        for transition in actuator_description.transitions:
            if (
                str(transition.from_) == from_operation_mode_id
                and str(transition.to) == to_operation_mode_id
            ):
                return transition
        return None

    def get_operation_mode_power(
        self, om_wrapper: FrbcOperationModeWrapper, fill_level: float, factor: float
    ) -> float:
        element = self.find_operation_mode_element(om_wrapper, fill_level)
        power_watt = 0
        for power_range in element.power_ranges:
            if power_range.commodity_quantity in [
                CommodityQuantity.ELECTRIC_POWER_L1,
                CommodityQuantity.ELECTRIC_POWER_L2,
                CommodityQuantity.ELECTRIC_POWER_L3,
                CommodityQuantity.ELECTRIC_POWER_3_PHASE_SYMMETRIC,
            ]:
                start = power_range.start_of_range
                end = power_range.end_of_range
                power_watt += (end - start) * factor + start
        return power_watt

    @staticmethod
    def find_operation_mode_element(
        om_wrapper: FrbcOperationModeWrapper, fill_level: float
    ):
        starts = om_wrapper.fill_level_starts
        ends = om_wrapper.fill_level_ends

        # Assumes that starts is sorted, which is a reasonable assumption for S2 data.
        # Find the index of the interval start that is just less than or equal to fill_level.
        idx = np.searchsorted(starts, fill_level, side="right") - 1

        # Check if fill_level is within the found range.
        if idx >= 0 and fill_level <= ends[idx]:
            return om_wrapper.elements[idx]

        # Handle edge cases and gaps, consistent with the original logic.
        return (
            om_wrapper.elements[0]
            if fill_level < starts[0]
            else om_wrapper.elements[-1]
        )

    def get_operation_mode_fill_rate(
        self, om_wrapper: FrbcOperationModeWrapper, fill_level: float, factor: float
    ) -> float:
        element = self.find_operation_mode_element(om_wrapper, fill_level)
        fill_rate = element.fill_rate
        start = fill_rate.end_of_range
        end = fill_rate.start_of_range
        return (start - end) * factor + end

    @staticmethod
    def get_leakage_rate(target_timestep: "FrbcTimestep", fill_level: float) -> float:
        if target_timestep.leakage_behaviour is None:
            return 0.0

        element = S2FrbcDeviceStateWrapper.find_leakage_element(
            target_timestep.leakage_behaviour, fill_level
        )
        return element.leakage_rate if element else 0.0

    @staticmethod
    def find_leakage_element(
        leakage_behaviour: FRBCLeakageBehaviour, fill_level: float
    ) -> Optional[FRBCLeakageBehaviourElement]:
        if not leakage_behaviour.elements:
            return None

        # Calculate starts and ends arrays directly to avoid monkey-patching issues
        starts = np.array(
            [e.fill_level_range.start_of_range for e in leakage_behaviour.elements]
        )
        ends = np.array(
            [e.fill_level_range.end_of_range for e in leakage_behaviour.elements]
        )

        # Use binary search for efficient lookup
        idx = np.searchsorted(starts, fill_level, side="right") - 1

        if idx >= 0 and fill_level <= ends[idx]:
            return leakage_behaviour.elements[idx]

        return (
            leakage_behaviour.elements[0]
            if fill_level < starts[0]
            else leakage_behaviour.elements[-1]
        )

    @staticmethod
    def calculate_bucket(target_timestep: "FrbcTimestep", fill_level: float) -> int:
        (
            fill_level_lower_limit,
            fill_level_upper_limit,
            nr_of_buckets,
        ) = target_timestep.get_bucket_calculation_params()

        if fill_level_upper_limit == fill_level_lower_limit:
            return 0

        bucket = int(
            (fill_level - fill_level_lower_limit)
            / (fill_level_upper_limit - fill_level_lower_limit)
            * nr_of_buckets
        )
        return min(max(bucket, 0), nr_of_buckets - 1)

    @staticmethod
    @lru_cache(maxsize=None)
    def get_timer_duration(
        target_timestep: "FrbcTimestep", actuator_id: str, timer_id: str
    ) -> timedelta:
        return timedelta(
            milliseconds=S2FrbcDeviceStateWrapper.get_timer_duration_milliseconds(
                target_timestep, actuator_id, timer_id
            )
        )

    @staticmethod
    @lru_cache(maxsize=None)
    def get_timer_duration_milliseconds(
        target_timestep: "FrbcTimestep", actuator_id: str, timer_id: str
    ) -> int:
        actuator_description = S2FrbcDeviceStateWrapper.get_actuator_description(
            target_timestep, actuator_id
        )
        if actuator_description is None:
            raise ValueError(
                f"Actuator description not found for actuator {actuator_id}"
            )

        timer = next(
            (t for t in actuator_description.timers if str(t.id) == timer_id), None
        )
        return timer.duration.root if timer else 0

    @staticmethod
    @lru_cache(maxsize=None)
    def get_actuator_description(
        target_timestep: "FrbcTimestep", actuator_id: str
    ) -> Optional[FRBCActuatorDescription]:
        return next(
            (
                ad
                for ad in target_timestep.system_description.actuators
                if str(ad.id) == actuator_id
            ),
            None,
        )

    def get_energy_in_current_timestep(self) -> CommodityQuantity:
        return self.device_state.get_energy_in_current_timestep()

    @property
    def actuator_statuses(self) -> List[FRBCActuatorStatus]:
        return self.device_state.actuator_statuses or []

    @property
    def storage_status(self) -> List[FRBCStorageStatus]:
        # The return type is correct but mypy does not understand the structure of s2python correctly
        return self.device_state.storage_status  # type: ignore[return-value]
