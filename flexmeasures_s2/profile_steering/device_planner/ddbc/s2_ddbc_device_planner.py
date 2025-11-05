from datetime import datetime
from typing import Optional
from flexmeasures_s2.profile_steering.device_planner.device_planner_abstract import (
    DevicePlanner,
)
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from flexmeasures_s2.profile_steering.common.device_plan import DevicePlan
from flexmeasures_s2.profile_steering.common.proposal import Proposal
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_device_state import (
    S2DdbcDeviceState,
)
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_plan import (
    S2DdbcPlan,
)
from flexmeasures_s2.profile_steering.device_planner.ddbc.ddbc_planning_window import (
    DdbcPlanningWindow,
)


class S2DdbcDevicePlanner(DevicePlanner):
    """
    Device planner for DDBC (Demand Driven Based Control) devices.

    DDBC devices control supply-based systems like heat pumps or gas boilers
    that need to meet thermal demand forecasts.
    """

    STRATIFICATION_LAYERS = 50

    def __init__(
        self,
        device_state: S2DdbcDeviceState,
        profile_metadata: ProfileMetadata,
        plan_due_by_date: datetime,
        congestion_point_id: str,
    ):
        self.device_state = device_state
        self.profile_metadata = profile_metadata
        self._congestion_point_id = congestion_point_id
        self.priority_class_value = device_state.priority_class

        # Create zero and null profiles
        self.zero_profile = JouleProfile(metadata=profile_metadata, value=0)
        self.null_profile = JouleProfile(
            metadata=profile_metadata,
            elements=[None] * profile_metadata.nr_of_timesteps,  # type: ignore[list-item]
        )

        # Track plans
        self.latest_plan: Optional[S2DdbcPlan] = None
        self.accepted_plan: Optional[S2DdbcPlan] = None

        # Initialize planning window for DDBC planning
        self.planning_window: Optional[DdbcPlanningWindow]
        if self.is_device_available(device_state):
            self.planning_window = DdbcPlanningWindow(
                device_state, profile_metadata, plan_due_by_date
            )
        else:
            self.planning_window = None

    def is_device_available(self, device_state: S2DdbcDeviceState) -> bool:
        """
        Check if the device is available for planning.
        Simplified version - just checks if device is online.
        """
        # TODO: Add more sophisticated availability checking based on system descriptions
        return device_state.is_online

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
        return self.priority_class_value

    def create_initial_planning(self, plan_due_by_date: datetime) -> S2DdbcPlan:
        """
        Create initial planning for a DDBC device.
        Uses the planning window to find a plan that meets demand forecasts.
        """
        if (
            self.is_device_available(self.device_state)
            and self.planning_window is not None
        ):
            # Use planning window to find best plan
            self.latest_plan = self.planning_window.find_best_plan(
                TargetProfile.null_profile(self.profile_metadata),
                self.null_profile,
                self.null_profile,
            )
        else:
            self.latest_plan = S2DdbcPlan(
                idle=True, energy=self.zero_profile, operation_mode_id=None
            )

        self.accepted_plan = self.latest_plan
        return self.latest_plan

    def create_improved_planning(
        self,
        difference_profile: TargetProfile,
        diff_to_max_value: JouleProfile,
        diff_to_min_value: JouleProfile,
        plan_due_by_date: datetime,
    ) -> Proposal:
        """
        Attempt to create an improved planning for a DDBC device.
        """
        if self.accepted_plan is None:
            raise ValueError("No accepted plan found")

        # Calculate target profiles
        target = difference_profile.add(self.accepted_plan.energy)
        max_profile = diff_to_max_value.add(self.accepted_plan.energy)
        min_profile = diff_to_min_value.add(self.accepted_plan.energy)

        if (
            self.is_device_available(self.device_state)
            and self.planning_window is not None
        ):
            # Use planning window to find best plan with targets
            self.latest_plan = self.planning_window.find_best_plan(
                target, min_profile, max_profile
            )
        else:
            self.latest_plan = S2DdbcPlan(
                idle=True, energy=self.zero_profile, operation_mode_id=None
            )

        proposal = Proposal(
            global_diff_target=difference_profile,
            diff_to_congestion_max=diff_to_max_value,
            diff_to_congestion_min=diff_to_min_value,
            proposed_plan=self.latest_plan.energy,
            old_plan=self.accepted_plan.energy,
            origin=self,
        )

        return proposal

    def accept_proposal(self, proposal: Proposal) -> None:
        """
        Accept a proposal for this device.
        Validates that the proposal is from this planner.
        """
        if self.latest_plan is None:
            raise ValueError("No latest plan found")

        if proposal.origin != self:
            raise ValueError(
                f"Storage controller '{self.device_id}' received a proposal that it did not send."
            )

        if proposal.proposed_plan != self.latest_plan.energy:
            raise ValueError(
                f"Storage controller '{self.device_id}' received a proposal that it did not send."
            )

        if proposal.get_congestion_improvement_value() < 0:
            raise ValueError(
                f"Storage controller '{self.device_id}' received a proposal with negative improvement"
            )

        self.accepted_plan = self.latest_plan

    def current_profile(self) -> JouleProfile:
        """
        Get the current profile of the device.
        """
        if self.accepted_plan is None:
            raise ValueError("No accepted plan found")
        return self.accepted_plan.energy

    def get_device_plan(self) -> DevicePlan:
        """
        Get the device plan for this DDBC device.
        """
        if self.accepted_plan is None:
            raise ValueError("No accepted plan found")

        # TODO: Convert plan to DDBC instructions
        # instruction_profile = self.convert_plan_to_instructions(
        #     self.profile_metadata,
        #     self.accepted_plan.operation_mode_id
        # )

        return DevicePlan(
            device_id=self.device_id,
            device_name=self.device_name,
            connection_id=self.connection_id,
            energy_profile=self.accepted_plan.energy,
            fill_level_profile=None,
            instruction_profile=None,  # TODO: Add DDBC instruction profile
        )

    def get_latest_plan(self) -> S2DdbcPlan:
        """
        Get the latest calculated plan.
        """
        if self.latest_plan is None:
            raise ValueError("No latest plan found")
        return self.latest_plan

    def set_accepted_plan(self, plan: S2DdbcPlan) -> None:
        """
        Forcefully set the accepted plan for the device.
        """
        if not isinstance(plan, S2DdbcPlan):
            raise TypeError(f"Expected S2DdbcPlan, but got {type(plan)}")
        self.accepted_plan = plan
