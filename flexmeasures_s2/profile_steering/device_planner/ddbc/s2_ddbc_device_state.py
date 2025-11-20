from datetime import datetime
from typing import List, Optional, Any, Dict


class S2DdbcDeviceState:
    """Device state for Demand-Driven Based Control (DDBC) devices.

    Holds the current state and configuration of a DDBC device, including:
    - Device identification and connection information
    - System descriptions defining device capabilities
    - Demand forecasts indicating expected demand
    - Actuator statuses showing current actuator states
    - Pricing information (e.g., gas price) for cost optimization

    DDBC devices are demand-driven systems that respond to average demand rate
    forecasts by selecting appropriate actuator operation modes.
    """

    DEFAULT_GAS_PRICE_PER_M3 = 2.0

    def __init__(
        self,
        device_id: str,
        device_name: str,
        connection_id: str,
        priority_class: int,
        timestamp: datetime,
        energy_in_current_timestep: float,
        is_online: bool,
        power_forecast: Optional[Any],
        system_descriptions: List[Any],
        demand_forecasts: List[Any],
        actuator_statuses: Optional[Dict[str, Any]] = None,
        gas_price_per_m3: Optional[float] = None,
    ):
        self.device_id = device_id
        self.device_name = device_name
        self.connection_id = connection_id
        self.priority_class = priority_class
        self.timestamp = timestamp
        self.energy_in_current_timestep = energy_in_current_timestep
        self.is_online = is_online
        self.power_forecast = power_forecast
        self.system_descriptions = system_descriptions
        self.demand_forecasts = demand_forecasts
        self.actuator_statuses = actuator_statuses or {}
        self.gas_price_per_m3 = (
            gas_price_per_m3
            if gas_price_per_m3 is not None
            else self.DEFAULT_GAS_PRICE_PER_M3
        )

    def get_device_id(self) -> str:
        return self.device_id

    def get_device_name(self) -> str:
        return self.device_name

    def get_connection_id(self) -> str:
        return self.connection_id

    def get_priority_class(self) -> int:
        return self.priority_class

    def get_timestamp(self) -> datetime:
        return self.timestamp

    def get_energy_in_current_timestep(self) -> float:
        return self.energy_in_current_timestep

    def is_device_online(self) -> bool:
        return self.is_online

    def get_power_forecast(self) -> Optional[Any]:
        return self.power_forecast

    def get_system_descriptions(self) -> List[Any]:
        return self.system_descriptions

    def get_demand_forecasts(self) -> List[Any]:
        return self.demand_forecasts

    def get_gas_price_per_m3(self) -> float:
        return self.gas_price_per_m3

    def get_actuator_statuses(self) -> Dict[str, Any]:
        return self.actuator_statuses
