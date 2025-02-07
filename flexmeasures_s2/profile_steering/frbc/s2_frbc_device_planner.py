from datetime import datetime, timedelta
from typing import Optional
from operation_mode_profile_tree import OperationModeProfileTree
from common.joule_profile import JouleProfile
from common.proposal import Proposal
from common.target_profile import TargetProfile
from s2_frbc_plan import S2FrbcPlan
from s2_frbc_instruction_profile import S2FrbcInstructionProfile
from common.profile_metadata import ProfileMetadata
from frbc.s2_frbc_device_state_wrapper import S2FrbcDeviceStateWrapper
from common.device_planner.device_plan import DevicePlan


class S2FrbcDevicePlanner:
    def __init__(self, s2_frbc_state: S2FrbcDeviceStateWrapper, profile_metadata: ProfileMetadata, plan_due_by_date: datetime):
        self.s2_frbc_state = s2_frbc_state
        self.profile_metadata = profile_metadata
        self.zero_profile = JouleProfile(profile_metadata, 0)
        self.null_profile = JouleProfile(profile_metadata, None)
        self.state_tree: Optional[OperationModeProfileTree] = None
        if self.is_storage_available(s2_frbc_state):
            self.state_tree = OperationModeProfileTree(
                s2_frbc_state, profile_metadata, plan_due_by_date
            )
        self.priority_class = s2_frbc_state.get_priority_class()
        self.latest_plan: Optional[S2FrbcPlan] = None
        self.accepted_plan: Optional[S2FrbcPlan] = None

    def is_storage_available(self, storage_state: S2FrbcDeviceStateWrapper) -> bool:
        latest_before_first_ptu = OperationModeProfileTree.get_latest_before(
            self.profile_metadata.get_profile_start(),
            storage_state.get_system_descriptions(),
            lambda sd: sd.get_valid_from(),
        )
        if not storage_state.get_system_descriptions():
            return False
        if latest_before_first_ptu is None:
            active_and_upcoming_system_descriptions_has_active_storage = any(
                sd.get_valid_from() <= self.profile_metadata.get_profile_end()
                and sd.get_valid_from() >= self.profile_metadata.get_profile_start()
                and sd.get_storage().get_status() is not None
                for sd in storage_state.get_system_descriptions()
            )
        else:
            active_and_upcoming_system_descriptions_has_active_storage = any(
                sd.get_valid_from() <= self.profile_metadata.get_profile_end()
                and sd.get_valid_from() >= latest_before_first_ptu.get_valid_from()
                and sd.get_storage().get_status() is not None
                for sd in storage_state.get_system_descriptions()
            )
        return (
            storage_state.is_online()
            and active_and_upcoming_system_descriptions_has_active_storage
        )

    def get_device_id(self) -> str:
        return self.s2_frbc_state.get_device_id()

    def get_connection_id(self) -> str:
        return self.s2_frbc_state.get_connection_id()

    def get_device_name(self) -> str:
        return self.s2_frbc_state.get_device_name()

    def create_improved_planning(
        self, diff_to_global_target: JouleProfile, diff_to_max: JouleProfile, diff_to_min: JouleProfile, plan_due_by_date: datetime
    ) -> Proposal:
        target = diff_to_global_target.add(self.accepted_plan.get_energy())
        max_profile = diff_to_max.add(self.accepted_plan.get_energy())
        min_profile = diff_to_min.add(self.accepted_plan.get_energy())
        if self.is_storage_available(self.s2_frbc_state):
            self.latest_plan = self.state_tree.find_best_plan(
                target, min_profile, max_profile
            )
        else:
            self.latest_plan = S2FrbcPlan(True, self.zero_profile, None, None, None)
        proposal = Proposal(
            diff_to_global_target,
            diff_to_max,
            diff_to_min,
            self.latest_plan.get_energy(),
            self.accepted_plan.get_energy(),
            self,
        )
        return proposal

    def create_initial_planning(self, plan_due_by_date: datetime) -> JouleProfile:
        if self.is_storage_available(self.s2_frbc_state):
            self.latest_plan = self.state_tree.find_best_plan(
                TargetProfile.null_profile(self.profile_metadata),
                self.null_profile,
                self.null_profile,
            )
        else:
            self.latest_plan = S2FrbcPlan(True, self.zero_profile, None, None, None)
        self.accepted_plan = self.latest_plan
        return self.latest_plan.get_energy()

    def accept_proposal(self, accepted_proposal: Proposal) -> None:
        if accepted_proposal.get_origin() != self:
            raise ValueError(
                f"Storage controller '{self.get_device_id()}' received a proposal that he did not send."
            )
        if not accepted_proposal.get_proposed_plan().equals(
            self.latest_plan.get_energy()
        ):
            raise ValueError(
                f"Storage controller '{self.get_device_id()}' received a proposal that he did not send."
            )
        if accepted_proposal.get_congestion_improvement_value() < 0:
            raise ValueError(
                f"Storage controller '{self.get_device_id()}' received a proposal with negative improvement"
            )
        self.accepted_plan = self.latest_plan

    def get_current_profile(self) -> JouleProfile:
        return self.accepted_plan.get_energy()

    def get_latest_plan(self) -> Optional[S2FrbcPlan]:
        return self.latest_plan

    def get_device_plan(self) -> DevicePlan:
        return DevicePlan(
            self.get_device_id(),
            self.get_device_name(),
            self.get_connection_id(),
            self.accepted_plan.get_energy(),
            self.accepted_plan.get_fill_level(),
            self.convert_plan_to_instructions(
                self.profile_metadata, self.accepted_plan
            ),
            self.accepted_plan.get_s2_frbc_insights_profile(),
        )

    @staticmethod
    def convert_plan_to_instructions(profile_metadata: ProfileMetadata, device_plan: S2FrbcPlan) -> S2FrbcInstructionProfile:
        elements = []
        actuator_configurations_per_timestep = device_plan.get_operation_mode_id()
        if actuator_configurations_per_timestep is not None:
            for actuator_configurations in actuator_configurations_per_timestep:
                new_element = S2FrbcInstructionProfile.Element(
                    not actuator_configurations, actuator_configurations
                )
                elements.append(new_element)
        else:
            elements = [None] * profile_metadata.get_nr_of_timesteps()
        return S2FrbcInstructionProfile(profile_metadata, elements)

    def get_priority_class(self) -> int:
        return self.priority_class
