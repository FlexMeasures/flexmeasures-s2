from datetime import datetime
from typing import Dict, Optional, Any, List
import uuid

# Common data types
from flexmeasures_s2.profile_steering.common.joule_range_profile import (
    JouleRangeProfile,
)
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile


class ClusterTarget:
    """Represents targets for cluster planning.

    ClusterTarget instances express how a plan should look. There are two
    hierarchical levels at which targets can be set:

    1. Global level: A target for the cluster as a whole (TargetProfile)
    2. Congestion point level: Targets for specific congestion points
       (JouleRangeProfile with min/max constraints)

    The global target is typically a line profile (energy over time), while
    congestion point targets are range profiles that constrain the aggregated
    energy at each congestion point to stay within min/max bounds.

    The planning algorithm optimizes device schedules to match the global target
    while respecting congestion point constraints.
    """

    def __init__(
        self,
        generated_at: datetime,
        parent_id: Any,
        generated_by: Any,
        global_target_profile: TargetProfile,
        congestion_point_targets: Optional[Dict[str, JouleRangeProfile]] = None,
    ):
        """
        Initialize a ClusterTarget instance.

        Args:
            generated_at: When the target was generated
            parent_id: The ID of the parent target
            generated_by: The entity that generated the target
            global_target_profile: The global target profile for the cluster
            congestion_point_targets: Targets for specific congestion points
        """
        self._id = str(uuid.uuid4())
        self._generated_at = generated_at
        self._parent_id = parent_id
        self._generated_by = generated_by
        self._global_target_profile = global_target_profile
        self._congestion_point_targets = congestion_point_targets or {}

        # Validate
        if global_target_profile is None:
            raise ValueError("global_target_profile cannot be None")

        if congestion_point_targets is not None:
            for cp_id, cp_target in congestion_point_targets.items():
                if not cp_target.is_compatible(global_target_profile):
                    raise ValueError(
                        f"Congestion point target {cp_id} is not compatible with the global target profile. "
                        f"Expected global metadata: {global_target_profile.metadata}, "
                        f"but congestion profile had {cp_target.metadata}"
                    )

    def get_id(self) -> str:
        """
        Get the ID of this target.

        Returns:
            The target ID
        """
        return self._id

    def get_generated_at(self) -> datetime:
        """
        Get when this target was generated.
        Returns:
            The generation timestamp
        """
        return self._generated_at

    def get_parent_id(self) -> Any:
        """
        Get the parent ID of this target.

        Returns:
            The parent ID
        """
        return self._parent_id

    def get_generated_by(self) -> Any:
        """
        Get the entity that generated this target.

        Returns:
            The generator entity
        """
        return self._generated_by

    def get_global_target_profile(self) -> TargetProfile:
        """
        Get the global target profile.

        Returns:
            The global target profile
        """
        return self._global_target_profile

    def get_congestion_point_targets(self) -> Dict[str, JouleRangeProfile]:
        """
        Get all congestion point targets.

        Returns:
            A dictionary mapping congestion point IDs to their targets
        """
        return self._congestion_point_targets

    def get_congestion_point_target(
        self, congestion_point_id: str
    ) -> Optional[JouleRangeProfile]:
        """
        Get the target for a specific congestion point.

        Args:
            congestion_point_id: The ID of the congestion point

        Returns:
            The target for the congestion point, or None if not found
        """
        return self._congestion_point_targets.get(congestion_point_id)

    @property
    def metadata(self) -> Any:
        """
        Get the profile metadata.

        Returns:
            The profile metadata
        """
        return self._global_target_profile.metadata

    def get_target_energy(self) -> float:
        """
        Get the total target energy.

        Returns:
            The total energy
        """
        return self._global_target_profile.get_total_energy()

    def is_compatible(self, other: Any) -> bool:
        """
        Check if this target is compatible with another profile.

        Args:
            other: The other profile to check compatibility with

        Returns:
            True if compatible, False otherwise
        """
        return self._global_target_profile.is_compatible(other)

    def subprofile(self, new_start_date: datetime) -> "ClusterTarget":
        """
        Create a subprofile starting at the specified date.

        Args:
            new_start_date: The new start date for the profile

        Returns:
            A new ClusterTarget instance with adjusted start date
        """
        plans = {}
        for cp_id, cp_target in self._congestion_point_targets.items():
            plans[cp_id] = cp_target.subprofile(new_start_date)

        return ClusterTarget(
            self._generated_at,
            self._parent_id,
            self._generated_by,
            self._global_target_profile.subprofile(new_start_date),
            plans,
        )

    def adjust_nr_of_elements(self, nr_of_elements: int) -> "ClusterTarget":
        """
        Adjust the number of elements in the profile.

        Args:
            nr_of_elements: The new number of elements

        Returns:
            A new ClusterTarget instance with adjusted number of elements
        """
        plans = {}
        for cp_id, cp_target in self._congestion_point_targets.items():
            plans[cp_id] = cp_target.adjust_nr_of_elements(nr_of_elements)

        return ClusterTarget(
            self._generated_at,
            self._parent_id,
            self._generated_by,
            self._global_target_profile.adjust_nr_of_elements(nr_of_elements),
            plans,
        )

    def set_congestion_point_target(
        self,
        congestion_point_id: str,
        congestion_point_target: JouleRangeProfile,
        elements: Optional[List[Any]] = None,
    ):
        """
        Set a target for a specific congestion point.

        Args:
            congestion_point_id: The ID of the congestion point
            congestion_point_target: The target for the congestion point
            elements: Optional elements to set in the target profile
        """
        if not congestion_point_target.is_compatible(self._global_target_profile):
            raise ValueError(
                f"Congestion point target {congestion_point_id} is not compatible with the global target profile"
            )

        self._congestion_point_targets[congestion_point_id] = congestion_point_target

        if elements is not None:
            self._congestion_point_targets[congestion_point_id].elements = elements

    def contains_energy_target(self) -> bool:
        """
        Check if this cluster target contains any energy targets (JouleElement instances).

        Returns:
            True if there are any JouleElement instances in the global target profile, False otherwise
        """
        from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile

        for element in self._global_target_profile.elements:
            if isinstance(element, TargetProfile.JouleElement):
                return True
        return False
