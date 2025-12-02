"""
Example script demonstrating DDBC (Demand-Driven Based Control) planning.

This script tests the PlanningServiceImpl with DDBC devices, following the pattern from
example_schedule_itho.py and using test data from S2DdbcTests.java.

The tests create hybrid heating systems with:
- Gas boiler actuators (natural gas commodity)
- Heat pump actuators (electricity commodity)
- Average demand rate forecasts
- Various target types (energy, tariff) to test optimization

To run:
    python flexmeasures_s2/profile_steering/examples/example_schedule_ddbc.py
"""

import pytest

from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid
import time
import pandas as pd
import os
from decimal import Decimal

from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_device_state import (
    S2DdbcDeviceState,
)
from s2python.ddbc import (
    DDBCSystemDescription,
    DDBCAverageDemandRateForecast,
    DDBCAverageDemandRateForecastElement,
    DDBCActuatorDescription,
    DDBCActuatorStatus,
    DDBCOperationMode,
)
from s2python.common import NumberRange, PowerRange, CommodityQuantity, Commodity
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata

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
PLANNING_WINDOW = pd.Timedelta("PT50M")  # 50 minutes = 10 timesteps of 5 minutes
PLANNING_RESOLUTION = pd.Timedelta("PT5M")  # 5 minutes per timestep

T = PLANNING_WINDOW // PLANNING_RESOLUTION  # number of time steps
TIMESTEP_DURATION = PLANNING_RESOLUTION / pd.Timedelta("PT1S")  # duration in seconds


def create_hybrid_heating_device_state_test_by_plotting(
    device_id: str,
    start_time: datetime,
    profile_length: int = T,
) -> S2DdbcDeviceState:
    """
    Create a DDBC device state for a hybrid heating system.

    Based on S2DdbcTests.java testByPlotting() method.
    System has:
    - Gas boiler: 0-20kW (using natural gas, ~2000/3600 liters/second)
    - Heat pump: 0-2kW (using electricity)
    - Both provide 0-10kW heating supply rate
    - Average demand rate forecast of 10kW constant

    Args:
        device_id: Unique device identifier
        start_time: Start time for planning
        profile_length: Number of timesteps

    Returns:
        S2DdbcDeviceState configured for hybrid heating
    """
    # Create UUIDs for actuators and operation modes
    gas_id = str(uuid.uuid4())
    gas_work_mode_id = str(uuid.uuid4())
    hp_id = str(uuid.uuid4())
    hp_work_mode_id = str(uuid.uuid4())

    # Gas boiler actuator
    # 1 m3 gas ~= 10 kWh energy, so 20kW boiler uses ~2000/3600 liters/second
    gas_actuator = DDBCActuatorDescription(
        id=gas_id,
        diagnostic_label="gas",
        supported_commodites=[Commodity.GAS],
        operation_modes=[
            DDBCOperationMode(
                Id=gas_work_mode_id,
                id=gas_work_mode_id,
                diagnostic_label="gas_on",
                power_ranges=[
                    PowerRange(
                        start_of_range=Decimal("0"),
                        end_of_range=Decimal(str(2000 / 3600)),  # liters/second
                        commodity_quantity=CommodityQuantity.NATURAL_GAS_FLOW_RATE,
                    )
                ],
                supply_range=[
                    NumberRange(
                        start_of_range=Decimal("0"),
                        end_of_range=Decimal("10000"),  # 10kW in Watts
                    )
                ],
                abnormal_condition_only=False,
            )
        ],
        transitions=[],
        timers=[],
    )

    # Heat pump actuator
    hp_actuator = DDBCActuatorDescription(
        id=hp_id,
        diagnostic_label="hp",
        supported_commodites=[Commodity.ELECTRICITY],
        operation_modes=[
            DDBCOperationMode(
                Id=hp_work_mode_id,
                id=hp_work_mode_id,
                diagnostic_label="hp_on",
                power_ranges=[
                    PowerRange(
                        start_of_range=Decimal("0"),
                        end_of_range=Decimal("2000"),  # 2kW in Watts
                        commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1,
                    )
                ],
                supply_range=[
                    NumberRange(
                        start_of_range=Decimal("0"),
                        end_of_range=Decimal("10000"),  # 10kW in Watts
                    )
                ],
                abnormal_condition_only=False,
            )
        ],
        transitions=[],
        timers=[],
    )

    # Actuator statuses - both starting in their "on" mode at factor 1.0
    actuator_statuses = {
        gas_id: DDBCActuatorStatus(
            message_id=str(uuid.uuid4()),
            actuator_id=gas_id,
            active_operation_mode_id=gas_work_mode_id,
            operation_mode_factor=Decimal("1.0"),
        ),
        hp_id: DDBCActuatorStatus(
            message_id=str(uuid.uuid4()),
            actuator_id=hp_id,
            active_operation_mode_id=hp_work_mode_id,
            operation_mode_factor=Decimal("1.0"),
        ),
    }

    # System description
    system_description = DDBCSystemDescription(
        message_id=str(uuid.uuid4()),
        valid_from=start_time,
        actuators=[gas_actuator, hp_actuator],
        present_demand_rate=NumberRange(
            start_of_range=Decimal("10000"),
            end_of_range=Decimal("10000"),
        ),
        provides_average_demand_rate_forecast=True,
    )

    # Average demand rate forecast - constant 10kW demand
    demand_rate_elements = []
    for _ in range(profile_length):
        demand_rate_elements.append(
            DDBCAverageDemandRateForecastElement(
                duration=int(TIMESTEP_DURATION),
                demand_rate_expected=Decimal("10000"),  # 10kW constant demand
            )
        )

    demand_rate_forecast = DDBCAverageDemandRateForecast(
        message_id=str(uuid.uuid4()),
        start_time=start_time,
        elements=demand_rate_elements,
    )

    # Create device state
    device_state = S2DdbcDeviceState(
        device_id=device_id,
        device_name=f"DDBC Hybrid Heating {device_id}",
        connection_id=f"{device_id}_connection",
        priority_class=0,
        timestamp=start_time,
        energy_in_current_timestep=0.0,
        is_online=True,
        power_forecast=None,
        system_descriptions=[system_description],
        demand_forecasts=[demand_rate_forecast],
        actuator_statuses=actuator_statuses,
        gas_price_per_m3=2.0,  # €2 per m3 of gas
    )

    return device_state


