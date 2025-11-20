from flexmeasures_s2.profile_steering.common.proposal import Proposal
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from flexmeasures_s2.profile_steering.device_planner.device_planner_abstract import (
    DevicePlanner,
)


class ProposalWithoutImprovement(Proposal):
    def __init__(self, plan: JouleProfile, origin: DevicePlanner):
        null_target = TargetProfile(
            plan.metadata.profile_start,
            plan.metadata.timestep_duration,
            [TargetProfile.NULL_ELEMENT] * plan.metadata.nr_of_timesteps,
        )
        null_joule_profile = JouleProfile(
            plan.metadata.profile_start,
            plan.metadata.timestep_duration,
            [0] * plan.metadata.nr_of_timesteps,
        )
        super().__init__(
            global_diff_target=null_target,
            diff_to_congestion_max=null_joule_profile,
            diff_to_congestion_min=null_joule_profile,
            proposed_plan=plan,
            old_plan=plan,
            origin=origin,
        )

    def get_global_improvement_value(self) -> float:
        return 0.0

    def get_congestion_improvement_value(self) -> float:
        return 0.0

    def get_cost_improvement_value(self) -> float:
        return 0.0
