"""
Simplified DDBC test that uses the simplified device state.
This test demonstrates DDBC device integration without complex S2 objects.
"""
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from datetime import datetime, timedelta, timezone
import time
import pandas as pd
import os
from s2python.common import PowerValue, CommodityQuantity
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
PLANNING_WINDOW = pd.Timedelta("PT2H")  # Shorter window for testing
PLANNING_RESOLUTION = pd.Timedelta("PT5M")

T = PLANNING_WINDOW // PLANNING_RESOLUTION
TIMESTEP_DURATION = PLANNING_RESOLUTION / pd.Timedelta("PT1S")


def create_ddbc_device_state_simple(
    device_id: str, start_time: datetime
) -> S2DdbcDeviceState:
    """
    Create a simplified DDBC device state for testing.
    Uses empty lists for system descriptions and demand forecasts.
    """
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
        system_descriptions=[],  # Simplified: empty list
        demand_forecasts=[],  # Simplified: empty list
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
    ax1.set_title("Predicted vs Target Energy - DDBC Devices (Simplified)")
    ax1.legend(loc="best")
    ax1.grid(True)

    ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=15))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.autofmt_xdate()

    plt.tight_layout()
    os.makedirs("plots", exist_ok=True)
    plt.savefig(f"plots/ddbc_simple_plot_D={D}_T={T}.png")
    print(f"Plot saved to plots/ddbc_simple_plot_D={D}_T={T}.png")


def get_target_profile_elements(number_of_elements: int):
    """Create target profile elements for testing."""
    target_elements = []
    # Simple varying target for testing
    for i in range(number_of_elements):
        if i < number_of_elements // 4:
            target_elements.append(5000000)  # 5 MJ
        elif i < number_of_elements // 2:
            target_elements.append(3000000)  # 3 MJ
        elif i < 3 * number_of_elements // 4:
            target_elements.append(2000000)  # 2 MJ
        else:
            target_elements.append(4000000)  # 4 MJ
    return target_elements


def test_planning_service_impl_with_ddbc_devices_simple():
    """Test the PlanningServiceImpl with simplified DDBC devices."""
    print("Testing PlanningServiceImpl with simplified DDBC devices")
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
        create_ddbc_device_state_simple(
            f"ddbc_device_{i + 1}",
            target_metadata.profile_start,
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
        reason="Testing DDBC planning (simplified)",
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
            print(f"  Total energy: {total_energy} Joules (zero for simplified test)")
            print(f"  Instruction profile: {device_plan.instruction_profile}")

    assert len(energy_profile.elements) == target_metadata.nr_of_timesteps
    print("Test completed successfully!")
    print("\nNote: This is a simplified test. Full DDBC planning with state trees")
    print("      and optimization would be implemented in ddbc_planning_window.py")


if __name__ == "__main__":
    test_planning_service_impl_with_ddbc_devices_simple()
