from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from datetime import datetime, timedelta, timezone
import uuid
import logging
import time
import pandas as pd
import os
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
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata
from s2python.frbc import FRBCSystemDescription
from s2python.frbc import FRBCUsageForecast
from s2python.frbc import FRBCFillLevelTargetProfile
from s2python.frbc import FRBCLeakageBehaviour
from s2python.frbc import FRBCOperationModeElement
from s2python.frbc import FRBCActuatorStatus, FRBCStorageStatus, FRBCStorageDescription
from s2python.common import PowerRange, Duration
from s2python.common import NumberRange
from s2python.common import CommodityQuantity
from s2python.common import Transition
from s2python.common import Timer
from s2python.common import PowerValue
from s2python.common import Commodity

from flexmeasures_s2.scheduler.schedulers import (
    PlanningServiceImpl,
    PlanningServiceConfig,
    ClusterState,
    ClusterTarget,
)
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

# Configuration parameters
D = 1  # number of devices
B = 200  # number of buckets
S = 30  # number of stratification layers
PLANNING_WINDOW = pd.Timedelta("PT24H")
PLANNING_RESOLUTION = pd.Timedelta("PT5M")

T = PLANNING_WINDOW // PLANNING_RESOLUTION
TIMESTEP_DURATION = PLANNING_RESOLUTION / pd.Timedelta("PT1S")


