from datetime import datetime
from typing import Optional
import logging

from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.proposal import Proposal
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_plan import S2DdbcPlan
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_instruction_profile import (
    S2DdbcInstructionProfile,
)
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata
from flexmeasures_s2.profile_steering.common.device_plan import DevicePlan
from flexmeasures_s2.profile_steering.device_planner.ddbc.ddbc_planning_window import (
    DdbcPlanningWindow,
)
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_device_state import (
    S2DdbcDeviceState,
)
from flexmeasures_s2.profile_steering.device_planner.device_planner_abstract import (
    DevicePlanner,
)


class S2DdbcDevicePlanner(DevicePlanner):
    """Device planner for Demand-Driven Based Control (DDBC) devices."""

    STRATIFICATION_LAYERS = 50

    def __init__(
        self,
        s2_ddbc_state: S2DdbcDeviceState,
        profile_metadata: ProfileMetadata,
        plan_due_by_date: datetime,
        congestion_point_id: str,
    ):
        self._congestion_point_id = congestion_point_id
        self.s2_ddbc_state = s2_ddbc_state
        self.profile_metadata = profile_metadata
        self.zero_profile = JouleProfile(
            profile_metadata.profile_start,
            profile_metadata.timestep_duration,
            [0] * profile_metadata.nr_of_timesteps,
        )
        self.null_profile = JouleProfile(
            profile_metadata.profile_start,
            profile_metadata.timestep_duration,
            elements=[None] * profile_metadata.nr_of_timesteps,
        )

        self.state_tree: Optional[DdbcPlanningWindow]
        if self._is_device_available(self.s2_ddbc_state):
            self.state_tree = DdbcPlanningWindow(
                self.s2_ddbc_state,
                profile_metadata,
                plan_due_by_date,
            )
        else:
            self.state_tree = None

        self._priority_class = s2_ddbc_state.get_priority_class()
        self.latest_plan: Optional[S2DdbcPlan] = None
        self.accepted_plan: Optional[S2DdbcPlan] = None

    def _is_device_available(self, ddbc_state: S2DdbcDeviceState) -> bool:
        """Check if the device is available for planning."""
        return ddbc_state.is_device_online()

    @property
    def priority_class(self) -> int:
        return self._priority_class

    @property
    def device_id(self) -> str:
        return self.s2_ddbc_state.get_device_id()

    @property
    def connection_id(self) -> str:
        return self.s2_ddbc_state.get_connection_id()

    @property
    def congestion_point_id(self) -> str:
        return self._congestion_point_id

    @property
    def device_name(self) -> str:
        return self.s2_ddbc_state.get_device_name()

    def create_improved_planning(
        self,
        diff_to_global_target: TargetProfile,
        diff_to_max: JouleProfile,
        diff_to_min: JouleProfile,
        plan_due_by_date: datetime,
    ) -> Proposal:
        """Create an improved planning based on the difference to global target."""
        if self.accepted_plan is None:
            raise ValueError("No accepted plan found")

        target = diff_to_global_target.add(self.accepted_plan.get_energy())
        max_profile = diff_to_max.add(self.accepted_plan.get_energy())
        min_profile = diff_to_min.add(self.accepted_plan.get_energy())

        if (
            self._is_device_available(self.s2_ddbc_state)
            and self.state_tree is not None
        ):
            self.latest_plan = self.state_tree.find_best_plan(
                target, min_profile, max_profile
            )
        else:
            self.latest_plan = S2DdbcPlan(
                idle=True,
                energy=self.zero_profile,
                operation_mode_id=None,
                s2_ddbc_insights_profile=None,
            )

        if self.latest_plan is None:
            raise ValueError("No latest plan found")

        proposal = Proposal(
            global_diff_target=diff_to_global_target,
            diff_to_congestion_max=diff_to_max,
            diff_to_congestion_min=diff_to_min,
            proposed_plan=self.latest_plan.get_energy(),
            old_plan=self.accepted_plan.get_energy(),
            origin=self,
        )
        return proposal

    def create_initial_planning(self, plan_due_by_date: datetime) -> S2DdbcPlan:
        """Create an initial planning."""
        if (
            self._is_device_available(self.s2_ddbc_state)
            and self.state_tree is not None
        ):
            self.latest_plan = self.state_tree.find_best_plan(
                TargetProfile.null_profile(self.profile_metadata),
                self.null_profile,
                self.null_profile,
            )
        else:
            self.latest_plan = S2DdbcPlan(
                idle=True,
                energy=self.zero_profile,
                operation_mode_id=None,
                s2_ddbc_insights_profile=None,
            )
        self.accepted_plan = self.latest_plan
        return self.latest_plan

    def accept_proposal(self, accepted_proposal: Proposal) -> None:
        """Accept a proposal."""
        if self.latest_plan is None:
            raise ValueError("No latest plan found")
        if accepted_proposal.origin != self:
            raise ValueError(
                f"Device controller '{self.device_id}' received a proposal that it did not send."
            )
        if not accepted_proposal.proposed_plan == self.latest_plan.get_energy():
            raise ValueError(
                f"Device controller '{self.device_id}' received a proposal that it did not send."
            )
        if accepted_proposal.get_congestion_improvement_value() < 0:
            raise ValueError(
                f"Device controller '{self.device_id}' received a proposal with negative improvement"
            )
        self.accepted_plan = self.latest_plan

    def get_latest_plan(self) -> Optional[S2DdbcPlan]:
        """Get the latest plan."""
        return self.latest_plan

    def set_accepted_plan(self, plan: S2DdbcPlan) -> None:
        """Set the accepted plan."""
        if not isinstance(plan, S2DdbcPlan):
            raise TypeError(f"Expected S2DdbcPlan, but got {type(plan)}")
        self.accepted_plan = plan

    def current_profile(self) -> JouleProfile:
        """Get the current profile."""
        if self.accepted_plan is None:
            raise ValueError("No accepted plan found")
        return self.accepted_plan.get_energy()

    def get_device_plan(self) -> Optional[DevicePlan]:
        """Get the device plan."""
        if self.accepted_plan is None:
            return None

        logging.debug(
            dict(
                device_id=self.device_id,
                device_name=self.device_name,
                connection_id=self.connection_id,
                energy_profile=self.accepted_plan.get_energy(),
                instruction_profile=self.convert_plan_to_instructions(
                    self.profile_metadata, self.accepted_plan
                ),
            )
        )
        return DevicePlan(
            device_id=self.device_id,
            device_name=self.device_name,
            connection_id=self.connection_id,
            energy_profile=self.accepted_plan.get_energy(),
            fill_level_profile=None,
            instruction_profile=self.convert_plan_to_instructions(
                self.profile_metadata, self.accepted_plan
            ),
            insights_profile=self.accepted_plan.get_s2_ddbc_insights_profile(),
        )

    @staticmethod
    def convert_plan_to_instructions(
        profile_metadata: ProfileMetadata, device_plan: S2DdbcPlan
    ) -> S2DdbcInstructionProfile:
        """Convert a plan to instruction profile."""
        elements = []
        actuator_configurations_per_timestep = device_plan.get_operation_mode_id()

        if actuator_configurations_per_timestep is not None:
            for actuator_configurations in actuator_configurations_per_timestep:
                new_element = S2DdbcInstructionProfile.Element(
                    not actuator_configurations, actuator_configurations
                )
                elements.append(new_element)

        return S2DdbcInstructionProfile(profile_metadata, elements)