def create_changing_demand_device_state(
    device_id: str,
    start_time: datetime,
    profile_length: int = T,
) -> S2DdbcDeviceState:
    """
    Create a DDBC device state with changing demand rates.

    Based on S2DdbcTests.java testChangingDemand() method.
    System has alternating demand: 0kW for even timesteps, 4kW for odd timesteps.

    Args:
        device_id: Unique device identifier
        start_time: Start time for planning
        profile_length: Number of timesteps

    Returns:
        S2DdbcDeviceState configured with changing demand
    """
    # Create UUIDs for actuators and operation modes (using fixed UUIDs from Java test)
    hp_id = "d4d0743f-2bd7-4910-9716-33a73b265d06"
    hp_work_mode_id = "55c236fc-e225-41f6-b5ca-3aacfe512359"
    gas_id = "38216739-2458-46bd-baf0-3fabab96e218"
    gas_work_mode_id = "22e63800-92e5-4ad3-a027-ede5b4c00d48"

    # Heat pump actuator
    hp_actuator = DDBCActuatorDescription(
        id=hp_id,
        diagnostic_label="heat pump",
        supported_commodites=[Commodity.ELECTRICITY],
        operation_modes=[
            DDBCOperationMode(
                Id=hp_work_mode_id,
                id=hp_work_mode_id,
                diagnostic_label="heat pump mode",
                power_ranges=[
                    PowerRange(
                        start_of_range=Decimal("0"),
                        end_of_range=Decimal("1000"),  # 1kW in Watts
                        commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1,
                    )
                ],
                supply_range=[
                    NumberRange(
                        start_of_range=Decimal("0"),
                        end_of_range=Decimal("4500"),  # 4.5kW in Watts
                    )
                ],
                abnormal_condition_only=False,
            )
        ],
        transitions=[],
        timers=[],
    )

    # Gas boiler actuator
    gas_actuator = DDBCActuatorDescription(
        id=gas_id,
        diagnostic_label="gas boiler",
        supported_commodites=[Commodity.GAS],
        operation_modes=[
            DDBCOperationMode(
                Id=gas_work_mode_id,
                id=gas_work_mode_id,
                diagnostic_label="gas boiler mode",
                power_ranges=[
                    PowerRange(
                        start_of_range=Decimal("0"),
                        end_of_range=Decimal("0.6"),  # liters/second
                        commodity_quantity=CommodityQuantity.NATURAL_GAS_FLOW_RATE,
                    )
                ],
                supply_range=[
                    NumberRange(
                        start_of_range=Decimal("0"),
                        end_of_range=Decimal("20000"),  # 20kW in Watts
                    )
                ],
                abnormal_condition_only=False,
            )
        ],
        transitions=[],
        timers=[],
    )

    # Actuator statuses - both starting off
    actuator_statuses = {
        hp_id: DDBCActuatorStatus(
            message_id=str(uuid.uuid4()),
            actuator_id=hp_id,
            active_operation_mode_id=hp_work_mode_id,
            operation_mode_factor=Decimal("0"),
        ),
        gas_id: DDBCActuatorStatus(
            message_id=str(uuid.uuid4()),
            actuator_id=gas_id,
            active_operation_mode_id=gas_work_mode_id,
            operation_mode_factor=Decimal("0"),
        ),
    }

    # System description
    system_description = DDBCSystemDescription(
        message_id=str(uuid.uuid4()),
        valid_from=start_time,
        actuators=[hp_actuator, gas_actuator],
        present_demand_rate=NumberRange(
            start_of_range=Decimal("0"),
            end_of_range=Decimal("4000"),
        ),
        provides_average_demand_rate_forecast=True,
    )

    # Average demand rate forecast - alternating: 0kW for even, 4kW for odd
    demand_rate_elements = []
    for i in range(profile_length):
        demand_rate = 0 if i % 2 == 0 else 4000
        demand_rate_elements.append(
            DDBCAverageDemandRateForecastElement(
                duration=int(TIMESTEP_DURATION),
                demand_rate_expected=Decimal(str(demand_rate)),
            )
        )

    demand_rate_forecast = DDBCAverageDemandRateForecast(
        message_id=str(uuid.uuid4()),
        start_time=start_time,
        elements=demand_rate_elements,
    )

    # Create device state
    device_state = S2DdbcDeviceState(
        device_id=device_id,
        device_name=f"DDBC Changing Demand {device_id}",
        connection_id=f"{device_id}_connection",
        priority_class=0,
        timestamp=start_time,
        energy_in_current_timestep=0.0,
        is_online=True,
        power_forecast=None,
        system_descriptions=[system_description],
        demand_forecasts=[demand_rate_forecast],
        actuator_statuses=actuator_statuses,
        gas_price_per_m3=2.0,
    )

    return device_state