def create_itho_device_state(
    device_id: str,
    start_time: datetime,
    planning_window_duration: timedelta | None = None,
    include_fill_level_target: bool = True,
    include_usage_forecast: bool = True,
) -> S2FrbcDeviceState:
    """
    Create device state from FRBC messages extracted from itho.yaml
    """

    # FRBC.SystemDescription from line 2 of itho.yaml
    # DHW_OFF operation mode
    dhw_off_mode_id = "959eb2c3-3d92-4ca1-8005-1d9caab972a5"
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
    dhw_off_mode = FRBCOperationMode(
        id=dhw_off_mode_id,
        diagnostic_label="DHW_OFF",
        elements=[dhw_off_element],
        abnormal_condition_only=False,
    )

    # DHW_ON operation mode
    dhw_on_mode_id = "31314092-4456-43f8-89dd-0421194bc821"
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
    dhw_on_mode = FRBCOperationMode(
        id=dhw_on_mode_id,
        diagnostic_label="DHW_ON",
        elements=[dhw_on_element],
        abnormal_condition_only=False,
    )

    # Timers
    min_on_timer_id = "702cd17f-ac40-429e-93d4-ce69c8eb8040"
    min_on_timer = Timer(
        id=min_on_timer_id,
        diagnostic_label="DHW Minimum On Time",
        duration=Duration(root=1800000),  # 30 minutes in milliseconds
    )

    min_off_timer_id = "b27ef8c9-c440-44cb-8deb-f7f85f491a92"
    min_off_timer = Timer(
        id=min_off_timer_id,
        diagnostic_label="DHW Minimum Off Time",
        duration=Duration(root=600000),  # 10 minutes in milliseconds
    )

    # Transitions
    off_to_on_transition_id = "4359a2e3-8782-4192-9775-2a29b828c45e"
    off_to_on_transition = Transition(
        id=off_to_on_transition_id,
        **{"from": dhw_off_mode_id},
        to=dhw_on_mode_id,
        start_timers=[min_on_timer_id],
        blocking_timers=[min_off_timer_id],
        transition_duration=300000,  # 5 minutes in milliseconds
        abnormal_condition_only=False,
    )

    on_to_off_transition_id = "8d3bdeae-5052-4579-a62b-a36b427df63a"
    on_to_off_transition = Transition(
        id=on_to_off_transition_id,
        **{"from": dhw_on_mode_id},
        to=dhw_off_mode_id,
        start_timers=[min_off_timer_id],
        blocking_timers=[min_on_timer_id],
        transition_duration=180000,  # 3 minutes in milliseconds
        abnormal_condition_only=False,
    )

    # Actuator
    actuator_id = "189f6a58-e78a-4c3f-bcda-6cd151342285"
    actuator_description = FRBCActuatorDescription(
        id=actuator_id,
        diagnostic_label="Heat Pump (DHW)",
        supported_commodities=[Commodity.ELECTRICITY],
        operation_modes=[dhw_off_mode, dhw_on_mode],
        transitions=[off_to_on_transition, on_to_off_transition],
        timers=[min_on_timer, min_off_timer],
    )

    # Storage description
    storage_description = FRBCStorageDescription(
        diagnostic_label="DHW Buffer",
        fill_level_label="Temperature in degrees Celcius",
        provides_leakage_behaviour=True,
        provides_fill_level_target_profile=True,
        provides_usage_forecast=True,
        fill_level_range=NumberRange(start_of_range=10.0, end_of_range=61.5),
    )

    # System description
    system_description = FRBCSystemDescription(
        message_id=str(uuid.uuid4()),
        valid_from=start_time,
        actuators=[actuator_description],
        storage=storage_description,
    )

    # FRBC.ActuatorStatus from line 123 (present_fill_level=16.182)
    actuator_status = FRBCActuatorStatus(
        message_id=str(uuid.uuid4()),
        actuator_id=actuator_id,
        active_operation_mode_id=dhw_off_mode_id,
        operation_mode_factor=0.0,
    )

    # FRBC.StorageStatus from line 94
    present_fill_level = 16.182  # Current fill level from device
    storage_status = FRBCStorageStatus(
        message_id=str(uuid.uuid4()),
        present_fill_level=present_fill_level,
    )

    # FRBC.LeakageBehaviour from line 71
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

    # Calculate total planning window in milliseconds
    if planning_window_duration is None:
        planning_window_duration = PLANNING_WINDOW

    # Create fill level target profile (only if requested)
    fill_level_target_profile = None
    if include_fill_level_target:
        # FRBC.FillLevelTargetProfile - aligned with planning window start time
        # CRITICAL: target_start_time must match planning window start_time
        target_start_time = start_time

        # Get heating parameters from SystemDescription
        # From DHW_ON operation mode: fill_rate = 0.002031807896078361 per second
        # This means: 0.002031807896078361 °C per second when heating at full power (1100W)
        fill_rate_per_second = 0.002031807896078361
        timestep_duration_seconds = TIMESTEP_DURATION
        fill_level_min = (
            10.0  # From fill level target profile in itho.yaml (maintenance periods)
        )
        fill_level_max = (
            55.0  # From fill level target profile in itho.yaml (maintenance periods)
        )
        peak_target_min = 51.5  # Peak period minimum target
        peak_target_max = 55.0  # Peak period maximum target

        # Calculate how long it takes to heat from current level to peak target
        # Time needed = (target_temp - current_temp) / fill_rate
        temp_rise_needed = peak_target_min - present_fill_level
        heating_time_seconds = temp_rise_needed / fill_rate_per_second
        heating_time_timesteps = (
            int(heating_time_seconds / timestep_duration_seconds) + 1
        )  # Add 1 for safety margin

        print("=" * 80)
        print("FILL LEVEL TARGET CONFIGURATION")
        print("=" * 80)
        print(f"Current fill level: {present_fill_level}°C")
        print(f"Peak target: [{peak_target_min}, {peak_target_max}]°C")
        print(f"Fill rate: {fill_rate_per_second} °C/second (when heating at 1100W)")
        print(f"Temperature rise needed: {temp_rise_needed:.2f}°C")
        print(
            f"Heating time required: {heating_time_seconds/3600:.2f} hours ({heating_time_timesteps} timesteps)"
        )
        print("")
        print("STRATEGY:")
        print("  - Peak periods require 51.5-55.0°C (constraint: fill_level >= 51.5°C)")
        print(f"  - Current level ({present_fill_level}°C) is BELOW peak requirement")
        print("  - Optimizer sees constraint violation at peak times if not heated")
        print("  - Optimizer MUST heat to 51.5°C before/during peak periods")
        print("  - Optimizer will minimize cost by heating during CHEAP hours")
        print(
            f"  - Target start_time aligned with planning start_time: {target_start_time}"
        )
        print("=" * 80)

        # Create fill level target profile elements
        # Use the EXACT pattern from itho.yaml line 116
        # Pattern: 10 elements with alternating maintenance and peak periods
        # Maintenance: [10.0, 55.0]°C, Peak: [51.5, 55.0]°C

        elements = []

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

        for duration_ms, range_min, range_max in fill_level_target_elements:
            elements.append(
                FRBCFillLevelTargetProfileElement(
                    duration=Duration(root=duration_ms),
                    fill_level_range=NumberRange(
                        start_of_range=range_min, end_of_range=range_max
                    ),
                )
            )

        # Verify total duration matches planning window
        # Extract duration value (Duration objects store milliseconds in .root)
        def get_duration_ms(elem):
            duration = elem.duration
            if isinstance(duration, (int, float)):
                return int(duration)  # Assume milliseconds if numeric
            elif hasattr(duration, "root"):
                return int(duration.root)  # Duration.root is in milliseconds
            else:
                return int(duration)

        total_duration_ms = sum(get_duration_ms(elem) for elem in elements)
        total_duration_seconds = total_duration_ms / 1000.0
        print(
            f"\nTarget profile duration: {total_duration_seconds/3600:.2f} hours ({total_duration_ms/1000:.0f} seconds)"
        )
        print(
            f"Planning window duration: {planning_window_duration.total_seconds()/3600:.2f} hours ({planning_window_duration.total_seconds():.0f} seconds)"
        )
        print(f"Number of elements: {len(elements)}")

        fill_level_target_profile = FRBCFillLevelTargetProfile(
            message_id=str(uuid.uuid4()),
            start_time=target_start_time,
            elements=elements,
        )
    else:
        print(
            "\nFill level target profile: NOT CREATED (include_fill_level_target=False)"
        )

    # Create simulated usage forecast (only if requested)
    usage_forecast = None
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

        # Verify total duration (extract duration value, handling both int/float and Duration objects)
        def get_duration_ms_usage(elem):
            duration = elem.duration
            if isinstance(duration, (int, float)):
                return int(duration)  # Assume milliseconds if numeric
            elif hasattr(duration, "root"):
                return int(duration.root)  # Duration.root is in milliseconds
            else:
                return int(duration)

        total_usage_duration_ms = sum(
            get_duration_ms_usage(elem) for elem in usage_elements
        )
        total_usage_duration_seconds = total_usage_duration_ms / 1000.0

        print("\nUsage forecast created:")
        print(
            f"  Total duration: {total_usage_duration_seconds/3600:.2f} hours ({total_usage_duration_ms/1000:.0f} seconds)"
        )
        print(f"  Number of elements: {len(usage_elements)}")
        print(
            f"  Base usage rate: {base_usage_rate} °C/second ({base_usage_rate*3600:.4f} °C/hour)"
        )
        print(
            f"  Peak usage rate: {peak_usage_rate} °C/second ({peak_usage_rate*3600:.4f} °C/hour)"
        )
        print("  Usage during peaks will reduce fill level, forcing optimizer to heat")

        usage_forecast = FRBCUsageForecast(
            message_id=str(uuid.uuid4()),
            start_time=start_time,
            elements=usage_elements,
        )
    else:
        print("\nUsage forecast: NOT CREATED (include_usage_forecast=False)")

    # Create device state with optional fill level target and usage forecast
    device_state = S2FrbcDeviceState(
        device_id=device_id,
        device_name="ITHO DHW Heat Pump",
        connection_id=device_id + "_connection",
        priority_class=1,
        timestamp=start_time,
        energy_in_current_timestep=PowerValue(
            value=0, commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1
        ),
        is_online=True,
        power_forecast=None,
        system_descriptions=[system_description],
        leakage_behaviours=[leakage_behaviour],
        usage_forecasts=[usage_forecast]
        if (include_usage_forecast and usage_forecast)
        else [],
        fill_level_target_profiles=[fill_level_target_profile]
        if (include_fill_level_target and fill_level_target_profile)
        else [],
        computational_parameters=S2FrbcDeviceState.ComputationalParameters(B, S),
        actuator_statuses=[actuator_status],
        storage_status=storage_status,
    )

    return device_state


def convert_fill_level_target_to_timeseries(
    fill_level_target_profile,
    start_time,
    timestep_duration,
    nr_of_timesteps,
):
    """
    Convert FRBCFillLevelTargetProfile to time series arrays for plotting.

    Returns:
        tuple: (target_min_values, target_max_values) as lists
    """
    target_min = []
    target_max = []

    if fill_level_target_profile is None or not fill_level_target_profile.elements:
        return [None] * nr_of_timesteps, [None] * nr_of_timesteps

    current_timestep = 0
    timestep_seconds = timestep_duration.total_seconds()

    for element in fill_level_target_profile.elements:
        # Duration is in milliseconds - extract the actual value
        duration_ms = (
            element.duration
            if isinstance(element.duration, (int, float))
            else getattr(element.duration, "root", element.duration)
        )
        duration_seconds = duration_ms / 1000
        num_timesteps = int(duration_seconds / timestep_seconds)

        # Get the fill level range for this element
        min_level = element.fill_level_range.start_of_range
        max_level = element.fill_level_range.end_of_range

        # Add values for all timesteps in this element's duration
        for _ in range(min(num_timesteps, nr_of_timesteps - current_timestep)):
            target_min.append(min_level)
            target_max.append(max_level)
            current_timestep += 1

        if current_timestep >= nr_of_timesteps:
            break

    # Fill remaining timesteps if needed
    while len(target_min) < nr_of_timesteps:
        target_min.append(target_min[-1] if target_min else None)
        target_max.append(target_max[-1] if target_max else None)

    return target_min[:nr_of_timesteps], target_max[:nr_of_timesteps]


