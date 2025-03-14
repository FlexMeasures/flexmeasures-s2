from datetime import datetime
from typing import List, Dict, Any, Optional

# Core profile steering imports
from flexmeasures_s2.profile_steering.root_planner import RootPlanner
from flexmeasures_s2.profile_steering.congestion_point_planner import (
    CongestionPointPlanner,
)

# Common data types
from flexmeasures_s2.profile_steering.common.joule_range_profile import (
    JouleRangeProfile,
)
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
# Device planner imports
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_planner import (
    S2FrbcDevicePlanner,
)
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state import (
    S2FrbcDeviceState,
)

# Import other device planners as needed
# Import statements for other device planners would go here

# Logger setup
import logging

logger = logging.getLogger(__name__)


class PlanningServiceConfig:
    """Configuration for the planning service."""

    def __init__(
        self,
        energy_improvement_criterion: float = 0.01,
        cost_improvement_criterion: float = 0.01,
        congestion_retry_iterations: int = 5,
        multithreaded: bool = False,
    ):
        self._energy_improvement_criterion = energy_improvement_criterion
        self._cost_improvement_criterion = cost_improvement_criterion
        self._congestion_retry_iterations = congestion_retry_iterations
        self._multithreaded = multithreaded

    def energy_improvement_criterion(self) -> float:
        return self._energy_improvement_criterion

    def cost_improvement_criterion(self) -> float:
        return self._cost_improvement_criterion

    def congestion_retry_iterations(self) -> int:
        return self._congestion_retry_iterations

    def multithreaded(self) -> bool:
        return self._multithreaded


class ClusterState:
    """Class representing the state of a cluster of devices."""

    def __init__(self, device_states: Dict[str, Any] = None):
        self._device_states = device_states or {}
        self._congestion_points = {}  # Map from connection ID to congestion point ID

    def get_device_states(self) -> Dict[str, Any]:
        return self._device_states

    def get_congestion_point(self, connection_id: str) -> Optional[str]:
        return self._congestion_points.get(connection_id)

    def set_congestion_point(self, connection_id: str, congestion_point_id: str):
        
        self._congestion_points[connection_id] = congestion_point_id

    def get_congestion_points(self) -> List[str]:
        return list(set(self._congestion_points.values()))


class ClusterTarget:
    """Class representing a target for a cluster."""

    def __init__(self, generated_at: datetime, parent_id: Any, generated_by: Any, global_target_profile: TargetProfile, congestion_point_targets: Optional[Dict[str, JouleRangeProfile]] = None) -> None:
        self._generated_at = generated_at
        self._parent_id = parent_id
        self._generated_by = generated_by
        self._global_target_profile = global_target_profile
        self._congestion_point_targets = congestion_point_targets
        if congestion_point_targets is not None:
            for congestion_point_id, congestion_point_target in congestion_point_targets.items():
                if not congestion_point_target.is_compatible(global_target_profile):
                    raise ValueError(f"Congestion point target {congestion_point_id} is not compatible with the global target profile")
    
    def get_global_target_profile(self) -> Any:
        return self._global_target_profile

    def get_profile_metadata(self) -> Any:
        return self._global_target_profile.get_profile_metadata()

    def get_congestion_point_target(
        self, congestion_point_id: str
    ) -> Optional[JouleRangeProfile]:
        if self._congestion_point_targets is None:
            return None
        return self._congestion_point_targets.get(congestion_point_id)

    def get_congestion_point_targets(self) -> Dict[str, JouleRangeProfile]:
        if self._congestion_point_targets is None:
            return {}
        return self._congestion_point_targets
    
    def set_congestion_point_target(self, congestion_point_id: str, congestion_point_target: JouleRangeProfile):
        if self._congestion_point_targets is None:
            self._congestion_point_targets = {}
        self._congestion_point_targets[congestion_point_id] = congestion_point_target


class DevicePlan:
    """Class representing a plan for a device."""

    def __init__(self, device_id: str, profile: JouleProfile):
        self._device_id = device_id
        self._profile = profile

    def get_device_id(self) -> str:
        return self._device_id

    def get_profile(self) -> JouleProfile:
        return self._profile


class ClusterPlanData:
    """Class representing planning data for a cluster."""

    def __init__(self, device_plans: List[DevicePlan], profile_metadata: Any):
        self._device_plans = device_plans
        self._profile_metadata = profile_metadata

    def get_device_plans(self) -> List[DevicePlan]:
        return self._device_plans

    def get_profile_metadata(self) -> Any:
        return self._profile_metadata


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
    ):
        self._state = state
        self._target = target
        self._plan_data = plan_data
        self._reason = reason
        self._plan_due_by_date = plan_due_by_date
        self._parent_plan = parent_plan

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


class PlanningService:
    """Interface for planning services."""

    def plan(
        self,
        state: ClusterState,
        target: ClusterTarget,
        planning_window: int,
        reason: str,
        plan_due_by_date: datetime,
        optimize_for_target: bool,
        max_priority_class: int,
    ) -> ClusterPlan:
        """Create a plan for the cluster."""
        raise NotImplementedError("Subclasses must implement this method")


