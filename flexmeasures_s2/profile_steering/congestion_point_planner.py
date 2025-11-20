from datetime import datetime
from typing import Any, Optional, List
import concurrent.futures
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.joule_range_profile import (
    JouleRangeProfile,
)
from flexmeasures_s2.profile_steering.common.proposal import Proposal
from flexmeasures_s2.profile_steering.device_planner.device_planner_abstract import (
    DevicePlanner,
)
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile


def _get_device_proposal(
    device: DevicePlanner,
    difference_profile: TargetProfile,
    diff_to_max_value: JouleProfile,
    diff_to_min_value: JouleProfile,
    plan_due_by_date: datetime,
) -> Optional[Proposal]:
    """Helper function to be called by the process pool executor for pickling."""
    try:
        return device.create_improved_planning(
            difference_profile,
            diff_to_max_value,
            diff_to_min_value,
            plan_due_by_date,
        )
    except Exception:
        # print(f"Error getting proposal from device {device.device_id} in worker: {e}")
        return None


def _get_initial_device_plan(
    device: DevicePlanner, plan_due_by_date: datetime
) -> tuple[str, Any]:
    """Helper function to be called by the process pool executor for initial planning."""
    try:
        plan = device.create_initial_planning(plan_due_by_date)
        return (device.device_id, plan)
    except Exception as e:
        print(
            f"Error getting initial plan from device {device.device_id} in worker: {e}"
        )
        print(f"Exception type: {type(e).__name__}")
        import traceback

        print("Full traceback:")
        traceback.print_exc()
        return (device.device_id, None)


