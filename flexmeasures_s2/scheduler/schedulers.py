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
from flexmeasures_s2.profile_steering.device_planner.nocontrol.s2_nocontrol_device_planner import (
    S2NoControlDevicePlanner,
)
from flexmeasures_s2.profile_steering.device_planner.nocontrol.s2_nocontrol_device_state import (
    S2NoControlDeviceState,
)
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_device_planner import (
    S2DdbcDevicePlanner,
)
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_device_state import (
    S2DdbcDeviceState,
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
        # Always accepting all targets is NOT possible if there is an energy target
        always_accept_all_proposals = not target.contains_energy_target()

        root_planner = RootPlanner(
            target.get_global_target_profile(),
            self.config.energy_improvement_criterion(),
            self.config.cost_improvement_criterion(),
            always_accept_all_proposals,
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
                        elements=congestion_point_target.elements
                        if congestion_point_target is not None
                        else [],
                    )

                cpc = CongestionPointPlanner(congestion_point, congestion_point_target, self.config.multithreaded())  # type: ignore[arg-type]
                root_planner.add_congestion_point_controller(cpc)

            # Add the appropriate device planner based on the device state type
            if isinstance(device_state, S2FrbcDeviceState):
                logger.debug("S2 FRBC planner created!")
                cpc.add_device_controller(
                    S2FrbcDevicePlanner(
                        s2_frbc_state=device_state,
                        profile_metadata=target.metadata,
                        plan_due_by_date=plan_due_by_date,
                        congestion_point_id=congestion_point,
                    )
                )
            elif isinstance(device_state, S2NoControlDeviceState):
                logger.debug("S2 NoControl planner created!")
                cpc.add_device_controller(
                    S2NoControlDevicePlanner(
                        device_state=device_state,
                        profile_metadata=target.metadata,
                        congestion_point_id=congestion_point,
                    )
                )
            elif isinstance(device_state, S2DdbcDeviceState):
                logger.debug("S2 DDBC planner created!")
                cpc.add_device_controller(
                    S2DdbcDevicePlanner(
                        s2_ddbc_state=device_state,
                        profile_metadata=target.metadata,
                        plan_due_by_date=plan_due_by_date,
                        congestion_point_id=congestion_point,
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
        self.frbc_device_data = None  # Store FRBC device data from WebSocket

    def compute(self, *args, **kwargs):
        """
        Compute the optimal energy profile using the S2 profile steering algorithm.

        Returns:
            List: List containing FRBCInstruction objects and metadata dicts
        """
        if not self.config_deserialized:
            self.deserialize_config()

        try:
            # Create planning service
            config = PlanningServiceConfig()
            planning_service = PlanningServiceImpl(config)

            # Use FRBC device data if available, otherwise use mock data
            if self.frbc_device_data is not None:
                logger.info("Creating device states and cluster target from FRBC data")
                device_states = self.create_device_states_from_frbc_data()
                cluster_target = self.create_cluster_target_from_frbc_data()
            else:
                # Fallback to mock data for testing
                logger.info("Using mock device states and cluster target")
                device_states = self.create_mock_device_states()
                cluster_target = self.create_mock_cluster_target()

            logger.info(f"Created cluster state with {len(device_states)} devices")
            cluster_state = ClusterState(self.start, device_states, {})

            # Generate plan
            logger.info("Starting planning service...")
            try:
                cluster_plan = planning_service.plan(
                    state=cluster_state,
                    target=cluster_target,
                    planning_window=int((self.end - self.start).total_seconds()),
                    reason="S2 scheduling",
                    plan_due_by_date=self.start + pd.Timedelta(seconds=10),
                    optimize_for_target=True,
                    max_priority_class=1,
                )
                logger.info("Planning service completed successfully")
            except Exception as planning_error:
                logger.error(f"Planning service failed: {planning_error}")
                # Generate instructions directly without planning
                if self.frbc_device_data is not None:
                    logger.info("Falling back to simple FRBC instruction generation")
                    instructions = self._generate_simple_frbc_instructions()
                else:
                    instructions = []

                # Create empty energy data
                num_timesteps = int((self.end - self.start) / self.resolution)
                energy_data = {
                    "sensor": self.sensor,
                    "data": pd.Series(
                        [0] * num_timesteps,
                        index=pd.date_range(
                            self.start, self.end, freq=self.resolution, inclusive="left"
                        ),
                    ),
                }
                return instructions + [energy_data]

            # Extract FRBCInstructions from device plans
            instructions = []
            device_plans = cluster_plan.get_plan_data().get_device_plans()

            for device_plan in device_plans:
                if device_plan and device_plan.instruction_profile:
                    instructions.extend(device_plan.instruction_profile.elements)

            # If we have FRBC device data but no instructions from planning,
            # generate simple instructions based on the received data
            if not instructions and self.frbc_device_data is not None:
                logger.info(
                    "No instructions from planning service, generating simple FRBC instructions"
                )
                instructions = self._generate_simple_frbc_instructions()

            # Add energy data entry for potential storage
            try:
                energy_profile = cluster_plan.get_joule_profile()
                if energy_profile is not None and energy_profile.elements is not None:
                    energy_data = {
                        "sensor": self.sensor,
                        "data": pd.Series(
                            energy_profile.elements,
                            index=pd.date_range(
                                self.start,
                                self.end,
                                freq=self.resolution,
                                inclusive="left",
                            ),
                        ),
                    }
                else:
                    # Create empty energy data if profile is None or has no elements
                    num_timesteps = int((self.end - self.start) / self.resolution)
                    energy_data = {
                        "sensor": self.sensor,
                        "data": pd.Series(
                            [0] * num_timesteps,
                            index=pd.date_range(
                                self.start,
                                self.end,
                                freq=self.resolution,
                                inclusive="left",
                            ),
                        ),
                    }
            except Exception as profile_error:
                logger.warning(
                    f"Failed to get energy profile: {profile_error}, using fallback"
                )
                # Create empty energy data as fallback
                num_timesteps = int((self.end - self.start) / self.resolution)
                energy_data = {
                    "sensor": self.sensor,
                    "data": pd.Series(
                        [0] * num_timesteps,
                        index=pd.date_range(
                            self.start, self.end, freq=self.resolution, inclusive="left"
                        ),
                    ),
                }

            return instructions + [energy_data]

        except Exception as e:
            logger.error(f"Error in S2Scheduler.compute(): {e}")
            import traceback

            logger.debug(f"Traceback: {traceback.format_exc()}")
            # Return empty list on error
            return []

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

    def create_mock_device_states(self) -> Dict[str, Any]:
        """
        Create mock device states for testing.

        Returns:
            Dict[str, Any]: Dictionary of mock device states
        """
        from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state import (
            S2FrbcDeviceState,
        )
        from s2python.common import PowerValue, CommodityQuantity

        # Create a simple mock device state for testing
        mock_device_state = S2FrbcDeviceState(
            device_id="mock_device_1",
            device_name="Mock Device 1",
            connection_id="mock_connection_1",
            priority_class=1,
            timestamp=self.start,
            energy_in_current_timestep=PowerValue(
                value=0, commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1
            ),
            is_online=True,
            power_forecast=None,
            system_descriptions=[],
            leakage_behaviours=[],
            usage_forecasts=[],
            fill_level_target_profiles=[],
            computational_parameters=S2FrbcDeviceState.ComputationalParameters(100, 20),
            actuator_statuses=[],
            storage_status=[],
        )

        return {"mock_device_1": mock_device_state}

    def create_mock_cluster_target(self) -> ClusterTarget:
        """
        Create a mock cluster target for testing.

        Returns:
            ClusterTarget: Mock cluster target
        """
        from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
        from flexmeasures_s2.profile_steering.common.profile_metadata import (
            ProfileMetadata,
        )

        # Create mock profile metadata
        profile_metadata = ProfileMetadata(
            profile_start=self.start,
            timestep_duration=self.resolution,
            nr_of_timesteps=int((self.end - self.start) / self.resolution),
        )

        # Create a simple target profile with zeros
        target_elements = [0] * profile_metadata.nr_of_timesteps
        # Type ignore: TargetProfile constructor accepts List[int] and converts to JouleElement
        global_target_profile = TargetProfile(
            profile_start=profile_metadata.profile_start,
            timestep_duration=profile_metadata.timestep_duration,
            elements=target_elements,  # type: ignore[arg-type]
        )

        return ClusterTarget(
            generated_at=self.start,
            parent_id=None,
            generated_by=None,
            global_target_profile=global_target_profile,
            congestion_point_targets={},
        )

    def create_device_states_from_frbc_data(self) -> Dict[str, Any]:
        """
        Create device states from received FRBC data.

        Returns:
            Dict[str, Any]: Dictionary of device states created from FRBC data
        """
        from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state import (
            S2FrbcDeviceState,
        )
        from s2python.common import PowerValue, CommodityQuantity

        if self.frbc_device_data is None:
            return self.create_mock_device_states()

        # Extract information from received FRBC data
        device_id = self.frbc_device_data.resource_id or "frbc_device_1"
        system_desc = self.frbc_device_data.system_description
        storage_status = self.frbc_device_data.storage_status

        # Create device state using the received FRBC data
        device_state = S2FrbcDeviceState(
            device_id=device_id,
            device_name=f"FRBC Device {device_id}",
            connection_id=f"{device_id}_connection",
            priority_class=1,
            timestamp=self.start,
            energy_in_current_timestep=PowerValue(
                value=0, commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1
            ),
            is_online=True,
            power_forecast=None,
            system_descriptions=[system_desc] if system_desc else [],
            leakage_behaviours=[],
            usage_forecasts=[],
            fill_level_target_profiles=[self.frbc_device_data.fill_level_target_profile]
            if self.frbc_device_data.fill_level_target_profile
            else [],
            computational_parameters=S2FrbcDeviceState.ComputationalParameters(100, 20),
            actuator_statuses=list(self.frbc_device_data.actuator_statuses.values())
            if hasattr(self.frbc_device_data, "actuator_statuses")
            else [],
            storage_status=[storage_status] if storage_status else [],
        )

        return {device_id: device_state}

    def create_cluster_target_from_frbc_data(self) -> ClusterTarget:
        """
        Create a cluster target from FRBC device data.

        Returns:
            ClusterTarget: Cluster target based on FRBC data
        """
        from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
        from flexmeasures_s2.profile_steering.common.profile_metadata import (
            ProfileMetadata,
        )

        if (
            self.frbc_device_data is None
            or self.frbc_device_data.fill_level_target_profile is None
        ):
            return self.create_mock_cluster_target()

        # Create profile metadata
        profile_metadata = ProfileMetadata(
            profile_start=self.start,
            timestep_duration=self.resolution,
            nr_of_timesteps=int((self.end - self.start) / self.resolution),
        )

        # Convert FRBC fill level target to energy target
        # This is a simplified conversion - in practice you'd need more sophisticated logic
        target_elements = self._convert_frbc_fill_level_to_energy_target(
            self.frbc_device_data.fill_level_target_profile,
            profile_metadata.nr_of_timesteps,
        )

        # Type ignore: TargetProfile constructor accepts List[int] and converts to JouleElement
        target_mode = "costs"  # Default mode when running outside Flask context
        logging.debug(f"Target mode = {target_mode}")
        if target_mode == "energy":
            global_target_profile = TargetProfile(
                profile_start=profile_metadata.profile_start,
                timestep_duration=profile_metadata.timestep_duration,
                elements=target_elements,  # type: ignore[arg-type]
            )
        elif target_mode == "costs":
            # For standalone operation, fall back to energy target mode
            logging.warning(
                "Cost target mode requires Flask context, falling back to energy target mode"
            )
            # Fall back to creating a simple energy target
            global_target_profile = TargetProfile(
                profile_start=profile_metadata.profile_start,
                timestep_duration=profile_metadata.timestep_duration,
                elements=target_elements,  # type: ignore[arg-type]
            )
        else:
            raise ValueError(f"Unknown FLEXMEASURES_S2_TARGET_MODE='{target_mode}'")

        return ClusterTarget(
            generated_at=self.start,
            parent_id=None,
            generated_by=None,
            global_target_profile=global_target_profile,
            congestion_point_targets={},
        )

    def _convert_frbc_fill_level_to_energy_target(
        self, fill_level_profile, nr_timesteps: int
    ) -> list:
        """
        Convert FRBC fill level target profile to energy target profile.

        This is a simplified conversion for demonstration.
        """
        # Simple conversion: aim for charging when fill level targets are higher
        target_elements = []

        if fill_level_profile and fill_level_profile.elements:
            # For each target element, determine if we need to charge/discharge
            current_timestep = 0

            for element in fill_level_profile.elements:
                duration_seconds = (
                    getattr(element.duration, "value", 0) / 1000
                )  # Convert ms to seconds
                timesteps_for_element = max(
                    1, int(duration_seconds / self.resolution.total_seconds())
                )

                # Simple logic: if target range is high, we want to charge (positive energy)
                target_range_avg = (
                    element.fill_level_range.start_of_range
                    + element.fill_level_range.end_of_range
                ) / 2

                if target_range_avg > 50:  # Above 50% - charging target
                    energy_target = 10000  # 10kJ per timestep
                else:  # Below 50% - minimal energy
                    energy_target = 1000  # 1kJ per timestep

                # Add target for this duration
                for _ in range(
                    min(timesteps_for_element, nr_timesteps - current_timestep)
                ):
                    target_elements.append(energy_target)
                    current_timestep += 1

                if current_timestep >= nr_timesteps:
                    break

        # Fill remaining timesteps with zeros
        while len(target_elements) < nr_timesteps:
            target_elements.append(0)

        return target_elements[:nr_timesteps]

    def _generate_simple_frbc_instructions(self) -> list:
        """
        Generate simple FRBC instructions based on received device data.

        Returns:
            List of FRBCInstruction objects
        """
        from s2python.frbc import FRBCInstruction
        from datetime import timezone
        import uuid

        if (
            self.frbc_device_data is None
            or self.frbc_device_data.system_description is None
        ):
            return []

        instructions = []
        system_desc = self.frbc_device_data.system_description
        fill_level_target = self.frbc_device_data.fill_level_target_profile

        # Extract actuator and operation mode information
        if system_desc.actuators:
            actuator = system_desc.actuators[0]  # Use first actuator
            if actuator.operation_modes:
                operation_mode = actuator.operation_modes[0]  # Use first operation mode

                # Determine operation mode factor based on fill level targets
                operation_mode_factor = 0.5  # Default

                if fill_level_target and fill_level_target.elements:
                    # Simple logic: higher target ranges get higher factors
                    for element in fill_level_target.elements:
                        target_avg = (
                            element.fill_level_range.start_of_range
                            + element.fill_level_range.end_of_range
                        ) / 2
                        if target_avg > 50:
                            operation_mode_factor = 0.8  # Higher factor for charging
                        else:
                            operation_mode_factor = 0.2  # Lower factor for maintaining
                        break  # Use first element for simplicity

                # Generate instruction for near future
                execution_time = self.start.replace(tzinfo=timezone.utc)

                instruction = FRBCInstruction(
                    message_id=str(uuid.uuid4()),
                    id=str(uuid.uuid4()),
                    actuator_id=str(actuator.id),
                    operation_mode=str(operation_mode.id),
                    operation_mode_factor=operation_mode_factor,
                    execution_time=execution_time,
                    abnormal_condition=False,
                )

                instructions.append(instruction)
                logger.info(f"Generated FRBC instruction: {instruction.to_json()}")

        return instructions
