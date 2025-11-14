"""
Local test script using S2FlaskScheduler (similar to example_schedule_itho.py but using the Flask scheduler).

This script tests the S2FlaskScheduler directly without needing a WebSocket connection.
It mimics the behavior of s2_ws_sync.py by creating FRBCDeviceData and calling the scheduler.
"""

from datetime import datetime, timedelta, timezone
import logging
import time
import pandas as pd
import os
import sys
from s2python.frbc import FRBCInstruction

from flexmeasures_s2.scheduler.scheduler_flask import S2FlaskScheduler

# Add current directory to path to import from example_schedule_itho
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from example_schedule_itho import (  # noqa: E402
    create_itho_device_state,
    convert_fill_level_target_to_timeseries,
    plot_planning_results,
    save_instructions_to_file,
    get_cost_target_profile_elements,
    calculate_cost_from_energy_and_tariffs,
    PLANNING_RESOLUTION,
    T,
    TIMESTEP_DURATION,
)

# Import Flask app creation
from flexmeasures.app import create as create_flexmeasures_app  # noqa: E402

# Configuration parameters (same as example_schedule_itho.py)
# These are already imported from example_schedule_itho.py above


class MockFRBCDeviceData:
    """Mock FRBCDeviceData class to mimic the structure from s2_ws_sync.py"""

    def __init__(self):
        self.system_description = None
        self.fill_level_target_profile = None
        self.storage_status = None
        self.actuator_statuses = {}
        self.usage_forecast = None
        self.leakage_behaviour = None
        self.resource_id = None
        self.instructions = []


def create_frbc_device_data_from_device_state(
    device_state, resource_id: str
) -> MockFRBCDeviceData:
    """Convert S2FrbcDeviceState to FRBCDeviceData structure for scheduler.

    Only includes fields that are actually present (matches itho.yaml behavior).
    """
    frbc_data = MockFRBCDeviceData()
    frbc_data.resource_id = resource_id

    if device_state.system_descriptions:
        frbc_data.system_description = device_state.system_descriptions[0]

    # Only include fill_level_target_profile if it exists
    if device_state.fill_level_target_profiles:
        frbc_data.fill_level_target_profile = device_state.fill_level_target_profiles[0]

    # Only include usage_forecast if it exists (don't pass None)
    if device_state.usage_forecasts:
        frbc_data.usage_forecast = device_state.usage_forecasts[0]

    # Only include leakage_behaviour if it exists
    if device_state.leakage_behaviours:
        frbc_data.leakage_behaviour = device_state.leakage_behaviours[0]

    # storage_status is a single object, not a list
    if device_state.storage_status:
        frbc_data.storage_status = device_state.storage_status

    if device_state.actuator_statuses:
        # Convert list to dict by actuator_id
        for actuator_status in device_state.actuator_statuses:
            frbc_data.actuator_statuses[
                str(actuator_status.actuator_id)
            ] = actuator_status

    return frbc_data