class CongestionPointPlanner:
    def __init__(
        self,
        congestion_point_id: str,
        congestion_target: JouleRangeProfile,
        multithreaded: bool = False,
    ):
        """Initialize a congestion point planner.

        Args:

            congestion_point_id: Unique identifier for this congestion point
            congestion_target: Target profile with range constraints for this congestion point
            multithreaded: Whether to use multiprocessing for device planning
        """
        self.MAX_ITERATIONS = 1000
        self.congestion_point_id = congestion_point_id
        self.congestion_target = congestion_target
        self.profile_metadata = congestion_target.metadata
        self.multithreaded = multithreaded

        # Create an empty profile (using all zeros)
        self.empty_profile = JouleProfile(
            profile_start=self.profile_metadata.profile_start,
            timestep_duration=self.profile_metadata.timestep_duration,
            elements=[0] * self.profile_metadata.nr_of_timesteps,  # type: ignore[list-item]
        )

        # List of device controllers that can be used for planning
        self.devices: List[DevicePlanner] = []

        # Keep track of accepted and latest plans
        self.accepted_plan = self.empty_profile
        self.latest_plan = self.empty_profile

    def add_device(self, device):
        """Add a device controller to this congestion point."""
        self.devices.append(device)

    @staticmethod
    def is_storage_available(self) -> bool:
        """Check if storage is available at this congestion point."""
        # For now, always assume storage is available
        return True

    def create_initial_planning(
        self, plan_due_by_date: datetime
    ) -> JouleProfile:  # noqa: C901
        """Create an initial plan for this congestion point.

        Args:
            plan_due_by_date: The date by which the plan must be ready

        Returns:
            A JouleProfile representing the initial plan
        """
        current_planning = self.empty_profile

        # Aggregate initial plans from all devices (parallel or sequential based on multithreaded setting)
        device_plans: dict[str, Any] = {}
        if self.multithreaded:
            # Use multiprocessing for parallel execution
            with concurrent.futures.ProcessPoolExecutor() as executor:
                futures = {
                    executor.submit(_get_initial_device_plan, device, plan_due_by_date)
                    for device in self.devices
                }
                for future in concurrent.futures.as_completed(futures):
                    device_id, plan = future.result()
                    if plan is not None:
                        device_plans[device_id] = plan
        else:
            # Use sequential execution to avoid pickling issues
            for device in self.devices:
                device_id, plan = _get_initial_device_plan(device, plan_due_by_date)
                if plan is not None:
                    device_plans[device_id] = plan

        # Update the state of the original device objects and aggregate energy profiles
        for device in self.devices:
            if device.device_id in device_plans:
                plan = device_plans[device.device_id]
                device.set_accepted_plan(plan)
                current_planning = current_planning.add(plan.energy)

        # Check if the current planning is within the congestion target range
        if self.congestion_target.is_within_range(current_planning):
            # print(
            #     "Current planning is within the congestion target range. Returning it."
            # )
            return current_planning

        # If the current planning is not within the congestion target range, optimize it
        # print(
        #     "Current planning is not within the congestion target range. Optimizing it."
        # )

        # print(f"Congestion target: {self.congestion_target}")
        # This is an old implementation that does not use the root planner
        # It is kept here for reference
        i = 0
        best_proposal = None

        max_priority_class = self.max_priority_class()
        min_priority_class = self.min_priority_class()

        # Iterate over priority classes
        for priority_class in range(min_priority_class, max_priority_class + 1):
            # print(f"Optimizing priority class: {priority_class}")
            pass
            while True:
                best_proposal = None
                diff_to_max = self.congestion_target.difference_with_max_value(
                    current_planning
                )
                diff_to_min = self.congestion_target.difference_with_min_value(
                    current_planning
                )

                # Try to get improved plans from each device controller
                for device in self.devices:
                    if device.priority_class <= priority_class:
                        try:
                            proposal = device.create_improved_planning(
                                self.empty_profile,  # type: ignore[arg-type]
                                diff_to_max,
                                diff_to_min,
                                plan_due_by_date,
                            )
                            if proposal is None:
                                raise ValueError(
                                    f"No proposal found for device {device.device_id}"
                                )
                            # print(
                            #     f"congestion point improvement for '{device.device_id}': {proposal.get_congestion_improvement_value()}"
                            # )
                            if (
                                best_proposal is None
                                or proposal.get_congestion_improvement_value()
                                > best_proposal.get_congestion_improvement_value()
                            ):
                                best_proposal = proposal
                        except Exception:
                            # print(
                            #     f"Error getting proposal from device {device.device_id}: {e}"
                            # )
                            continue

                if (
                    best_proposal is None
                    or best_proposal.get_congestion_improvement_value() <= 0
                ):
                    break

                # Update the current planning based on the best proposal
                current_planning = current_planning.subtract(
                    best_proposal.old_plan
                ).add(best_proposal.proposed_plan)
                best_proposal.origin.accept_proposal(best_proposal)
                i += 1

                # print(
                #     f"Initial planning '{self.congestion_point_id}': best controller '{best_proposal.origin.device_id}' with congestion improvement of {best_proposal.get_congestion_improvement_value()}. Iteration {i}."
                # )

                if i >= self.MAX_ITERATIONS:
                    break

        return current_planning

    def create_improved_planning(
        self,
        difference_profile: TargetProfile,
        priority_class: int,
        plan_due_by_date: datetime,
    ) -> Optional[Proposal]:
        """Create an improved plan based on the difference profile.

        Args:
            difference_profile: The difference between target and current planning
            priority_class: Priority class for this planning iteration
            plan_due_by_date: The date by which the plan must be ready

        Returns:
            A Proposal object if an improvement was found, None otherwise
        """
        best_proposal = None

        current_planning = self.get_current_planning()

        diff_to_max_value = self.congestion_target.difference_with_max_value(
            current_planning
        )
        diff_to_min_value = self.congestion_target.difference_with_min_value(
            current_planning
        )
        # print(f"diff_to_max_value: {diff_to_max_value}")
        # print(f"diff_to_min_value: {diff_to_min_value}")
        # Try to get improved plans from each device controller
        devices_to_plan = [
            d for d in self.devices if d.priority_class <= priority_class
        ]

        proposals = []
        if devices_to_plan:
            if self.multithreaded:
                # Use multiprocessing for parallel execution
                with concurrent.futures.ProcessPoolExecutor() as executor:
                    futures = {
                        executor.submit(
                            _get_device_proposal,
                            device,
                            difference_profile,
                            diff_to_max_value,
                            diff_to_min_value,
                            plan_due_by_date,
                        )
                        for device in devices_to_plan
                    }
                    for future in concurrent.futures.as_completed(futures):
                        proposal = future.result()
                        if proposal:
                            proposals.append(proposal)
            else:
                # Use sequential execution to avoid pickling issues
                for device in devices_to_plan:
                    proposal = _get_device_proposal(
                        device,
                        difference_profile,
                        diff_to_max_value,
                        diff_to_min_value,
                        plan_due_by_date,
                    )
                    if proposal:
                        proposals.append(proposal)

        for proposal in proposals:
            if proposal.get_congestion_improvement_value() < 0:
                # print(
                #     f"{proposal.origin.device_name}, congestion improvement: {proposal.get_congestion_improvement_value()}"
                # )
                pass

            if best_proposal is None or proposal.is_preferred_to(best_proposal):
                best_proposal = proposal

        if best_proposal is None:
            # print(
            #     f"CP '{self.congestion_point_id}': No proposal available at current priority level ({priority_class})"
            # )
            pass
        else:
            if best_proposal.get_congestion_improvement_value() == float("-inf"):
                raise ValueError(
                    "Invalid proposal with negative infinity improvement value"
                )

            # print(
            #     f"CP '{self.congestion_point_id}': Selected best controller '{best_proposal.origin.device_name}' with improvement of {best_proposal.get_global_improvement_value()}."
            # )

        return best_proposal

    def get_current_planning(self) -> JouleProfile:
        """Get the current planning profile."""
        # Return the latest accepted plan as the current planning
        current_planning = self.empty_profile
        for device in self.devices:
            # Ignore type error because current_profile is a JouleProfile but its considered a callable JouleProfile
            current_planning = current_planning.add(device.current_profile())  # type: ignore[arg-type]
        return current_planning

    def add_device_controller(self, device):
        """Add a device controller to this congestion point."""
        self.devices.append(device)

    def max_priority_class(self) -> int:
        """Get the maximum priority class among all devices."""
        if not self.devices:
            return 1
        return max(device.priority_class for device in self.devices)

    def min_priority_class(self) -> int:
        """Get the minimum priority class among all devices."""
        if not self.devices:
            return 1
        return min(device.priority_class for device in self.devices)
