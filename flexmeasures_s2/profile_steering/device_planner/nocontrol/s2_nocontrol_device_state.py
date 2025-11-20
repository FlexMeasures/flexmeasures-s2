from datetime import datetime
from typing import Optional
from s2python.common import PowerForecast, PowerValue


class S2NoControlDeviceState:
    """
    Device state for devices with no control capabilities.
    These devices only provide a power forecast and cannot be controlled.
    """

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

    def get_power_forecast(self) -> Optional[PowerForecast]:
        return self.power_forecast
