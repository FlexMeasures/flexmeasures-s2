from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from datetime import datetime, timedelta, timezone
import time
import pandas as pd
import os
import uuid
from s2python.common import PowerValue, CommodityQuantity
from s2python.ddbc import DDBCSystemDescription, DDBCActuatorDescription
from s2python.ddbc import DDBCOperationMode
from s2python.ddbc.ddbc_average_demand_rate_forecast import (
    DDBCAverageDemandRateForecast,
    DDBCAverageDemandRateForecastElement,
)
from s2python.common import NumberRange, PowerRange, Transition
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_device_state import (
    S2DdbcDeviceState,
)
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata

from flexmeasures_s2.scheduler.schedulers import (
    PlanningServiceImpl,
    PlanningServiceConfig,
    ClusterState,
    ClusterTarget,
)
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

D = 2  # Number of DDBC devices
PLANNING_WINDOW = pd.Timedelta("PT24H")  # Shorter window for testing
PLANNING_RESOLUTION = pd.Timedelta("PT5M")

T = PLANNING_WINDOW // PLANNING_RESOLUTION
TIMESTEP_DURATION = PLANNING_RESOLUTION / pd.Timedelta("PT1S")


def create_simple_ddbc_system_description(
    start_time: datetime,
) -> DDBCSystemDescription:
    """
    Create a simple DDBC system description for a heat pump.

    Args:
        start_time: When the system description is valid from

    Returns:
        A DDBCSystemDescription with a heat pump actuator
    """
    actuator_id = str(uuid.uuid4())
    operation_mode_id = str(uuid.uuid4())

    # Create operation mode for the heat pump
    # Use dictionary form with "Id" (capital I) to satisfy pydantic validation
    operation_mode_dict = {
        "Id": operation_mode_id,
        "id": operation_mode_id,
        "diagnostic_label": "heat_pump_on",
        "supply_range": [
            NumberRange(start_of_range=0, end_of_range=10)
        ],  # Supply in kW
        "power_ranges": [
            PowerRange(
                start_of_range=0,
                end_of_range=20000,  # 20 kW electric power (increased to allow optimization)
                commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1,
            )
        ],
        "abnormal_condition_only": False,
    }
    operation_mode = DDBCOperationMode(**operation_mode_dict)

    # Create actuator description
    from s2python.common import Commodity

    actuator = DDBCActuatorDescription(
        id=actuator_id,
        diagnostic_label="heat_pump",
        operation_modes=[operation_mode],
        transitions=[
            Transition(
                id=str(uuid.uuid4()),
                **{"from": operation_mode_id},
                to=operation_mode_id,
                start_timers=[],
                blocking_timers=[],
                transition_duration=None,
                abnormal_condition_only=False,
            )
        ],
        timers=[],
        supported_commodites=[Commodity.ELECTRICITY],
    )

    # Note: actuator_status is a separate S2 message, not part of the actuator description
    # It would be sent independently in a real device implementation
    # For this test, we don't need to attach it to the actuator

    # Create system description
    # present_demand_rate is a NumberRange indicating the current demand rate range
    present_demand_rate = NumberRange(start_of_range=0.0, end_of_range=10.0)

    system_description = DDBCSystemDescription(
        message_id=str(uuid.uuid4()),
        valid_from=start_time,
        actuators=[actuator],
        present_demand_rate=present_demand_rate,
        provides_average_demand_rate_forecast=True,  # This device can provide forecasts
    )

    return system_description


