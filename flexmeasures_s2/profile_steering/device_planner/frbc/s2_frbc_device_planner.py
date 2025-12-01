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


class S2FrbcDevicePlanner(DevicePlanner):
    """Device planner for Fill Rate Based Control (FRBC) devices.

    FRBC devices are storage systems (e.g., EV batteries, thermal storage)
    that can be charged/discharged to match energy targets. The planner
    optimizes operation modes to achieve fill level targets while respecting
    usage forecasts and constraints.

    The planning process:
    1. Creates a state tree (OperationModeProfileTree) representing possible
       storage states over time
    2. Searches for optimal operation mode sequences that meet fill level
       targets and usage forecasts
    3. Converts plans to instruction profiles for device control

    FRBC devices typically have:
    - Storage with fill level targets (state of charge targets)
    - Usage forecasts indicating expected consumption/production
    - Operation modes defining charge/discharge rates
    - Leakage behavior modeling energy losses
    - Multiple actuators with different characteristics

    The planner uses dynamic programming to explore the state space efficiently.
    """

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
        """Check if storage is available for planning.

        Determines if the device has active storage that can be planned for
        the current planning window. Checks:
        1. Device is online
        2. System descriptions exist and are active during the planning window

        Args:
            storage_state: The FRBC device state to check

        Returns:
            True if storage is available, False otherwise
        """
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
        """Create an improved planning based on the difference to global target.

        This method searches for a better plan that moves toward the global target
        while respecting congestion point constraints and fill level targets. It:
        1. Computes absolute targets from difference profiles
        2. Searches the operation mode profile tree for the best plan
        3. Creates a proposal comparing the new plan to the accepted plan

        The search considers:
        - Fill level targets (state of charge targets)
        - Usage forecasts (expected consumption/production)
        - Global energy targets
        - Congestion point constraints

        Args:
            diff_to_global_target: Difference between global target and current
                root-level planning
            diff_to_max: Difference to congestion point maximum constraint
            diff_to_min: Difference to congestion point minimum constraint
            plan_due_by_date: Deadline for completing the plan

        Returns:
            A Proposal object with the improved plan

        Raises:
            ValueError: If no accepted plan exists
        """
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
        """Create an initial planning.

        Creates a baseline plan that meets fill level targets and usage forecasts
        without optimizing for global energy targets. This is used as the starting
        point for iterative improvement.

        Args:
            plan_due_by_date: Deadline for completing the plan
            ids: Optional dictionary for tracking IDs (used for debugging)

        Returns:
            An S2FrbcPlan representing the initial plan
        """
        if self.is_storage_available(self.s2_frbc_state):
            if ids is None:
                self.latest_plan = self.state_tree.find_best_plan(
                    target_profile=TargetProfile.null_profile(self.profile_metadata),
                    diff_to_min_profile=self.null_profile,
                    diff_to_max_profile=self.null_profile,
                )
            else:
                self.latest_plan = self.state_tree.find_best_plan(
                    target_profile=TargetProfile.null_profile(self.profile_metadata),
                    diff_to_min_profile=self.null_profile,
                    diff_to_max_profile=self.null_profile,
                    ids=ids,
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
        """Accept a proposal and update the accepted plan.

        Validates that the proposal is from this planner and matches the latest
        plan, then updates the accepted plan.

        Args:
            accepted_proposal: The proposal to accept

        Raises:
            ValueError: If the proposal is invalid or doesn't match expectations
        """
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
        """Get the latest calculated plan.

        Returns:
            The latest plan, which may not have been accepted yet
        """
        return self.latest_plan

    def set_accepted_plan(self, plan: S2FrbcPlan) -> None:
        """Set the accepted plan forcefully.

        This is used during initial planning to set the baseline plan.

        Args:
            plan: The plan to set as accepted

        Raises:
            TypeError: If the plan is not an S2FrbcPlan instance
        """
        if not isinstance(plan, S2FrbcPlan):
            raise TypeError(f"Expected S2FrbcPlan, but got {type(plan)}")
        self.accepted_plan = plan

    def current_profile(self) -> JouleProfile:
        """Get the current accepted energy profile.

        Returns:
            The energy profile from the accepted plan

        Raises:
            ValueError: If no accepted plan exists
        """
        if self.accepted_plan is None:
            raise ValueError("No accepted plan found")
        return self.accepted_plan.energy

    def get_device_plan(self) -> Optional[DevicePlan]:
        """Get the device plan for this FRBC device.

        Converts the accepted plan to a DevicePlan with energy profile,
        fill level profile, and instruction profile for device control.

        Returns:
            A DevicePlan with energy profile, fill level profile, and instructions,
            or None if no accepted plan exists
        """
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
        """Convert a plan to instruction profile.

        Converts operation mode configurations from the plan into FRBCInstruction
        objects that can be sent to the device for control. Each instruction
        specifies which operation mode to use for each actuator at each timestep.

        Args:
            profile_metadata: Metadata describing the profile timing
            device_plan: The device plan containing operation mode configurations

        Returns:
            An S2FrbcInstructionProfile with FRBCInstruction elements for device control
        """
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
