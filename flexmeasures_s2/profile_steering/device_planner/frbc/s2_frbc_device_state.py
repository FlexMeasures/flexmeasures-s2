from datetime import datetime
from typing import List, Optional
from s2python.common import PowerForecast
from s2python.frbc import (
    FRBCSystemDescription,
    FRBCLeakageBehaviour,
    FRBCUsageForecast,
    FRBCFillLevelTargetProfile,
)
from s2python.frbc.frbc_actuator_status import FRBCActuatorStatus
from s2python.generated.gen_s2 import FRBCStorageStatus, PowerValue


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

        def __init__(self, nr_of_buckets: int, stratification_layers: int):
            self.nr_of_buckets = nr_of_buckets
            self.stratification_layers = stratification_layers

        def get_nr_of_buckets(self) -> int:
            return self.nr_of_buckets

        def get_stratification_layers(self) -> int:
            return self.stratification_layers

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
        system_descriptions: List[FRBCSystemDescription],
        leakage_behaviours: List[FRBCLeakageBehaviour],
        usage_forecasts: List[FRBCUsageForecast],
        fill_level_target_profiles: List[FRBCFillLevelTargetProfile],
        computational_parameters: ComputationalParameters,
        storage_status: FRBCStorageStatus = None,
        actuator_statuses: Optional[List[FRBCActuatorStatus]] = None,
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
        self.leakage_behaviours = leakage_behaviours
        self.usage_forecasts = usage_forecasts
        self.fill_level_target_profiles = fill_level_target_profiles
        self.computational_parameters = computational_parameters
        self.storage_status = storage_status
        self.actuator_statuses = actuator_statuses

    def get_system_descriptions(self) -> List[FRBCSystemDescription]:
        return self.system_descriptions

    def get_leakage_behaviours(self) -> List[FRBCLeakageBehaviour]:
        return self.leakage_behaviours

    def get_device_name(self) -> str:
        return self.device_name

    def get_computational_parameters(self) -> ComputationalParameters:
        return self.computational_parameters

    def get_power_forecast(self) -> Optional[PowerForecast]:
        return self.power_forecast

    def get_energy_in_current_timestep(self) -> PowerValue:
        return self.energy_in_current_timestep