def create_simple_demand_forecast(
    start_time: datetime, nr_of_timesteps: int, timestep_duration: float
) -> DDBCAverageDemandRateForecast:
    """
    Create a simple demand forecast for thermal energy.

    Args:
        start_time: When the forecast starts
        nr_of_timesteps: Number of timesteps
        timestep_duration: Duration of each timestep in seconds

    Returns:
        A DDBCAverageDemandRateForecast with varying demand
    """
    elements = []

    for i in range(nr_of_timesteps):
        # Simulate varying thermal demand (in supply units, e.g., kW)
        if i < nr_of_timesteps // 4:
            demand_rate = 5.0  # High demand
        elif i < nr_of_timesteps // 2:
            demand_rate = 3.0  # Medium demand
        elif i < 3 * nr_of_timesteps // 4:
            demand_rate = 2.0  # Low demand
        else:
            demand_rate = 4.0  # Medium-high demand

        element = DDBCAverageDemandRateForecastElement(
            duration=int(timestep_duration * 1000),  # Convert to milliseconds
            demand_rate_expected=demand_rate,  # Note: field name is 'demand_rate_expected', not 'average_demand_rate_expected'
        )
        elements.append(element)

    return DDBCAverageDemandRateForecast(
        message_id=str(uuid.uuid4()), start_time=start_time, elements=elements
    )


def create_ddbc_device_state(
    device_id: str, start_time: datetime, nr_of_timesteps: int, timestep_duration: float
) -> S2DdbcDeviceState:
    """
    Create a DDBC device state (e.g., for a heat pump).

    Args:
        device_id: ID of the device
        start_time: When the planning starts
        nr_of_timesteps: Number of timesteps
        timestep_duration: Duration of each timestep in seconds

    Returns:
        An S2DdbcDeviceState with system description and demand forecast
    """
    system_description = create_simple_ddbc_system_description(start_time)
    demand_forecast = create_simple_demand_forecast(
        start_time, nr_of_timesteps, timestep_duration
    )

    device_state = S2DdbcDeviceState(
        device_id=device_id,
        device_name=device_id,
        connection_id=device_id + "_connection",
        priority_class=1,
        timestamp=start_time,
        energy_in_current_timestep=PowerValue(
            value=0, commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1
        ),
        is_online=True,
        power_forecast=None,  # DDBC devices don't need power forecast
        system_descriptions=[system_description],
        demand_forecasts=[demand_forecast],
        gas_price_per_m3=2.0,  # €2 per m3 of gas
    )
    return device_state


def plot_planning_results(
    timestep_duration,
    nr_of_timesteps,
    predicted_energy_elements,
    target_energy_elements,
):
    """
    Plots the energy comparison for DDBC devices.
    """
    timestep_start_times = [
        datetime(1970, 1, 1, tzinfo=timezone.utc)
        + timedelta(seconds=i * timestep_duration.total_seconds())
        for i in range(nr_of_timesteps)
    ]

    fig, ax1 = plt.subplots(1, 1, figsize=(12, 8))

    ax1.plot(
        timestep_start_times,
        predicted_energy_elements,
        label="Predicted Energy (DDBC Devices)",
        color="blue",
    )
    ax1.plot(
        timestep_start_times,
        target_energy_elements,
        label="Target Energy",
        color="red",
        linestyle="dotted",
        linewidth=2,
    )

    ax1.set_ylabel("Energy (Joules)")
    ax1.set_title("Predicted vs Target Energy - DDBC Devices")
    ax1.legend(loc="best")
    ax1.grid(True)

    ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=15))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.autofmt_xdate()

    plt.tight_layout()
    os.makedirs("plots", exist_ok=True)
    plt.savefig(f"plots/ddbc_plot_D={D}_T={T}.png")
    print(f"Plot saved to plots/ddbc_plot_D={D}_T={T}.png")