def test_itho_with_flask_scheduler(
    include_fill_level_target=True,
    include_usage_forecast=True,
    suffix="_flask_scheduler",
):
    """Test S2FlaskScheduler with ITHO DHW device using variable cost targets.

    Args:
        include_fill_level_target: If True, include fill level target profile
        include_usage_forecast: If True, include usage forecast
        suffix: Suffix for output files
    """
    print("=" * 80)
    print("Test: ITHO DHW Heat Pump with S2FlaskScheduler")
    print(f"  Fill level target: {'Yes' if include_fill_level_target else 'No'}")
    print(f"  Usage forecast: {'Yes' if include_usage_forecast else 'No'}")
    print("=" * 80)

    # Create Flask app for scheduler context
    app = create_flexmeasures_app(env="development")

    with app.app_context():
        # Configure app settings for scheduler
        app.config.setdefault("FLEXMEASURES_S2_TARGET_MODE", "costs")
        app.config.setdefault("FLEXMEASURES_S2_PRICE_SENSOR", 2)

        # Start time is 15 minutes from now, aligned to 5-minute intervals
        now = datetime.now(timezone.utc)
        # Round to nearest 5-minute interval
        minutes = (now.minute // 5) * 5
        start_time = now.replace(minute=minutes, second=0, microsecond=0) + timedelta(
            minutes=15
        )
        print(f"Planning start time: {start_time}")

        # Create device state (same as example_schedule_itho.py)
        device_id = "itho_dhw_device_flask_001"
        device_state = create_itho_device_state(
            device_id,
            start_time,
            include_fill_level_target=include_fill_level_target,
            include_usage_forecast=include_usage_forecast,
        )

        # Convert device state to FRBCDeviceData format (mimics WebSocket server)
        frbc_device_data = create_frbc_device_data_from_device_state(
            device_state, device_id
        )

        # Create S2FlaskScheduler instance (mimics s2_ws_sync.py lines 291-310)
        scheduler = S2FlaskScheduler.__new__(S2FlaskScheduler)

        # Set basic time parameters (mimics s2_ws_sync.py lines 1029-1040)
        # If fill level target profile exists, use its start_time for the scheduler
        # Otherwise, align to 5-minute boundary
        if include_fill_level_target and device_state.fill_level_target_profiles:
            # Use the fill level target profile's start_time
            scheduler_start_time = device_state.fill_level_target_profiles[0].start_time
            print(f"Using fill level target profile start_time: {scheduler_start_time}")
        else:
            # Align to 5-minute boundary
            future_time = start_time
            minutes_offset = future_time.minute % 5
            scheduler_start_time = future_time.replace(
                minute=future_time.minute - minutes_offset, second=0, microsecond=0
            )
            print(f"Using aligned start_time: {scheduler_start_time}")

        scheduler.sensor = None
        scheduler.asset = None
        scheduler.start = scheduler_start_time
        scheduler.end = scheduler_start_time + timedelta(hours=24)
        scheduler.resolution = PLANNING_RESOLUTION
        scheduler.belief_time = scheduler_start_time
        scheduler.round_to_decimals = 6
        scheduler.flex_model = {}
        scheduler.flex_context = {}
        scheduler.fallback_scheduler_class = None

        # Initialize scheduler attributes (from __init__)
        scheduler.planning_service = None
        scheduler.config_deserialized = False
        scheduler.frbc_device_data = None

        # Set FRBC device data (mimics s2_ws_sync.py line 1032)
        scheduler.frbc_device_data = frbc_device_data

        # Set data source if available (for saving beliefs)
        try:
            from flexmeasures.data.services.users import get_or_create_source
            from flexmeasures import User

            # Try to get a default user for data source
            # In a real scenario, this would come from the WebSocket connection
            user = User.query.first()
            if user:
                data_source = get_or_create_source(user)
                scheduler.data_source = data_source
        except Exception as e:
            app.logger.debug(f"Could not set data source: {e}")
            scheduler.data_source = None

        print(
            f"Scheduler window: {scheduler.start.strftime('%Y-%m-%d %H:%M:%S')} → {scheduler.end.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        print("Generating plan using S2FlaskScheduler...")

        # Generate plan using scheduler
        start_planning_time = time.time()
        schedule_results = scheduler.compute()
        end_planning_time = time.time()
        execution_time = end_planning_time - start_planning_time

        print(f"Plan generated in {execution_time:.2f} seconds")

        # Extract FRBC instructions and energy data
        frbc_instructions = [
            result for result in schedule_results if isinstance(result, FRBCInstruction)
        ]

        energy_data = [
            result
            for result in schedule_results
            if isinstance(result, dict) and "device" in result and "data" in result
        ]

        fill_level_data = [
            result
            for result in schedule_results
            if isinstance(result, dict) and "fill level" in result
        ]

        print(f"Generated {len(frbc_instructions)} FRBC instruction(s)")
        print(f"Generated energy data for {len(energy_data)} device(s)")
        print(f"Generated fill level data for {len(fill_level_data)} device(s)")

        # Process energy profile
        total_energy_kwh = 0.0
        if energy_data:
            energy_series = energy_data[0]["data"]
            # Convert Joules to Watts (W = J / timestep_in_seconds)
            power_profile_watts = [
                energy / TIMESTEP_DURATION if pd.notna(energy) else 0
                for energy in energy_series.values
            ]

            # Calculate total energy consumption
            total_energy_joules = sum(
                energy_series.values[~pd.isna(energy_series.values)]
            )
            total_energy_kwh = total_energy_joules / 3_600_000
            print(f"Total energy consumption: {total_energy_kwh:.2f} kWh")
        else:
            power_profile_watts = [0] * T
            print("Warning: No energy data generated")

        # Process fill level profile
        fill_level_profile = None
        if fill_level_data:
            fill_level_series = fill_level_data[0]["data"]
            fill_level_profile = fill_level_series.values.tolist()
            print(
                f"Fill level profile available with {len(fill_level_profile)} elements"
            )
        else:
            print("Warning: No fill level data generated")

        # Analyze instructions
        if frbc_instructions:
            mode_changes = 0
            previous_mode = None
            for instruction in frbc_instructions:
                if hasattr(instruction, "operation_mode"):
                    if previous_mode and instruction.operation_mode != previous_mode:
                        mode_changes += 1
                    previous_mode = instruction.operation_mode
            print(f"Number of operation mode changes: {mode_changes}")

            # Group instructions by operation mode for summary
            mode_counts = {}
            for instr in frbc_instructions:
                mode_id = str(instr.operation_mode)[:8]
                mode_counts[mode_id] = mode_counts.get(mode_id, 0) + 1
            print("Operation mode distribution:")
            for mode_id, count in mode_counts.items():
                print(f"  Mode {mode_id}...: {count} instruction(s)")

        # Create cost target profile for plotting
        cost_target_elements = get_cost_target_profile_elements(T)
        if energy_data:
            energy_values = [
                energy_series.values[i] if i < len(energy_series.values) else 0
                for i in range(T)
            ]
        else:
            energy_values = [0] * T
        cost_elements = calculate_cost_from_energy_and_tariffs(
            energy_values, cost_target_elements
        )
        total_cost = sum(cost_elements)
        print(f"Total cost: ${total_cost:.2f}")

        # Extract fill level targets from device state
        fill_level_target_min = None
        fill_level_target_max = None
        if device_state.fill_level_target_profiles:
            target_profile = device_state.fill_level_target_profiles[0]
            (
                fill_level_target_min,
                fill_level_target_max,
            ) = convert_fill_level_target_to_timeseries(
                target_profile,
                start_time,
                timedelta(seconds=TIMESTEP_DURATION),
                T,
            )
            print("Fill level targets extracted from device state")

        # Create device plans list for saving instructions
        device_plans_list = []
        if frbc_instructions:
            # Create a mock device plan structure for saving
            class MockDevicePlan:
                def __init__(self):
                    self.device_id = device_id
                    self.instruction_profile = type(
                        "obj", (object,), {"elements": frbc_instructions}
                    )()
                    self.fill_level_profile = (
                        type(
                            "obj",
                            (object,),
                            {
                                "elements": fill_level_profile
                                if fill_level_profile
                                else []
                            },
                        )()
                        if fill_level_profile
                        else None
                    )

            device_plans_list = [MockDevicePlan()]

        # Save instructions to file
        save_instructions_to_file(device_plans_list, suffix, start_time, device_state)

        # Plot the results with tariff information
        plot_planning_results(
            timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
            nr_of_timesteps=T,
            predicted_energy_elements=power_profile_watts,
            fill_level_profile=fill_level_profile,
            fill_level_target_min=fill_level_target_min,
            fill_level_target_max=fill_level_target_max,
            start_time=start_time,
            suffix=suffix,
            tariff_elements=cost_target_elements,
        )

        print("ITHO Flask scheduler test completed successfully!")

        return {
            "instructions": frbc_instructions,
            "energy_profile": power_profile_watts,
            "fill_level_profile": fill_level_profile,
            "total_energy_kwh": total_energy_kwh if energy_data else 0,
            "total_cost": total_cost,
        }


def test_itho_with_usage_forecast_only():
    """Test with usage forecast only (no fill level target)."""
    return test_itho_with_flask_scheduler(
        include_fill_level_target=False,
        include_usage_forecast=True,
        suffix="_flask_usage_only",
    )


def test_itho_with_fill_level_target_only():
    """Test with fill level target only (no usage forecast)."""
    return test_itho_with_flask_scheduler(
        include_fill_level_target=True,
        include_usage_forecast=False,
        suffix="_flask_filltarget_only",
    )


if __name__ == "__main__":
    # Configure logging to show INFO messages
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )

    print("=" * 80)
    print("ITHO DHW Heat Pump Planning with S2FlaskScheduler")
    print("=" * 80)
    print()

    # Test 1: Both fill level target and usage forecast (default)
    # test_itho_with_flask_scheduler()

    # Test 2: Usage forecast only (no fill level target)
    # test_itho_with_usage_forecast_only()

    # Test 3: Fill level target only (no usage forecast)
    test_itho_with_fill_level_target_only()

    # Uncomment the test you want to run:
    try:
        # results = test_itho_with_flask_scheduler()
        # results = test_itho_with_usage_forecast_only()
        results = test_itho_with_fill_level_target_only()
        print("\n" + "=" * 80)
        print("Test Summary:")
        print(f"  Instructions generated: {len(results['instructions'])}")
        print(f"  Total energy: {results['total_energy_kwh']:.2f} kWh")
        print(f"  Total cost: ${results['total_cost']:.2f}")
        print("=" * 80)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        raise
