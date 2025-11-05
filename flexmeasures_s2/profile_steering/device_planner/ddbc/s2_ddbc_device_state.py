from datetime import datetime
from typing import Optional, List
from s2python.common import PowerForecast, PowerValue
from s2python.ddbc import DDBCSystemDescription
from s2python.ddbc.ddbc_average_demand_rate_forecast import (
    DDBCAverageDemandRateForecast,
)


class S2DdbcDeviceState:
    """
    Device state for DDBC (Demand Driven Based Control) devices.
    These devices control systems like heat pumps or gas boilers with supply-based control.
    """

    DEFAULT_GAS_PRICE_PER_M3 = 2.0

    def __init__(
        self,
        device_id: str,
        device_name: str,
        connection_id: str,
        priority_class: int,
        timestamp: datetime,
        energy_in_current_timestep: PowerValue,
        is_online: bool,
        power_forecast: Optional[PowerForecast],
        system_descriptions: List[DDBCSystemDescription],
        demand_forecasts: List[DDBCAverageDemandRateForecast],
        gas_price_per_m3: float = DEFAULT_GAS_PRICE_PER_M3,
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
        self.gas_price_per_m3 = gas_price_per_m3

    def get_power_forecast(self) -> Optional[PowerForecast]:
        return self.power_forecast

    def get_system_descriptions(self) -> List[DDBCSystemDescription]:
        return self.system_descriptions

    def get_demand_forecasts(self) -> List[DDBCAverageDemandRateForecast]:
        return self.demand_forecasts

    def get_gas_price_per_m3(self) -> float:
        return self.gas_price_per_m3

    def set_gas_price_per_m3(self, gas_price: float) -> None:
        self.gas_price_per_m3 = gas_price
