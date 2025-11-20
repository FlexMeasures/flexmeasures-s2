from datetime import datetime
from typing import Optional
from s2python.common import PowerForecast, PowerValue


class S2NoControlDeviceState:
    """Device state for devices with no control capabilities.

    Represents devices that have fixed consumption/production patterns and
    cannot be controlled (e.g., refrigerators, lighting, fixed loads). These
    devices only provide a power forecast indicating their expected behavior.

    NoControl devices are included in planning to account for their fixed
    consumption in the cluster's total energy profile, but they cannot
    contribute proposals for optimization since their behavior is fixed.

    Attributes:
        device_id: Unique identifier for the device
        device_name: Human-readable device name
        connection_id: Connection point identifier
        priority_class: Priority class for planning (typically 1)
        timestamp: Current timestamp
        energy_in_current_timestep: Current energy consumption/production
        is_online: Whether the device is currently online
        power_forecast: Power forecast indicating expected consumption/production
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
