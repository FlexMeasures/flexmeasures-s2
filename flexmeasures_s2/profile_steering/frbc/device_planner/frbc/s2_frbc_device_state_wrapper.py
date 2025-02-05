from datetime import datetime, timedelta
from s2_utils.s2_actuator_configuration import S2ActuatorConfiguration
from s2python.common import CommodityQuantity


class S2FrbcDeviceStateWrapper:
    epsilon = 1e-4

    def __init__(self, device_state):
        self.device_state = device_state
        self.nr_of_buckets = (
            device_state.get_computational_parameters().get_nr_of_buckets()
        )
        self.nr_of_stratification_layers = 0  # Initialize appropriately
        self.actuator_operation_mode_map_per_timestep = {}
        self.all_actions = {}
        self.operation_mode_uses_factor_map = {}
        self.operation_modes = {}

    def is_online(self):
        return self.device_state.is_online()

    def get_power_forecast(self):
        return self.device_state.get_power_forecast()

    def get_system_descriptions(self):
        return self.device_state.get_system_descriptions()

    def get_leakage_behaviours(self):
        return self.device_state.get_leakage_behaviours()

    def get_usage_forecasts(self):
        return self.device_state.get_usage_forecasts()

    def get_fill_level_target_profiles(self):
        return self.device_state.get_fill_level_target_profiles()

    def get_energy_in_current_timestep(self):
        return self.device_state.get_energy_in_current_timestep()

    def get_computational_parameters(self):
        return self.device_state.get_computational_parameters()

    def get_actuators(self, target_timestep):
        actuator_operation_mode_map = self.actuator_operation_mode_map_per_timestep.get(
            target_timestep.get_start_date()
        )
        if actuator_operation_mode_map is None:
            actuator_operation_mode_map = self.create_actuator_operation_mode_map(
                target_timestep
            )
        return actuator_operation_mode_map.keys()

    def get_normal_operation_modes_for_actuator(self, target_timestep, actuator_id):
        actuator_operation_mode_map = self.actuator_operation_mode_map_per_timestep.get(
            target_timestep.get_start_date()
        )
        if actuator_operation_mode_map is None:
            actuator_operation_mode_map = self.create_actuator_operation_mode_map(
                target_timestep
            )
        return actuator_operation_mode_map.get(actuator_id)

    def create_actuator_operation_mode_map(self, target_timestep):
        actuator_operation_mode_map = {}
        for a in target_timestep.get_system_description().get_actuators():
            actuator_operation_mode_map[a.get_id()] = [
                om.get_id()
                for om in a.get_operation_modes()
                if not om.get_abnormal_condition_only()
            ]
        self.actuator_operation_mode_map_per_timestep[
            target_timestep.get_start_date()
        ] = actuator_operation_mode_map
        return actuator_operation_mode_map

    def get_operation_mode(self, target_timestep, actuator_id, operation_mode_id):
        om_key = f"{actuator_id}-{operation_mode_id}"
        if om_key in self.operation_modes:
            return self.operation_modes[om_key]
        actuators = target_timestep.get_system_description().get_actuators()
        found_actuator_description = next(
            (ad for ad in actuators if ad.get_id() == actuator_id), None
        )
        if found_actuator_description:
            for operation_mode in found_actuator_description.get_operation_modes():
                if operation_mode.get_id() == operation_mode_id:
                    found_operation_mode = FrbcOperationModeWrapper(operation_mode)
                    self.operation_modes[om_key] = found_operation_mode
                    return found_operation_mode
        return None

    def operation_mode_uses_factor(
        self, target_timestep, actuator_id, operation_mode_id
    ):
        key = f"{actuator_id}-{operation_mode_id}"
        if key not in self.operation_mode_uses_factor_map:
            result = self.get_operation_mode(
                target_timestep, actuator_id, operation_mode_id
            ).is_uses_factor()
            self.operation_mode_uses_factor_map[key] = result
        return self.operation_mode_uses_factor_map[key]

    def get_all_possible_actuator_configurations(self, target_timestep):
        timestep_date = target_timestep.get_start_date()
        if timestep_date not in self.all_actions:
            possible_actuator_configs = {}
            for actuator_id in self.get_actuators(target_timestep):
                actuator_list = []
                for operation_mode_id in self.get_normal_operation_modes_for_actuator(
                    target_timestep, actuator_id
                ):
                    if self.operation_mode_uses_factor(
                        target_timestep, actuator_id, operation_mode_id
                    ):
                        for i in range(self.nr_of_stratification_layers + 1):
                            factor_for_actuator = i * (
                                1.0 / self.nr_of_stratification_layers
                            )
                            actuator_list.append(
                                S2ActuatorConfiguration(
                                    operation_mode_id, factor_for_actuator
                                )
                            )
                    else:
                        actuator_list.append(
                            S2ActuatorConfiguration(operation_mode_id, 0.0)
                        )
                possible_actuator_configs[actuator_id] = actuator_list
            keys = list(possible_actuator_configs.keys())
            actions_for_timestep = []
            combination = [0] * len(keys)
            actions_for_timestep.append(
                self.combination_to_map(combination, keys, possible_actuator_configs)
            )
            while self.increase(combination, keys, possible_actuator_configs):
                actions_for_timestep.append(
                    self.combination_to_map(
                        combination, keys, possible_actuator_configs
                    )
                )
            self.all_actions[timestep_date] = actions_for_timestep
        return self.all_actions[timestep_date]

    def combination_to_map(self, cur, keys, possible_actuator_configs):
        combination = {}
        for i, key in enumerate(keys):
            combination[key] = possible_actuator_configs[key][cur[i]]
        return combination

    def increase(self, cur, keys, possible_actuator_configs):
        cur[0] += 1
        for i, key in enumerate(keys):
            if cur[i] >= len(possible_actuator_configs[key]):
                if i + 1 >= len(keys):
                    return False
                cur[i] = 0
                cur[i + 1] += 1
        return True

    @staticmethod
    def get_transition(
        target_timestep, actuator_id, from_operation_mode_id, to_operation_mode_id
    ):
        actuator_description = S2FrbcDeviceStateWrapper.get_actuator_description(
            target_timestep, actuator_id
        )
        for transition in actuator_description.get_transitions():
            if (
                transition.get_from() == from_operation_mode_id
                and transition.get_to() == to_operation_mode_id
            ):
                return transition
        return None

    def get_operation_mode_power(self, om, fill_level, factor):
        element = self.find_operation_mode_element(om, fill_level)
        power_watt = 0
        for power_range in element.get_power_ranges():
            if power_range.get_commodity_quantity() in [
                CommodityQuantity.ELECTRIC_POWER_L1,
                CommodityQuantity.ELECTRIC_POWER_L2,
                CommodityQuantity.ELECTRIC_POWER_L3,
                CommodityQuantity.ELECTRIC_POWER_3_PHASE_SYMMETRIC,
            ]:
                start = power_range.get_start_of_range()
                end = power_range.get_end_of_range()
                power_watt += (end - start) * factor + start
        return power_watt

    @staticmethod
    def find_operation_mode_element(om, fill_level):
        element = next(
            (
                e
                for e in om.get_elements()
                if e.get_fill_level_range().get_start_of_range()
                <= fill_level
                <= e.get_fill_level_range().get_end_of_range()
            ),
            None,
        )
        if element is None:
            first = om.get_elements()[0]
            last = om.get_elements()[-1]
            element = (
                first
                if fill_level < first.get_fill_level_range().get_start_of_range()
                else last
            )
        return element

    def get_operation_mode_fill_rate(self, om, fill_level, factor):
        element = self.find_operation_mode_element(om, fill_level)
        fill_rate = element.get_fill_rate()
        start = fill_rate.get_end_of_range()
        end = fill_rate.get_start_of_range()
        return (start - end) * factor + end

    @staticmethod
    def get_leakage_rate(target_timestep, fill_level):
        if target_timestep.get_leakage_behaviour() is None:
            return 0
        else:
            return S2FrbcDeviceStateWrapper.find_leakage_element(
                target_timestep, fill_level
            ).get_leakage_rate()

    @staticmethod
    def find_leakage_element(target_timestep, fill_level):
        leakage = target_timestep.get_leakage_behaviour()
        element = next(
            (
                e
                for e in leakage.get_elements()
                if e.get_fill_level_range().get_start_of_range()
                <= fill_level
                <= e.get_fill_level_range().get_end_of_range()
            ),
            None,
        )
        if element is None:
            first = leakage.get_elements()[0]
            last = leakage.get_elements()[-1]
            element = (
                first
                if fill_level < first.get_fill_level_range().get_start_of_range()
                else last
            )
        return element

    @staticmethod
    def calculate_bucket(target_timestep, fill_level):
        fill_level_lower_limit = (
            target_timestep.get_system_description()
            .get_storage()
            .get_fill_level_range()
            .get_start_of_range()
        )
        fill_level_upper_limit = (
            target_timestep.get_system_description()
            .get_storage()
            .get_fill_level_range()
            .get_end_of_range()
        )
        return int(
            (fill_level - fill_level_lower_limit)
            / (fill_level_upper_limit - fill_level_lower_limit)
            * target_timestep.get_nr_of_buckets()
        )

    @staticmethod
    def get_timer_duration_milliseconds(target_timestep, actuator_id, timer_id):
        actuator_description = S2FrbcDeviceStateWrapper.get_actuator_description(
            target_timestep, actuator_id
        )
        timer = next(
            (t for t in actuator_description.get_timers() if t.get_id() == timer_id),
            None,
        )
        return timer.get_duration() if timer else 0

    @staticmethod
    def get_timer_duration(target_timestep, actuator_id, timer_id):
        return timedelta(
            milliseconds=S2FrbcDeviceStateWrapper.get_timer_duration_milliseconds(
                target_timestep, actuator_id, timer_id
            )
        )

    @staticmethod
    def get_actuator_description(target_timestep, actuator_id):
        return next(
            (
                ad
                for ad in target_timestep.get_system_description().get_actuators()
                if ad.get_id() == actuator_id
            ),
            None,
        )