def create_price_tradeoff_device_state(
    device_id: str,
    start_time: datetime,
    profile_length: int = 3,
) -> S2DdbcDeviceState:
    """
    Create a DDBC device state for testing price tradeoff.

    Based on S2DdbcTests.java testPriceTradeoffWithNaturalGas() method.
    System has:
    - Gas boiler: 0-18kW supply, 0-0.568720358 liters/second gas consumption
    - Heat pump: 0-5kW supply, 0-1.1kW electricity consumption
    - Constant demand rate of ~11.556kW

    Args:
        device_id: Unique device identifier
        start_time: Start time for planning
        profile_length: Number of timesteps (3 for this test)

    Returns:
        S2DdbcDeviceState configured for price tradeoff testing
    """
    # Create UUIDs for actuators and operation modes
    gas_id = str(uuid.uuid4())
    gas_work_mode_id = str(uuid.uuid4())
    hp_id = str(uuid.uuid4())
    hp_work_mode_id = str(uuid.uuid4())

    # Gas boiler actuator
    gas_actuator = DDBCActuatorDescription(
        id=gas_id,
        diagnostic_label="gas",
        supported_commodites=[Commodity.GAS],
        operation_modes=[
            DDBCOperationMode(
                Id=gas_work_mode_id,
                id=gas_work_mode_id,
                diagnostic_label=gas_work_mode_id,
                power_ranges=[
                    PowerRange(
                        start_of_range=Decimal("0"),
                        end_of_range=Decimal("0.568720358"),  # liters/second
                        commodity_quantity=CommodityQuantity.NATURAL_GAS_FLOW_RATE,
                    )
                ],
                supply_range=[
                    NumberRange(
                        start_of_range=Decimal("0"),
                        end_of_range=Decimal("18000"),  # 18kW in Watts
                    )
                ],
                abnormal_condition_only=False,
            )
        ],
        transitions=[],
        timers=[],
    )

    # Heat pump actuator
    hp_actuator = DDBCActuatorDescription(
        id=hp_id,
        diagnostic_label="heatpump",
        supported_commodites=[Commodity.ELECTRICITY],
        operation_modes=[
            DDBCOperationMode(
                Id=hp_work_mode_id,
                id=hp_work_mode_id,
                diagnostic_label=hp_work_mode_id,
                power_ranges=[
                    PowerRange(
                        start_of_range=Decimal("0"),
                        end_of_range=Decimal("1100"),  # 1.1kW in Watts
                        commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1,
                    )
                ],
                supply_range=[
                    NumberRange(
                        start_of_range=Decimal("0"),
                        end_of_range=Decimal("5000"),  # 5kW in Watts
                    )
                ],
                abnormal_condition_only=False,
            )
        ],
        transitions=[],
        timers=[],
    )

    # Actuator statuses - both starting off
    actuator_statuses = {
        gas_id: DDBCActuatorStatus(
            message_id=str(uuid.uuid4()),
            actuator_id=gas_id,
            active_operation_mode_id=gas_work_mode_id,
            operation_mode_factor=Decimal("0"),
        ),
        hp_id: DDBCActuatorStatus(
            message_id=str(uuid.uuid4()),
            actuator_id=hp_id,
            active_operation_mode_id=hp_work_mode_id,
            operation_mode_factor=Decimal("0"),
        ),
    }

    # System description
    demand_rate_value = Decimal("11556.54")
    system_description = DDBCSystemDescription(
        message_id=str(uuid.uuid4()),
        valid_from=start_time,
        actuators=[gas_actuator, hp_actuator],
        present_demand_rate=NumberRange(
            start_of_range=demand_rate_value,
            end_of_range=demand_rate_value,
        ),
        provides_average_demand_rate_forecast=True,
    )

    # Average demand rate forecast - constant ~11.556kW
    demand_rate_elements = []
    demand_rates = [
        Decimal("11556.54"),
        Decimal("11556.54"),
        Decimal("11556.527159385734"),
    ]
    for i in range(profile_length):
        demand_rate_elements.append(
            DDBCAverageDemandRateForecastElement(
                duration=int(TIMESTEP_DURATION),
                demand_rate_expected=demand_rates[i]
                if i < len(demand_rates)
                else demand_rates[0],
            )
        )

    demand_rate_forecast = DDBCAverageDemandRateForecast(
        message_id=str(uuid.uuid4()),
        start_time=start_time,
        elements=demand_rate_elements,
    )

    # Create device state
    device_state = S2DdbcDeviceState(
        device_id=device_id,
        device_name=f"DDBC Price Tradeoff {device_id}",
        connection_id=f"{device_id}_connection",
        priority_class=0,
        timestamp=start_time,
        energy_in_current_timestep=0.0,
        is_online=True,
        power_forecast=None,
        system_descriptions=[system_description],
        demand_forecasts=[demand_rate_forecast],
        actuator_statuses=actuator_statuses,
        gas_price_per_m3=2.0,
    )

    return device_state


