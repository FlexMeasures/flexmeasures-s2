from datetime import datetime
from typing import List, Optional
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from .joule_range_profile import JouleRangeProfile
from .proposal import Proposal

class CongestionPointPlanner:
    def __init__(self, congestion_point_id: str, congestion_target: JouleRangeProfile):
        """Initialize a congestion point planner.
        
        Args:
            congestion_point_id: Unique identifier for this congestion point
            congestion_target: Target profile with range constraints for this congestion point
        """
        self.congestion_point_id = congestion_point_id
        self.congestion_target = congestion_target
        self.profile_metadata = congestion_target.get_profile_metadata()
        
        # Create an empty profile (using all zeros)
        self.empty_profile = JouleProfile(
            self.profile_metadata.get_profile_start(),
            self.profile_metadata.get_timestep_duration(),
            elements=[0] * self.profile_metadata.nr_of_timesteps
        )
        
        # List of device controllers that can be used for planning
        self.devices = []
        
        # Keep track of accepted and latest plans
        self.accepted_plan = self.empty_profile
        self.latest_plan = self.empty_profile

    def add_device(self, device):
        """Add a device controller to this congestion point."""
        self.devices.append(device)

    def is_storage_available(self) -> bool:
        """Check if storage is available at this congestion point."""
        # For now, always assume storage is available
        return True

    def create_initial_planning(self, plan_due_by_date: datetime) -> JouleProfile:
        """Create an initial plan for this congestion point.
        
        Args:
            plan_due_by_date: The date by which the plan must be ready
            
        Returns:
            A JouleProfile representing the initial plan
        """
        current_planning = self.empty_profile

        # Aggregate initial plans from all devices
        for device in self.devices:
            current_planning = current_planning.add(device.create_initial_planning(plan_due_by_date))

        # Check if the current planning is within the congestion target range
        if self.congestion_target.is_within_range(current_planning):
            return current_planning

        i = 0
        best_proposal = None

        max_priority_class = self.max_priority_class()
        min_priority_class = self.min_priority_class()

        # Iterate over priority classes
        for priority_class in range(min_priority_class, max_priority_class + 1):
            print(f"Optimizing priority class: {priority_class}")
            while True:
                best_proposal = None
                diff_to_max = self.congestion_target.difference_with_max_value(current_planning)
                diff_to_min = self.congestion_target.difference_with_min_value(current_planning)

                # Try to get improved plans from each device controller
                for device in self.devices:
                    if device.get_priority_class() <= priority_class:
                        try:
                            proposal = device.create_improved_planning(
                                self.empty_profile,  # Assuming empty global target
                                diff_to_max,
                                diff_to_min,
                                plan_due_by_date
                            )
                            print(f"congestion impr for '{device.get_device_id()}': {proposal.get_congestion_improvement_value()}")
                            if best_proposal is None or proposal.get_congestion_improvement_value() > best_proposal.get_congestion_improvement_value():
                                best_proposal = proposal
                        except Exception as e:
                            print(f"Error getting proposal from device {device.get_device_id()}: {e}")
                            continue

                if best_proposal is None or best_proposal.get_congestion_improvement_value() <= 0:
                    break

                # Update the current planning based on the best proposal
                current_planning = current_planning.subtract(best_proposal.get_old_plan()).add(best_proposal.get_proposed_plan())
                best_proposal.get_origin().accept_proposal(best_proposal)
                i += 1

                print(f"Initial planning '{self.congestion_point_id}': best controller '{best_proposal.get_origin().get_device_id()}' with congestion improvement of {best_proposal.get_congestion_improvement_value()}. Iteration {i}.")

                if i >= self.MAX_ITERATIONS:
                    break

        return current_planning

    def create_improved_planning(
        self, 
        difference_profile: JouleProfile,
        target_metadata: any,
        priority_class: int,
        plan_due_by_date: datetime
    ) -> Optional[Proposal]:
        """Create an improved plan based on the difference profile.
        
        Args:
            difference_profile: The difference between target and current planning
            target_metadata: Metadata about the target profile
            priority_class: Priority class for this planning iteration
            plan_due_by_date: The date by which the plan must be ready
            
        Returns:
            A Proposal object if an improvement was found, None otherwise
        """
        best_proposal = None

        current_planning = self.get_current_planning()

        diff_to_max_value = self.congestion_target.difference_with_max_value(current_planning)
        diff_to_min_value = self.congestion_target.difference_with_min_value(current_planning)

        # Try to get improved plans from each device controller
        for device in self.devices:
            if device.get_priority_class() <= priority_class:
                try:
                    # Get an improved plan from this device
                    proposal = device.create_improved_planning(
                        difference_profile,
                        diff_to_max_value,
                        diff_to_min_value,
                        plan_due_by_date
                    )
                    if proposal.get_congestion_improvement_value() < 0:
                        print(f"{device.get_device_name()}, congestion improvement: {proposal.get_congestion_improvement_value()}")
                    
                    if best_proposal is None or proposal.is_preferred_to(best_proposal):
                        best_proposal = proposal
                except Exception as e:
                    print(f"Error getting proposal from device {device.get_device_id()}: {e}")
                    continue

        if best_proposal is None:
            print(f"CP '{self.congestion_point_id}': No proposal available at current priority level ({priority_class})")
        else:
            if best_proposal.get_congestion_improvement_value() == float('-inf'):
                raise ValueError("Invalid proposal with negative infinity improvement value")

            print(f"CP '{self.congestion_point_id}': Selected best controller '{best_proposal.get_origin().get_device_name()}' with improvement of {best_proposal.get_global_improvement_value()}.")

        return best_proposal

    def get_current_planning(self) -> JouleProfile:
        """Get the current planning profile."""
        # Return the latest accepted plan as the current planning
        current_planning = self.empty_profile
        for device in self.devices:
            current_planning = current_planning.add(device.get_current_profile())
        return current_planning

    def add_device_controller(self, device):
        """Add a device controller to this congestion point."""
        self.devices.append(device)

    def get_device_controllers(self) -> List[DevicePlanner]:
        """Get the list of device controllers."""
        return self.devices
    
    def max_priority_class(self) -> int:
        """Get the maximum priority class among all devices."""
        if not self.devices:
            return 1
        return max(device.get_priority_class() for device in self.devices)

    def min_priority_class(self) -> int:
        """Get the minimum priority class among all devices."""
        if not self.devices:
            return 1
        return min(device.get_priority_class() for device in self.devices)
