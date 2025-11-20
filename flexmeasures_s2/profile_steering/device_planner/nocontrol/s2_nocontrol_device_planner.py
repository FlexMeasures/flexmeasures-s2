from datetime import datetime
from typing import Optional
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.proposal import Proposal
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from flexmeasures_s2.profile_steering.common.device_plan import DevicePlan
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata
from flexmeasures_s2.profile_steering.device_planner.device_planner_abstract import (
    DevicePlanner,
)
from flexmeasures_s2.profile_steering.device_planner.nocontrol.s2_nocontrol_device_state import (
    S2NoControlDeviceState,
)
from flexmeasures_s2.profile_steering.device_planner.nocontrol.conversion_utils import (
    convert_power_forecast,
)
from flexmeasures_s2.profile_steering.device_planner.nocontrol.proposal_without_improvement import (
    ProposalWithoutImprovement,
)
from flexmeasures_s2.profile_steering.device_planner.nocontrol.s2_nocontrol_plan import (
    S2NoControlPlan,
)


class S2NoControlDevicePlanner(DevicePlanner):
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
            energy_profile = JouleProfile(
                profile_start=profile_metadata.profile_start,
                timestep_duration=profile_metadata.timestep_duration,
                elements=[0] * profile_metadata.nr_of_timesteps,
            )
        else:
            energy_profile = convert_power_forecast(
                device_state.get_power_forecast(), profile_metadata
            )
        self.profile = S2NoControlPlan(energy=energy_profile)
        self.accepted_plan: Optional[S2NoControlPlan] = None

    @property
    def priority_class(self) -> int:
        return self.device_state.priority_class

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

    def create_initial_planning(
        self, plan_due_by_date: datetime, ids: Optional[dict] = None
    ) -> S2NoControlPlan:
        self.accepted_plan = self.profile
        return self.profile

    def create_improved_planning(
        self,
        difference_profile: TargetProfile,
        diff_to_max_value: JouleProfile,
        diff_to_min_value: JouleProfile,
        plan_due_by_date: datetime,
    ) -> Optional[Proposal]:
        if self.accepted_plan is None:
            raise ValueError("No accepted plan found")
        return ProposalWithoutImprovement(self.profile.energy, self)

    def accept_proposal(self, accepted_proposal: Proposal) -> None:
        if accepted_proposal.origin != self:
            raise ValueError(
                f"Planner for '{self.device_id}' received a proposal that he did not send."
            )

        if (
            accepted_proposal.proposed_plan.elements
            != accepted_proposal.old_plan.elements
            or accepted_proposal.old_plan.elements != self.profile.energy.elements
        ):
            raise ValueError(
                f"Planner for '{self.device_id}' received a proposal that he did not send."
            )
        self.accepted_plan = self.profile

    def current_profile(self) -> JouleProfile:
        if self.accepted_plan is None:
            raise ValueError("No accepted plan found")
        return self.accepted_plan.energy

    def get_device_plan(self) -> Optional[DevicePlan]:
        if self.accepted_plan is None:
            return None
        return DevicePlan(
            device_id=self.device_id,
            device_name=self.device_name,
            connection_id=self.connection_id,
            energy_profile=self.accepted_plan.energy,
            fill_level_profile=None,
            instruction_profile=None,
        )

    def get_latest_plan(self) -> Optional[S2NoControlPlan]:
        return self.profile

    def set_accepted_plan(self, plan: S2NoControlPlan) -> None:
        if not isinstance(plan, S2NoControlPlan):
            raise TypeError(f"Expected S2NoControlPlan, but got {type(plan)}")
        self.accepted_plan = plan
        self.profile = plan