def plot_ddbc_results(
    timestep_duration: timedelta,
    nr_of_timesteps: int,
    energy_profile: list,
    supply_rates: Optional[list] = None,
    demand_rates: Optional[list] = None,
    factor_hp: Optional[list] = None,
    factor_gas: Optional[list] = None,
    start_time: Optional[datetime] = None,
    suffix: str = "",
    test_name: str = "DDBC",
):
    """Plot DDBC planning results."""
    os.makedirs("plots", exist_ok=True)

    if start_time is None:
        start_time = datetime(1970, 1, 1, tzinfo=timezone.utc)

    timestep_start_times = [
        start_time + timedelta(seconds=i * timestep_duration.total_seconds())
        for i in range(nr_of_timesteps)
    ]

    fig, ax1 = plt.subplots(1, 1, figsize=(14, 8))

    # Energy plot
    ax1.plot(
        timestep_start_times,
        energy_profile,
        label="Energy (Watts)",
        color="green",
        linewidth=2,
        marker="o",
    )
    ax1.set_ylabel("Power (Watts)", color="green")
    ax1.tick_params(axis="y", labelcolor="green")
    ax1.set_xlabel("Time")
    ax1.grid(True, alpha=0.3)

    # Add supply rates if available
    if supply_rates is not None:
        ax2 = ax1.twinx()
        ax2.plot(
            timestep_start_times,
            supply_rates,
            label="Supply Rate (Watts)",
            color="blue",
            linewidth=2,
            marker="s",
        )
        ax2.set_ylabel("Supply Rate (Watts)", color="blue")
        ax2.tick_params(axis="y", labelcolor="blue")

    # Add demand rates if available
    if demand_rates is not None:
        ax3 = ax1.twinx()
        ax3.spines["right"].set_position(("outward", 60))
        ax3.plot(
            timestep_start_times,
            demand_rates,
            label="Demand Rate (Watts)",
            color="red",
            linewidth=2,
            marker="^",
            linestyle="--",
        )
        ax3.set_ylabel("Demand Rate (Watts)", color="red")
        ax3.tick_params(axis="y", labelcolor="red")

    # Add factors if available
    if factor_hp is not None or factor_gas is not None:
        ax4 = ax1.twinx()
        ax4.spines["right"].set_position(("outward", 120))
        if factor_hp is not None:
            ax4.plot(
                timestep_start_times,
                factor_hp,
                label="HP Factor",
                color="orange",
                linewidth=1.5,
                marker="x",
            )
        if factor_gas is not None:
            ax4.plot(
                timestep_start_times,
                factor_gas,
                label="Gas Factor",
                color="purple",
                linewidth=1.5,
                marker="+",
            )
        ax4.set_ylabel("Operation Mode Factor", color="orange")
        ax4.tick_params(axis="y", labelcolor="orange")
        ax4.set_ylim([0, 1.1])

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    all_lines = lines1
    all_labels = labels1
    if supply_rates is not None:
        lines2, labels2 = ax2.get_legend_handles_labels()
        all_lines.extend(lines2)
        all_labels.extend(labels2)
    if demand_rates is not None:
        lines3, labels3 = ax3.get_legend_handles_labels()
        all_lines.extend(lines3)
        all_labels.extend(labels3)
    if factor_hp is not None or factor_gas is not None:
        lines4, labels4 = ax4.get_legend_handles_labels()
        all_lines.extend(lines4)
        all_labels.extend(labels4)
    ax1.legend(all_lines, all_labels, loc="upper left")

    ax1.set_title(f"{test_name} - Energy and Supply Planning")
    ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=5))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.autofmt_xdate()

    plt.tight_layout()
    plot_filename = f"plots/ddbc_planning_results{suffix}.png"
    plt.savefig(plot_filename)
    print(f"Plot saved to {plot_filename}")
    plt.close()


