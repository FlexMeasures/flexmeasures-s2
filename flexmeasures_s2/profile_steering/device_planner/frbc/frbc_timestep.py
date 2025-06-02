from datetime import datetime, timedelta
from typing import List, Optional

from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from flexmeasures_s2.profile_steering.s2_utils.number_range_wrapper import (
    NumberRangeWrapper,
)
from s2python.frbc import FRBCSystemDescription, FRBCLeakageBehaviour
from flexmeasures_s2.profile_steering.device_planner.frbc.frbc_state import FrbcState
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state import (
    S2FrbcDeviceState,
)
from enum import Enum


class SelectionReason(Enum):
    NO_ALTERNATIVE = "NA"
    EMERGENCY_STATE = "ES"
    CONGESTION_CONSTRAINT = "CC"
    ENERGY_TARGET = "ET"
    TARIFF_TARGET = "TT"
    MIN_ENERGY = "ME"

    @property
    def abbr(self) -> str:
        return self.value


class FrbcTimestep:
    def __init__(
        self,
        start_date: datetime,
        end_date: datetime,
        system_description: FRBCSystemDescription,
        leakage_behaviour: FRBCLeakageBehaviour,
        fill_level_target: Optional[NumberRangeWrapper],
        forecasted_fill_level_usage: float,
        computational_parameters: S2FrbcDeviceState.ComputationalParameters,
    ):
        self.nr_of_buckets: int = computational_parameters.get_nr_of_buckets()
        self.start_date: datetime = start_date
        self.end_date: datetime = end_date
        self.duration: timedelta = end_date - start_date
        self.system_description: FRBCSystemDescription = system_description
        self.leakage_behaviour: FRBCLeakageBehaviour = leakage_behaviour
        self.fill_level_target: Optional[NumberRangeWrapper] = fill_level_target
        self.forecasted_fill_level_usage: float = forecasted_fill_level_usage
        self.state_list: List[Optional[FrbcState]] = [None] * (self.nr_of_buckets + 1)
        self.emergency_state: Optional[FrbcState] = None
        # print timestep start date and end date
        # print(f"Timestep start date: {self.start_date}, end date: {self.end_date}")
        # print(f"Forecasted fill level usage: {self.forecasted_fill_level_usage}")
        # if self.fill_level_target is not None:
        #     print(f"Fill level start of range: {self.fill_level_target.start_of_range}")
        #     print(f"Fill level end of range: {self.fill_level_target.end_of_range}")

    def get_nr_of_buckets(self) -> int:
        return self.nr_of_buckets

    def set_targets(
        self, target: float, min_constraint: float, max_constraint: float
    ) -> None:
        self.target = target
        self.min_constraint = min_constraint
        self.max_constraint = max_constraint

    def add_state(self, state: FrbcState) -> None:
        if state and state.is_within_fill_level_range():
            stored_state = self.state_list[state.bucket]
            if stored_state is None:
                self.state_list[state.bucket] = state
                state.set_selection_reason(SelectionReason.NO_ALTERNATIVE)
            else:
                selection_result = state.is_preferable_than(stored_state)
                if selection_result.result:
                    self.state_list[state.bucket] = state
                self.state_list[state.bucket].set_selection_reason(selection_result.reason)  # type: ignore
        else:
            if (
                self.emergency_state is None
                or state.get_fill_level_distance()
                < self.emergency_state.get_fill_level_distance()
            ):
                self.emergency_state = state
                state.set_selection_reason(SelectionReason.EMERGENCY_STATE)

    def add_all_states(self, states: List[FrbcState]) -> None:
        for state in states:
            self.add_state(state)

    def get_duration_seconds(self) -> int:
        return int(self.duration.total_seconds())

    def get_target(self) -> TargetProfile.JouleElement:
        return self.target

    def get_final_states(self) -> List[FrbcState]:
        final_states = [state for state in self.state_list if state is not None]
        # print out the position of the states in final_states

        if not final_states and self.emergency_state is not None:
            return [self.emergency_state]
        return final_states

    def get_final_states_within_fill_level_target(self) -> List[FrbcState]:
        final_states = self.get_final_states()
        if self.fill_level_target is None:
            return final_states
        final_states = [
            s for s in final_states if self.state_is_within_fill_level_target_range(s)
        ]
        if final_states:
            return final_states
        best_state = min(
            self.get_final_states(), key=self.get_fill_level_target_distance
        )
        return [best_state]

    def state_is_within_fill_level_target_range(self, state: FrbcState) -> bool:
        if self.fill_level_target is None:
            return True
        return (
            self.fill_level_target.get_start_of_range() is None
            or state.fill_level >= self.fill_level_target.get_start_of_range()
        ) and (
            self.fill_level_target.get_end_of_range() is None
            or state.fill_level <= self.fill_level_target.get_end_of_range()
        )

    def get_fill_level_target_distance(self, state: FrbcState) -> float:
        if self.fill_level_target is None:
            return 0
        if (
            self.fill_level_target.get_end_of_range() is None
            or state.fill_level < self.fill_level_target.get_start_of_range()
        ):
            return self.fill_level_target.get_start_of_range() - state.fill_level
        else:
            return state.fill_level - self.fill_level_target.get_end_of_range()

    def clear(self) -> None:
        self.state_list = [None] * len(self.state_list)
        self.emergency_state = None