def plot_planning_results(
    timestep_duration,
    nr_of_timesteps,
    predicted_energy_elements,
    fill_level_profile=None,
    fill_level_target_min=None,
    fill_level_target_max=None,
    start_time=None,
    suffix="",
    tariff_elements=None,
):
    """
    Plots the energy and optionally fill level profiles using matplotlib.

    Args:
        suffix: Optional suffix for the filename (e.g., "_cost" or "_energy")
        tariff_elements: Optional list of tariff values to display (for cost optimization)
    """
    # Generate timestep_start_times
    if start_time is None:
        start_time = datetime(1970, 1, 1, tzinfo=timezone.utc)

    timestep_start_times = [
        start_time + timedelta(seconds=i * timestep_duration.total_seconds())
        for i in range(nr_of_timesteps)
    ]

    if fill_level_profile is not None:
        # Create a figure with dual y-axes
        fig, ax1 = plt.subplots(1, 1, figsize=(14, 8))

        # If tariffs are provided, add them as background shading
        if tariff_elements is not None:
            # Normalize tariffs to 0-1 range for color intensity
            min_tariff = min(tariff_elements)
            max_tariff = max(tariff_elements)
            tariff_range = max_tariff - min_tariff

            # Color background based on tariff (red = expensive, green = cheap)
            for i in range(len(timestep_start_times) - 1):
                if tariff_range > 0:
                    intensity = (tariff_elements[i] - min_tariff) / tariff_range
                else:
                    intensity = 0
                # Red for high prices, yellow for medium, green for low
                color = (intensity, 1 - intensity * 0.5, 0)  # RGB
                ax1.axvspan(
                    timestep_start_times[i],
                    timestep_start_times[i + 1],
                    alpha=0.15,
                    color=color,
                )

            # Add a text annotation explaining the background colors
            ax1.text(
                0.02,
                0.98,
                f"Background: Red=High price (${max_tariff:.2f}/kWh), Green=Low price (${min_tariff:.2f}/kWh)",
                transform=ax1.transAxes,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
                fontsize=9,
            )

        # Energy plot on left y-axis
        ax1.plot(
            timestep_start_times,
            predicted_energy_elements,
            label="Power Consumption (W)",
            color="darkblue",
            linewidth=2.5,
            zorder=10,
        )
        ax1.set_ylabel("Power (W)", color="darkblue")
        ax1.tick_params(axis="y", labelcolor="darkblue")
        ax1.grid(True, alpha=0.3, zorder=0)

        # Fill level plot on right y-axis
        ax2 = ax1.twinx()
        ax2.plot(
            timestep_start_times,
            fill_level_profile,
            label="Actual Temperature (°C)",
            color="red",
            linewidth=2,
        )

        # Plot fill level targets if provided
        if fill_level_target_min is not None and fill_level_target_max is not None:
            # Filter out None values and convert to numeric arrays
            target_min_numeric = []
            target_max_numeric = []
            times_numeric = []

            for i, (t, min_val, max_val) in enumerate(
                zip(timestep_start_times, fill_level_target_min, fill_level_target_max)
            ):
                if min_val is not None and max_val is not None:
                    try:
                        min_float = float(min_val)
                        max_float = float(max_val)
                        target_min_numeric.append(min_float)
                        target_max_numeric.append(max_float)
                        times_numeric.append(t)
                    except (ValueError, TypeError):
                        continue

            if target_min_numeric and target_max_numeric:
                ax2.fill_between(
                    times_numeric,
                    target_min_numeric,
                    target_max_numeric,
                    alpha=0.2,
                    color="blue",
                    label="Target Range (°C)",
                )
                ax2.plot(
                    times_numeric,
                    target_min_numeric,
                    color="blue",
                    linestyle="--",
                    linewidth=1,
                    alpha=0.5,
                )
                ax2.plot(
                    times_numeric,
                    target_max_numeric,
                    color="blue",
                    linestyle="--",
                    linewidth=1,
                    alpha=0.5,
                )

        ax2.set_ylabel("Temperature (°C)", color="red")
        ax2.tick_params(axis="y", labelcolor="red")

        # Combined legend
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

        ax1.set_title("ITHO DHW Heat Pump Schedule")
    else:
        # Create a figure with a single subplot for energy only
        fig, ax1 = plt.subplots(1, 1, figsize=(14, 8))

        ax1.plot(
            timestep_start_times,
            predicted_energy_elements,
            label="Power Consumption (W)",
            color="green",
            linewidth=2,
        )
        ax1.set_ylabel("Power (W)")
        ax1.set_title("ITHO DHW Heat Pump Schedule - Power Consumption")
        ax1.legend(loc="best")
        ax1.grid(True)

    # Format the x-axis to show time with hourly ticks
    ax1.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.autofmt_xdate()

    # Adjust layout
    plt.tight_layout()

    # Save plot
    os.makedirs("plots", exist_ok=True)
    filename = f"plots/itho_schedule{suffix}_D={D}_B={B}_S={S}_T={T}.png"
    plt.savefig(filename)
    print(f"Plot saved to {filename}")

    plt.show()


def get_energy_target_profile_elements(number_of_elements: int, start_time: datetime):
    """
    Create energy target profile elements based on time of day.
    Encourage heating during off-peak hours, discourage during peak hours.
    """
    target_elements = []

    for i in range(number_of_elements):
        current_time = start_time + timedelta(seconds=i * TIMESTEP_DURATION)
        hour = current_time.hour

        # Energy targets in Joules per timestep
        # Heat pump consumes 1100W, so per 5-minute timestep: 1100W * 300s = 330,000 J
        if 0 <= hour < 6:  # Night hours (00:00-06:00) - encourage heating
            target_elements.append(330000)  # Full power
        elif 6 <= hour < 9:  # Morning (06:00-09:00) - moderate
            target_elements.append(165000)  # Half power
        elif 9 <= hour < 17:  # Peak hours (09:00-17:00) - discourage
            target_elements.append(0)  # Minimize
        elif 17 <= hour < 21:  # Evening (17:00-21:00) - moderate
            target_elements.append(165000)  # Half power
        else:  # Late evening (21:00-24:00) - encourage
            target_elements.append(330000)  # Full power

    return target_elements