def extract_insights_from_device_plan(
    device_plan, hp_actuator_id=None, gas_actuator_id=None
):
    """
    Extract insights (supply rates, factors) from device plan.

    Args:
        device_plan: DevicePlan object
        hp_actuator_id: Optional heat pump actuator ID (UUID string) for matching
        gas_actuator_id: Optional gas actuator ID (UUID string) for matching

    Returns:
        Tuple of (supply_rates, factor_hp, factor_gas)
    """
    supply_rates = []
    factor_hp = []
    factor_gas = []

    # Try to get insights from device plan's insights_profile if available
    # DevicePlan may have insights_profile as an extra field (Pydantic allows arbitrary types)
    insights = getattr(device_plan, "insights_profile", None)

    if insights and hasattr(insights, "elements"):
        for elem in insights.elements:
            if elem:
                supply_rates.append(
                    elem.supply_rate if hasattr(elem, "supply_rate") else 0
                )
                configs = (
                    elem.actuator_configurations
                    if hasattr(elem, "actuator_configurations")
                    else {}
                )
                # Extract factors
                hp_factor = None
                gas_factor = None

                # If we have actuator IDs, use them for matching
                if hp_actuator_id or gas_actuator_id:
                    for actuator_id, config in configs.items():
                        actuator_id_str = str(actuator_id)
                        if hp_actuator_id and actuator_id_str == str(hp_actuator_id):
                            if isinstance(config, dict):
                                hp_factor = config.get("factor", 0)
                            elif hasattr(config, "factor"):
                                hp_factor = config.factor
                        elif gas_actuator_id and actuator_id_str == str(
                            gas_actuator_id
                        ):
                            if isinstance(config, dict):
                                gas_factor = config.get("factor", 0)
                            elif hasattr(config, "factor"):
                                gas_factor = config.factor
                else:
                    # Fallback: try to match by checking all configs
                    for actuator_id, config in configs.items():
                        if isinstance(config, dict):
                            # Handle dict format
                            factor = config.get("factor", 0)
                            if factor > 0:  # If there's a factor, assign it
                                if hp_factor is None:
                                    hp_factor = factor
                                elif gas_factor is None:
                                    gas_factor = factor
                        else:
                            # Handle S2DdbcActuatorConfiguration object
                            if hasattr(config, "factor") and config.factor:
                                if hp_factor is None:
                                    hp_factor = config.factor
                                elif gas_factor is None:
                                    gas_factor = config.factor

                factor_hp.append(hp_factor if hp_factor is not None else 0)
                factor_gas.append(gas_factor if gas_factor is not None else 0)
            else:
                supply_rates.append(0)
                factor_hp.append(0)
                factor_gas.append(0)

    return supply_rates, factor_hp, factor_gas


