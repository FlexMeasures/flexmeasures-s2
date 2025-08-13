from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple, TYPE_CHECKING

from flexmeasures_s2.profile_steering.s2_utils.number_range_wrapper import (
    NumberRangeWrapper,
)
from s2python.frbc import FRBCSystemDescription, FRBCLeakageBehaviour

if TYPE_CHECKING:
    from flexmeasures_s2.profile_steering.device_planner.frbc.frbc_state import (
        FrbcState,
    )

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
        computational_parameters: "S2FrbcDeviceState.ComputationalParameters",
        **kwargs,
    ):
        self.system_description = system_description
        self.computational_parameters = computational_parameters
        self.leakage_behaviour = leakage_behaviour
        self.forecasted_fill_level_usage = forecasted_fill_level_usage
        self.fill_level_target = fill_level_target
        self.previous_actuator_statuses: Dict[str, str] = kwargs.get(
            "previous_actuator_statuses", {}
        )
        self.timers: Dict[str, timedelta] = kwargs.get("timers", {})
        self._states_by_bucket: Dict[int, FrbcState] = {}
        self.start_date = start_date
        self.end_date = end_date
        self.best_plan: Optional[FrbcState] = None
        self.emergency_state: Optional[FrbcState] = None
        self.target: float = 0.0
        self.min_constraint: float = 0.0
        self.max_constraint: float = 0.0

        # Cache for bucket calculation
        self._bucket_calc_params: Optional[Tuple[float, float, int]] = None

    def get_bucket_calculation_params(self) -> Tuple[float, float, int]:
        if self._bucket_calc_params is None:
            fill_level_range = self.system_description.storage.fill_level_range
            self._bucket_calc_params = (
                fill_level_range.start_of_range,
                fill_level_range.end_of_range,
                self.get_nr_of_buckets(),
            )
        return self._bucket_calc_params

    def get_nr_of_buckets(self) -> int:
        if self.computational_parameters is None:
            raise ValueError("Computational parameters are not set")
        return self.computational_parameters.get_nr_of_buckets()

    def set_targets(
        self, target: float, min_constraint: float, max_constraint: float
    ) -> None:
        self.target = target
        self.min_constraint = min_constraint
        self.max_constraint = max_constraint

    def add_state(self, state: Optional["FrbcState"]) -> None:
        if state is None:
            return

        if state.is_within_fill_level_range():
            bucket = state.bucket
            stored_state = self._states_by_bucket.get(bucket)
            if stored_state is None:
                self._states_by_bucket[bucket] = state
                state.set_selection_reason(SelectionReason.NO_ALTERNATIVE)
            else:
                selection_result = state.is_preferable_than(stored_state)
                if selection_result.result:
                    self._states_by_bucket[bucket] = state
                self._states_by_bucket[bucket].set_selection_reason(
                    selection_result.reason
                )
        else:
            if (
                self.emergency_state is None
                or state.get_fill_level_distance()
                < self.emergency_state.get_fill_level_distance()
            ):
                self.emergency_state = state
                state.set_selection_reason(SelectionReason.EMERGENCY_STATE)

    def add_all_states(self, states: List[Optional["FrbcState"]]) -> None:
        for state in states:
            self.add_state(state)

    @property
    def duration(self) -> timedelta:
        return self.end_date - self.start_date

    def get_duration_seconds(self) -> int:
        return int(self.duration.total_seconds())

    def get_target(self) -> float:
        return self.target

    def get_final_states(self) -> List["FrbcState"]:
        final_states = list(self._states_by_bucket.values())

        if not final_states and self.emergency_state is not None:
            return [self.emergency_state]
        return final_states

    def get_final_states_within_fill_level_target(self) -> List["FrbcState"]:
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

    def state_is_within_fill_level_target_range(self, state: "FrbcState") -> bool:
        if self.fill_level_target is None:
            return True
        return (
            self.fill_level_target.start_of_range is None
            or state.fill_level >= self.fill_level_target.start_of_range
        ) and (
            self.fill_level_target.end_of_range is None
            or state.fill_level <= self.fill_level_target.end_of_range
        )

    def get_fill_level_target_distance(self, state: "FrbcState") -> float:
        if self.fill_level_target is None:
            return 0
        if (
            self.fill_level_target.end_of_range is None
            or state.fill_level < self.fill_level_target.start_of_range
        ):
            return self.fill_level_target.start_of_range - state.fill_level
        else:
            return state.fill_level - self.fill_level_target.end_of_range

    def clear(self) -> None:
        self._states_by_bucket.clear()
        self.emergency_state = None
