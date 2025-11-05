from datetime import datetime
from flexmeasures_s2.profile_steering.device_planner.device_planner_abstract import (
    DevicePlanner,
)
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from flexmeasures_s2.profile_steering.common.device_plan import DevicePlan
from flexmeasures_s2.profile_steering.device_planner.nocontrol.s2_nocontrol_device_state import (
    S2NoControlDeviceState,
)
from flexmeasures_s2.profile_steering.device_planner.nocontrol.proposal_without_improvement import (
    ProposalWithoutImprovement,
)
from flexmeasures_s2.profile_steering.device_planner.nocontrol.conversion_utils import (
    convert_power_forecast_to_joule_profile,
)
from flexmeasures_s2.profile_steering.device_planner.nocontrol.s2_nocontrol_plan import (
    S2NoControlPlan,
)


class S2NoControlDevicePlanner(DevicePlanner):
    """
    Device planner for devices with no control capabilities.
    These devices have a fixed power forecast and cannot be optimized.
    This is a Python port of the Java S2NoControlDevicePlanner class.
    """

    def __init__(
        self,
        device_state: S2NoControlDeviceState,
        profile_metadata: ProfileMetadata,
        congestion_point_id: str,
    ):
        self.device_state = device_state
        self.profile_metadata = profile_metadata
        self._congestion_point_id = congestion_point_id

        if device_state.get_power_forecast() is None:
            self.profile = JouleProfile(metadata=profile_metadata, value=0)
        else:
            self.profile = convert_power_forecast_to_joule_profile(
                device_state.get_power_forecast(), profile_metadata
            )

    @property
    def device_id(self) -> str:
        return self.device_state.device_id

    @property
    def device_name(self) -> str:
        return self.device_state.device_name

    @property
    def connection_id(self) -> str:
        return self.device_state.connection_id

    @property
    def congestion_point_id(self) -> str:
        return self._congestion_point_id

    @property
    def priority_class(self) -> int:
        return self.device_state.priority_class

    def create_initial_planning(self, plan_due_by_date: datetime) -> S2NoControlPlan:
        """
        Create initial planning for a nocontrol device.
        Since the device cannot be controlled, this just returns the fixed profile.

        Args:
            plan_due_by_date: The date by which the plan must be ready (not used)

        Returns:
            A plan with the fixed power forecast profile
        """
        return S2NoControlPlan(self.profile)

    def create_improved_planning(
        self,
        difference_profile: TargetProfile,
        diff_to_max_value: JouleProfile,
        diff_to_min_value: JouleProfile,
        plan_due_by_date: datetime,
    ) -> ProposalWithoutImprovement:
        """
        Attempt to create an improved planning for a nocontrol device.
        Since the device cannot be controlled, this returns a proposal with no improvement.

        Args:
            difference_profile: The difference profile for the cluster (not used)
            diff_to_max_value: The difference to the maximum profile (not used)
            diff_to_min_value: The difference to the minimum profile (not used)
            plan_due_by_date: The date by which the plan must be ready (not used)

        Returns:
            A ProposalWithoutImprovement indicating no changes can be made
        """
        return ProposalWithoutImprovement(self.profile, self)

    def accept_proposal(self, proposal: ProposalWithoutImprovement) -> None:  # type: ignore[override]
        """
        Accept a proposal for this device.
        Validates that the proposal is from this planner and hasn't changed.

        Args:
            proposal: The proposal to accept

        Raises:
            ValueError: If the proposal is not valid
        """
        if proposal.origin != self:
            raise ValueError(
                f"Planner for '{self.device_id}' received a proposal that it did not send."
            )

        if proposal.proposed_plan != self.profile or proposal.old_plan != self.profile:
            raise ValueError(
                f"Planner for '{self.device_id}' received a proposal that it did not send."
            )

    def current_profile(self) -> JouleProfile:
        """
        Get the current profile of the device.

        Returns:
            The fixed power forecast profile
        """
        return self.profile

    def get_device_plan(self) -> DevicePlan:
        """
        Get the device plan for this nocontrol device.

        Returns:
            A DevicePlan with the fixed energy profile
        """
        return DevicePlan(
            device_id=self.device_id,
            device_name=self.device_name,
            connection_id=self.connection_id,
            energy_profile=self.profile,
            fill_level_profile=None,
            instruction_profile=None,
        )

    def get_latest_plan(self) -> S2NoControlPlan:
        """
        Get the latest calculated plan.
        For nocontrol devices, this is always the fixed profile.

        Returns:
            A plan with the fixed power forecast profile
        """
        return S2NoControlPlan(self.profile)

    def set_accepted_plan(self, plan: S2NoControlPlan) -> None:
        """
        Forcefully set the accepted plan for the device.
        For nocontrol devices, this validates but doesn't change the profile.

        Args:
            plan: The plan to set

        Raises:
            ValueError: If the plan doesn't match the fixed profile
        """
        if not isinstance(plan, S2NoControlPlan) or plan.energy != self.profile:
            raise ValueError(
                f"Cannot set a different plan for nocontrol device '{self.device_id}'"
            )