def test_ddbc_by_plotting():
    """
    Test DDBC planning with hybrid heating system.

    Based on S2DdbcTests.java testByPlotting() method.
    Creates a plan with energy targets and plots the results.
    """
    print("=" * 80)
    print("Test 1: DDBC Hybrid Heating - testByPlotting")
    print("=" * 80)

    # Start time aligned to 5-minute intervals
    now = datetime.now(timezone.utc)
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
    device_id = "ddbc_hybrid_heating_001"
    device_state = create_hybrid_heating_device_state_test_by_plotting(
        device_id, start_time, T
    )

    # Create Dictionary of device states
    device_states_dict = {device_id: device_state}

    # Create congestion points mapping
    congestion_points_by_connection_id = {device_id + "_connection": ""}

    # Create a cluster state
    cluster_state = ClusterState(
        start_time, device_states_dict, congestion_points_by_connection_id
    )

    # Create energy target profile
    # Similar to Java test: desiredJoule = i * 10000, minus initial planning
    # For simplicity, we'll create a simple increasing target
    target_profile_elements = []
    for i in range(T):
        desired_joule = i * 10000
        target_profile_elements.append(desired_joule)

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

    # Configuration
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
        reason="DDBC Hybrid Heating testByPlotting",
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

    # Convert Joules to Watts
    power_profile_watts = [
        energy / TIMESTEP_DURATION if energy is not None else 0
        for energy in energy_profile.elements
    ]

    # Extract insights
    device_plan = device_plans[0] if device_plans else None
    supply_rates = []
    factor_hp = []
    factor_gas = []
    demand_rates = [10000.0] * T  # Constant 10kW demand

    if device_plan:
        supply_rates, factor_hp, factor_gas = extract_insights_from_device_plan(
            device_plan
        )

    # Calculate total energy consumption
    total_energy_joules = sum(energy_profile.elements) if energy_profile.elements else 0
    total_energy_kwh = total_energy_joules / 3_600_000
    print(f"Total energy consumption: {total_energy_kwh:.2f} kWh")

    # Plot results
    plot_ddbc_results(
        timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
        nr_of_timesteps=T,
        energy_profile=power_profile_watts,
        supply_rates=supply_rates if supply_rates else None,
        demand_rates=demand_rates,
        factor_hp=factor_hp if factor_hp else None,
        factor_gas=factor_gas if factor_gas else None,
        start_time=start_time,
        suffix="_test_by_plotting",
        test_name="DDBC Test By Plotting",
    )

    print("DDBC testByPlotting completed successfully!")
    return cluster_plan


