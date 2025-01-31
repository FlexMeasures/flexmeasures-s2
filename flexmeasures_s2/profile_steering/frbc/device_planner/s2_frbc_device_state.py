from datetime import datetime
from typing import List


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
        energy_in_current_timestep,
        is_online: bool,
        power_forecast,
        system_descriptions: List,
        leakage_behaviours: List,
        usage_forecasts: List,
        fill_level_target_profiles: List,
        computational_parameters: "S2FrbcDeviceState.ComputationalParameters",
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

    def get_system_descriptions(self) -> List:
        return self.system_descriptions

    def get_leakage_behaviours(self) -> List:
        return self.leakage_behaviours

    def get_usage_forecasts(self) -> List:
        return self.usage_forecasts

    def get_fill_level_target_profiles(self) -> List:
        return self.fill_level_target_profiles

    def get_computational_parameters(
        self,
    ) -> "S2FrbcDeviceState.ComputationalParameters":
        return self.computational_parameters
