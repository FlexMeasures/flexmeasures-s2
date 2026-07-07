from datetime import datetime
from typing import Optional
from abc import ABC, abstractmethod
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from flexmeasures_s2.profile_steering.common.device_planner.device_plan import (
    DevicePlan,
)


class DevicePlanner(ABC):
    @abstractmethod
    def get_device_id(self) -> str:
        """Get the device ID."""
        pass

    @abstractmethod
    def get_device_name(self) -> str:
        """Get the device name."""
        pass

    @abstractmethod
    def get_connection_id(self) -> str:
        """Get the connection ID."""
        pass

    @abstractmethod
    def create_improved_planning(
        self,
        cluster_diff_profile: TargetProfile,
        diff_to_max_profile: JouleProfile,
        diff_to_min_profile: JouleProfile,
        plan_due_by_date: datetime,
    ) -> "Proposal":
        """Create an improved planning proposal.

        Args:
            cluster_diff_profile: The difference profile for the cluster
            diff_to_max_profile: The difference to the maximum profile
            diff_to_min_profile: The difference to the minimum profile
            plan_due_by_date: The date by which the plan must be ready

        Returns:
            A Proposal object representing the improved plan
        """
        pass

    @abstractmethod
    def create_initial_planning(self, plan_due_by_date: datetime) -> JouleProfile:
        """Create an initial planning profile.

        Args:
            plan_due_by_date: The date by which the plan must be ready

        Returns:
            A JouleProfile representing the initial plan
        """
        pass

    @abstractmethod
    def accept_proposal(self, accepted_proposal: "Proposal"):
        """Accept a proposal and update the device's planning.

        Args:
            accepted_proposal: The proposal to accept
        """
        pass

    @abstractmethod
    def get_current_profile(self) -> JouleProfile:
        """Get the current profile of the device."""
        pass

    @abstractmethod
    def get_device_plan(self) -> Optional[DevicePlan]:
        """Get the device plan."""
        pass

    @abstractmethod
    def get_priority_class(self) -> int:
        """Get the priority class of the device."""
        pass