def test_ddbc_changing_demand():
    """
    Test DDBC planning with changing demand rates.

    Based on S2DdbcTests.java testChangingDemand() method.
    Tests that supply matches alternating demand (0kW even, 4kW odd).
    """
    print("\n" + "=" * 80)
    print("Test 2: DDBC Changing Demand")
    print("=" * 80)

    # Start time aligned to 5-minute intervals
    now = datetime.now(timezone.utc)
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
    device_id = "ddbc_changing_demand_001"
    device_state = create_changing_demand_device_state(device_id, start_time, T)

    # Create Dictionary of device states
    device_states_dict = {device_id: device_state}

    # Create congestion points mapping
    congestion_points_by_connection_id = {device_id + "_connection": ""}

    # Create a cluster state
    cluster_state = ClusterState(
        start_time, device_states_dict, congestion_points_by_connection_id
    )

    # Create null target profile (no energy target, just meet demand)
    target_profile_elements = []
    for _ in range(T):
        target_profile_elements.append(None)

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

    # Configuration
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
        reason="DDBC Changing Demand test",
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

    # Convert Joules to Watts
    power_profile_watts = [
        energy / TIMESTEP_DURATION if energy is not None else 0
        for energy in energy_profile.elements
    ]

    # Extract insights
    device_plan = device_plans[0] if device_plans else None
    supply_rates = []

    # Expectation as described in create_changing_demand_device_state
    demand_rates = [0 if i % 2 == 0 else 4000 for i in range(T)]

    if device_plan:
        supply_rates, _, _ = extract_insights_from_device_plan(device_plan)

    # Verify results match expected pattern
    print("\nVerifying results:")
    for i in range(min(T, len(supply_rates))):
        actual_supply = supply_rates[i] if i < len(supply_rates) else 0
        actual_energy = power_profile_watts[i] if i < len(power_profile_watts) else 0
        print(
            f"  Timestep {i}: Demand={demand_rates[i]}W, Supply={actual_supply:.1f}W, Energy={actual_energy:.1f}W"
        )
        threshold = 500  # somehow related to the number of stratification layers
        if i % 2 == 0:
            assert (
                abs(actual_supply) < threshold
            ), f"Even timestep {i} should have ~0 supply, got {actual_supply}"
            assert (
                abs(actual_energy) < threshold
            ), f"Even timestep {i} should have ~0 energy, got {actual_energy}"
        else:
            assert (
                abs(actual_supply - 4000) < threshold
            ), f"Odd timestep {i} should have ~4000W supply, got {actual_supply}"
            assert actual_energy > 0, f"Odd timestep {i} should have positive energy"

    # Plot results
    plot_ddbc_results(
        timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
        nr_of_timesteps=T,
        energy_profile=power_profile_watts,
        supply_rates=supply_rates if supply_rates else None,
        demand_rates=demand_rates,
        start_time=start_time,
        suffix="_changing_demand",
        test_name="DDBC Changing Demand",
    )

    print("DDBC changing demand test completed successfully!")
    return cluster_plan


