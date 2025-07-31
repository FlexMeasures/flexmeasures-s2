from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from flexmeasures_s2.profile_steering.common.proposal import Proposal
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.device_plan import (
    DevicePlan,
)


class DevicePlanner(ABC):
    """Abstract base class for all device planners."""

    @property
    @abstractmethod
    def device_id(self) -> str:
        """The device ID."""
        raise NotImplementedError

    @property
    @abstractmethod
    def device_name(self) -> str:
        """The device name."""
        raise NotImplementedError

    @property
    @abstractmethod
    def connection_id(self) -> str:
        """The connection ID."""
        raise NotImplementedError

    @property
    @abstractmethod
    def congestion_point_id(self) -> str:
        """The congestion point ID this device belongs to."""
        raise NotImplementedError

    @abstractmethod
    def create_improved_planning(
        self,
        difference_profile: JouleProfile,
        diff_to_max_value: JouleProfile,
        diff_to_min_value: JouleProfile,
        plan_due_by_date: datetime,
    ) -> Optional["Proposal"]:
        """Create an improved planning profile based on the difference profile.

        Args:
            difference_profile: The difference profile for the cluster
            diff_to_max_value: The difference to the maximum profile
            diff_to_min_value: The difference to the minimum profile
            plan_due_by_date: The date by which the plan must be ready

        Returns:
            A Proposal object if an improvement was found, None otherwise
        """
        pass

    @abstractmethod
    def create_initial_planning(self, plan_due_by_date: datetime) -> "Any":
        """Create an initial planning profile.

        Args:
            plan_due_by_date: The date by which the plan must be ready

        Returns:
            A plan object for the device.
        """
        pass

    @abstractmethod
    def accept_proposal(self, proposal: "Proposal") -> None:
        """This method is called when a proposal from this device is accepted by a higher-level controller.

        Args:
            proposal: The proposal that was accepted
        """
        pass

    @abstractmethod
    def current_profile(self) -> JouleProfile:
        """Get the current profile of the device."""
        pass

    @abstractmethod
    def get_device_plan(self) -> Optional[DevicePlan]:
        """Get the device plan."""
        pass

    @abstractmethod
    def get_latest_plan(self) -> Any:
        """Get the latest calculated plan, which may not have been accepted yet."""
        pass

    @abstractmethod
    def set_accepted_plan(self, plan: Any):
        """Forcefully set the accepted plan for the device."""
        pass
