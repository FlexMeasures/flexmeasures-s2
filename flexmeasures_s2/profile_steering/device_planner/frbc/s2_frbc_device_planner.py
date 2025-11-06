from datetime import datetime
from typing import Optional

# import logging

from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.proposal import Proposal
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_plan import S2FrbcPlan
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_instruction_profile import (
    S2FrbcInstructionProfile,
)
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata
from flexmeasures_s2.profile_steering.common.device_plan import (
    DevicePlan,
)
from flexmeasures_s2.profile_steering.device_planner.frbc.operation_mode_profile_tree import (
    OperationModeProfileTree,
)
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state import (
    S2FrbcDeviceState,
)
from flexmeasures_s2.profile_steering.device_planner.device_planner_abstract import (
    DevicePlanner,
)
from s2python.frbc import FRBCInstruction

# make sure this is a DevicePlanner


class S2FrbcDevicePlanner(DevicePlanner):
    def __init__(
        self,
        s2_frbc_state: S2FrbcDeviceState,
        profile_metadata: ProfileMetadata,
        plan_due_by_date: datetime,
        congestion_point_id: str,
    ):
        self._congestion_point_id = congestion_point_id
        self.s2_frbc_state = s2_frbc_state
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
        if self.is_storage_available(self.s2_frbc_state):
            self.state_tree = OperationModeProfileTree(
                self.s2_frbc_state,
                profile_metadata,
                plan_due_by_date,
            )
        self._priority_class = 1
        self.latest_plan: Optional[S2FrbcPlan] = None
        self.accepted_plan: Optional[S2FrbcPlan] = None

    def is_storage_available(self, storage_state: S2FrbcDeviceState) -> bool:
        latest_before_first_ptu = OperationModeProfileTree.get_latest_before(
            self.profile_metadata.profile_start.replace(tzinfo=None),
            storage_state.get_system_descriptions(),
            lambda sd: sd.valid_from.replace(tzinfo=None),
        )
        if not storage_state.get_system_descriptions():
            return False
        if latest_before_first_ptu is None:
            active_and_upcoming_system_descriptions_has_active_storage = any(
                # TODO: ask if TypeError: can't compare offset-naive and offset-aware datetimes could be solved differently
                self.profile_metadata.profile_end.replace(tzinfo=None)
                >= sd.valid_from.replace(tzinfo=None)
                >= self.profile_metadata.profile_start.replace(tzinfo=None)
                for sd in storage_state.get_system_descriptions()
            )
        else:
            active_and_upcoming_system_descriptions_has_active_storage = any(
                self.profile_metadata.profile_end.replace(tzinfo=None)
                >= sd.valid_from.replace(tzinfo=None)
                >= latest_before_first_ptu.valid_from.replace(tzinfo=None)
                for sd in storage_state.get_system_descriptions()
            )
        return (
            storage_state.is_online
            and active_and_upcoming_system_descriptions_has_active_storage
        )

    @property
    def priority_class(self) -> int:
        return self.s2_frbc_state.priority_class

    @property
    def device_id(self) -> str:
        return self.s2_frbc_state.device_id

    @property
    def connection_id(self) -> str:
        return self.s2_frbc_state.connection_id

    @property
    def congestion_point_id(self) -> str:
        return self._congestion_point_id

    @property
    def device_name(self) -> str:
        return self.s2_frbc_state.device_name

    def create_improved_planning(
        self,
        diff_to_global_target: TargetProfile,
        diff_to_max: JouleProfile,
        diff_to_min: JouleProfile,
        plan_due_by_date: datetime,
    ) -> Proposal:
        if self.accepted_plan is None:
            raise ValueError("No accepted plan found")

        # print(f"\n{'='*80}")
        # print(f"DEVICE PLANNER: create_improved_planning for {self.device_name}")
        # print(
        #     f"  Accepted plan energy: {sum(self.accepted_plan.energy.elements) if self.accepted_plan.energy else 0} J"
        # )
        # print(
        #     f"  diff_to_global_target has Joule elements: {diff_to_global_target.nr_of_joule_target_elements()}"
        # )
        # print(
        #     f"  diff_to_global_target nr_of_timesteps: {diff_to_global_target.metadata.nr_of_timesteps}"
        # )

        # Count tariff elements
        # tariff_count = sum(
        #     1
        #     for e in diff_to_global_target.elements
        #     if isinstance(e, TargetProfile.TariffElement)
        # )
        # null_count = sum(
        #     1
        #     for e in diff_to_global_target.elements
        #     if isinstance(e, TargetProfile.NullElement)
        # )
        # print(
        #     f"  Target elements: {tariff_count} TariffElement, {null_count} NullElement, {len(diff_to_global_target.elements)} total"
        # )

        # Show sample tariff values
        # if tariff_count > 0:
        #     sample_tariffs = [
        #         e.get_tariff()
        #         for e in diff_to_global_target.elements[:10]
        #         if isinstance(e, TargetProfile.TariffElement)
        #     ]
        #     print(f"  Sample tariff values (first 10): {sample_tariffs}")
        pass

        # TODO: check if diff_to_global_target has tarrif elements
        # TODO: check for NULL elements in target
        if diff_to_global_target.nr_of_joule_target_elements() != 0:
            target = diff_to_global_target.add(self.accepted_plan.energy)
        else:
            target = diff_to_global_target
            # print(
            #     "diff_to_global_target has no Joule elements, using the target directly"
            # )
            pass

        # print("  Final target for find_best_plan:")
        # tariff_count_final = sum(
        #     1 for e in target.elements if isinstance(e, TargetProfile.TariffElement)
        # )
        # null_count_final = sum(
        #     1 for e in target.elements if isinstance(e, TargetProfile.NullElement)
        # )
        # print(f"    {tariff_count_final} TariffElement, {null_count_final} NullElement")
        # print(f"{'='*80}\n")

        max_profile = diff_to_max.add(self.accepted_plan.energy)
        min_profile = diff_to_min.add(self.accepted_plan.energy)

        if self.is_storage_available(self.s2_frbc_state):
            self.latest_plan = self.state_tree.find_best_plan(
                target, min_profile, max_profile
            )

            # Log the new plan
            # new_energy = (
            #     sum(self.latest_plan.energy.elements)
            #     if self.latest_plan and self.latest_plan.energy
            #     else 0
            # )
            # print(f"  New plan energy: {new_energy} J")
            # print(
            #     f"  Energy difference: {new_energy - sum(self.accepted_plan.energy.elements)} J"
            # )
        else:
            self.latest_plan = S2FrbcPlan(
                idle=True,
                energy=self.zero_profile,
                fill_level=None,
                operation_mode_id=[],
            )
        if self.latest_plan is None:
            raise ValueError("No latest plan found")
        proposal = Proposal(
            global_diff_target=diff_to_global_target,
            diff_to_congestion_max=diff_to_max,
            diff_to_congestion_min=diff_to_min,
            proposed_plan=self.latest_plan.energy,
            old_plan=self.accepted_plan.energy,
            origin=self,
        )
        return proposal

    def create_initial_planning(
        self, plan_due_by_date: datetime, ids: Optional[dict] = None
    ) -> S2FrbcPlan:
        if self.is_storage_available(self.s2_frbc_state):
            if ids is None:
                self.latest_plan = self.state_tree.find_best_plan(
                    TargetProfile.null_profile(self.profile_metadata),
                    self.null_profile,
                    self.null_profile,
                )
            else:
                self.latest_plan = self.state_tree.find_best_plan(
                    TargetProfile.null_profile(self.profile_metadata),
                    self.null_profile,
                    self.null_profile,
                    ids,
                )
        else:
            self.latest_plan = S2FrbcPlan(
                idle=True,
                energy=self.zero_profile,
                fill_level=None,
                operation_mode_id=[],
            )
        self.accepted_plan = self.latest_plan
        return self.latest_plan

    def accept_proposal(self, accepted_proposal: Proposal) -> None:
        if self.latest_plan is None:
            raise ValueError("No latest plan found")
        if accepted_proposal.origin != self:
            raise ValueError(
                f"Storage controller '{self.device_id}' received a proposal that he did not send."
            )
        if not accepted_proposal.proposed_plan == self.latest_plan.energy:
            raise ValueError(
                f"Storage controller '{self.device_id}' received a proposal that he did not send."
            )
        if accepted_proposal.get_congestion_improvement_value() < 0:
            raise ValueError(
                f"Storage controller '{self.device_id}' received a proposal with negative improvement"
            )
        self.accepted_plan = self.latest_plan

    def get_latest_plan(self) -> Optional[S2FrbcPlan]:
        return self.latest_plan

    def set_accepted_plan(self, plan: S2FrbcPlan) -> None:
        if not isinstance(plan, S2FrbcPlan):
            raise TypeError(f"Expected S2FrbcPlan, but got {type(plan)}")
        self.accepted_plan = plan

    def current_profile(self) -> JouleProfile:
        if self.accepted_plan is None:
            raise ValueError("No accepted plan found")
        return self.accepted_plan.energy

    def get_device_plan(self) -> Optional[DevicePlan]:
        if self.accepted_plan is None:
            return None
        # logging.debug(
        #     dict(
        #         device_id=self.device_id,
        #         device_name=self.device_name,
        #         connection_id=self.connection_id,
        #         energy_profile=self.accepted_plan.energy,
        #         fill_level_profile=self.accepted_plan.fill_level,
        #         instruction_profile=self.convert_plan_to_instructions(
        #             self.profile_metadata, self.accepted_plan
        #         ),
        #     )
        # )
        return DevicePlan(
            device_id=self.device_id,
            device_name=self.device_name,
            connection_id=self.connection_id,
            energy_profile=self.accepted_plan.energy,
            fill_level_profile=self.accepted_plan.fill_level,
            instruction_profile=self.convert_plan_to_instructions(
                self.profile_metadata, self.accepted_plan
            ),
        )

    @staticmethod
    def convert_plan_to_instructions(
        profile_metadata: ProfileMetadata, device_plan: S2FrbcPlan
    ) -> S2FrbcInstructionProfile:
        import uuid
        from datetime import timedelta

        elements = []
        actuator_configurations_per_timestep = device_plan.get_operation_mode_id()

        if actuator_configurations_per_timestep is not None:
            for timestep_index, actuator_configurations_dict in enumerate(
                actuator_configurations_per_timestep
            ):
                # Calculate execution time for this timestep
                execution_time = profile_metadata.profile_start + timedelta(
                    seconds=timestep_index
                    * profile_metadata.timestep_duration.total_seconds()
                )
                # Ensure timezone-aware datetime
                if execution_time.tzinfo is None:
                    from datetime import timezone

                    execution_time = execution_time.replace(tzinfo=timezone.utc)

                # Create instructions for each actuator at this timestep
                for (
                    actuator_id,
                    actuator_config,
                ) in actuator_configurations_dict.items():
                    if actuator_config is not None:
                        instruction = FRBCInstruction(
                            message_id=str(uuid.uuid4()),
                            id=str(uuid.uuid4()),
                            actuator_id=str(actuator_id),
                            operation_mode=str(actuator_config.operation_mode_id),
                            operation_mode_factor=float(actuator_config.factor),
                            execution_time=execution_time,
                            abnormal_condition=False,
                        )
                        elements.append(instruction)

        return S2FrbcInstructionProfile(
            profile_start=profile_metadata.profile_start,
            timestep_duration=profile_metadata.timestep_duration,
            elements=elements,
        )
