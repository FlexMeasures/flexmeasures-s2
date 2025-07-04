from datetime import datetime
from typing import List, Dict, Any, Optional
import uuid

# Common data types
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.joule_range_profile import (
    JouleRangeProfile,
)

# Import from common data structures to avoid circular imports
from flexmeasures_s2.profile_steering.common_data_structures import (
    ClusterState,
    DevicePlan,
)

# Import cluster target
from flexmeasures_s2.profile_steering.cluster_target import ClusterTarget


class ClusterPlanData:
    """Class representing planning data for a cluster."""

    class CpData:
        """Class representing data for a congestion point."""

        def __init__(
            self,
            cp_id: str,
            cp_plan: List[float],
            der_plans: Dict[str, List[float]],
            cp_consumption: List[float],
            cp_production: List[float],
            cp_consumption_max: float,
            cp_production_max: float,
        ):
            self._cp_id = cp_id
            self._cp_plan = cp_plan
            self._der_plans = der_plans
            self._cp_consumption = cp_consumption
            self._cp_production = cp_production
            self._cp_consumption_max = cp_consumption_max
            self._cp_production_max = cp_production_max

        def get_cp_id(self) -> str:
            return self._cp_id

        def get_cp_plan(self) -> List[float]:
            return self._cp_plan

        def get_der_plans(self) -> Dict[str, List[float]]:
            return self._der_plans

        def get_cp_consumption(self) -> List[float]:
            return self._cp_consumption

        def get_cp_production(self) -> List[float]:
            return self._cp_production

        def get_cp_consumption_max(self) -> float:
            return self._cp_consumption_max

        def get_cp_production_max(self) -> float:
            return self._cp_production_max

        def add_der_plan(
            self, der_name: str, value: JouleProfile
        ) -> "ClusterPlanData.CpData":
            """Add a device energy resource plan to this congestion point.

            Args:
                der_name: The name of the device energy resource
                value: The profile of the device energy resource

            Returns:
                A new CpData instance with the added device energy resource plan
            """
            der_plan = to_float_array(value)
            new_cp_plan = [0] * len(self._cp_plan)
            cp_consumption = [0] * len(self._cp_plan)
            cp_production = [0] * len(self._cp_plan)
            consumption_max = self._cp_consumption_max
            production_max = self._cp_production_max

            for i in range(len(self._cp_plan)):
                new_cp_plan[i] = der_plan[i] + self._cp_plan[i]
                cp_consumption[i] = self._cp_consumption[i]
                cp_production[i] = self._cp_production[i]

                if der_plan[i] >= 0:
                    cp_consumption[i] += der_plan[i]
                    consumption_max = max(cp_consumption[i], consumption_max)
                else:
                    cp_production[i] += der_plan[i]
                    production_max = min(cp_production[i], production_max)

            new_der_plans = self._der_plans.copy()
            new_der_plans[der_name] = der_plan

            return ClusterPlanData.CpData(
                self._cp_id,
                new_cp_plan,
                new_der_plans,
                cp_consumption,
                cp_production,
                consumption_max,
                production_max,
            )

        @classmethod
        def empty(cls, cp_id: str, profile_metadata: Any) -> "ClusterPlanData.CpData":
            """Create an empty CpData instance.

            Args:
                cp_id: The congestion point ID
                profile_metadata: Metadata about the profile

            Returns:
                An empty CpData instance
            """
            timesteps = profile_metadata.nr_of_timesteps
            return cls(
                cp_id,
                [0.0] * timesteps,
                {},
                [0.0] * timesteps,
                [0.0] * timesteps,
                0.0,
                0.0,
            )

    def __init__(
        self,
        device_plans: List[DevicePlan] = None,
        profile_metadata: Any = None,
        _id: str = None,
        reason: str = None,
        target: Any = None,
        active_target: Any = None,
        current_plan: List[float] = None,
        start: int = None,
        step: int = None,
        global_deviation_score: float = 1.0,
        constraint_violation_score: float = 1.0,
        cp_datas: Dict[str, CpData] = None,
    ):
        self._device_plans = device_plans or []
        self._profile_metadata = profile_metadata
        self._id = _id
        self._reason = reason
        self._target = target
        self._active_target = active_target
        self._current_plan = current_plan
        self._start = start
        self._step = step
        self._global_deviation_score = global_deviation_score
        self._constraint_violation_score = constraint_violation_score
        self._cp_datas = cp_datas or {}

    def get_device_plans(self) -> List[DevicePlan]:
        return self._device_plans

    @property
    def metadata(self):
        return self._profile_metadata

    def get_id(self) -> str:
        return self._id

    def get_reason(self) -> str:
        return self._reason

    def get_target(self) -> Any:
        return self._target

    def get_active_target(self) -> Any:
        return self._active_target

    def get_current_plan(self) -> List[float]:
        return self._current_plan

    def get_start(self) -> int:
        return self._start

    def get_step(self) -> int:
        return self._step

    def get_global_deviation_score(self) -> float:
        return self._global_deviation_score

    def get_constraint_violation_score(self) -> float:
        return self._constraint_violation_score

    def get_cp_datas(self) -> Dict[str, CpData]:
        return self._cp_datas

    def is_compatible(self, other: Any) -> bool:
        """Check if this cluster plan data is compatible with another profile.

        Args:
            other: The other profile to check compatibility with

        Returns:
            True if compatible, False otherwise
        """
        if self._profile_metadata is None:
            return False

        return self._profile_metadata.is_compatible(other.metadata)

    def subprofile(self, new_start_date: datetime) -> "ClusterPlanData":
        """Create a subprofile starting at the specified date.

        Args:
            new_start_date: The new start date for the profile

        Returns:
            A new ClusterPlanData instance with adjusted start date
        """
        # Create a copy of this instance with adjusted device plans
        new_device_plans = []
        for device_plan in self._device_plans:
            new_profile = device_plan.get_profile().subprofile(new_start_date)
            new_device_plans.append(DevicePlan(device_plan.device_id, new_profile))

        # Create new profile metadata with adjusted start date
        new_profile_metadata = self._profile_metadata.subprofile(new_start_date)

        return ClusterPlanData(
            device_plans=new_device_plans,
            profile_metadata=new_profile_metadata,
            _id=self._id,
            reason=self._reason,
            target=self._target,
            active_target=self._active_target,
            current_plan=self._current_plan,
            start=int(new_start_date.timestamp() * 1000),
            # Convert to milliseconds
            step=self._step,
            global_deviation_score=self._global_deviation_score,
            constraint_violation_score=self._constraint_violation_score,
            cp_datas=self._cp_datas,
        )

    def adjust_nr_of_elements(self, nr_of_elements: int) -> "ClusterPlanData":
        """Adjust the number of elements in the profile.

        Args:
            nr_of_elements: The new number of elements

        Returns:
            A new ClusterPlanData instance with adjusted number of elements
        """
        # Create a copy of this instance with adjusted device plans
        new_device_plans = []
        for device_plan in self._device_plans:
            new_profile = device_plan.get_profile().adjust_nr_of_elements(
                nr_of_elements
            )
            new_device_plans.append(DevicePlan(device_plan.device_id, new_profile))

        # Create new profile metadata with adjusted number of elements
        new_profile_metadata = self._profile_metadata.adjust_nr_of_elements(
            nr_of_elements
        )

        return ClusterPlanData(
            device_plans=new_device_plans,
            profile_metadata=new_profile_metadata,
            _id=self._id,
            reason=self._reason,
            target=self._target,
            active_target=self._active_target,
            current_plan=(
                self._current_plan[:nr_of_elements] if self._current_plan else None
            ),
            start=self._start,
            step=self._step,
            global_deviation_score=self._global_deviation_score,
            constraint_violation_score=self._constraint_violation_score,
            cp_datas=self._cp_datas,
        )

    @classmethod
    def from_cluster_plan(
        cls,
        cluster_plan: "ClusterPlan",
        active_target: ClusterTarget = None,
        active_plan: JouleProfile = None,
    ) -> "ClusterPlanData":
        """Create a ClusterPlanData instance from a ClusterPlan.

        Args:
            cluster_plan: The cluster plan to create the data from
            active_target: The active target for the cluster
            active_plan: The active plan for the cluster

        Returns:
            A ClusterPlanData instance
        """
        congestion_points = {}

        # Get the device plans from the cluster plan
        cluster_plan_data = cluster_plan.get_plan_data()
        if cluster_plan_data is None:
            return None  # type: ignore

        # Process each device plan
        for device_plan in cluster_plan_data.get_device_plans():
            cp_id = cluster_plan.get_state().get_congestion_point(
                device_plan.get_connection_id()
            )
            if cp_id is None:
                # The interface needs all devices to function properly. So for devices without congestion point, set a
                # dummy congestion point so that those device plans go through.
                cp_id = "No congestion point"

            if cp_id not in congestion_points:
                congestion_points[cp_id] = ClusterPlanData.CpData.empty(
                    cp_id, cluster_plan.get_plan_data().metadata
                )

            congestion_points[cp_id] = congestion_points[cp_id].add_der_plan(
                device_plan.device_id, device_plan.get_profile()
            )

        # Create the current plan
        if active_plan is None:
            # Extract the plan from the cluster plan's JouleProfile
            joule_profile = cluster_plan.get_joule_profile()
            current_plan = [
                element if element is not None else 0.0
                for element in joule_profile.elements
            ]
        else:
            # Use the active plan, adjusting it to the profile metadata
            profile_start = cluster_plan.get_plan_data().metadata.profile_start
            nr_of_timesteps = cluster_plan.get_plan_data().metadata.nr_of_timesteps

            subprofile = active_plan.subprofile(profile_start)
            adjusted_profile = subprofile.adjust_nr_of_elements(nr_of_timesteps)
            current_plan = [
                element if element is not None else 0.0
                for element in adjusted_profile.elements
            ]

        # Get the profile metadata
        profile_metadata = cluster_plan.get_plan_data().metadata

        # Set up the active target
        actual_active_target = (
            active_target if active_target is not None else cluster_plan.get_target()
        )

        # Calculate timestamps
        start_time = (
            profile_metadata.profile_start.timestamp() * 1000
        )  # Convert to milliseconds
        timestep_duration = (
            profile_metadata.timestep_duration.total_seconds() * 1000
        )  # Convert to milliseconds

        # Get scores, defaulting to 1.0 if they're NaN
        global_deviation_score = cluster_plan.get_global_deviation_score()
        global_deviation_score = (
            1.0 if global_deviation_score is None else global_deviation_score
        )

        constraint_violation_score = cluster_plan.get_constraint_violation_score()
        constraint_violation_score = (
            1.0 if constraint_violation_score is None else constraint_violation_score
        )

        return cls(
            device_plans=cluster_plan_data.get_device_plans(),
            profile_metadata=profile_metadata,
            _id=str(cluster_plan.get_id()),
            reason=cluster_plan.get_reason(),
            target=cluster_plan.get_target(),
            active_target=actual_active_target,
            current_plan=current_plan,
            start=int(start_time),
            step=int(timestep_duration),
            global_deviation_score=global_deviation_score,
            constraint_violation_score=constraint_violation_score,
            cp_datas=congestion_points,
        )


