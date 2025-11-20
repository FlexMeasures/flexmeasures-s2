"""
Example script demonstrating DDBC (Demand-Driven Based Control) planning using Flask scheduler.

This script tests the S2FlaskScheduler with DDBC devices, following the pattern from
example_schedule_itho_flask.py and using test data from S2DdbcTests.java.

The test creates a hybrid heating system with:
- A gas boiler actuator (natural gas commodity)
- A heat pump actuator (electricity commodity)
- Average demand rate forecasts
- Tariff-based targets to optimize cost

To run:
    python flexmeasures_s2/profile_steering/examples/example_schedule_ddbc.py
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import logging
import time
import pandas as pd
import os
import uuid
from decimal import Decimal

# Import Flask app creation
from flexmeasures.app import create as create_flexmeasures_app

from flexmeasures_s2.scheduler.scheduler_flask import S2FlaskScheduler
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
import matplotlib.pyplot as plt

# Configuration parameters
PLANNING_WINDOW = pd.Timedelta("PT24H")
PLANNING_RESOLUTION = pd.Timedelta("PT1H")
# S = 30  # Number of stratification layers (matching FRBC) [NOT CURRENTLY USED]

T = PLANNING_WINDOW // PLANNING_RESOLUTION  # number of time steps
TIMESTEP_DURATION = PLANNING_RESOLUTION / pd.Timedelta("PT1S")


class MockDDBCDeviceData:
    """Mock DDBCDeviceData class to mimic the structure from WebSocket integration."""

    def __init__(self):
        self.system_description = None
        self.demand_forecasts = []
        self.actuator_statuses = {}
        self.resource_id = None


def create_hybrid_heating_device_state(
    device_id: str,
    start_time: datetime,
    profile_length: int = T,
) -> S2DdbcDeviceState:
    """
    Create a DDBC device state for a hybrid heating system.

    Based on S2DdbcTests.java testByPlotting() method.
    System has:
    - Gas boiler: 0-20kW (using natural gas)
    - Heat pump: 0-2kW (using electricity)
    - Both provide 0-10kW heating supply rate
    - Average demand rate forecast of 10kW

    Args:
        device_id: Unique device identifier
        start_time: Start time for planning
        profile_length: Number of timesteps

    Returns:
        S2DdbcDeviceState configured for hybrid heating
    """
    # Create UUIDs for actuators and operation modes
    # Use strings - s2python validates and expects string UUIDs
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
    # Dictionary keys must be strings to match device state wrapper expectations
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


def create_ddbc_device_data_from_device_state(
    device_state: S2DdbcDeviceState, resource_id: str
) -> MockDDBCDeviceData:
    """Convert S2DdbcDeviceState to DDBCDeviceData structure for scheduler."""
    ddbc_data = MockDDBCDeviceData()
    ddbc_data.resource_id = resource_id

    if device_state.system_descriptions:
        ddbc_data.system_description = device_state.system_descriptions[0]

    ddbc_data.demand_forecasts = device_state.demand_forecasts

    if hasattr(device_state, "actuator_statuses"):
        # Convert dict to dict (already in correct format)
        ddbc_data.actuator_statuses = device_state.actuator_statuses

    return ddbc_data


def get_cost_target_profile_elements(num_elements: int) -> list:
    """
    Create cost target profile with time-of-use pricing.

    Simulates variable electricity pricing to test cost optimization:
    - Night hours (00:00-06:00): 0.10 EUR/kWh (cheap - favor heat pump)
    - Morning (06:00-09:00): 0.15 EUR/kWh
    - Peak hours (09:00-17:00): 0.30 EUR/kWh (expensive - favor gas boiler)
    - Evening (17:00-21:00): 0.25 EUR/kWh
    - Late evening (21:00-24:00): 0.15 EUR/kWh
    """
    cost_elements = []

    for timestep in range(num_elements):
        # Calculate hour of day based on timestep
        hour = (timestep * int(PLANNING_RESOLUTION.total_seconds() / 60)) // 60

        if 0 <= hour < 6:
            tariff = 0.10  # Cheap night rate
        elif 6 <= hour < 9:
            tariff = 0.15
        elif 9 <= hour < 17:
            tariff = 0.30  # Expensive peak rate
        elif 17 <= hour < 21:
            tariff = 0.25
        else:
            tariff = 0.15

        cost_elements.append(tariff)

    return cost_elements


def test_ddbc_with_flask_scheduler(
    profile_length: int = T,
    use_tariff_target: bool = True,
    suffix="_ddbc_flask",
):
    """
    Test S2FlaskScheduler with DDBC hybrid heating device.

    Args:
        profile_length: Number of timesteps to plan
        use_tariff_target: If True, use tariff-based targets; else use joule targets
        suffix: Suffix for output files
    """
    print("=" * 80)
    print("Test: DDBC Hybrid Heating with S2FlaskScheduler")
    print(f"  Profile length: {profile_length} timesteps")
    print(f"  Target type: {'Tariff' if use_tariff_target else 'Joule'}")
    print("=" * 80)

    # Create Flask app for scheduler context
    app = create_flexmeasures_app(env="development")

    with app.app_context():
        # Configure app settings for scheduler
        app.config.setdefault(
            "FLEXMEASURES_S2_TARGET_MODE", "costs" if use_tariff_target else "energy"
        )
        app.config.setdefault("FLEXMEASURES_S2_PRICE_SENSOR", 2)

        # Start time aligned to the planning resolution
        resolution_minutes = PLANNING_RESOLUTION // pd.Timedelta(minutes=1)
        now = datetime.now(timezone.utc)
        minutes = (now.minute // resolution_minutes) * resolution_minutes
        start_time = now.replace(minute=minutes, second=0, microsecond=0)
        print(f"Planning start time: {start_time}")

        # Create device state
        device_id = f"ddbc_hybrid_heating_{suffix}"
        device_state = create_hybrid_heating_device_state(
            device_id,
            start_time,
            profile_length,
        )

        # Convert device state to DDBCDeviceData format
        ddbc_device_data = create_ddbc_device_data_from_device_state(
            device_state, device_id
        )

        # Create S2FlaskScheduler instance
        scheduler = S2FlaskScheduler.__new__(S2FlaskScheduler)

        # Set basic time parameters
        scheduler.sensor = None
        scheduler.asset = None
        scheduler.start = start_time
        scheduler.end = start_time + timedelta(
            seconds=TIMESTEP_DURATION * profile_length
        )
        scheduler.resolution = PLANNING_RESOLUTION
        scheduler.belief_time = start_time
        scheduler.round_to_decimals = 6
        scheduler.flex_model = {}
        scheduler.flex_context = {}
        scheduler.fallback_scheduler_class = None

        # Initialize scheduler attributes
        scheduler.planning_service = None
        scheduler.config_deserialized = False
        scheduler.ddbc_device_data = ddbc_device_data  # Note: using ddbc_device_data

        # Set data source if available
        try:
            from flexmeasures.data.services.users import get_or_create_source
            from flexmeasures import User

            user = User.query.first()
            if user:
                data_source = get_or_create_source(user)
                scheduler.data_source = data_source
        except Exception as e:
            app.logger.debug(f"Could not set data source: {e}")
            scheduler.data_source = None

        print(
            f"Scheduler window: {scheduler.start.strftime('%Y-%m-%d %H:%M:%S')} → "
            f"{scheduler.end.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        print("Generating plan using S2FlaskScheduler...")

        # Generate plan using scheduler
        start_planning_time = time.time()

        # Note: The scheduler's compute() method will call PlanningServiceImpl
        # which should handle DDBC devices if properly integrated
        schedule_results = scheduler.compute()

        end_planning_time = time.time()
        execution_time = end_planning_time - start_planning_time

        print(f"Plan generated in {execution_time:.2f} seconds")

        # Extract results
        energy_data = [
            result
            for result in schedule_results
            if isinstance(result, dict) and "device" in result and "data" in result
        ]

        print(f"Generated energy data for {len(energy_data)} device(s)")

        # Process energy profile
        total_energy_kwh = 0.0
        if energy_data:
            energy_series = energy_data[0]["data"]
            # Convert Joules to kWh - trim to profile_length
            energy_values_joules = [
                energy if pd.notna(energy) else 0
                for energy in energy_series.values[:profile_length]
            ]
            total_energy_joules = sum(energy_values_joules)
            total_energy_kwh = total_energy_joules / 3_600_000
            print(f"Total energy consumption: {total_energy_kwh:.2f} kWh")

            # Convert to Watts for plotting
            power_profile_watts = [
                energy / TIMESTEP_DURATION if energy > 0 else 0
                for energy in energy_values_joules
            ]
        else:
            power_profile_watts = [0] * profile_length
            print("Warning: No energy data generated")

        # Create cost profile if using tariff targets
        cost_elements = None
        cost_target_elements = None
        if use_tariff_target:
            cost_target_elements = get_cost_target_profile_elements(profile_length)
            if energy_data:
                # Calculate actual costs
                cost_elements = []
                for energy_joules, tariff in zip(
                    energy_values_joules, cost_target_elements
                ):
                    kwh = energy_joules / 3_600_000
                    cost = kwh * tariff
                    cost_elements.append(cost)
                total_cost = sum(cost_elements)
                print(f"Total cost: ${total_cost:.4f}")

        # Plot results
        plot_ddbc_results(
            timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
            nr_of_timesteps=profile_length,
            energy_profile=power_profile_watts,
            cost_elements=cost_elements,
            cost_target_elements=cost_target_elements,
            start_time=start_time,
            suffix=suffix,
        )

        print("DDBC Flask scheduler test completed!")

        return {
            "energy_profile": power_profile_watts,
            "total_energy_kwh": total_energy_kwh if energy_data else 0,
            "total_cost": sum(cost_elements) if cost_elements else 0,
        }


def plot_ddbc_results(
    timestep_duration: timedelta,
    nr_of_timesteps: int,
    energy_profile: list,
    cost_elements: Optional[list] = None,
    cost_target_elements: Optional[list] = None,
    start_time: Optional[datetime] = None,
    suffix: str = "",
):
    """Plot DDBC planning results."""
    # Create output directory
    os.makedirs("plots", exist_ok=True)

    if cost_elements is not None or cost_target_elements is not None:
        # Create dual-axis plot for energy and cost
        fig, ax1 = plt.subplots(1, 1, figsize=(14, 8))

        timesteps = list(range(nr_of_timesteps))

        # Energy plot on left y-axis
        ax1.plot(
            timesteps,
            energy_profile,
            label="Energy (Watts)",
            color="green",
            linewidth=2,
            marker="o",
        )
        ax1.set_ylabel("Power (Watts)", color="green")
        ax1.tick_params(axis="y", labelcolor="green")
        ax1.set_xlabel("Timestep")
        ax1.grid(True, alpha=0.3)

        # Cost plot on right y-axis
        ax2 = ax1.twinx()
        if cost_target_elements is not None:
            ax2.plot(
                timesteps,
                cost_target_elements,
                label="Tariff (EUR/kWh)",
                color="orange",
                linestyle="dashed",
                linewidth=2,
                marker="s",
            )
        if cost_elements is not None:
            ax2.plot(
                timesteps,
                cost_elements,
                label="Cost (EUR)",
                color="blue",
                linewidth=2,
                marker="^",
            )
        ax2.set_ylabel("Cost / Tariff", color="blue")
        ax2.tick_params(axis="y", labelcolor="blue")

        # Combined legend
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

        ax1.set_title("DDBC Hybrid Heating - Energy and Cost Planning")
    else:
        # Simple energy plot
        fig, ax1 = plt.subplots(1, 1, figsize=(12, 6))

        timesteps = list(range(nr_of_timesteps))
        ax1.plot(
            timesteps,
            energy_profile,
            label="Energy (Watts)",
            color="green",
            linewidth=2,
            marker="o",
        )
        ax1.set_xlabel("Timestep")
        ax1.set_ylabel("Power (Watts)")
        ax1.set_title("DDBC Hybrid Heating - Energy Profile")
        ax1.legend()
        ax1.grid(True)

    plt.tight_layout()
    plot_filename = f"plots/ddbc_planning_results{suffix}.png"
    plt.savefig(plot_filename)
    print(f"Plot saved to {plot_filename}")
    plt.close()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )

    print("=" * 80)
    print("DDBC Hybrid Heating Planning with S2FlaskScheduler")
    print("=" * 80)
    print()

    try:
        # Test with tariff-based optimization
        results = test_ddbc_with_flask_scheduler(
            profile_length=T,
            use_tariff_target=True,
            suffix="_tariff",
        )

        print("\n" + "=" * 80)
        print("Test Summary:")
        print(f"  Total energy: {results['total_energy_kwh']:.2f} kWh")
        print(f"  Total cost: ${results['total_cost']:.4f}")
        print("=" * 80)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        raise
