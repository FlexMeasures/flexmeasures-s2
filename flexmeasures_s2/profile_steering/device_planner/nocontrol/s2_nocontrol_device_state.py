from datetime import datetime
from typing import Optional
from s2python.common import PowerForecast
from s2python.generated.gen_s2 import PowerValue


class S2NoControlDeviceState:
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
    ):
        self.device_id = device_id
        self.device_name = device_name
        self.connection_id = connection_id
        self.priority_class = priority_class
        self.timestamp = timestamp
        self.energy_in_current_timestep = energy_in_current_timestep
        self.is_online = is_online
        self.power_forecast = power_forecast

    def get_device_id(self) -> str:
        return self.device_id

    def get_device_name(self) -> str:
        return self.device_name

    def get_connection_id(self) -> str:
        return self.connection_id

    def get_priority_class(self) -> int:
        return self.priority_class

    def get_power_forecast(self) -> Optional[PowerForecast]:
        return self.power_forecast
