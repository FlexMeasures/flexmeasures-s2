from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from s2python.common import PowerForecast
from s2python.frbc import (
    FRBCSystemDescription,
    FRBCLeakageBehaviour,
    FRBCUsageForecast,
    FRBCFillLevelTargetProfile,
)
from s2python.frbc.frbc_actuator_status import FRBCActuatorStatus
from s2python.generated.gen_s2 import FRBCStorageStatus, PowerValue


@dataclass
class S2FrbcDeviceState:
    """Device state for Fill Rate Based Control (FRBC) devices.

    Holds the current state and configuration of an FRBC device, including:
    - Device identification and connection information
    - System descriptions defining storage capabilities and operation modes
    - Leakage behaviors modeling energy losses
    - Usage forecasts indicating expected consumption/production
    - Fill level target profiles specifying state of charge targets
    - Computational parameters (buckets, stratification layers) for planning
    - Storage status showing current fill level
    - Actuator statuses showing current actuator states

    FRBC devices are storage systems that can be charged/discharged to match
    energy targets while respecting fill level constraints and usage forecasts.
    """

    device_id: str
    device_name: str
    connection_id: str
    priority_class: int
    timestamp: datetime
    energy_in_current_timestep: PowerValue
    is_online: bool
    power_forecast: Optional[PowerForecast] = None
    system_descriptions: list[FRBCSystemDescription] = field(default_factory=list)
    leakage_behaviours: list[FRBCLeakageBehaviour] = field(default_factory=list)
    usage_forecasts: list[FRBCUsageForecast] = field(default_factory=list)
    fill_level_target_profiles: list[FRBCFillLevelTargetProfile] = field(
        default_factory=list
    )
    computational_parameters: "S2FrbcDeviceState.ComputationalParameters" = None
    storage_status: Optional[FRBCStorageStatus] = None
    actuator_statuses: Optional[list[FRBCActuatorStatus]] = field(default_factory=list)

    @dataclass
    class ComputationalParameters:
        """Computational parameters for FRBC planning.

        These parameters control the granularity and accuracy of the planning
        algorithm:
        - nr_of_buckets: Number of discrete fill level states (higher = more
          accurate but slower)
        - stratification_layers: Number of layers for thermal stratification
          modeling (for thermal storage systems)

        Attributes:
            nr_of_buckets: Number of fill level buckets for discretization
            stratification_layers: Number of stratification layers
        """

        nr_of_buckets: int
        stratification_layers: int

    def __hash__(self):
        return hash((self.device_id, self.timestamp))

    @property
    def nr_of_buckets(self) -> int:
        return self.computational_parameters.nr_of_buckets

    @property
    def nr_of_stratification_layers(self) -> int:
        return self.computational_parameters.stratification_layers
