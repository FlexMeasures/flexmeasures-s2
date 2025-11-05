from datetime import datetime
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from functools import lru_cache

from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_plan import (
    S2DdbcActuatorConfiguration,
)
from flexmeasures_s2.profile_steering.device_planner.ddbc.ddbc_operation_mode_wrapper import (
    DdbcOperationModeWrapper,
)

if TYPE_CHECKING:
    from flexmeasures_s2.profile_steering.device_planner.ddbc.ddbc_timestep import (
        DdbcTimestep,
    )

from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_device_state import (
    S2DdbcDeviceState,
)


class S2DdbcDeviceStateWrapper:
    """
    Wrapper for S2DdbcDeviceState that adds caching and utility methods.
    Similar to S2FrbcDeviceStateWrapper but for DDBC devices.
    """

    epsilon = 1e-4

    def __init__(self, device_state: S2DdbcDeviceState):
        self.device_state: S2DdbcDeviceState = device_state
        self.actuator_operation_mode_map_per_timestep: Dict[
            datetime, Dict[str, List[str]]
        ] = {}
        self.all_actions: Dict[
            datetime, List[Dict[str, S2DdbcActuatorConfiguration]]
        ] = {}
        self.operation_modes: Dict[str, DdbcOperationModeWrapper] = {}

    @property
    def is_online(self) -> bool:
        return self.device_state.is_online

    def get_power_forecast(self) -> Any:
        return self.device_state.get_power_forecast()

    def get_system_descriptions(self) -> Any:
        return self.device_state.get_system_descriptions()

    def get_demand_forecasts(self) -> Any:
        return self.device_state.get_demand_forecasts()

    def get_gas_price_per_m3(self) -> float:
        return self.device_state.get_gas_price_per_m3()

    @lru_cache(maxsize=None)
    def get_actuators(self, target_timestep: "DdbcTimestep") -> List[str]:
        return list(self.create_actuator_operation_mode_map(target_timestep).keys())

    @lru_cache(maxsize=None)
    def get_normal_operation_modes_for_actuator(
        self, target_timestep: "DdbcTimestep", actuator_id: str
    ) -> List[str]:
        actuator_operation_mode_map = self.create_actuator_operation_mode_map(
            target_timestep
        )
        return actuator_operation_mode_map.get(actuator_id, [])

    @lru_cache(maxsize=None)
    def create_actuator_operation_mode_map(
        self, target_timestep: "DdbcTimestep"
    ) -> Dict[str, List[str]]:
        actuator_operation_mode_map = {}
        for a in target_timestep.system_description.actuators:
            actuator_operation_mode_map[str(a.id)] = [
                str(om.id) for om in a.operation_modes if not om.abnormal_condition_only
            ]
        return actuator_operation_mode_map

    @lru_cache(maxsize=None)
    def get_operation_mode(
        self, target_timestep: "DdbcTimestep", actuator_id: str, operation_mode_id: str
    ) -> Optional[DdbcOperationModeWrapper]:
        """Get operation mode wrapper for a specific actuator and operation mode."""
        om_key = f"{actuator_id}-{operation_mode_id}"

        if om_key in self.operation_modes:
            return self.operation_modes[om_key]

        # Find the actuator and operation mode
        for actuator in target_timestep.system_description.actuators:
            if str(actuator.id) == actuator_id:
                for operation_mode in actuator.operation_modes:
                    if str(operation_mode.id) == operation_mode_id:
                        wrapper = DdbcOperationModeWrapper(operation_mode)
                        self.operation_modes[om_key] = wrapper
                        return wrapper

        return None
