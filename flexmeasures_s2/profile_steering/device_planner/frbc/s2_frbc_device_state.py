from datetime import datetime
from typing import List, Optional
from s2python.common import CommodityQuantity, PowerForecast
from s2python.frbc import (
    FRBCSystemDescription,
    FRBCLeakageBehaviour,
    FRBCUsageForecast,
    FRBCFillLevelTargetProfile,
)
from s2python.generated.gen_s2 import PowerValue


class S2FrbcDeviceState:
    class ComputationalParameters:
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

    def get_system_descriptions(self) -> List[FRBCSystemDescription]:
        return self.system_descriptions

    def get_leakage_behaviours(self) -> List[FRBCLeakageBehaviour]:
        return self.leakage_behaviours

    def get_usage_forecasts(self) -> List[FRBCUsageForecast]:
        return self.usage_forecasts

    def get_fill_level_target_profiles(self) -> List[FRBCFillLevelTargetProfile]:
        return self.fill_level_target_profiles

    def get_device_id(self) -> str:
        return self.device_id

    def get_device_name(self) -> str:
        return self.device_name

    def get_connection_id(self) -> str:
        return self.connection_id

    def _is_online(self) -> bool:
        return self.is_online

    def get_computational_parameters(self) -> ComputationalParameters:
        return self.computational_parameters

    def get_power_forecast(self) -> Optional[PowerForecast]:
        return self.power_forecast

    def get_energy_in_current_timestep(self) -> CommodityQuantity:
        return self.energy_in_current_timestep
