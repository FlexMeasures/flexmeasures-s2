from flexmeasures_s2.profile_steering.common.proposal import Proposal
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.device_planner.device_planner_abstract import (
    DevicePlanner,
)


class ProposalWithoutImprovement(Proposal):
    """A special proposal for devices that cannot be improved.

    This proposal type is used for nocontrol devices that have fixed power
    forecasts and cannot be optimized. It always returns zero improvement
    values, indicating that no changes can be made to the device's plan.

    The planning algorithm accepts these proposals to acknowledge that the
    device has been considered, but they never win the proposal comparison
    since they provide no improvement.

    Attributes:
        All attributes inherited from Proposal, but with zero improvement values
    """

    def __init__(self, plan: JouleProfile, origin: DevicePlanner):
        # Call parent constructor with None for diff profiles since
        # nocontrol devices don't respond to target profiles
        super().__init__(
            global_diff_target=None,  # type: ignore[arg-type]
            diff_to_congestion_max=None,  # type: ignore[arg-type]
            diff_to_congestion_min=None,  # type: ignore[arg-type]
            proposed_plan=plan,
            old_plan=plan,
            origin=origin,
        )

    def get_global_improvement_value(self) -> float:
        """No improvement possible for nocontrol devices."""
        return 0.0

    def get_congestion_improvement_value(self) -> float:
        """No improvement possible for nocontrol devices."""
        return 0.0

    def get_cost_improvement_value(self) -> float:
        """No improvement possible for nocontrol devices."""
        return 0.0
