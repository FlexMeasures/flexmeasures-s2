import pandas as pd
from datetime import datetime
from typing import Any, Dict, Optional
import logging

from flexmeasures import Scheduler

# Profile steering imports
from flexmeasures_s2.profile_steering.root_planner import RootPlanner
from flexmeasures_s2.profile_steering.congestion_point_planner import (
    CongestionPointPlanner,
)
from flexmeasures_s2.profile_steering.common.joule_range_profile import (
    JouleRangeProfile,
)
from flexmeasures_s2.profile_steering.common_data_structures import (
    ClusterState,
)
from flexmeasures_s2.profile_steering.cluster_plan import ClusterPlan, ClusterPlanData
from flexmeasures_s2.profile_steering.cluster_target import ClusterTarget
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_planner import (
    S2FrbcDevicePlanner,
)
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state import (
    S2FrbcDeviceState,
)

# Schema imports
from flexmeasures_s2.scheduler.schemas import S2FlexModelSchema, TNOFlexContextSchema

# Logger setup
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
                cluster_state, device_state.connection_id
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
                        target.get_global_target_profile().metadata,
                        elements=congestion_point_target.elements,  # type: ignore[union-attr]
                    )

                cpc = CongestionPointPlanner(congestion_point, congestion_point_target, self.config.multithreaded())  # type: ignore[arg-type]
                root_planner.add_congestion_point_controller(cpc)

            # Add the appropriate device planner based on the device state type
            if isinstance(device_state, S2FrbcDeviceState):
                logger.debug("S2 FRBC planner created!")
                cpc.add_device_controller(
                    S2FrbcDevicePlanner(
                        device_state,
                        target.metadata,
                        plan_due_by_date,
                        congestion_point,
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
                target.set_congestion_point_target(
                    congestion_point_id=cp,
                    congestion_point_target=JouleRangeProfile(
                        profile_start=target.get_global_target_profile().metadata,
                    ),
                )

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
                for device in cpc.devices:
                    device_plans.append(device.get_device_plan())

            # Create and return the cluster plan
            plan_data = ClusterPlanData(device_plans, target.metadata)  # type: ignore[arg-type]
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


class S2Scheduler(Scheduler):
    """
    S2Scheduler integrates the profile steering planning service with FlexMeasures.

    This scheduler uses the PlanningServiceImpl to create optimal energy profiles
    for devices in a cluster based on targets and constraints.
    """

    __author__ = "TNO"
    __version__ = "1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.planning_service = None
        self.config_deserialized = False

    def compute(self, *args, **kwargs):
        """
        Compute the optimal energy profile using the S2 profile steering algorithm.

        Returns:
            pandas.Series: Energy profile with timestamps as index and energy values
        """
        if not self.config_deserialized:
            self.deserialize_config()

        # TODO: Implement the actual scheduling logic
        # This should:
        # 1. Create ClusterState from FlexMeasures data
        # 2. Create ClusterTarget from flex_model
        # 3. Call planning_service.plan()
        # 4. Convert the result to pandas.Series

        raise NotImplementedError("S2Scheduler.compute() needs to be implemented")

        # Placeholder return
        return pd.Series(
            self.sensor.get_attribute("capacity_in_mw"),
            index=pd.date_range(
                self.start, self.end, freq=self.resolution, inclusive="left"
            ),
        )

    def deserialize_config(self):
        """Deserialize the flex configuration from asset attributes."""
        # Find flex-model in asset attributes
        self.flex_model = self.asset.attributes.get("flex-model", {})

        self.deserialize_flex_config()
        self.config_deserialized = True

    def deserialize_flex_config(self):
        """Deserialize flex-model and flex-context"""
        # Deserialize flex-model
        self.flex_model = S2FlexModelSchema().load(self.flex_model)

        # Deserialize self.flex_context
        self.flex_context = TNOFlexContextSchema().load(self.flex_context)

    def create_planning_service(
        self, config: Optional[PlanningServiceConfig] = None
    ) -> PlanningServiceImpl:
        """
        Create a planning service instance with the given configuration.

        Args:
            config: Planning service configuration. If None, uses default values.

        Returns:
            PlanningServiceImpl: Configured planning service instance
        """
        if config is None:
            config = PlanningServiceConfig()

        return PlanningServiceImpl(config)

    def create_cluster_state(self, device_states: Dict[str, Any]) -> ClusterState:
        """
        Create a ClusterState from device states.

        Args:
            device_states: Dictionary of device states

        Returns:
            ClusterState: Cluster state for planning
        """
        # TODO: Implement conversion from FlexMeasures device data to ClusterState
        raise NotImplementedError("create_cluster_state() needs to be implemented")

    def create_cluster_target(self, target_profile: Any) -> ClusterTarget:
        """
        Create a ClusterTarget from target profile data.

        Args:
            target_profile: Target profile data from flex_model

        Returns:
            ClusterTarget: Cluster target for planning
        """
        # TODO: Implement conversion from flex_model to ClusterTarget
        raise NotImplementedError("create_cluster_target() needs to be implemented")
