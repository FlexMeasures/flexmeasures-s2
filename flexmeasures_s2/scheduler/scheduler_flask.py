from datetime import datetime, timedelta
from typing import Any, Dict
import pytz

from flask import current_app as app
import pandas as pd

from flexmeasures import Scheduler, Sensor
from flexmeasures.data import db
from flexmeasures.data.models.planning.utils import initialize_index
from flexmeasures.data.queries.utils import simplify_index
from flexmeasures.utils.flexmeasures_inflection import pluralize

# Profile steering imports
from flexmeasures_s2.profile_steering.common_data_structures import ClusterState
from flexmeasures_s2.profile_steering.cluster_plan import ClusterPlan
from flexmeasures_s2.profile_steering.cluster_target import ClusterTarget
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state import (
    S2FrbcDeviceState,
)
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from s2python.frbc import FRBCInstruction

from flexmeasures_s2.scheduler.schedulers import (
    PlanningServiceConfig,
    PlanningServiceImpl,
)


class S2FlaskScheduler(Scheduler):
    """
    S2FlaskScheduler integrates the profile steering planning service with FlexMeasures.

    This is the Flask-compatible version that uses app.logger and app.config
    for integration within the FlexMeasures application context.

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
            self.start = floor_datetime(datetime.now(pytz.utc), self.resolution)
            self.end = self.start + timedelta(hours=24)

            app.logger.info("S2FlaskScheduler.compute() called")

            if not hasattr(self, "frbc_device_data") or self.frbc_device_data is None:
                app.logger.error("No FRBC device data available for planning")
                return []

            # Create device states from FRBC data
            app.logger.info("Creating device states and cluster target from FRBC data")
            device_states, cluster_target = self._create_cluster_state_and_target()

            if not device_states:
                app.logger.warning("No device states created, returning empty result")
                return []

            # Create cluster state
            cluster_state = ClusterState(
                timestamp=datetime.now(),
                device_states=device_states,
                congestion_points_by_connection_id={
                    device_id: "" for device_id in device_states.keys()
                },
            )

            # Get planning service
            planning_service = self._get_planning_service()

            # Calculate planning window
            planning_window_seconds = (self.end - self.start).total_seconds()

            app.logger.info(f"Planning window: {planning_window_seconds} seconds")
            app.logger.info(f"Planning period: {self.start} to {self.end}")

            # Generate plan
            app.logger.info("Generating cluster plan")
            cluster_plan = planning_service.plan(
                state=cluster_state,
                target=cluster_target,
                planning_window=planning_window_seconds,
                reason="S2 WebSocket planning request",
                plan_due_by_date=self.start,
                optimize_for_target=True,
                max_priority_class=1,
            )

            if cluster_plan is None:
                app.logger.error("Planning service returned None")
                return []

            app.logger.info("Plan generated successfully")

            # Convert cluster plan to instructions
            instructions = self._convert_cluster_plan_to_instructions(cluster_plan)
            app.logger.info(f"Generated {len(instructions)} instructions")

            # Add energy data entry for potential storage
            try:
                device_plans = cluster_plan.get_plan_data().get_device_plans()
                for device_plan in device_plans:
                    instructions.append(
                        {
                            "device": device_plan.device_id,
                            "data": pd.Series(
                                device_plan.energy_profile.elements,
                                index=pd.date_range(
                                    self.start,
                                    self.end,
                                    freq=self.resolution,
                                    inclusive="left",
                                ),
                            ),
                        }
                    )
            except Exception as exc:
                self.app.logger.warning(
                    f"Energy profiles of devices could not be retrieved: {str(exc)}"
                )
            return instructions

        except Exception as e:
            app.logger.error(f"Error in S2FlaskScheduler.compute(): {e}")
            import traceback

            app.logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    def _get_planning_service(self) -> PlanningServiceImpl:
        """Get or create the planning service instance."""
        if not hasattr(self, "planning_service") or self.planning_service is None:
            config = PlanningServiceConfig(
                energy_improvement_criterion=10.0,
                cost_improvement_criterion=1.0,
                congestion_retry_iterations=10,
                multithreaded=False,
            )
            self.planning_service = PlanningServiceImpl(config)
            app.logger.info("Planning service initialized")
        return self.planning_service

    def _create_cluster_state_and_target(self):
        """Create cluster state and target from FRBC device data."""
        device_states = self.create_device_states_from_frbc_data()

        if not device_states:
            return device_states, None

        # Create cluster target
        cluster_target = self._create_cluster_target()

        return device_states, cluster_target

    def _create_cluster_target(self) -> ClusterTarget:
        """Create cluster target profile."""

        # Calculate profile metadata
        profile_metadata = ProfileMetadata(
            profile_start=self.start,
            timestep_duration=self.resolution,
            nr_of_timesteps=int((self.end - self.start) / self.resolution),
        )

        # Get target elements (this could be from sensor data or configuration)
        target_elements = self._get_target_elements(profile_metadata.nr_of_timesteps)

        # Type ignore: TargetProfile constructor accepts List[int] and converts to JouleElement
        target_mode = app.config.get("FLEXMEASURES_S2_TARGET_MODE", "costs")
        app.logger.debug(f"Target mode = {target_mode}")
        if target_mode == "energy":
            global_target_profile = TargetProfile(
                profile_start=profile_metadata.profile_start,
                timestep_duration=profile_metadata.timestep_duration,
                elements=target_elements,  # type: ignore[arg-type]
            )
        else:  # target_mode == "costs"
            price_sensor_id = app.config.get("FLEXMEASURES_S2_PRICE_SENSOR", 2)
            price_sensor = db.session.get(Sensor, price_sensor_id)
            if price_sensor is None:
                app.logger.warning(
                    "Cannot create cost-based target without sensor. Using default energy target."
                )
                global_target_profile = TargetProfile(
                    profile_start=profile_metadata.profile_start,
                    timestep_duration=profile_metadata.timestep_duration,
                    elements=target_elements,  # type: ignore[arg-type]
                )
            else:
                # Query tariff data for the planning period
                tariffs = price_sensor.search_beliefs(
                    event_starts_after=self.start,
                    event_ends_before=self.end,
                    resolution=self.resolution,
                    beliefs_before=self.belief_time,
                    most_recent_beliefs_only=True,
                )

                if (
                    n_missing_prices := (self.end - self.start) // self.resolution
                    - len(tariffs)
                ) > 0:
                    tariffs = simplify_index(tariffs)
                    tariffs = tariffs.reindex(
                        initialize_index(
                            start=self.start, end=self.end, resolution=self.resolution
                        )
                    )
                    if n_missing_prices == len(tariffs):
                        app.logger.warning(
                            f"All prices are missing in the period {self.start.isoformat()} until {self.end.isoformat()}; assuming a constant energy price of 1 EUR/MWh"
                        )
                        tariffs = tariffs.fillna(1)
                    else:
                        app.logger.warning(
                            f"Forward filling {n_missing_prices} {pluralize('price', n_missing_prices)} in the period {self.start.isoformat()} until {self.end.isoformat()}"
                        )
                        tariffs = tariffs.ffill()

                global_target_profile = TargetProfile.from_tariff_values(
                    metadata=profile_metadata,
                    tariff_values=tariffs.values,
                )

        # Create cluster target
        cluster_target = ClusterTarget(
            generated_at=datetime.now(),
            parent_id=None,
            generated_by=None,
            global_target_profile=global_target_profile,
            congestion_point_targets={},
        )

        return cluster_target

    def _get_target_elements(self, num_elements: int) -> list[int]:
        """Get target elements for the planning horizon."""
        # This could be configured via app.config or calculated based on business logic
        # For now, use a simple pattern similar to the example
        target_elements = []

        # Simple pattern: low consumption at night, higher during day
        for i in range(num_elements):
            hour_of_day = (i * (self.resolution.total_seconds() / 3600)) % 24
            if 0 <= hour_of_day < 6:  # Night: 0 consumption
                target_elements.append(0)
            elif 6 <= hour_of_day < 9:  # Morning: moderate consumption
                target_elements.append(4200000)  # 4.2 MJ
            elif 9 <= hour_of_day < 17:  # Day: no specific target
                target_elements.append(0)
            elif 17 <= hour_of_day < 21:  # Evening: moderate consumption
                target_elements.append(4200000)  # 4.2 MJ
            else:  # Late evening: high consumption
                target_elements.append(8800000)  # 8.8 MJ

        return target_elements

    def _convert_cluster_plan_to_instructions(self, cluster_plan: ClusterPlan) -> list:
        """Convert cluster plan to FRBC instructions."""
        instructions = []

        # Get device plans from cluster plan
        device_plans = cluster_plan.get_plan_data().get_device_plans()

        for device_plan in device_plans:
            if device_plan is None:
                continue

            try:
                # Convert device plan to instructions
                device_instructions = device_plan.instruction_profile.elements

                for instruction in device_instructions:
                    if isinstance(instruction, FRBCInstruction):
                        instructions.append(instruction)

                # Add metadata about the plan
                instructions.append(
                    {
                        "device_id": device_plan.device_id,
                        "plan_type": "FRBC",
                        "num_instructions": len(device_instructions),
                    }
                )

            except Exception as e:
                app.logger.error(f"Error converting device plan to instructions: {e}")
                continue

        return instructions

    def set_frbc_device_data(self, device_data: Any):
        """Set FRBC device data for planning."""
        self.frbc_device_data = device_data
        if hasattr(device_data, "resource_id"):
            app.logger.debug(
                f"FRBC device data set for device {device_data.resource_id}"
            )
        elif isinstance(device_data, dict):
            app.logger.debug(f"FRBC device data set for {len(device_data)} devices")
        else:
            app.logger.debug(f"FRBC device data set: {type(device_data)}")

    def create_device_states_from_frbc_data(self) -> Dict[str, Any]:
        """
        Create device states from received FRBC data.

        Returns:
            Dict[str, Any]: Dictionary of device states created from FRBC data
        """
        from s2python.common import PowerValue, CommodityQuantity

        if not hasattr(self, "frbc_device_data") or self.frbc_device_data is None:
            app.logger.warning("No FRBC device data available")
            return {}

        device_states = {}

        # Handle single FRBCDeviceData object from WebSocket
        if hasattr(self.frbc_device_data, "resource_id"):
            frbc_data = self.frbc_device_data
            device_id = frbc_data.resource_id or "frbc_device_1"

            try:
                app.logger.debug(f"Creating device state for {device_id}")

                # Extract information from received FRBC data object
                system_desc = frbc_data.system_description
                storage_status = frbc_data.storage_status
                actuator_statuses = (
                    list(frbc_data.actuator_statuses.values())
                    if hasattr(frbc_data, "actuator_statuses")
                    else []
                )
                fill_level_target_profile = frbc_data.fill_level_target_profile

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
                    fill_level_target_profiles=[fill_level_target_profile]
                    if fill_level_target_profile
                    else [],
                    computational_parameters=S2FrbcDeviceState.ComputationalParameters(
                        100, 20
                    ),
                    actuator_statuses=actuator_statuses,
                    storage_status=[storage_status] if storage_status else [],
                )

                device_states[device_id] = device_state
                app.logger.debug(f"Device state created for {device_id}")

            except Exception as e:
                app.logger.error(f"Error creating device state for {device_id}: {e}")

        # Handle dictionary of device data (backward compatibility)
        elif isinstance(self.frbc_device_data, dict):
            for device_id, frbc_data in self.frbc_device_data.items():
                try:
                    app.logger.debug(f"Creating device state for {device_id}")

                    # Extract information from received FRBC data
                    system_desc = frbc_data.get("system_description")
                    storage_status = frbc_data.get("storage_status")
                    actuator_statuses = (
                        list(frbc_data.get("actuator_statuses", {}).values())
                        if "actuator_statuses" in frbc_data
                        else [frbc_data.get("actuator_status")]
                        if frbc_data.get("actuator_status")
                        else []
                    )
                    fill_level_target_profile = frbc_data.get(
                        "fill_level_target_profile"
                    )

                    # Create device state using the received FRBC data
                    device_state = S2FrbcDeviceState(
                        device_id=device_id,
                        device_name=f"FRBC Device {device_id}",
                        connection_id=f"{device_id}_connection",
                        priority_class=1,
                        timestamp=self.start,
                        energy_in_current_timestep=PowerValue(
                            value=0,
                            commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1,
                        ),
                        is_online=True,
                        power_forecast=None,
                        system_descriptions=[system_desc] if system_desc else [],
                        leakage_behaviours=[],
                        usage_forecasts=[],
                        fill_level_target_profiles=[fill_level_target_profile]
                        if fill_level_target_profile
                        else [],
                        computational_parameters=S2FrbcDeviceState.ComputationalParameters(
                            100, 20
                        ),
                        actuator_statuses=actuator_statuses,
                        storage_status=[storage_status] if storage_status else [],
                    )

                    device_states[device_id] = device_state
                    app.logger.debug(f"Device state created for {device_id}")

                except Exception as e:
                    app.logger.error(
                        f"Error creating device state for {device_id}: {e}"
                    )
                    continue
        else:
            app.logger.error(
                f"Unexpected FRBC device data type: {type(self.frbc_device_data)}"
            )

        return device_states

    def deserialize_config(self):
        """Deserialize the flex_model configuration."""
        # For now, we use default configuration
        # This could be extended to read from self.flex_model if needed
        self.config_deserialized = True
        app.logger.debug("S2FlaskScheduler config deserialized")


def floor_datetime(dt, resolution):
    # Ensure dt is timezone-aware
    if dt.tzinfo is None:
        raise ValueError("Input datetime must be timezone-aware")

    # Get total seconds since midnight
    midnight = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    seconds_since_midnight = (dt - midnight).total_seconds()

    # Floor the seconds to the nearest resolution
    floored_seconds = int(seconds_since_midnight // resolution.total_seconds()) * int(
        resolution.total_seconds()
    )

    # Return the floored datetime
    return midnight + timedelta(seconds=floored_seconds)