def test_ddbc_price_tradeoff():
    """
    Test DDBC planning with price tradeoff between gas and electricity.

    Based on S2DdbcTests.java testPriceTradeoffWithNaturalGas() method.
    Tests that heat pump is used when electricity is cheaper, gas when more expensive.
    """
    print("\n" + "=" * 80)
    print("Test 3: DDBC Price Tradeoff with Natural Gas")
    print("=" * 80)

    # Start time aligned to 5-minute intervals
    now = datetime.now(timezone.utc)
    minutes = (now.minute // 5) * 5
    start_time = now.replace(minute=minutes, second=0, microsecond=0) + timedelta(
        minutes=15
    )
    print(f"Planning start time: {start_time}")

    # Create profile metadata (3 timesteps for this test)
    profile_length = 3
    target_metadata = ProfileMetadata(
        profile_start=start_time,
        timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
        nr_of_timesteps=profile_length,
    )

    # Create device state
    device_id = "ddbc_price_tradeoff_001"
    device_state = create_price_tradeoff_device_state(
        device_id, start_time, profile_length
    )

    # Create Dictionary of device states
    device_states_dict = {device_id: device_state}

    # Create congestion points mapping
    congestion_points_by_connection_id = {device_id + "_connection": ""}

    # Create a cluster state
    cluster_state = ClusterState(
        start_time, device_states_dict, congestion_points_by_connection_id
    )

    # Create tariff target profile
    # Based on Java test: 1.02 (below cutoff), 1.04 (above cutoff), 1.02 (below cutoff)
    # Cutoff price is ~1.034 EUR/kWh where gas and electricity are equally expensive
    tariff_elements = [1.02, 1.04, 1.02]

    cost_target_profile = TargetProfile.from_tariff_values(
        target_metadata, tariff_elements
    )

    # Create a cluster target
    cluster_target = ClusterTarget(
        start_time,
        None,
        None,
        global_target_profile=cost_target_profile,
        congestion_point_targets={},
    )

    # Configuration
    config = PlanningServiceConfig(
        energy_improvement_criterion=10.0,
        cost_improvement_criterion=0.01,  # Lower threshold for cost optimization
        congestion_retry_iterations=10,
        multithreaded=False,
    )

    print("Generating cost-optimized plan...")
    print(f"Tariff profile: {tariff_elements} EUR/kWh")
    print("Expected: HP on when electricity < 1.034 EUR/kWh, Gas when > 1.034 EUR/kWh")

    # Create planning service implementation
    service = PlanningServiceImpl(config)

    # Generate a plan
    plan_due_by_date = start_time + timedelta(seconds=10)
    start_planning_time = time.time()

    cluster_plan = service.plan(
        state=cluster_state,
        target=cluster_target,
        planning_window=TIMESTEP_DURATION * profile_length,
        reason="DDBC Price Tradeoff test",
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

    # Convert Joules to Watts
    # power_profile_watts = [
    #     energy / TIMESTEP_DURATION if energy is not None else 0
    #     for energy in energy_profile.elements
    # ]

    # Extract insights and operation mode factors
    device_plan = device_plans[0] if device_plans else None
    factor_hp = []
    factor_gas = []
    # supply_rates = []
    # demand_rates = [11556.54, 11556.54, 11556.527159385734]

    # Get actuator IDs from device state for matching
    hp_actuator_id = None
    gas_actuator_id = None
    if device_state and device_state.system_descriptions:
        for sys_desc in device_state.system_descriptions:
            for actuator in sys_desc.actuators:
                actuator_id_str = str(actuator.id)
                if (
                    actuator.diagnostic_label
                    and "heatpump" in actuator.diagnostic_label.lower()
                ):
                    hp_actuator_id = actuator_id_str
                elif (
                    actuator.diagnostic_label
                    and "gas" in actuator.diagnostic_label.lower()
                ):
                    gas_actuator_id = actuator_id_str

    if device_plan:
        supply_rates, factor_hp, factor_gas = extract_insights_from_device_plan(
            device_plan, hp_actuator_id=hp_actuator_id, gas_actuator_id=gas_actuator_id
        )

    # Verify price tradeoff behavior
    print("\nVerifying price tradeoff:")
    print("Timestep | Tariff | HP Factor | Gas Factor | Expected Behavior")
    print("-" * 70)
    for i in range(profile_length):
        tariff = tariff_elements[i]
        hp_f = factor_hp[i] if i < len(factor_hp) else 0
        gas_f = factor_gas[i] if i < len(factor_gas) else 0
        expected = "HP on" if tariff < 1.034 else "Gas on"
        print(
            f"   {i}     | {tariff:.2f}  |   {hp_f:.2f}    |   {gas_f:.2f}   | {expected}"  # noqa: E221, E222
        )

        # Assertions based on Java test
        # Note: The optimization might not always achieve perfect factors due to demand constraints
        # We check that the system is responding to price signals
        if tariff < 1.034:  # Below cutoff - should favor heat pump
            assert (
                hp_f > gas_f
            ), "When electricity is cheaper, HP should be used more than gas"
        else:  # Above cutoff - should favor gas
            assert (
                hp_f < gas_f
            ), "When electricity is more expensive, Gas should be used more than HP"

    # Calculate total energy consumption
    total_energy_joules = sum(energy_profile.elements) if energy_profile.elements else 0
    total_energy_kwh = total_energy_joules / 3_600_000
    assert 0.197 == pytest.approx(total_energy_kwh, 0.001)

    # Plot results
    # plot_ddbc_results(
    #     timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
    #     nr_of_timesteps=profile_length,
    #     energy_profile=power_profile_watts,
    #     supply_rates=supply_rates if supply_rates else None,
    #     demand_rates=demand_rates,
    #     factor_hp=factor_hp if factor_hp else None,
    #     factor_gas=factor_gas if factor_gas else None,
    #     start_time=start_time,
    #     suffix="_price_tradeoff",
    #     test_name="DDBC Price Tradeoff",
    # )

    print("DDBC price tradeoff test completed successfully!")
    return cluster_plan