def get_cost_target_profile_elements(number_of_elements: int):
    """
    Create cost target profile elements with dynamic pricing pattern.
    Similar to the EV example.
    """
    cost_elements = []
    intervals_per_hour = number_of_elements // 24

    for hour in range(24):
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

        # Add the tariff for all intervals in this hour
        cost_elements.extend([tariff] * intervals_per_hour)

    return cost_elements[:number_of_elements]


def calculate_cost_from_energy_and_tariffs(energy_elements, tariff_elements):
    """Calculate cost from energy usage and tariff rates."""
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


def save_instructions_to_file(
    device_plans_list, filename_suffix, start_time, device_state=None
):
    """
    Save instruction profiles to a text file.

    Args:
        device_plans_list: List of device plans containing instruction profiles
        filename_suffix: Suffix for the output filename
        start_time: Start time of the planning window
        device_state: Device state containing operation mode mappings (optional)
    """
    if not device_plans_list:
        print(f"No device plans to save for {filename_suffix}")
        return

    # Create operation mode ID to name mapping
    operation_mode_names = {}
    if device_state and device_state.system_descriptions:
        for system_desc in device_state.system_descriptions:
            if hasattr(system_desc, "actuators"):
                for actuator in system_desc.actuators:
                    if hasattr(actuator, "operation_modes"):
                        for mode in actuator.operation_modes:
                            operation_mode_names[mode.id] = mode.diagnostic_label

    os.makedirs("instructions", exist_ok=True)
    filename = (
        f"instructions/itho_instructions{filename_suffix}_D={D}_B={B}_S={S}_T={T}.txt"
    )

    with open(filename, "w") as f:
        f.write("=" * 80 + "\n")
        f.write(
            f"ITHO DHW Heat Pump Instructions{filename_suffix.replace('_', ' ').title()}\n"
        )
        f.write("=" * 80 + "\n")
        f.write(f"Planning start time: {start_time}\n")
        f.write(f"Planning window: {PLANNING_WINDOW}\n")
        f.write(f"Resolution: {PLANNING_RESOLUTION}\n")
        f.write(f"Total timesteps: {T}\n")
        f.write("=" * 80 + "\n\n")

        for device_plan in device_plans_list:
            if device_plan and device_plan.instruction_profile:
                f.write(f"Device: {device_plan.device_id}\n")
                f.write(
                    f"Number of instructions: {len(device_plan.instruction_profile.elements)}\n"
                )
                f.write("-" * 80 + "\n\n")

                instructions = device_plan.instruction_profile.elements

                # Group consecutive instructions with same operation mode
                if instructions:
                    current_mode = None
                    current_mode_start = None
                    current_mode_start_idx = 0
                    mode_count = 0

                    f.write("Instruction Timeline:\n")
                    f.write("-" * 80 + "\n")

                    for i, instruction in enumerate(instructions):
                        if hasattr(instruction, "operation_mode"):
                            if instruction.operation_mode != current_mode:
                                # Print previous mode summary if exists
                                if current_mode is not None:
                                    duration = i - current_mode_start_idx
                                    duration_minutes = duration * TIMESTEP_DURATION / 60
                                    mode_name = operation_mode_names.get(
                                        current_mode, current_mode
                                    )
                                    f.write(f"  Mode: {mode_name}\n")
                                    f.write(
                                        f"  Start: {current_mode_start} (timestep {current_mode_start_idx})\n"
                                    )
                                    f.write(
                                        f"  Duration: {duration} timesteps ({duration_minutes:.1f} minutes)\n"
                                    )
                                    f.write(
                                        f"  Operation mode factor: {getattr(instruction, 'operation_mode_factor', 'N/A')}\n"
                                    )
                                    f.write("-" * 40 + "\n")
                                    mode_count += 1

                                # Start new mode
                                current_mode = instruction.operation_mode
                                current_mode_start = getattr(
                                    instruction, "execution_time", f"Timestep {i}"
                                )
                                current_mode_start_idx = i

                    # Print final mode
                    if current_mode is not None:
                        duration = len(instructions) - current_mode_start_idx
                        duration_minutes = duration * TIMESTEP_DURATION / 60
                        mode_name = operation_mode_names.get(current_mode, current_mode)
                        f.write(f"  Mode: {mode_name}\n")
                        f.write(
                            f"  Start: {current_mode_start} (timestep {current_mode_start_idx})\n"
                        )
                        f.write(
                            f"  Duration: {duration} timesteps ({duration_minutes:.1f} minutes)\n"
                        )
                        f.write("-" * 40 + "\n")
                        mode_count += 1

                    f.write(f"\nTotal operation mode changes: {mode_count - 1}\n")
                    f.write("=" * 80 + "\n\n")

                    # Detailed instruction list
                    f.write("Detailed Instruction List:\n")
                    f.write("=" * 80 + "\n")
                    for i, instruction in enumerate(instructions):
                        f.write(f"\nInstruction #{i+1}:\n")
                        f.write(f"  Timestep: {i}\n")
                        f.write(
                            f"  Time: {start_time + timedelta(seconds=i * TIMESTEP_DURATION)}\n"
                        )

                        if hasattr(instruction, "id"):
                            f.write(f"  ID: {instruction.id}\n")
                        if hasattr(instruction, "actuator_id"):
                            f.write(f"  Actuator ID: {instruction.actuator_id}\n")
                        if hasattr(instruction, "operation_mode"):
                            mode_name = operation_mode_names.get(
                                instruction.operation_mode, instruction.operation_mode
                            )
                            f.write(f"  Operation Mode: {mode_name}\n")
                            if operation_mode_names.get(instruction.operation_mode):
                                f.write(
                                    f"  Operation Mode ID: {instruction.operation_mode}\n"
                                )
                        if hasattr(instruction, "operation_mode_factor"):
                            f.write(
                                f"  Operation Mode Factor: {instruction.operation_mode_factor}\n"
                            )
                        if hasattr(instruction, "execution_time"):
                            f.write(f"  Execution Time: {instruction.execution_time}\n")

                        f.write("-" * 40 + "\n")

    print(f"Instructions saved to: {filename}")