def to_float_array(profile: JouleProfile) -> List[float]:
    """Convert a JouleProfile to a list of floats.

    Args:
        profile: The profile to convert

    Returns:
        A list of floats
    """
    result = [0.0] * profile.metadata.nr_of_timesteps
    for i, element in enumerate(profile.get_elements()):
        result[i] = 0.0 if element is None else float(element)
    return result


class ClusterPlan:
    """Class representing a plan for a cluster."""

    def __init__(
        self,
        state: ClusterState,
        target: ClusterTarget,
        plan_data: ClusterPlanData,
        reason: str,
        plan_due_by_date: datetime,
        parent_plan: Optional["ClusterPlan"] = None,
        _id: Optional[str] = None,
        global_deviation_score: Optional[float] = None,
        constraint_violation_score: Optional[float] = None,
        activated_at: Optional[datetime] = None,
        planned_energy: Optional[float] = None,
    ):
        self._state = state
        self._target = target
        self._plan_data = plan_data
        self._reason = reason
        self._plan_due_by_date = plan_due_by_date
        self._parent_plan = parent_plan
        self._id = _id or str(uuid.uuid4())
        self._global_deviation_score = global_deviation_score
        self._constraint_violation_score = constraint_violation_score
        self._joule_profile = None  # Will be initialized when needed
        self._activated_at = activated_at
        self._planned_energy = planned_energy  # Lazy evaluation field

    def get_state(self) -> ClusterState:
        return self._state

    def get_target(self) -> ClusterTarget:
        return self._target

    def get_plan_data(self) -> ClusterPlanData:
        return self._plan_data

    def get_reason(self) -> str:
        return self._reason

    def get_plan_due_by_date(self) -> datetime:
        return self._plan_due_by_date

    def get_parent_plan(self) -> Optional["ClusterPlan"]:
        return self._parent_plan

    def get_id(self) -> str:
        return self._id

    def get_activated_at(self) -> Optional[datetime]:
        return self._activated_at

    def get_target_energy(self) -> float:
        """Get the target energy for this plan.

        Returns:
            The target energy
        """
        return self._target.get_target_energy()

    def get_planned_energy(self) -> float:
        """Get the planned energy for this plan.

        Returns:
            The planned energy
        """
        if self._planned_energy is None:
            # Calculate the planned energy as the sum of all device plans
            sum_energy = 0.0
            for device_plan in self._plan_data.get_device_plans():
                sum_energy += device_plan.get_profile().get_total_energy()
            self._planned_energy = sum_energy

        return self._planned_energy

    def get_global_deviation_score(self) -> Optional[float]:
        """Calculate the score for the deviation between target and plan. Lower is better.

        Returns:
            The global deviation score, or None if not set
        """
        if self._global_deviation_score is None:
            joule_target_segment = (
                self._target.get_global_target_profile().target_elements_to_joule_profile()
            )
            if not joule_target_segment.elements:
                # No joule target, so that's by default a perfect score!
                return 0.0

            target = joule_target_segment.elements
            plan_segment = self.get_joule_profile().subprofile(
                joule_target_segment.metadata.profile_start
            )
            plan = plan_segment.elements

            sum_squared_distance = 0.0
            for i in range(len(target)):
                if target[i] is not None:
                    sum_squared_distance += abs(target[i] - plan[i])

            if plan_segment.get_total_energy() == 0.0:
                self._global_deviation_score = 0.0
            else:
                self._global_deviation_score = (
                    sum_squared_distance / plan_segment.get_total_energy()
                )

        return self._global_deviation_score

    def get_constraint_violation_score(self) -> Optional[float]:
        """Calculate the score for violation of constraint targets. Lower is better.

        Returns:
            The constraint violation score, or None if not set
        """
        if self._constraint_violation_score is None:
            violation_sum = 0.0

            for cp_id, cp_profile in self.get_profile_per_congestion_point().items():
                plan = cp_profile.elements
                congestion_point_target = self._target.get_congestion_point_target(
                    cp_id
                )

                if congestion_point_target is not None:
                    # If there is no target, we don't need to calculate it for the violation sum
                    target_elements = congestion_point_target.elements

                    for i in range(len(target_elements)):
                        element = target_elements[i]
                        max_joule = element.max_joule
                        min_joule = element.min_joule

                        if max_joule is not None and plan[i] > max_joule:
                            violation_sum += abs(plan[i] - max_joule)

                        if min_joule is not None and plan[i] < min_joule:
                            violation_sum += abs(min_joule - plan[i])

            planned_energy = self.get_planned_energy()
            if planned_energy == 0.0:
                self._constraint_violation_score = 0.0
            else:
                self._constraint_violation_score = violation_sum / planned_energy

        return self._constraint_violation_score

    def has_constraint_violation(self) -> bool:
        """Check if this plan has any constraint violations.

        Returns:
            True if there are constraint violations, False otherwise
        """
        for cp_id, cp_profile in self.get_profile_per_congestion_point().items():
            plan = cp_profile.elements
            congestion_point_target = self._target.get_congestion_point_target(cp_id)

            if congestion_point_target is not None:
                # If there is no target, we don't need to check for violations
                target_elements = congestion_point_target.elements

                for i in range(len(target_elements)):
                    element = target_elements[i]
                    max_joule = element.max_joule
                    min_joule = element.min_joule
                    plan_value = plan[i]

                    if max_joule is not None and plan_value > max_joule:
                        return True

                    if min_joule is not None and plan_value < min_joule:
                        return True

        return False

    def is_compatible(self, other: Any) -> bool:
        """Check if this cluster plan is compatible with another profile.

        Args:
            other: The other profile to check compatibility with

        Returns:
            True if compatible, False otherwise
        """
        return self._plan_data.is_compatible(other)

    def subprofile(self, new_start_date: datetime) -> "ClusterPlan":
        """Create a subprofile starting at the specified date.

        Args:
            new_start_date: The new start date for the profile

        Returns:
            A new ClusterPlan instance with adjusted start date
        """
        return ClusterPlan(
            state=self._state,
            target=self._target.subprofile(new_start_date),
            plan_data=self._plan_data.subprofile(new_start_date),
            reason=self._reason,
            plan_due_by_date=self._plan_due_by_date,
            parent_plan=None,
            _id=self._id,
            activated_at=None,
        )

    def adjust_nr_of_elements(self, nr_of_elements: int) -> "ClusterPlan":
        """Adjust the number of elements in the profile.

        Args:
            nr_of_elements: The new number of elements

        Returns:
            A new ClusterPlan instance with adjusted number of elements
        """
        return ClusterPlan(
            state=self._state,
            target=self._target.adjust_nr_of_elements(nr_of_elements),
            plan_data=self._plan_data.adjust_nr_of_elements(nr_of_elements),
            reason=self._reason,
            plan_due_by_date=self._plan_due_by_date,
            parent_plan=None,
            _id=self._id,
            activated_at=None,
        )

    @property
    def metadata(self) -> Any:
        """Get the profile metadata for this plan.

        Returns:
            The profile metadata
        """
        return self._target.metadata

    def get_profile_per_congestion_point(self) -> Dict[str, JouleProfile]:
        """Get the profile for each congestion point.

        Returns:
            A dictionary mapping congestion point IDs to profiles
        """
        result = {}

        for device_plan in self._plan_data.get_device_plans():
            cp_id = self._state.get_congestion_point(device_plan.get_connection_id())
            profile = device_plan.get_profile()

            if cp_id in result:
                result[cp_id] = result[cp_id].add(profile)
            else:
                result[cp_id] = profile

        return result

    def get_joule_profile(self) -> JouleProfile:
        """Get the JouleProfile for this plan.

        Returns:
            The JouleProfile for this plan
        """

        # Add all device plans to the profile
        sum_profile = JouleProfile(
            profile_start=self.metadata.profile_start,
            timestep_duration=self.metadata.timestep_duration,
            profile_length=self.metadata.nr_of_timesteps,
            value=0.0,
        )
        for device_plan in self._plan_data.get_device_plans():
            sum_profile = sum_profile.add(device_plan.get_energy_profile())

        return sum_profile
