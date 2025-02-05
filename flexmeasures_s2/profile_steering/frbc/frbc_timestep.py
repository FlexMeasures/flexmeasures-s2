from datetime import datetime, timedelta
from s2python.frbc import FRBCSystemDescription, FRBCLeakageBehaviour
from frbc_state import FrbcState, SelectionReason


class FrbcTimestep:
    def __init__(
        self,
        start_date: datetime,
        end_date: datetime,
        system_description: FRBCSystemDescription,
        leakage_behaviour: FRBCLeakageBehaviour,
        fill_level_target: float,
        forecasted_fill_level_usage: float,
        computational_parameters: object,
    ):
        self.nr_of_buckets = computational_parameters.get_nr_of_buckets()
        self.start_date = start_date
        self.end_date = end_date
        self.duration = end_date - start_date
        self.system_description = system_description
        self.leakage_behaviour = leakage_behaviour
        self.fill_level_target = fill_level_target
        self.forecasted_fill_level_usage = forecasted_fill_level_usage
        self.state_list = [None] * (self.nr_of_buckets + 1)
        self.emergency_state = None

    def get_nr_of_buckets(self):
        return self.nr_of_buckets

    def set_targets(self, target, min_constraint, max_constraint):
        self.target = target
        self.min_constraint = min_constraint
        self.max_constraint = max_constraint

    def add_state(self, state: FrbcState):
        if state.is_within_fill_level_range():
            stored_state = self.state_list[state.get_bucket()]
            if stored_state is None:
                self.state_list[state.get_bucket()] = state
                state.set_selection_reason(SelectionReason.NO_ALTERNATIVE)
            else:
                selection_result = state.is_preferable_than(stored_state)
                if selection_result.result:
                    self.state_list[state.get_bucket()] = state
                self.state_list[state.get_bucket()].set_selection_reason(
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

    def add_all_states(self, states):
        for state in states:
            self.add_state(state)

    def get_start_date(self):
        return self.start_date

    def get_end_date(self):
        return self.end_date

    def get_system_description(self):
        return self.system_description

    def get_leakage_behaviour(self):
        return self.leakage_behaviour

    def get_duration(self):
        return self.duration

    def get_duration_seconds(self):
        return int(self.duration.total_seconds())

    def get_target(self):
        return self.target

    def get_min_constraint(self):
        return self.min_constraint

    def get_max_constraint(self):
        return self.max_constraint

    def get_fill_level_target(self):
        return self.fill_level_target

    def get_state_list(self):
        return self.state_list

    def get_final_states(self):
        final_states = [state for state in self.state_list if state is not None]
        if not final_states:
            return [self.emergency_state]
        return final_states

    def get_final_states_within_fill_level_target(self):
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

    def state_is_within_fill_level_target_range(self, state):
        if self.fill_level_target is None:
            return True
        return (
            self.fill_level_target.get_start_of_range() is None
            or state.get_fill_level() >= self.fill_level_target.get_start_of_range()
        ) and (
            self.fill_level_target.get_end_of_range() is None
            or state.get_fill_level() <= self.fill_level_target.get_end_of_range()
        )

    def get_fill_level_target_distance(self, state):
        if (
            self.fill_level_target.get_end_of_range() is None
            or state.get_fill_level() < self.fill_level_target.get_start_of_range()
        ):
            return self.fill_level_target.get_start_of_range() - state.get_fill_level()
        else:
            return state.get_fill_level() - self.fill_level_target.get_end_of_range()

    def get_forecasted_usage(self):
        return self.forecasted_fill_level_usage

    def clear(self):
        self.state_list = [None] * len(self.state_list)
        self.emergency_state = None