def test_itho_planning_with_energy_target():
    """Test the PlanningServiceImpl with ITHO DHW device using energy targets."""
    print("=" * 80)
    print("Test 1: ITHO DHW Heat Pump with Energy Target Profile")
    print("=" * 80)

    # Start time is 15 minutes from now, aligned to 5-minute intervals
    now = datetime.now(timezone.utc)
    # Round to nearest 5-minute interval
    minutes = (now.minute // 5) * 5
    start_time = now.replace(minute=minutes, second=0, microsecond=0) + timedelta(
        minutes=15
    )
    print(f"Planning start time: {start_time}")

    # Create profile metadata
    target_metadata = ProfileMetadata(
        profile_start=start_time,
        timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
        nr_of_timesteps=T,
    )

    # Create device state
    device_id = "itho_dhw_device_001"
    device_state = create_itho_device_state(device_id, start_time)

    # Create Dictionary of device states
    device_states_dict = {device_id: device_state}

    # Create congestion points mapping
    congestion_points_by_connection_id = {device_id: ""}

    # Create a cluster state
    cluster_state = ClusterState(
        start_time, device_states_dict, congestion_points_by_connection_id
    )

    # Create energy target profile based on time of day
    target_profile_elements = get_energy_target_profile_elements(T, start_time)
    global_target_profile = TargetProfile(
        profile_start=target_metadata.profile_start,
        timestep_duration=target_metadata.timestep_duration,
        elements=target_profile_elements,
    )

    # Create a cluster target
    cluster_target = ClusterTarget(
        start_time,
        None,
        None,
        global_target_profile=global_target_profile,
        congestion_point_targets={},
    )

    # Configuration similar to example_schedule_frbc.py
    config = PlanningServiceConfig(
        energy_improvement_criterion=10.0,
        cost_improvement_criterion=1.0,
        congestion_retry_iterations=10,
        multithreaded=False,
    )

    print("Generating plan...")

    # Create planning service implementation
    service = PlanningServiceImpl(config)

    # Generate a plan
    plan_due_by_date = start_time + timedelta(seconds=10)
    start_planning_time = time.time()

    cluster_plan = service.plan(
        state=cluster_state,
        target=cluster_target,
        planning_window=TIMESTEP_DURATION * T,
        reason="ITHO DHW Heat Pump scheduling",
        plan_due_by_date=plan_due_by_date,
        optimize_for_target=True,
        max_priority_class=1,
    )

    end_planning_time = time.time()
    execution_time = end_planning_time - start_planning_time

    print(f"Plan generated in {execution_time:.2f} seconds")

    # Assert and process results
    assert cluster_plan is not None, "Cluster plan is None"
    print("Successfully generated cluster plan")

    # Get the plan data
    device_plans = cluster_plan.get_plan_data().get_device_plans()
    energy_profile = cluster_plan.get_joule_profile()

    # Convert Joules to Watts (W = J / timestep_in_seconds)
    power_profile_watts = [
        energy / TIMESTEP_DURATION if energy is not None else 0
        for energy in energy_profile.elements
    ]

    # Get fill level profile if available
    fill_level_profile = None
    device_plans_list = [plan for plan in device_plans if plan is not None]

    if device_plans_list:
        device_plan = device_plans_list[0]
        if (
            hasattr(device_plan, "fill_level_profile")
            and device_plan.fill_level_profile
        ):
            fill_level_profile = device_plan.fill_level_profile.elements
            print(
                f"Fill level profile available with {len(fill_level_profile)} elements"
            )

        if device_plan.instruction_profile:
            instructions = device_plan.instruction_profile.elements
            print(f"Device has {len(instructions)} instructions")

            # Analyze operation mode changes
            mode_changes = 0
            previous_mode = None
            for instruction in instructions:
                if hasattr(instruction, "operation_mode"):
                    if previous_mode and instruction.operation_mode != previous_mode:
                        mode_changes += 1
                    previous_mode = instruction.operation_mode
            print(f"Number of operation mode changes: {mode_changes}")

    # Calculate total energy consumption
    total_energy_kwh = sum(energy_profile.elements) / 3_600_000
    print(f"Total energy consumption: {total_energy_kwh:.2f} kWh")

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

    # Save instructions to file
    save_instructions_to_file(device_plans_list, "_energy", start_time, device_state)

    # Plot the results
    plot_planning_results(
        timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
        nr_of_timesteps=T,
        predicted_energy_elements=power_profile_watts,
        fill_level_profile=fill_level_profile,
        fill_level_target_min=fill_level_target_min,
        fill_level_target_max=fill_level_target_max,
        start_time=start_time,
        suffix="_energy",
    )

    print("ITHO energy target test completed successfully!")

    return cluster_plan


def test_itho_planning_with_constant_cost():
    """Test the PlanningServiceImpl with ITHO DHW device using constant cost."""
    print("\n" + "=" * 80)
    print("Test 2: ITHO DHW Heat Pump with Constant Cost (1 EUR/kWh)")
    print("=" * 80)

    # Start time is 15 minutes from now, aligned to 5-minute intervals
    now = datetime.now(timezone.utc)
    # Round to nearest 5-minute interval
    minutes = (now.minute // 5) * 5
    start_time = now.replace(minute=minutes, second=0, microsecond=0) + timedelta(
        minutes=15
    )
    print(f"Planning start time: {start_time}")

    # Create profile metadata
    target_metadata = ProfileMetadata(
        profile_start=start_time,
        timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
        nr_of_timesteps=T,
    )

    # Create device state
    device_id = "itho_dhw_device_002"
    device_state = create_itho_device_state(device_id, start_time)

    # Create Dictionary of device states
    device_states_dict = {device_id: device_state}

    # Create congestion points mapping
    congestion_points_by_connection_id = {device_id: ""}

    # Create a cluster state
    cluster_state = ClusterState(
        start_time, device_states_dict, congestion_points_by_connection_id
    )

    # Create constant cost target profile (1 EUR/kWh for all timesteps)
    constant_cost_elements = [1.0] * T

    # Create a cost-based target profile
    cost_target_profile = TargetProfile.from_tariff_values(
        target_metadata, constant_cost_elements
    )

    # Create a cluster target with cost target
    cluster_target = ClusterTarget(
        start_time,
        None,
        None,
        global_target_profile=cost_target_profile,
        congestion_point_targets={},
    )

    # Configuration similar to example_schedule_frbc.py
    config = PlanningServiceConfig(
        energy_improvement_criterion=10.0,
        cost_improvement_criterion=1.0,
        congestion_retry_iterations=10,
        multithreaded=False,
    )

    print("Generating constant-cost plan...")

    # Create planning service implementation
    service = PlanningServiceImpl(config)

    # Generate a plan
    plan_due_by_date = start_time + timedelta(seconds=10)
    start_planning_time = time.time()

    cluster_plan = service.plan(
        state=cluster_state,
        target=cluster_target,
        planning_window=TIMESTEP_DURATION * T,
        reason="ITHO DHW Heat Pump constant cost optimization",
        plan_due_by_date=plan_due_by_date,
        optimize_for_target=True,
        max_priority_class=1,
    )

    end_planning_time = time.time()
    execution_time = end_planning_time - start_planning_time

    print(f"Constant-cost plan generated in {execution_time:.2f} seconds")

    # Assert and process results
    assert cluster_plan is not None, "Cluster plan is None"
    print("Successfully generated constant-cost cluster plan")

    # Get the plan data
    device_plans = cluster_plan.get_plan_data().get_device_plans()
    energy_profile = cluster_plan.get_joule_profile()

    # Convert Joules to Watts (W = J / timestep_in_seconds)
    power_profile_watts = [
        energy / TIMESTEP_DURATION if energy is not None else 0
        for energy in energy_profile.elements
    ]

    # Get fill level profile if available
    fill_level_profile = None
    device_plans_list = [plan for plan in device_plans if plan is not None]

    if device_plans_list:
        device_plan = device_plans_list[0]
        if (
            hasattr(device_plan, "fill_level_profile")
            and device_plan.fill_level_profile
        ):
            fill_level_profile = device_plan.fill_level_profile.elements
            print(
                f"Fill level profile available with {len(fill_level_profile)} elements"
            )

        if device_plan.instruction_profile:
            instructions = device_plan.instruction_profile.elements
            print(f"Device has {len(instructions)} instructions")

            # Analyze operation mode changes
            mode_changes = 0
            previous_mode = None
            for instruction in instructions:
                if hasattr(instruction, "operation_mode"):
                    if previous_mode and instruction.operation_mode != previous_mode:
                        mode_changes += 1
                    previous_mode = instruction.operation_mode
            print(f"Number of operation mode changes: {mode_changes}")

    # Calculate total energy consumption
    total_energy_kwh = sum(energy_profile.elements) / 3_600_000
    print(f"Total energy consumption: {total_energy_kwh:.2f} kWh")

    # Calculate the actual costs from the energy profile and tariffs
    cost_elements = calculate_cost_from_energy_and_tariffs(
        energy_profile.elements, constant_cost_elements
    )
    total_cost = sum(cost_elements)
    print(f"Total cost: €{total_cost:.2f}")

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

    # Save instructions to file
    save_instructions_to_file(
        device_plans_list, "_constant_cost", start_time, device_state
    )

    # Plot the results with constant tariff information
    plot_planning_results(
        timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
        nr_of_timesteps=T,
        predicted_energy_elements=power_profile_watts,
        fill_level_profile=fill_level_profile,
        fill_level_target_min=fill_level_target_min,
        fill_level_target_max=fill_level_target_max,
        start_time=start_time,
        suffix="_constant_cost",
        tariff_elements=constant_cost_elements,
    )

    print("ITHO constant cost test completed successfully!")

    return cluster_plan


def test_itho_planning_with_cost_target():
    """Test the PlanningServiceImpl with ITHO DHW device using variable cost targets."""
    print("\n" + "=" * 80)
    print("Test 3: ITHO DHW Heat Pump with Variable Cost Target Profile")
    print("=" * 80)

    # Start time is 15 minutes from now, aligned to 5-minute intervals
    now = datetime.now(timezone.utc)
    # Round to nearest 5-minute interval
    minutes = (now.minute // 5) * 5
    start_time = now.replace(minute=minutes, second=0, microsecond=0) + timedelta(
        minutes=15
    )
    print(f"Planning start time: {start_time}")

    # Create profile metadata
    target_metadata = ProfileMetadata(
        profile_start=start_time,
        timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
        nr_of_timesteps=T,
    )

    # Create device state
    device_id = "itho_dhw_device_003"
    device_state = create_itho_device_state(device_id, start_time)

    # Create Dictionary of device states
    device_states_dict = {device_id: device_state}

    # Create congestion points mapping
    congestion_points_by_connection_id = {device_id: ""}

    # Create a cluster state
    cluster_state = ClusterState(
        start_time, device_states_dict, congestion_points_by_connection_id
    )

    # Create variable cost target profile
    cost_target_elements = get_cost_target_profile_elements(T)

    # Create a cost-based target profile
    cost_target_profile = TargetProfile.from_tariff_values(
        target_metadata, cost_target_elements
    )

    # Create a cluster target with cost target
    cluster_target = ClusterTarget(
        start_time,
        None,
        None,
        global_target_profile=cost_target_profile,
        congestion_point_targets={},
    )

    # Configuration similar to example_schedule_frbc.py
    config = PlanningServiceConfig(
        energy_improvement_criterion=10.0,
        cost_improvement_criterion=1.0,
        congestion_retry_iterations=10,
        multithreaded=False,
    )

    print("Generating cost-optimized plan...")

    # Create planning service implementation
    service = PlanningServiceImpl(config)

    # Generate a plan
    plan_due_by_date = start_time + timedelta(seconds=10)
    start_planning_time = time.time()

    cluster_plan = service.plan(
        state=cluster_state,
        target=cluster_target,
        planning_window=TIMESTEP_DURATION * T,
        reason="ITHO DHW Heat Pump cost optimization",
        plan_due_by_date=plan_due_by_date,
        optimize_for_target=True,
        max_priority_class=1,
    )

    end_planning_time = time.time()
    execution_time = end_planning_time - start_planning_time

    print(f"Cost-optimized plan generated in {execution_time:.2f} seconds")

    # Assert and process results
    assert cluster_plan is not None, "Cluster plan is None"
    print("Successfully generated cost-optimized cluster plan")

    # Get the plan data
    device_plans = cluster_plan.get_plan_data().get_device_plans()
    energy_profile = cluster_plan.get_joule_profile()

    # Convert Joules to Watts (W = J / timestep_in_seconds)
    power_profile_watts = [
        energy / TIMESTEP_DURATION if energy is not None else 0
        for energy in energy_profile.elements
    ]

    # Get fill level profile if available
    fill_level_profile = None
    device_plans_list = [plan for plan in device_plans if plan is not None]

    if device_plans_list:
        device_plan = device_plans_list[0]
        if (
            hasattr(device_plan, "fill_level_profile")
            and device_plan.fill_level_profile
        ):
            fill_level_profile = device_plan.fill_level_profile.elements
            print(
                f"Fill level profile available with {len(fill_level_profile)} elements"
            )

        if device_plan.instruction_profile:
            instructions = device_plan.instruction_profile.elements
            print(f"Device has {len(instructions)} instructions")

            # Analyze operation mode changes
            mode_changes = 0
            previous_mode = None
            for instruction in instructions:
                if hasattr(instruction, "operation_mode"):
                    if previous_mode and instruction.operation_mode != previous_mode:
                        mode_changes += 1
                    previous_mode = instruction.operation_mode
            print(f"Number of operation mode changes: {mode_changes}")

    # Calculate total energy consumption
    total_energy_kwh = sum(energy_profile.elements) / 3_600_000
    print(f"Total energy consumption: {total_energy_kwh:.2f} kWh")

    # Calculate the actual costs from the energy profile and tariffs
    cost_elements = calculate_cost_from_energy_and_tariffs(
        energy_profile.elements, cost_target_elements
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

    # Save instructions to file
    save_instructions_to_file(device_plans_list, "_cost", start_time, device_state)

    # Plot the results with tariff information
    plot_planning_results(
        timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
        nr_of_timesteps=T,
        predicted_energy_elements=power_profile_watts,
        fill_level_profile=fill_level_profile,
        fill_level_target_min=fill_level_target_min,
        fill_level_target_max=fill_level_target_max,
        start_time=start_time,
        suffix="_cost",
        tariff_elements=cost_target_elements,
    )

    print("ITHO cost target test completed successfully!")

    return cluster_plan


def test_itho_planning_with_usage_forecast_only():
    """Test the PlanningServiceImpl with ITHO DHW device using ONLY usage forecast (no fill level target)."""
    print("\n" + "=" * 80)
    print(
        "Test 4: ITHO DHW Heat Pump with Usage Forecast ONLY (no FillLevelTargetProfile)"
    )
    print("=" * 80)

    # Start time is 15 minutes from now, aligned to 5-minute intervals
    now = datetime.now(timezone.utc)
    # Round to nearest 5-minute interval
    minutes = (now.minute // 5) * 5
    start_time = now.replace(minute=minutes, second=0, microsecond=0) + timedelta(
        minutes=15
    )
    print(f"Planning start time: {start_time}")

    # Create profile metadata
    target_metadata = ProfileMetadata(
        profile_start=start_time,
        timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
        nr_of_timesteps=T,
    )

    # Create device state WITH usage forecast but WITHOUT fill level target
    device_id = "itho_dhw_device_004"
    device_state = create_itho_device_state(
        device_id,
        start_time,
        include_fill_level_target=False,  # NO fill level target
        include_usage_forecast=True,  # YES usage forecast
    )

    # Create Dictionary of device states
    device_states_dict = {device_id: device_state}

    # Create congestion points mapping
    congestion_points_by_connection_id = {device_id: ""}

    # Create a cluster state
    cluster_state = ClusterState(
        start_time, device_states_dict, congestion_points_by_connection_id
    )

    # Create variable cost target profile
    cost_target_elements = get_cost_target_profile_elements(T)

    # Create a cost-based target profile
    cost_target_profile = TargetProfile.from_tariff_values(
        target_metadata, cost_target_elements
    )

    # Create a cluster target with cost target
    cluster_target = ClusterTarget(
        start_time,
        None,
        None,
        global_target_profile=cost_target_profile,
        congestion_point_targets={},
    )

    # Configuration similar to example_schedule_frbc.py
    config = PlanningServiceConfig(
        energy_improvement_criterion=10.0,
        cost_improvement_criterion=1.0,
        congestion_retry_iterations=10,
        multithreaded=False,
    )

    print("Generating plan with usage forecast only (no fill level target)...")

    # Create planning service implementation
    service = PlanningServiceImpl(config)

    # Generate a plan
    plan_due_by_date = start_time + timedelta(seconds=10)
    start_planning_time = time.time()

    cluster_plan = service.plan(
        state=cluster_state,
        target=cluster_target,
        planning_window=TIMESTEP_DURATION * T,
        reason="ITHO DHW Heat Pump with usage forecast only",
        plan_due_by_date=plan_due_by_date,
        optimize_for_target=True,
        max_priority_class=1,
    )

    end_planning_time = time.time()
    execution_time = end_planning_time - start_planning_time

    print(f"Plan generated in {execution_time:.2f} seconds")

    # Assert and process results
    assert cluster_plan is not None, "Cluster plan is None"
    print("Successfully generated cluster plan with usage forecast only")

    # Get the plan data
    device_plans = cluster_plan.get_plan_data().get_device_plans()
    energy_profile = cluster_plan.get_joule_profile()

    # Convert Joules to Watts (W = J / timestep_in_seconds)
    power_profile_watts = [
        energy / TIMESTEP_DURATION if energy is not None else 0
        for energy in energy_profile.elements
    ]

    # Get fill level profile if available
    fill_level_profile = None
    device_plans_list = [plan for plan in device_plans if plan is not None]

    if device_plans_list:
        device_plan = device_plans_list[0]
        if (
            hasattr(device_plan, "fill_level_profile")
            and device_plan.fill_level_profile
        ):
            fill_level_profile = device_plan.fill_level_profile.elements
            print(
                f"Fill level profile available with {len(fill_level_profile)} elements"
            )

        if device_plan.instruction_profile:
            instructions = device_plan.instruction_profile.elements
            print(f"Device has {len(instructions)} instructions")

            # Analyze operation mode changes
            mode_changes = 0
            previous_mode = None
            for instruction in instructions:
                if hasattr(instruction, "operation_mode"):
                    if previous_mode and instruction.operation_mode != previous_mode:
                        mode_changes += 1
                    previous_mode = instruction.operation_mode
            print(f"Number of operation mode changes: {mode_changes}")

    # Calculate total energy consumption
    total_energy_kwh = sum(energy_profile.elements) / 3_600_000
    print(f"Total energy consumption: {total_energy_kwh:.2f} kWh")

    # Calculate the actual costs from the energy profile and tariffs
    cost_elements = calculate_cost_from_energy_and_tariffs(
        energy_profile.elements, cost_target_elements
    )
    total_cost = sum(cost_elements)
    print(f"Total cost: ${total_cost:.2f}")

    # No fill level targets to extract (they were not included)
    fill_level_target_min = None
    fill_level_target_max = None
    print("No fill level targets (test uses usage forecast only)")

    # Save instructions to file
    save_instructions_to_file(
        device_plans_list, "_usage_only", start_time, device_state
    )

    # Plot the results with tariff information
    plot_planning_results(
        timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
        nr_of_timesteps=T,
        predicted_energy_elements=power_profile_watts,
        fill_level_profile=fill_level_profile,
        fill_level_target_min=fill_level_target_min,
        fill_level_target_max=fill_level_target_max,
        start_time=start_time,
        suffix="_usage_only",
        tariff_elements=cost_target_elements,
    )

    print("ITHO usage forecast only test completed successfully!")

    return cluster_plan


def test_itho_planning_with_fill_level_target_only():
    """Test the PlanningServiceImpl with ITHO DHW device using ONLY fill level target (no usage forecast)."""
    print("\n" + "=" * 80)
    print(
        "Test 5: ITHO DHW Heat Pump with FillLevelTargetProfile ONLY (no UsageForecast)"
    )
    print("=" * 80)

    # Start time is 15 minutes from now, aligned to 5-minute intervals
    now = datetime.now(timezone.utc)
    # Round to nearest 5-minute interval
    minutes = (now.minute // 5) * 5
    start_time = now.replace(minute=minutes, second=0, microsecond=0) + timedelta(
        minutes=15
    )
    print(f"Planning start time: {start_time}")

    # Create profile metadata
    target_metadata = ProfileMetadata(
        profile_start=start_time,
        timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
        nr_of_timesteps=T,
    )

    # Create device state WITH fill level target but WITHOUT usage forecast
    device_id = "itho_dhw_device_005"
    device_state = create_itho_device_state(
        device_id,
        start_time,
        include_fill_level_target=True,  # YES fill level target
        include_usage_forecast=False,  # NO usage forecast
    )

    # Create Dictionary of device states
    device_states_dict = {device_id: device_state}

    # Create congestion points mapping
    congestion_points_by_connection_id = {device_id: ""}

    # Create a cluster state
    cluster_state = ClusterState(
        start_time, device_states_dict, congestion_points_by_connection_id
    )

    # Create variable cost target profile
    cost_target_elements = get_cost_target_profile_elements(T)

    # Create a cost-based target profile
    cost_target_profile = TargetProfile.from_tariff_values(
        target_metadata, cost_target_elements
    )

    # Create a cluster target with cost target
    cluster_target = ClusterTarget(
        start_time,
        None,
        None,
        global_target_profile=cost_target_profile,
        congestion_point_targets={},
    )

    # Configuration similar to example_schedule_frbc.py
    config = PlanningServiceConfig(
        energy_improvement_criterion=10.0,
        cost_improvement_criterion=1.0,
        congestion_retry_iterations=10,
        multithreaded=False,
    )

    print("Generating plan with fill level target only (no usage forecast)...")

    # Create planning service implementation
    service = PlanningServiceImpl(config)

    # Generate a plan
    plan_due_by_date = start_time + timedelta(seconds=10)
    start_planning_time = time.time()

    cluster_plan = service.plan(
        state=cluster_state,
        target=cluster_target,
        planning_window=TIMESTEP_DURATION * T,
        reason="ITHO DHW Heat Pump with fill level target only",
        plan_due_by_date=plan_due_by_date,
        optimize_for_target=True,
        max_priority_class=1,
    )

    end_planning_time = time.time()
    execution_time = end_planning_time - start_planning_time

    print(f"Plan generated in {execution_time:.2f} seconds")

    # Assert and process results
    assert cluster_plan is not None, "Cluster plan is None"
    print("Successfully generated cluster plan with fill level target only")

    # Get the plan data
    device_plans = cluster_plan.get_plan_data().get_device_plans()
    energy_profile = cluster_plan.get_joule_profile()

    # Convert Joules to Watts (W = J / timestep_in_seconds)
    power_profile_watts = [
        energy / TIMESTEP_DURATION if energy is not None else 0
        for energy in energy_profile.elements
    ]

    # Get fill level profile if available
    fill_level_profile = None
    device_plans_list = [plan for plan in device_plans if plan is not None]

    if device_plans_list:
        device_plan = device_plans_list[0]
        if (
            hasattr(device_plan, "fill_level_profile")
            and device_plan.fill_level_profile
        ):
            fill_level_profile = device_plan.fill_level_profile.elements
            print(
                f"Fill level profile available with {len(fill_level_profile)} elements"
            )

        if device_plan.instruction_profile:
            instructions = device_plan.instruction_profile.elements
            print(f"Device has {len(instructions)} instructions")

            # Analyze operation mode changes
            mode_changes = 0
            previous_mode = None
            for instruction in instructions:
                if hasattr(instruction, "operation_mode"):
                    if previous_mode and instruction.operation_mode != previous_mode:
                        mode_changes += 1
                    previous_mode = instruction.operation_mode
            print(f"Number of operation mode changes: {mode_changes}")

    # Calculate total energy consumption
    total_energy_kwh = sum(energy_profile.elements) / 3_600_000
    print(f"Total energy consumption: {total_energy_kwh:.2f} kWh")

    # Calculate the actual costs from the energy profile and tariffs
    cost_elements = calculate_cost_from_energy_and_tariffs(
        energy_profile.elements, cost_target_elements
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
    else:
        print("No fill level targets found in device state")

    # Save instructions to file
    save_instructions_to_file(
        device_plans_list, "_filltarget_only", start_time, device_state
    )

    # Plot the results with tariff information
    plot_planning_results(
        timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
        nr_of_timesteps=T,
        predicted_energy_elements=power_profile_watts,
        fill_level_profile=fill_level_profile,
        fill_level_target_min=fill_level_target_min,
        fill_level_target_max=fill_level_target_max,
        start_time=start_time,
        suffix="_filltarget_only",
        tariff_elements=cost_target_elements,
    )

    print("ITHO fill level target only test completed successfully!")

    return cluster_plan


if __name__ == "__main__":
    # Configure logging to show DEBUG messages
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )

    # Optionally, set specific loggers to different levels
    # logging.getLogger('matplotlib').setLevel(logging.WARNING)

    print("=" * 80)
    print("ITHO DHW Heat Pump Planning Examples with DEBUG Logging")
    print("=" * 80)
    print()

    # Test 1: Energy targeting
    # test_itho_planning_with_energy_target()

    # print("\n" + "=" * 80 + "\n")

    # Test 2: Constant cost (1 EUR/kWh)
    # test_itho_planning_with_constant_cost()

    # print("\n" + "=" * 80 + "\n")

    # Test 3: Variable cost targeting (with both fill level target and usage forecast)
    # test_itho_planning_with_cost_target()

    # print("\n" + "=" * 80 + "\n")

    # Test 4: Usage forecast ONLY (no fill level target)
    # test_itho_planning_with_usage_forecast_only()

    # print("\n" + "=" * 80 + "\n")

    # Test 5: Fill level target ONLY (no usage forecast)
    test_itho_planning_with_fill_level_target_only()

    # Default: run Test 3 (variable cost with both profiles)
    # test_itho_planning_with_cost_target()
