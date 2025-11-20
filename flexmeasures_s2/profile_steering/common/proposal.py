from typing import Optional
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from flexmeasures_s2.profile_steering.device_planner.device_planner_abstract import (
    DevicePlanner,
)


class Proposal:
    """Represents a proposed plan improvement from a device planner.

    A Proposal contains:
    - The proposed new plan (proposed_plan)
    - The current plan being replaced (old_plan)
    - Improvement metrics (energy, cost, congestion)
    - Context information (global target difference, congestion constraints)

    Proposals are evaluated by the planning algorithm to determine which
    improvements to accept. The evaluation considers:
    1. Congestion improvement: How much the proposal reduces constraint violations
    2. Global improvement: How much the proposal moves toward the global target
    3. Cost improvement: How much the proposal reduces cost (for tariff-based targets)

    Proposals are compared using is_preferred_to() which prioritizes congestion
    improvements first, then global improvements, then cost improvements.
    """

    def __init__(
        self,
        global_diff_target: TargetProfile,
        diff_to_congestion_max: JouleProfile,
        diff_to_congestion_min: JouleProfile,
        proposed_plan: JouleProfile,
        old_plan: JouleProfile,
        origin: DevicePlanner,
    ):
        """Initialize a proposal.

        Args:
            global_diff_target: Difference between global target and current
                root-level planning. Used to compute global improvement.
            diff_to_congestion_max: Difference to congestion point maximum constraint.
                Positive values indicate exceeding the max.
            diff_to_congestion_min: Difference to congestion point minimum constraint.
                Negative values indicate below the min.
            proposed_plan: The new plan being proposed
            old_plan: The current plan being replaced
            origin: The device planner that created this proposal
        """
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
        """Calculate the global energy improvement value.

        Computes the reduction in quadratic distance to the global target.
        Positive values indicate improvement (moving closer to target).

        Returns:
            The improvement value (positive = better)
        """
        if self.global_improvement_value is None:
            # print(f"self.old_plan: {self.old_plan}")
            # print(f"self.proposed_plan: {self.proposed_plan}")
            # print the quadratic distance of the global diff target
            # print(f"self.global_diff_target.sum_quadratic_distance(): {self.global_diff_target.sum_quadratic_distance()}")
            self.global_improvement_value = (
                self.global_diff_target.sum_quadratic_distance()
                - self.global_diff_target.add(self.old_plan)
                .subtract(self.proposed_plan)
                .sum_quadratic_distance()
            )
        return self.global_improvement_value

    def get_cost_improvement_value(self) -> float:
        """Calculate the cost improvement value.

        Computes the reduction in cost based on tariff elements in the target.
        Positive values indicate cost reduction (improvement).

        Returns:
            The cost improvement value (positive = lower cost)
        """
        if self.cost_improvement_value is None:
            self.cost_improvement_value = self.get_cost(
                self.old_plan, self.global_diff_target
            ) - self.get_cost(self.proposed_plan, self.global_diff_target)
        return self.cost_improvement_value

    @staticmethod
    def get_cost(plan: JouleProfile, target_profile: TargetProfile) -> float:
        cost = 0.0
        tariff_count = 0
        null_count = 0
        for i in range(target_profile.metadata.nr_of_timesteps):
            joule_usage = plan.elements[i]
            target_element = target_profile.elements[i]
            if isinstance(target_element, TargetProfile.TariffElement):
                tariff_count += 1
                if joule_usage is not None:
                    cost += (joule_usage / 3_600_000) * target_element.get_tariff()
            elif isinstance(target_element, TargetProfile.NullElement):
                null_count += 1
        if tariff_count == 0 and null_count > 0:
            # print(
            #     f"  WARNING: get_cost called with {null_count} NullElements, {tariff_count} TariffElements - cost will be 0!"
            # )
            pass
        return cost

    def get_congestion_improvement_value(self) -> float:
        """Calculate the congestion point improvement value.

        Computes the reduction in constraint violations at the congestion point.
        Positive values indicate improvement (reducing violations of min/max constraints).

        Returns:
            The congestion improvement value (positive = fewer violations)
        """
        if self.congestion_improvement_value is None:
            zero_profile = JouleProfile(
                self.old_plan.metadata.profile_start,
                self.old_plan.metadata.timestep_duration,
                [0] * len(self.old_plan.elements),
            )
            exceed_max_target_old = self.diff_to_congestion_max.minimum(
                zero_profile
            ).sum_quadratic_distance()
            # print(f"exceed_max_target_old: {exceed_max_target_old}")
            # print(f"self.diff_to_congestion_max: {self.diff_to_congestion_max}")
            exceed_max_target_proposal = (
                self.diff_to_congestion_max.add(self.old_plan)
                .subtract(self.proposed_plan)
                .minimum(zero_profile)
                .sum_quadratic_distance()
            )
            # print(f"exceed_max_target_proposal: {exceed_max_target_proposal}")
            exceed_min_target_old = self.diff_to_congestion_min.maximum(
                zero_profile
            ).sum_quadratic_distance()
            # print(f"exceed_min_target_old: {exceed_min_target_old}")
            exceed_min_target_proposal = (
                self.diff_to_congestion_min.add(self.old_plan)
                .subtract(self.proposed_plan)
                .maximum(zero_profile)
                .sum_quadratic_distance()
            )
            # print(f"exceed_min_target_proposal: {exceed_min_target_proposal}")
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
                # print(f"congestion_improvement_value: {self.congestion_improvement_value}")
        return self.congestion_improvement_value

    def is_preferred_to(self, other: "Proposal") -> bool:
        """Check if this proposal is preferred over another.

        Comparison logic:
        1. If this proposal has non-negative congestion improvement:
           - Prefer the one with higher global improvement
           - If equal, prefer the one with higher cost improvement
        2. If this proposal has negative congestion improvement, it's not preferred

        Args:
            other: The other proposal to compare against

        Returns:
            True if this proposal is preferred, False otherwise
        """
        if self.get_congestion_improvement_value() >= 0:
            if (
                self.get_global_improvement_value()
                > other.get_global_improvement_value()
            ):
                return True
            elif (
                self.get_global_improvement_value()
                == other.get_global_improvement_value()
                and self.get_cost_improvement_value()
                > other.get_cost_improvement_value()
            ):
                return True
        return False
