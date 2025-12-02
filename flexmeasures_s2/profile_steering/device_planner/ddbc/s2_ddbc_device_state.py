from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any


@dataclass
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

    device_id: str
    device_name: str
    connection_id: str
    priority_class: int
    timestamp: datetime
    energy_in_current_timestep: float
    is_online: bool
    power_forecast: Optional[Any]
    system_descriptions: list[Any]
    demand_forecasts: list[Any]
    actuator_statuses: dict[str, Any] = field(default_factory=dict)
    gas_price_per_m3: float = 2.0