def get_target_profile_elements(number_of_elements: int):
    """
    Create target profile elements for testing DDBC optimization.
    Similar pattern to FRBC test - starts low, ramps up, then high usage.

    With 20kW electrical capacity and 300s timesteps:
    - Low: 500kJ (0.5 MJ) ≈ 1.67 kW average
    - Med: 1500kJ (1.5 MJ) ≈ 5 kW average
    - High: 3000kJ (3 MJ) ≈ 10 kW average (matches demand-based generation)
    """
    target_elements = []
    # First quarter: low energy target (encourage minimal operation)
    target_elements.extend([500000] * (number_of_elements // 4))  # 0.5 MJ
    # Second quarter: medium energy target
    target_elements.extend([1500000] * (number_of_elements // 4))  # 1.5 MJ
    # Third quarter: low again
    target_elements.extend([800000] * (number_of_elements // 4))  # 0.8 MJ
    # Final quarter: high energy target (meet all demand)
    remaining = number_of_elements - len(target_elements)
    target_elements.extend([3000000] * remaining)  # 3 MJ
    return target_elements


def test_planning_service_impl_with_ddbc_devices():
    """Test the PlanningServiceImpl with DDBC devices."""
    print("Testing PlanningServiceImpl with DDBC devices")
    print(f"Number of devices: {D}")
    print(f"Number of timesteps: {T}")

    target_metadata = ProfileMetadata(
        profile_start=datetime(1970, 1, 1, tzinfo=timezone.utc),
        timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
        nr_of_timesteps=T,
    )
    plan_due_by_date = target_metadata.profile_start + timedelta(seconds=10)
    target_profile_elements = get_target_profile_elements(T)

    global_target_profile = TargetProfile(
        profile_start=target_metadata.profile_start,
        timestep_duration=target_metadata.timestep_duration,
        elements=target_profile_elements,
    )

    device_states = [
        create_ddbc_device_state(
            f"ddbc_device_{i + 1}",
            target_metadata.profile_start,
            T,
            TIMESTEP_DURATION,
        )
        for i in range(D)
    ]

    device_states_dict = {
        device_state.device_id: device_state for device_state in device_states
    }

    congestion_points_by_connection_id = {
        device_state.connection_id: "" for device_state in device_states
    }

    cluster_state = ClusterState(
        datetime.now(), device_states_dict, congestion_points_by_connection_id
    )

    congestion_point_targets = {}
    cluster_target = ClusterTarget(
        datetime.now(),
        None,
        None,
        global_target_profile=global_target_profile,
        congestion_point_targets=congestion_point_targets,
    )

    config = PlanningServiceConfig(
        energy_improvement_criterion=10.0,
        cost_improvement_criterion=1.0,
        congestion_retry_iterations=10,
        multithreaded=False,
    )

    print("Generating plan!")

    service = PlanningServiceImpl(config)

    start_time = time.time()
    cluster_plan = service.plan(
        state=cluster_state,
        target=cluster_target,
        planning_window=TIMESTEP_DURATION * T,
        reason="Testing DDBC planning",
        plan_due_by_date=plan_due_by_date,
        optimize_for_target=True,
        max_priority_class=1,
    )
    end_time = time.time()
    execution_time = end_time - start_time

    print(f"Plan generated in {execution_time:.2f} seconds")

    assert cluster_plan is not None
    print("Got cluster plan")

    if cluster_plan is None:
        print("Cluster plan is None")
        return

    device_plans = cluster_plan.get_plan_data().get_device_plans()
    energy_profile = cluster_plan.get_joule_profile()

    plot_planning_results(
        timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
        nr_of_timesteps=T,
        predicted_energy_elements=energy_profile.elements,
        target_energy_elements=target_profile_elements,
    )

    device_plans = [plan for plan in device_plans if plan is not None]

    assert len(device_plans) > 0
    print(f"Got {len(device_plans)} device plans")

    for device_plan in device_plans:
        if device_plan:
            print(f"Device {device_plan.device_id}:")
            total_energy = sum(
                e for e in device_plan.energy_profile.elements if e is not None
            )
            print(f"  Total energy: {total_energy} Joules")
            print(f"  Instruction profile: {device_plan.instruction_profile}")

    assert len(energy_profile.elements) == target_metadata.nr_of_timesteps
    print("Test completed successfully!")


if __name__ == "__main__":
    test_planning_service_impl_with_ddbc_devices()
