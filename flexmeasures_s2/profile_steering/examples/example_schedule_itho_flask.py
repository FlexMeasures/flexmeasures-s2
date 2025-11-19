"""
Local test script using S2FlaskScheduler for ITHO DHW Heat Pump device.

This script tests the S2FlaskScheduler directly without needing a WebSocket connection.
It mimics the behavior of s2_ws_sync.py by creating FRBCDeviceData and calling the scheduler.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import logging
import time
import pandas as pd
import os
import uuid
from s2python.frbc import FRBCInstruction
from s2python.frbc.frbc_actuator_description import FRBCActuatorDescription
from s2python.frbc.frbc_fill_level_target_profile_element import (
    FRBCFillLevelTargetProfileElement,
)
from s2python.frbc.frbc_leakage_behaviour_element import FRBCLeakageBehaviourElement
from s2python.frbc.frbc_operation_mode import FRBCOperationMode
from s2python.frbc.frbc_usage_forecast_element import FRBCUsageForecastElement
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state import (
    S2FrbcDeviceState,
)
from s2python.frbc import FRBCSystemDescription
from s2python.frbc import FRBCUsageForecast
from s2python.frbc import FRBCFillLevelTargetProfile
from s2python.frbc import FRBCLeakageBehaviour
from s2python.frbc import FRBCOperationModeElement
from s2python.frbc import FRBCActuatorStatus, FRBCStorageStatus, FRBCStorageDescription
from s2python.common import PowerRange
from s2python.common import NumberRange
from s2python.common import CommodityQuantity
from s2python.common import Transition
from s2python.common import Timer
from s2python.common import PowerValue
from s2python.common import Commodity
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from flexmeasures_s2.scheduler.scheduler_flask import S2FlaskScheduler

# Import Flask app creation
from flexmeasures.app import create as create_flexmeasures_app  # noqa: E402

# Configuration parameters
PLANNING_RESOLUTION = pd.Timedelta("PT5M")  # 5 minutes
PLANNING_WINDOW = pd.Timedelta("PT24H")  # 24 hours
T = (
    PLANNING_WINDOW // PLANNING_RESOLUTION
)  # number of time steps (288 for 24h with 5min resolution)
TIMESTEP_DURATION = PLANNING_RESOLUTION / pd.Timedelta(
    "PT1S"
)  # duration in seconds (300 seconds)
B = 200  # number of buckets for stratification
S = 30  # number of stratification layers


def create_itho_device_state(
    device_id: str,
    start_time: datetime,
    include_fill_level_target: bool = True,
    include_usage_forecast: bool = True,
) -> S2FrbcDeviceState:
    """Create an ITHO DHW Heat Pump device state for testing.

    Args:
        device_id: Unique identifier for the device
        start_time: Start time for the device planning
        include_fill_level_target: Whether to include fill level target profile
        include_usage_forecast: Whether to include usage forecast

    Returns:
        S2FrbcDeviceState: Configured ITHO DHW device state
    """
    # Create operation modes (matching example_schedule_itho.py)
    dhw_off_mode_id = str(uuid.uuid4())
    dhw_on_mode_id = str(uuid.uuid4())

    # DHW_OFF operation mode
    dhw_off_element = FRBCOperationModeElement(
        fill_level_range=NumberRange(start_of_range=0.0, end_of_range=100.0),
        fill_rate=NumberRange(start_of_range=0.0, end_of_range=0.0),
        power_ranges=[
            PowerRange(
                start_of_range=0.0,
                end_of_range=0.0,
                commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1,
            )
        ],
        running_costs=NumberRange(start_of_range=0.0, end_of_range=0.0),
    )
    off_mode = FRBCOperationMode(
        id=dhw_off_mode_id,
        diagnostic_label="DHW_OFF",
        elements=[dhw_off_element],
        abnormal_condition_only=False,
    )

    # DHW_ON operation mode
    dhw_on_element = FRBCOperationModeElement(
        fill_level_range=NumberRange(start_of_range=10.0, end_of_range=61.5),
        fill_rate=NumberRange(
            start_of_range=0.002031807896078361, end_of_range=0.002031807896078361
        ),
        power_ranges=[
            PowerRange(
                start_of_range=1100.0,
                end_of_range=1100.0,
                commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1,
            )
        ],
    )
    dhw_mode = FRBCOperationMode(
        id=dhw_on_mode_id,
        diagnostic_label="DHW_ON",
        elements=[dhw_on_element],
        abnormal_condition_only=False,
    )

    # Create timers
    min_on_timer_id = str(uuid.uuid4())
    min_off_timer_id = str(uuid.uuid4())

    min_on_timer = Timer(
        id=min_on_timer_id,
        diagnostic_label="DHW Minimum On Time",
        duration=1800000,  # 30 minutes in milliseconds
    )

    min_off_timer = Timer(
        id=min_off_timer_id,
        diagnostic_label="DHW Minimum Off Time",
        duration=600000,  # 10 minutes in milliseconds
    )

    # Create transitions
    off_to_on_transition_id = str(uuid.uuid4())
    off_to_on_transition = Transition(
        id=off_to_on_transition_id,
        **{"from": dhw_off_mode_id},
        to=dhw_on_mode_id,
        start_timers=[min_on_timer_id],
        blocking_timers=[min_off_timer_id],
        transition_duration=300000,  # 5 minutes in milliseconds
        abnormal_condition_only=False,
    )

    on_to_off_transition_id = str(uuid.uuid4())
    on_to_off_transition = Transition(
        id=on_to_off_transition_id,
        **{"from": dhw_on_mode_id},
        to=dhw_off_mode_id,
        start_timers=[min_off_timer_id],
        blocking_timers=[min_on_timer_id],
        transition_duration=180000,  # 3 minutes in milliseconds
        abnormal_condition_only=False,
    )

    # Create actuator
    actuator_id = str(uuid.uuid4())
    actuator = FRBCActuatorDescription(
        id=actuator_id,
        diagnostic_label="Heat Pump (DHW)",
        supported_commodities=[Commodity.ELECTRICITY],
        operation_modes=[off_mode, dhw_mode],
        transitions=[off_to_on_transition, on_to_off_transition],
        timers=[min_on_timer, min_off_timer],
    )

    # Create storage description
    storage_description = FRBCStorageDescription(
        diagnostic_label="DHW Buffer",
        fill_level_label="Temperature in degrees Celcius",
        provides_leakage_behaviour=True,
        provides_fill_level_target_profile=True,
        provides_usage_forecast=True,
        fill_level_range=NumberRange(start_of_range=10.0, end_of_range=61.5),
    )

    # Create system description
    system_description = FRBCSystemDescription(
        message_id=str(uuid.uuid4()),
        valid_from=start_time,
        actuators=[actuator],
        storage=storage_description,
    )

    # Create actuator status (starting in OFF mode)
    actuator_status = FRBCActuatorStatus(
        message_id=str(uuid.uuid4()),
        actuator_id=actuator_id,
        active_operation_mode_id=dhw_off_mode_id,
        operation_mode_factor=0.0,
    )

    # Create storage status (current temperature from itho.yaml)
    present_fill_level = 16.182  # Current fill level from device
    storage_status = FRBCStorageStatus(
        message_id=str(uuid.uuid4()),
        present_fill_level=present_fill_level,
    )

    # Create leakage behaviour (from itho.yaml)
    leakage_behaviour = FRBCLeakageBehaviour(
        message_id=str(uuid.uuid4()),
        valid_from=start_time,
        elements=[
            FRBCLeakageBehaviourElement(
                fill_level_range=NumberRange(start_of_range=10.0, end_of_range=61.5),
                leakage_rate=0.00004464134898917508,
            )
        ],
    )

    # Create simulated usage forecast (only if requested)
    usage_forecasts = []
    if include_usage_forecast:
        # Usage represents hot water being drawn, which reduces fill level (temperature)
        # Positive usage_rate_expected means fill level decreases per second
        # Match the pattern from fill level target profile (10 elements with same durations)
        # Higher usage during peak periods to force heating

        usage_elements = []

        # Usage rates (fill level decrease per second)
        # Higher usage during peak periods to force heating
        base_usage_rate = 0.00001  # Low base usage (0.00001 °C/second = 0.036 °C/hour)
        peak_usage_rate = (
            0.0001  # High usage during peaks (0.0001 °C/second = 0.36 °C/hour)
        )

        # Match the fill level target profile pattern exactly
        # Use same durations and pattern: maintenance periods have low usage, peak periods have high usage
        usage_forecast_elements = [
            (23400000, base_usage_rate),  # Maintenance period 1
            (5400000, peak_usage_rate),  # Peak period 1
            (32400000, base_usage_rate),  # Maintenance period 2
            (10800000, peak_usage_rate),  # Peak period 2
            (14400000, base_usage_rate),  # Maintenance period 3
            (23400000, base_usage_rate),  # Maintenance period 4
            (5400000, peak_usage_rate),  # Peak period 3
            (32400000, base_usage_rate),  # Maintenance period 5
            (10800000, peak_usage_rate),  # Peak period 4
            (14400000, base_usage_rate),  # Maintenance period 6
        ]

        for duration_ms, usage_rate in usage_forecast_elements:
            usage_elements.append(
                FRBCUsageForecastElement(
                    duration=duration_ms,
                    usage_rate_expected=usage_rate,
                )
            )

        usage_forecast = FRBCUsageForecast(
            message_id=str(uuid.uuid4()),
            start_time=start_time,
            elements=usage_elements,
        )
        usage_forecasts = [usage_forecast]

    # Create fill level target profile (only if requested)
    fill_level_target_profiles = []
    if include_fill_level_target:
        # FRBC.FillLevelTargetProfile - exact pattern from itho.yaml
        # Pattern: 10 elements with alternating maintenance and peak periods
        # Maintenance: [10.0, 55.0]°C, Peak: [51.5, 55.0]°C

        fill_level_min = (
            10.0  # From fill level target profile in itho.yaml (maintenance periods)
        )
        fill_level_max = (
            55.0  # From fill level target profile in itho.yaml (maintenance periods)
        )
        peak_target_min = 51.5  # Peak period minimum target
        peak_target_max = 55.0  # Peak period maximum target

        # Create fill level target profile elements
        # Original pattern from itho.yaml (durations in milliseconds):
        # Element 1: 23400000 ms (6.5 hours) - maintenance [10.0, 55.0]
        # Element 2: 5400000 ms (1.5 hours) - peak [51.5, 55.0]
        # Element 3: 32400000 ms (9 hours) - maintenance [10.0, 55.0]
        # Element 4: 10800000 ms (3 hours) - peak [51.5, 55.0]
        # Element 5: 14400000 ms (4 hours) - maintenance [10.0, 55.0]
        # Element 6: 23400000 ms (6.5 hours) - maintenance [10.0, 55.0]
        # Element 7: 5400000 ms (1.5 hours) - peak [51.5, 55.0]
        # Element 8: 32400000 ms (9 hours) - maintenance [10.0, 55.0]
        # Element 9: 10800000 ms (3 hours) - peak [51.5, 55.0]
        # Element 10: 14400000 ms (4 hours) - maintenance [10.0, 55.0]

        # Define the pattern exactly as in itho.yaml
        fill_level_target_elements = [
            (23400000, fill_level_min, fill_level_max),  # Maintenance
            (5400000, peak_target_min, peak_target_max),  # Peak
            (32400000, fill_level_min, fill_level_max),  # Maintenance
            (10800000, peak_target_min, peak_target_max),  # Peak
            (14400000, fill_level_min, fill_level_max),  # Maintenance
            (23400000, fill_level_min, fill_level_max),  # Maintenance
            (5400000, peak_target_min, peak_target_max),  # Peak
            (32400000, fill_level_min, fill_level_max),  # Maintenance
            (10800000, peak_target_min, peak_target_max),  # Peak
            (14400000, fill_level_min, fill_level_max),  # Maintenance
        ]

        elements = []
        for duration_ms, range_min, range_max in fill_level_target_elements:
            elements.append(
                FRBCFillLevelTargetProfileElement(
                    duration=duration_ms,
                    fill_level_range=NumberRange(
                        start_of_range=range_min, end_of_range=range_max
                    ),
                )
            )

        fill_level_target = FRBCFillLevelTargetProfile(
            message_id=str(uuid.uuid4()),
            start_time=start_time,
            elements=elements,
        )
        fill_level_target_profiles = [fill_level_target]

    # Create device state
    device_state = S2FrbcDeviceState(
        device_id=device_id,
        device_name=f"ITHO DHW {device_id}",
        connection_id=f"{device_id}_connection",
        priority_class=1,
        timestamp=start_time,
        energy_in_current_timestep=PowerValue(
            value=0, commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1
        ),
        is_online=True,
        power_forecast=None,
        system_descriptions=[system_description],
        leakage_behaviours=[leakage_behaviour],
        usage_forecasts=usage_forecasts,
        fill_level_target_profiles=fill_level_target_profiles,
        computational_parameters=S2FrbcDeviceState.ComputationalParameters(B, S),
        actuator_statuses=[actuator_status],
        storage_status=storage_status,
    )

    return device_state


def convert_fill_level_target_to_timeseries(
    target_profile: FRBCFillLevelTargetProfile,
    start_time: datetime,
    timestep_duration: timedelta,
    nr_of_timesteps: int,
):
    """Convert fill level target profile to time series arrays.

    Args:
        target_profile: FRBC fill level target profile
        start_time: Start time of the planning window
        timestep_duration: Duration of each timestep
        nr_of_timesteps: Number of timesteps

    Returns:
        Tuple of (min_values, max_values) arrays
    """
    min_values = []
    max_values = []

    element_idx = 0

    for i in range(nr_of_timesteps):
        timestep_ms = i * timestep_duration.total_seconds() * 1000

        # Find which element we're in
        cumulative_duration = 0
        for idx, element in enumerate(target_profile.elements):
            if idx >= element_idx:
                # Extract duration value - handle both int and Duration object
                duration_value = element.duration
                if hasattr(duration_value, "root"):
                    duration_value = duration_value.root
                elif not isinstance(duration_value, (int, float)):
                    duration_value = int(duration_value)

                cumulative_duration += duration_value
                if timestep_ms < cumulative_duration:
                    min_values.append(element.fill_level_range.start_of_range)
                    max_values.append(element.fill_level_range.end_of_range)
                    break
        else:
            # Use last element if we're past all durations
            last_element = target_profile.elements[-1]
            min_values.append(last_element.fill_level_range.start_of_range)
            max_values.append(last_element.fill_level_range.end_of_range)

    return min_values, max_values


def get_cost_target_profile_elements(number_of_elements: int):
    """Create cost target profile elements with time-of-use pricing pattern.

    Args:
        number_of_elements: Number of 5-minute intervals

    Returns:
        List of tariff values in EUR/kWh
    """
    cost_elements = []

    for timestep in range(number_of_elements):
        # Calculate hour of day based on timestep (5-minute intervals)
        hour = (timestep * 5) // 60

        if 0 <= hour < 6:  # Night hours (00:00-06:00) - lowest cost
            tariff = 0.10  # 10 cents per kWh
        elif 6 <= hour < 9:  # Morning ramp-up (06:00-09:00)
            tariff = 0.15  # 15 cents per kWh
        elif 9 <= hour < 17:  # Peak hours (09:00-17:00) - highest cost
            tariff = 0.30  # 30 cents per kWh
        elif 17 <= hour < 21:  # Evening peak (17:00-21:00)
            tariff = 0.25  # 25 cents per kWh
        else:  # Late evening (21:00-24:00)
            tariff = 0.15  # 15 cents per kWh

        cost_elements.append(tariff)

    return cost_elements


def calculate_cost_from_energy_and_tariffs(energy_elements, tariff_elements):
    """Calculate cost from energy usage and tariff rates.

    Args:
        energy_elements: List of energy values in Joules
        tariff_elements: List of tariff values in EUR/kWh

    Returns:
        List of cost values in EUR
    """
    cost_elements = []
    for energy, tariff in zip(energy_elements, tariff_elements):
        if energy is not None and tariff is not None:
            # Convert Joules to kWh and multiply by tariff
            kwh = energy / 3_600_000  # 1 kWh = 3,600,000 Joules
            cost = kwh * tariff
            cost_elements.append(cost)
        else:
            cost_elements.append(0.0)
    return cost_elements


def plot_planning_results(
    timestep_duration: timedelta,
    nr_of_timesteps: int,
    predicted_energy_elements: list,
    fill_level_profile: Optional[list] = None,
    fill_level_target_min: Optional[list] = None,
    fill_level_target_max: Optional[list] = None,
    start_time: Optional[datetime] = None,
    suffix: str = "",
    tariff_elements: Optional[list] = None,
):
    """Plot ITHO DHW planning results with power, temperature, and tariff background.

    Creates a single comprehensive plot with:
    - Power consumption on left y-axis
    - Temperature (actual and target range) on right y-axis
    - Background colors showing tariff zones

    Args:
        timestep_duration: Duration of each timestep
        nr_of_timesteps: Number of timesteps
        predicted_energy_elements: List of predicted power values in Watts
        fill_level_profile: Optional list of fill level values (temperature)
        fill_level_target_min: Optional list of minimum target fill levels
        fill_level_target_max: Optional list of maximum target fill levels
        start_time: Start time for x-axis labels
        suffix: Suffix for output filename
        tariff_elements: Optional list of tariff values
    """
    os.makedirs("plots", exist_ok=True)

    # Create time axis
    if start_time:
        timestep_start_times = [
            start_time + timedelta(seconds=i * timestep_duration.total_seconds())
            for i in range(nr_of_timesteps)
        ]
    else:
        timestep_start_times = [
            datetime(1970, 1, 1, tzinfo=timezone.utc)
            + timedelta(seconds=i * timestep_duration.total_seconds())
            for i in range(nr_of_timesteps)
        ]

    # Create figure with single plot
    fig, ax1 = plt.subplots(1, 1, figsize=(16, 8))

    # Add tariff background colors if available
    if tariff_elements is not None:
        # Define tariff color mapping
        tariff_colors = {
            0.10: "#e8f5e9",  # Light green for cheap
            0.15: "#fff9c4",  # Light yellow for moderate
            0.25: "#ffe0b2",  # Light orange for high
            0.30: "#ffcdd2",  # Light red for peak
        }

        # Create background regions for tariff zones
        current_tariff = tariff_elements[0] if tariff_elements else None
        region_start = timestep_start_times[0]

        for i in range(1, len(tariff_elements)):
            if tariff_elements[i] != current_tariff or i == len(tariff_elements) - 1:
                # End of current tariff zone
                region_end = timestep_start_times[i]
                color = (
                    tariff_colors.get(current_tariff, "#f5f5f5")
                    if current_tariff is not None
                    else "#f5f5f5"
                )
                ax1.axvspan(region_start, region_end, alpha=0.3, color=color, zorder=0)

                # Start new zone
                current_tariff = tariff_elements[i]
                region_start = timestep_start_times[i]

        # Add last region
        color = (
            tariff_colors.get(current_tariff, "#f5f5f5")
            if current_tariff is not None
            else "#f5f5f5"
        )
        ax1.axvspan(
            region_start, timestep_start_times[-1], alpha=0.3, color=color, zorder=0
        )

    # Plot power consumption on left y-axis
    color_power = "tab:blue"
    ax1.set_xlabel("Time (Hour of Day)", fontsize=13, fontweight="bold")
    ax1.set_ylabel(
        "Power Consumption (W)", fontsize=13, fontweight="bold", color=color_power
    )
    line1 = ax1.plot(
        timestep_start_times,
        predicted_energy_elements,
        label="Power Consumption",
        color=color_power,
        linewidth=2.5,
        zorder=3,
    )
    ax1.tick_params(axis="y", labelcolor=color_power, labelsize=11)
    ax1.grid(True, alpha=0.3, linestyle="--", zorder=1)

    # Create second y-axis for temperature
    ax2 = ax1.twinx()
    color_temp = "tab:red"
    ax2.set_ylabel("Temperature (°C)", fontsize=13, fontweight="bold", color=color_temp)

    lines = line1.copy()

    # Plot temperature target range if available
    if fill_level_target_min and fill_level_target_max:
        fill = ax2.fill_between(
            timestep_start_times,
            fill_level_target_min,
            fill_level_target_max,
            alpha=0.25,
            color="lightgreen",
            label="Target Temperature Range",
            zorder=2,
        )
        lines.append(fill)

    # Plot actual temperature if available
    if fill_level_profile:
        line2 = ax2.plot(
            timestep_start_times,
            fill_level_profile,
            label="Actual Temperature",
            color=color_temp,
            linewidth=2.5,
            linestyle="-",
            marker="o",
            markersize=3,
            markevery=12,  # Mark every hour
            zorder=4,
        )
        lines.extend(line2)

    ax2.tick_params(axis="y", labelcolor=color_temp, labelsize=11)

    # Set title
    title = "ITHO DHW Heat Pump - Power & Temperature Profile"
    if tariff_elements:
        title += "\n(Background colors indicate electricity tariff levels)"
    ax1.set_title(title, fontsize=15, fontweight="bold", pad=20)

    # Create legend
    labels = [line.get_label() for line in lines]
    ax1.legend(lines, labels, loc="upper left", fontsize=11, framealpha=0.95)

    # Add tariff legend if available
    if tariff_elements is not None:
        from matplotlib.patches import Patch

        tariff_legend_elements = [
            Patch(facecolor="#e8f5e9", alpha=0.3, label="Low Tariff (0.10 €/kWh)"),
            Patch(facecolor="#fff9c4", alpha=0.3, label="Medium Tariff (0.15 €/kWh)"),
            Patch(facecolor="#ffe0b2", alpha=0.3, label="High Tariff (0.25 €/kWh)"),
            Patch(facecolor="#ffcdd2", alpha=0.3, label="Peak Tariff (0.30 €/kWh)"),
        ]
        ax2.legend(
            handles=tariff_legend_elements,
            loc="upper right",
            fontsize=10,
            framealpha=0.95,
            title="Electricity Tariffs",
        )

    # Format x-axis with hour labels
    if start_time:
        ax1.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax1.xaxis.set_minor_locator(mdates.MinuteLocator(interval=30))
    else:
        ax1.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    # Rotate x-axis labels for better readability
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right")

    # Adjust layout
    fig.tight_layout()

    # Save figure
    filename = f"plots/itho_schedule{suffix}_D=1_B={B}_S={S}_T={T}.png"
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    print(f"Plot saved to: {filename}")
    plt.close()


def save_instructions_to_file(
    device_plans: list,
    suffix: str,
    start_time: datetime,
    device_state: S2FrbcDeviceState,
):
    """Save instruction details to a text file.

    Args:
        device_plans: List of device plan objects with instruction profiles
        suffix: Suffix for output filename
        start_time: Start time of the planning window
        device_state: Device state for reference
    """
    os.makedirs("instructions", exist_ok=True)

    filename = f"instructions/itho_instructions{suffix}_D=1_B={B}_S={S}_T={T}.txt"

    with open(filename, "w") as f:
        f.write("=" * 80 + "\n")
        f.write(f"ITHO DHW Heat Pump Instructions{suffix.replace('_', ' ').title()}\n")
        f.write("=" * 80 + "\n")
        f.write(f"Planning start time: {start_time}\n")
        f.write(f"Planning window: {PLANNING_WINDOW}\n")
        f.write(f"Resolution: {PLANNING_RESOLUTION}\n")
        f.write(f"Total timesteps: {T}\n")
        f.write("=" * 80 + "\n\n")

        for device_plan in device_plans:
            if device_plan is None:
                continue

            device_id = device_plan.device_id
            instructions = device_plan.instruction_profile.elements

            f.write(f"Device: {device_id}\n")
            f.write(f"Number of instructions: {len(instructions)}\n")
            f.write("-" * 80 + "\n\n")

            # Write timeline summary
            f.write("Instruction Timeline:\n")
            f.write("-" * 80 + "\n")

            mode_changes = 0
            previous_mode = None
            current_run_start = None
            current_run_mode = None
            current_run_count = 0

            for idx, instruction in enumerate(instructions):
                mode_label = "UNKNOWN"
                if hasattr(instruction, "operation_mode"):
                    mode_id = str(instruction.operation_mode)
                    # Try to map to diagnostic label
                    for sys_desc in device_state.system_descriptions:
                        for actuator in sys_desc.actuators:
                            for op_mode in actuator.operation_modes:
                                if str(op_mode.id) == mode_id:
                                    mode_label = (
                                        op_mode.diagnostic_label.upper().replace(
                                            " ", "_"
                                        )
                                    )
                                    break

                    current_mode = mode_label

                    if previous_mode is None:
                        # First instruction
                        current_run_start = idx
                        current_run_mode = current_mode
                        current_run_count = 1
                    elif current_mode != previous_mode:
                        # Mode changed - write previous run
                        mode_changes += 1
                        duration_minutes = current_run_count * TIMESTEP_DURATION / 60
                        run_start_time = start_time + timedelta(
                            seconds=current_run_start * TIMESTEP_DURATION
                        )
                        f.write(f"  Mode: {current_run_mode}\n")
                        f.write(
                            f"  Start: {run_start_time} (timestep {current_run_start})\n"
                        )
                        f.write(
                            f"  Duration: {current_run_count} timesteps ({duration_minutes} minutes)\n"
                        )
                        if hasattr(
                            instructions[current_run_start], "operation_mode_factor"
                        ):
                            f.write(
                                f"  Operation mode factor: {instructions[current_run_start].operation_mode_factor}\n"
                            )
                        f.write("-" * 40 + "\n")

                        # Start new run
                        current_run_start = idx
                        current_run_mode = current_mode
                        current_run_count = 1
                    else:
                        # Same mode continues
                        current_run_count += 1

                    previous_mode = current_mode

            # Write last run
            if current_run_mode:
                duration_minutes = current_run_count * TIMESTEP_DURATION / 60
                run_start_time = start_time + timedelta(
                    seconds=current_run_start * TIMESTEP_DURATION
                )
                f.write(f"  Mode: {current_run_mode}\n")
                f.write(f"  Start: {run_start_time} (timestep {current_run_start})\n")
                f.write(
                    f"  Duration: {current_run_count} timesteps ({duration_minutes} minutes)\n"
                )
                f.write("-" * 40 + "\n")

            f.write(f"\nTotal operation mode changes: {mode_changes}\n")
            f.write("=" * 80 + "\n\n")

            # Write detailed list
            f.write("Detailed Instruction List:\n")
            f.write("=" * 80 + "\n\n")

            for idx, instruction in enumerate(
                instructions[:20]
            ):  # First 20 for brevity
                instr_time = start_time + timedelta(seconds=idx * TIMESTEP_DURATION)
                f.write(f"Instruction #{idx + 1}:\n")
                f.write(f"  Timestep: {idx}\n")
                f.write(f"  Time: {instr_time}\n")
                if hasattr(instruction, "operation_mode"):
                    f.write(f"  Operation mode: {instruction.operation_mode}\n")
                if hasattr(instruction, "operation_mode_factor"):
                    f.write(f"  Factor: {instruction.operation_mode_factor}\n")
                if hasattr(instruction, "execution_time"):
                    f.write(f"  Execution time: {instruction.execution_time}\n")
                f.write("\n")

            if len(instructions) > 20:
                f.write(f"... and {len(instructions) - 20} more instructions\n")

    print(f"Instructions saved to: {filename}")


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

    # Uncomment the test you want to run:
    try:
        # Test 1: Both fill level target and usage forecast (default)
        # results = test_itho_with_flask_scheduler()

        # Test 2: Usage forecast only (no fill level target)
        results = test_itho_with_usage_forecast_only()

        # Test 3: Fill level target only (no usage forecast)
        # results = test_itho_with_fill_level_target_only()

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
