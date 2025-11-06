from datetime import datetime
from typing import List, Dict
import logging

from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_device_state import (
    S2DdbcDeviceState,
)
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_device_state_wrapper import (
    S2DdbcDeviceStateWrapper,
)
from flexmeasures_s2.profile_steering.device_planner.ddbc.ddbc_timestep import (
    DdbcTimestep,
)
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_plan import (
    S2DdbcPlan,
    S2DdbcActuatorConfiguration,
)

logger = logging.getLogger(__name__)


class DdbcPlanningWindow:
    """
    Planning window for DDBC devices.
    Creates a simple plan that meets demand forecasts using available operation modes.
    """

    def __init__(
        self,
        device_state: S2DdbcDeviceState,
        profile_metadata: ProfileMetadata,
        plan_due_by_date: datetime,
    ):
        self.device_state_wrapper = S2DdbcDeviceStateWrapper(device_state)
        self.device_state = device_state
        self.profile_metadata = profile_metadata
        self.plan_due_by_date = plan_due_by_date
        self.timestep_duration_seconds = (
            profile_metadata.timestep_duration.total_seconds()
        )
        self.timesteps: List[DdbcTimestep] = []

        self._generate_timesteps()

    def _generate_timesteps(self):
        """Generate timesteps with system descriptions and demand forecasts."""
        timestep_start = self.profile_metadata.profile_start

        # Get the latest system description and demand forecast
        system_descriptions = self.device_state.get_system_descriptions()
        demand_forecasts = self.device_state.get_demand_forecasts()

        # Use the first available system description and demand forecast
        system_description = system_descriptions[0] if system_descriptions else None
        demand_forecast = demand_forecasts[0] if demand_forecasts else None

        for i in range(self.profile_metadata.nr_of_timesteps):
            timestep = DdbcTimestep(
                start_date=timestep_start,
                timestep_duration_seconds=self.timestep_duration_seconds,
                system_description=system_description,
                demand_forecast=demand_forecast,
            )
            self.timesteps.append(timestep)

            timestep_start = timestep_start + self.profile_metadata.timestep_duration

    def find_best_plan(
        self,
        target_profile: TargetProfile,
        diff_to_min_profile: JouleProfile,
        diff_to_max_profile: JouleProfile,
    ) -> S2DdbcPlan:
        """
        Find the best plan for DDBC device.
        Balances between meeting demand forecasts and optimizing for target profiles.
        """
        energy_elements: List[float] = []
        actuator_configs_per_timestep: List[Dict[str, S2DdbcActuatorConfiguration]] = []

        # Debug: log what kind of target we received
        try:
            if target_profile.elements and len(target_profile.elements) > 0:
                first_elem = target_profile.elements[0]
                # Check if it's a real target or null
                if first_elem is not None and not (
                    hasattr(first_elem, "__class__")
                    and "Null" in first_elem.__class__.__name__
                ):
                    # logger.info("DDBC planning WITH target (optimization mode)")
                    pass
                else:
                    # logger.info("DDBC planning with NULL target (initial planning)")
                    pass
        except Exception:
            pass  # Silently ignore logging errors

        for i, timestep in enumerate(self.timesteps):
            if timestep.system_description is None:
                # No system description available, add zero energy
                energy_elements.append(0.0)
                actuator_configs_per_timestep.append({})
                continue

            # Get the expected demand rate for this timestep
            expected_demand_rate = timestep.get_expected_demand_rate()

            # Get target energy for this timestep (if available)
            target_element = (
                target_profile.elements[i] if i < len(target_profile.elements) else None
            )
            min_element = (
                diff_to_min_profile.elements[i]
                if i < len(diff_to_min_profile.elements)
                else None
            )
            max_element = (
                diff_to_max_profile.elements[i]
                if i < len(diff_to_max_profile.elements)
                else None
            )

            # Handle target value (could be None, a NullElement, or a real value)
            target_energy_value = None
            if target_element is not None:
                # Check if it's a NullElement (skip it)
                if (
                    hasattr(target_element, "__class__")
                    and "Null" in target_element.__class__.__name__
                ):
                    target_energy_value = None  # Treat NullElement as no target
                elif hasattr(target_element, "value"):
                    target_energy_value = target_element.value
                else:
                    # It's a plain number
                    target_energy_value = target_element

            # Get available actuators and operation modes
            actuators = self.device_state_wrapper.get_actuators(timestep)

            if not actuators:
                # No actuators, add zero energy
                energy_elements.append(0.0)
                actuator_configs_per_timestep.append({})
                continue

            # Simple strategy: use first actuator
            actuator_id = actuators[0]
            operation_modes = (
                self.device_state_wrapper.get_normal_operation_modes_for_actuator(
                    timestep, actuator_id
                )
            )

            if not operation_modes:
                energy_elements.append(0.0)
                actuator_configs_per_timestep.append({})
                continue

            # Use the first operation mode
            operation_mode_id = operation_modes[0]
            om_wrapper = self.device_state_wrapper.get_operation_mode(
                timestep, actuator_id, operation_mode_id
            )

            if om_wrapper is None:
                energy_elements.append(0.0)
                actuator_configs_per_timestep.append({})
                continue

            # Calculate optimal factor based on context
            # For initial planning (null target): meet demand
            # For improved planning (with target): optimize towards target while respecting demand

            best_factor = 0.0

            if expected_demand_rate > 0 and om_wrapper.max_supply > 0:
                # Calculate factor needed to meet demand
                demand_factor = min(1.0, expected_demand_rate / om_wrapper.max_supply)

                # If we have a real target (not null), optimize towards it
                if target_energy_value is not None:
                    try:
                        # Handle JouleElement or plain number
                        if hasattr(target_energy_value, "value"):
                            target_energy = float(target_energy_value.value)
                        else:
                            target_energy = float(target_energy_value)

                        # Calculate what factor would give us the target energy
                        if om_wrapper.electrical_power_range:
                            max_power = om_wrapper.electrical_power_range.end_of_range
                            if max_power > 0:
                                # Target factor based on desired electrical energy
                                target_power = (
                                    target_energy / self.timestep_duration_seconds
                                )
                                target_factor = target_power / max_power
                                target_factor = max(0.0, min(1.0, target_factor))

                                # Key insight: DDBC must meet thermal demand (cannot go below demand_factor)
                                # But can use MORE electrical energy if target is higher
                                # This allows shifting from gas to electric when electricity is cheaper

                                # If target wants less energy than demand requires, meet demand (can't go lower)
                                # If target wants more energy, move towards target
                                if target_factor < demand_factor:
                                    best_factor = demand_factor  # Must meet demand
                                else:
                                    # Blend: prioritize demand but allow going higher for target
                                    # 60% demand minimum, up to 100% based on target
                                    best_factor = max(demand_factor, target_factor)
                            else:
                                best_factor = demand_factor
                        else:
                            best_factor = demand_factor
                    except (AttributeError, TypeError, ValueError):
                        # If target parsing fails, just use demand factor
                        best_factor = demand_factor
                else:
                    # No target (initial planning), just meet demand
                    best_factor = demand_factor

                # Respect congestion constraints
                test_energy = (
                    om_wrapper.get_electrical_power(best_factor)
                    * self.timestep_duration_seconds
                )

                if min_element is not None and min_element < 0:
                    # We have a minimum constraint (can't go below this)
                    min_energy = -min_element  # Convert diff to absolute
                    if test_energy < min_energy:
                        # Need to increase factor
                        if om_wrapper.electrical_power_range:
                            max_power = om_wrapper.electrical_power_range.end_of_range
                            if max_power > 0:
                                best_factor = min(
                                    1.0,
                                    (min_energy / self.timestep_duration_seconds)
                                    / max_power,
                                )

                if max_element is not None and max_element < 0:
                    # We have a maximum constraint (can't go above this)
                    max_energy = -max_element  # Convert diff to absolute
                    if test_energy > max_energy:
                        # Need to decrease factor
                        if om_wrapper.electrical_power_range:
                            max_power = om_wrapper.electrical_power_range.end_of_range
                            if max_power > 0:
                                best_factor = min(
                                    1.0,
                                    (max_energy / self.timestep_duration_seconds)
                                    / max_power,
                                )

            # Calculate final energy consumption
            electrical_power = om_wrapper.get_electrical_power(best_factor)
            timestep_energy = electrical_power * self.timestep_duration_seconds

            energy_elements.append(timestep_energy)

            # Store actuator configuration
            actuator_config = S2DdbcActuatorConfiguration(
                operation_mode_id=operation_mode_id,
                factor=best_factor,
            )
            actuator_configs_per_timestep.append({actuator_id: actuator_config})

        # Create energy profile
        energy_profile = JouleProfile(
            metadata=self.profile_metadata,
            elements=energy_elements,  # type: ignore[arg-type]
        )

        # Create and return plan
        return S2DdbcPlan(
            idle=all(e == 0.0 for e in energy_elements),
            energy=energy_profile,
            operation_mode_id=actuator_configs_per_timestep,
        )
