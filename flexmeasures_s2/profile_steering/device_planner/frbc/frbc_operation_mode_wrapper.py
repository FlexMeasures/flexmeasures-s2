from typing import List
from flexmeasures_s2.profile_steering.s2_utils.number_range_wrapper import (
    NumberRangeWrapper,
)
from s2python.frbc import FRBCOperationModeElement

class FrbcOperationModeElementWrapper:
    def __init__(self, frbc_operation_mode_element: FRBCOperationModeElement):
        self.fill_rate = NumberRangeWrapper(
            frbc_operation_mode_element.fill_rate.start_of_range,
            frbc_operation_mode_element.fill_rate.end_of_range,
        )
        self.power_ranges = [
            NumberRangeWrapper(pr.start_of_range, pr.end_of_range)
            for pr in frbc_operation_mode_element.power_ranges
        ]
        self.fill_level_range = NumberRangeWrapper(
            frbc_operation_mode_element.fill_level_range.start_of_range,
            frbc_operation_mode_element.fill_level_range.end_of_range,
        )
        self.frbc_operation_mode_element = frbc_operation_mode_element

    def get_fill_rate(self) -> NumberRangeWrapper:
        return self.fill_rate

    def get_power_ranges(self) -> List[NumberRangeWrapper]:
        return self.power_ranges

    def get_fill_level_range(self) -> NumberRangeWrapper:
        return self.fill_level_range
    
    def get_power_ranges(self):
        return self.frbc_operation_mode_element.power_ranges

class FrbcOperationModeWrapper:
    def __init__(self, frbc_operation_mode):
        self.id = frbc_operation_mode.id
        self.diagnostic_label = frbc_operation_mode.diagnostic_label
        self.abnormal_condition_only = frbc_operation_mode.abnormal_condition_only
        self.elements = [
            FrbcOperationModeElementWrapper(element)
            for element in frbc_operation_mode.elements
        ]
        self.uses_factor = self.calculate_uses_factor()

    def calculate_uses_factor(self) -> bool:
        from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state_wrapper import (
            S2FrbcDeviceStateWrapper,
        )

        for element in self.elements:
            if (
                abs(
                    element.get_fill_rate().get_start_of_range()
                    - element.get_fill_rate().get_end_of_range()
                )
                > S2FrbcDeviceStateWrapper.epsilon
            ):
                return True
            for power_range in element.get_power_ranges():
                if (
                    abs(
                        power_range.start_of_range
                        - power_range.end_of_range
                    )
                    > S2FrbcDeviceStateWrapper.epsilon
                ):
                    return True
        return False

    def get_elements(self) -> List[FrbcOperationModeElementWrapper]:
        return self.elements

    def is_uses_factor(self) -> bool:
        return self.uses_factor
