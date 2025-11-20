import numpy as np
from typing import List, Optional

from flexmeasures_s2.profile_steering.common.power_range_wrapper import (
    PowerRangeWrapper,
)
from flexmeasures_s2.profile_steering.s2_utils.number_range_wrapper import (
    NumberRangeWrapper,
)
from s2python.frbc import FRBCOperationMode, FRBCOperationModeElement


class FrbcOperationModeElementWrapper:
    def __init__(self, element: FRBCOperationModeElement):
        self.fill_level_range = NumberRangeWrapper(
            element.fill_level_range.start_of_range,
            element.fill_level_range.end_of_range,
        )
        self.fill_rate = NumberRangeWrapper(
            element.fill_rate.start_of_range, element.fill_rate.end_of_range
        )
        self.power_ranges: List[PowerRangeWrapper] = [
            PowerRangeWrapper(pr) for pr in element.power_ranges
        ]

        if element.running_costs is None:
            self.running_costs: Optional[NumberRangeWrapper] = None
        else:
            self.running_costs = NumberRangeWrapper(
                element.running_costs.start_of_range,
                element.running_costs.end_of_range,
            )

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, FrbcOperationModeElementWrapper):
            return False
        return (
            self.fill_level_range == o.fill_level_range
            and self.fill_rate == o.fill_rate
            and self.power_ranges == o.power_ranges
            and self.running_costs == o.running_costs
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.fill_level_range,
                self.fill_rate,
                tuple(self.power_ranges),
                self.running_costs,
            )
        )


class FrbcOperationModeWrapper:
    def __init__(self, frbc_operation_mode: FRBCOperationMode):
        self.id = frbc_operation_mode.id
        self.diagnostic_label = frbc_operation_mode.diagnostic_label
        self.abnormal_condition_only = frbc_operation_mode.abnormal_condition_only
        self.elements = [
            FrbcOperationModeElementWrapper(element)
            for element in frbc_operation_mode.elements
        ]
        self.uses_factor = self.calculate_uses_factor()

        # Pre-process elements into NumPy arrays for vectorization
        if self.elements:
            self.fill_level_starts = np.array(
                [e.fill_level_range.start_of_range for e in self.elements]
            )
            self.fill_level_ends = np.array(
                [e.fill_level_range.end_of_range for e in self.elements]
            )
        else:
            self.fill_level_starts = np.array([])
            self.fill_level_ends = np.array([])

    def calculate_uses_factor(self) -> bool:
        from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state_wrapper import (
            S2FrbcDeviceStateWrapper,
        )

        for element in self.elements:
            if (
                abs(element.fill_rate.start_of_range - element.fill_rate.end_of_range)
                > S2FrbcDeviceStateWrapper.epsilon
            ):
                return True
            for power_range in element.power_ranges:
                if (
                    abs(power_range.start_of_range - power_range.end_of_range)
                    > S2FrbcDeviceStateWrapper.epsilon
                ):
                    return True
        return False

    def is_uses_factor(self) -> bool:
        return self.uses_factor