class PlanningServiceImpl(PlanningService):
    """Implementation of the planning service."""

    DEFAULT_CONGESTION_POINT = ""

    def __init__(self, config: PlanningServiceConfig, context: Any = None):
        """Initialize the planning service.

        Args:
            config: Configuration for the planning service
            context: Execution context (used for multithreading)
        """
        self.config = config
        self.context = context
        logger.info("Planning service initialized")

    def get_congestion_point(
        self, cluster_state: ClusterState, connection_id: str
    ) -> str:
        """Get the congestion point for a connection ID.

        Args:
            cluster_state: The state of the cluster
            connection_id: The connection ID to get the congestion point for

        Returns:
            The congestion point ID, or DEFAULT_CONGESTION_POINT if none is assigned
        """
        congestion_point = cluster_state.get_congestion_point(connection_id)
        if congestion_point is None:
            # This can happen if a device has no congestion point assigned yet.
            # We handle this by giving them all the empty congestion point.
            return self.DEFAULT_CONGESTION_POINT
        return congestion_point

    def create_controller_tree(
        self,
        cluster_state: ClusterState,
        target: ClusterTarget,
        plan_due_by_date: datetime,
    ) -> RootPlanner:
        """Create a tree of controllers for planning.

        Args:
            cluster_state: The state of the cluster
            target: The target for the cluster
            plan_due_by_date: The date by which planning must be completed

        Returns:
            A RootPlanner with appropriate device planners added
        """
        root_planner = RootPlanner(
            target.get_global_target_profile(),
            self.config.energy_improvement_criterion(),
            self.config.cost_improvement_criterion(),
            self.context,
        )

        for device_id, device_state in cluster_state.get_device_states().items():
            congestion_point = self.get_congestion_point(
                cluster_state, device_state.get_connection_id()
            )
            cpc = root_planner.get_congestion_point_controller(congestion_point)

            if cpc is None:
                # Create a new congestion point controller if one doesn't exist yet
                congestion_point_target = target.get_congestion_point_target(
                    congestion_point
                )
                if congestion_point == self.DEFAULT_CONGESTION_POINT:
                    # This is a dummy congestion point. We will give it an empty profile.
                    congestion_point_target = JouleRangeProfile(
                        target.get_global_target_profile().get_profile_metadata()
                    )

                cpc = CongestionPointPlanner(congestion_point, congestion_point_target)
                root_planner.add_congestion_point_controller(cpc)

            # Add the appropriate device planner based on the device state type
            if isinstance(device_state, S2FrbcDeviceState):
                logger.debug("S2 FRBC planner created!")
                cpc.add_device_controller(
                    S2FrbcDevicePlanner(
                        device_state, target.get_profile_metadata(), plan_due_by_date
                    )
                )
            # Add other device types here as needed
            else:
                logger.warning(
                    f"Unknown device! No device planner added for {device_state}"
                )

        return root_planner

    def plan(
        self,
        state: ClusterState,
        target: ClusterTarget,
        planning_window: int,
        reason: str,
        plan_due_by_date: datetime,
        optimize_for_target: bool,
        max_priority_class: int,
    ) -> ClusterPlan:
        """Create a plan for the cluster.

        Args:
            state: The state of the cluster
            target: The target for the cluster
            planning_window: The planning window in seconds
            reason: The reason for planning
            plan_due_by_date: The date by which planning must be completed
            optimize_for_target: Whether to optimize for the target
            max_priority_class: The maximum priority class to optimize

        Returns:
            A ClusterPlan for the cluster
        """
        start_time = datetime.now()

        # Make sure that all congestion points in the ClusterState have a target:
        for cp in state.get_congestion_points():
            congestion_point_target = target.get_congestion_point_target(cp)
            if congestion_point_target is None and cp is not None:
                # We don't have a target for the congestion point
                logger.warning(
                    f"CongestionPoint without target! CongestionPoint: {cp}. Generating empty target."
                )
                target.set_congestion_point_target_global_target(cp, JouleRangeProfile(
                    target.get_global_target_profile().get_profile_metadata()
                ))

        # Create a tree of controllers and run the planning algorithm
        root_controller = self.create_controller_tree(state, target, plan_due_by_date)

        try: 
            root_controller.plan(
                plan_due_by_date,
                optimize_for_target,
                max_priority_class,
                self.config.multithreaded(),
            )

            # Collect device plans
            device_plans = []
            for cpc in root_controller.cp_controllers:
                for device in cpc.get_device_controllers():
                    device_plans.append(device.get_device_plan())

            # Create and return the cluster plan
            plan_data = ClusterPlanData(device_plans, target.get_profile_metadata())
            plan = ClusterPlan(state, target, plan_data, reason, plan_due_by_date, None)

            end_time = datetime.now()
            execution_time = (
                end_time - start_time
            ).total_seconds() * 1000  # Convert to milliseconds
            logger.info(f"Generated new plan in {execution_time} ms")

            return plan
        except Exception as e:
            logger.error(f"Error during planning: {e}")
            raise
