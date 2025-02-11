from typing import Optional
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from flexmeasures_s2.profile_steering.device_planner.device_planner import DevicePlanner


# TODO: need a DevicePlanner class
class Proposal:
    def __init__(
        self,
        global_diff_target: TargetProfile,
        diff_to_congestion_max: JouleProfile,
        diff_to_congestion_min: JouleProfile,
        proposed_plan: JouleProfile,
        old_plan: JouleProfile,
        origin: DevicePlanner,
    ):
        self.global_diff_target = global_diff_target
        self.diff_to_congestion_max = diff_to_congestion_max
        self.diff_to_congestion_min = diff_to_congestion_min
        self.proposed_plan = proposed_plan
        self.old_plan = old_plan
        self.global_improvement_value: Optional[float] = None
        self.congestion_improvement_value: Optional[float] = None
        self.cost_improvement_value: Optional[float] = None
        self.origin = origin

    def get_global_improvement_value(self) -> float:
        if self.global_improvement_value is None:
            self.global_improvement_value = (
                self.global_diff_target.sum_quadratic_distance()
                - self.global_diff_target.add(self.old_plan).subtract(self.proposed_plan).sum_quadratic_distance()
            )
        return self.global_improvement_value

    # def get_cost_improvement_value(self) -> float:
    #     if self.cost_improvement_value is None:
    #         self.cost_improvement_value = self.get_cost(
    #             self.old_plan, self.global_diff_target
    #         ) - self.get_cost(self.proposed_plan, self.global_diff_target)
    #     return self.cost_improvement_value

    # @staticmethod
    # def get_cost(plan: JouleProfile, target_profile: TargetProfile) -> float:
    #     cost = 0.0
    #     for i in range(target_profile.get_profile_metadata().get_nr_of_timesteps()):
    #         joule_usage = plan.get_elements()[i]
    #         target_element = target_profile.get_elements()[i]
    #         if isinstance(target_element, TargetProfile.TariffElement):
    #             cost += (joule_usage / 3_600_000) * target_element.get_tariff()
    #     return cost

    def get_congestion_improvement_value(self) -> float:
        if self.congestion_improvement_value is None:
            zero_profile = JouleProfile(
                self.old_plan.get_profile_metadata().get_profile_start(),
                self.old_plan.get_profile_metadata().get_timestep_duration(),
                [0] * len(self.old_plan.get_elements()),
            )
            exceed_max_target_old = self.diff_to_congestion_max.minimum(zero_profile).sum_quadratic_distance()
            exceed_max_target_proposal = (
                self.diff_to_congestion_max.add(self.old_plan)
                .subtract(self.proposed_plan)
                .minimum(zero_profile)
                .sum_quadratic_distance()
            )
            exceed_min_target_old = self.diff_to_congestion_min.maximum(zero_profile).sum_quadratic_distance()
            exceed_min_target_proposal = (
                self.diff_to_congestion_min.add(self.old_plan)
                .subtract(self.proposed_plan)
                .maximum(zero_profile)
                .sum_quadratic_distance()
            )
            if (
                exceed_max_target_old == exceed_max_target_proposal
                and exceed_min_target_old == exceed_min_target_proposal
            ):
                self.congestion_improvement_value = 0.0
            else:
                self.congestion_improvement_value = (
                    exceed_max_target_old
                    + exceed_min_target_old
                    - exceed_max_target_proposal
                    - exceed_min_target_proposal
                )
        return self.congestion_improvement_value

    def is_preferred_to(self, other: "Proposal") -> bool:
        if self.get_congestion_improvement_value() >= 0:
            if self.get_global_improvement_value() > other.get_global_improvement_value():
                return True
            elif (
                self.get_global_improvement_value()
                == other.get_global_improvement_value()
                # and self.get_cost_improvement_value()
                # > other.get_cost_improvement_value()
            ):
                return True
        return False

    def get_origin(self) -> DevicePlanner:
        return self.origin

    def get_proposed_plan(self) -> JouleProfile:
        return self.proposed_plan

    def get_old_plan(self) -> JouleProfile:
        return self.old_plan
