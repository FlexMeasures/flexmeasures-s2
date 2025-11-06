from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from datetime import datetime, timedelta, timezone

# import time
import pandas as pd
import os
import uuid
from s2python.common import PowerForecast, PowerValue, CommodityQuantity
from s2python.common import PowerForecastElement, PowerForecastValue
from flexmeasures_s2.profile_steering.device_planner.nocontrol.s2_nocontrol_device_state import (
    S2NoControlDeviceState,
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

D = 3
PLANNING_WINDOW = pd.Timedelta("PT24H")
PLANNING_RESOLUTION = pd.Timedelta("PT5M")

T = PLANNING_WINDOW // PLANNING_RESOLUTION
TIMESTEP_DURATION = PLANNING_RESOLUTION / pd.Timedelta("PT1S")


def create_simple_power_forecast(
    start_time: datetime, nr_of_timesteps: int, timestep_duration: float
) -> PowerForecast:
    """
    Create a simple power forecast with varying consumption.
    This simulates a device with fixed consumption pattern (e.g., a fridge).

    Args:
        start_time: When the forecast starts
        nr_of_timesteps: Number of timesteps
        timestep_duration: Duration of each timestep in seconds

    Returns:
        A PowerForecast with a realistic consumption pattern
    """
    elements = []

    for i in range(nr_of_timesteps):
        if i % 12 == 0:
            power_watts = 150.0
        elif i % 12 < 3:
            power_watts = 150.0
        else:
            power_watts = 0.0

        power_value = PowerForecastValue(
            value_expected=power_watts,
            commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1,
        )

        element = PowerForecastElement(
            duration=int(timestep_duration), power_values=[power_value]
        )
        elements.append(element)

    return PowerForecast(
        message_id=str(uuid.uuid4()),
        start_time=start_time,
        elements=elements,
    )


def create_nocontrol_device_state(
    device_id: str, start_time: datetime, nr_of_timesteps: int, timestep_duration: float
) -> S2NoControlDeviceState:
    """
    Create a nocontrol device state (e.g., for a non-controllable load like a fridge).

    Args:
        device_id: ID of the device
        start_time: When the planning starts
        nr_of_timesteps: Number of timesteps
        timestep_duration: Duration of each timestep in seconds

    Returns:
        An S2NoControlDeviceState with a power forecast
    """
    power_forecast = create_simple_power_forecast(
        start_time, nr_of_timesteps, timestep_duration
    )

    device_state = S2NoControlDeviceState(
        device_id=device_id,
        device_name=device_id,
        connection_id=device_id + "_connection",
        priority_class=1,
        timestamp=start_time,
        energy_in_current_timestep=PowerValue(
            value=0, commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1
        ),
        is_online=True,
        power_forecast=power_forecast,
    )
    return device_state


def plot_planning_results(
    timestep_duration,
    nr_of_timesteps,
    predicted_energy_elements,
    target_energy_elements,
):
    """
    Plots the energy comparison.

    :param timestep_duration: Duration of each timestep.
    :param nr_of_timesteps: Number of timesteps.
    :param predicted_energy_elements: List of predicted energy values.
    :param target_energy_elements: List of target energy values.
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
        label="Predicted Energy (NoControl Devices)",
        color="green",
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
    ax1.set_title("Predicted vs Target Energy - NoControl Devices")
    ax1.legend(loc="best")
    ax1.grid(True)

    ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    fig.autofmt_xdate()

    plt.tight_layout()
    os.makedirs("plots", exist_ok=True)
    plt.savefig(f"plots/nocontrol_plot_D={D}_T={T}.png")
    # print(f"Plot saved to plots/nocontrol_plot_D={D}_T={T}.png")


def get_target_profile_elements(number_of_elements: int):
    """Create target profile elements."""
    target_elements = []
    target_elements.extend([0] * 38)
    target_elements.extend([8400000] * 62)
    target_elements.extend([0] * 45)
    target_elements.extend([8400000] * 28)
    target_elements.extend([176000000] * 115)
    return target_elements[:number_of_elements]


def test_planning_service_impl_with_nocontrol_devices():
    """Test the PlanningServiceImpl with nocontrol devices."""
    # print("Testing PlanningServiceImpl with nocontrol devices")
    # print(f"Number of devices: {D}")
    # print(f"Number of timesteps: {T}")

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
        create_nocontrol_device_state(
            f"nocontrol_device_{i + 1}",
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

    # print("Generating plan!")

    service = PlanningServiceImpl(config)

    # start_time = time.time()
    cluster_plan = service.plan(
        state=cluster_state,
        target=cluster_target,
        planning_window=TIMESTEP_DURATION * T,
        reason="Testing NoControl planning",
        plan_due_by_date=plan_due_by_date,
        optimize_for_target=True,
        max_priority_class=1,
    )
    # end_time = time.time()
    # execution_time = end_time - start_time

    # print(f"Plan generated in {execution_time:.2f} seconds")

    assert cluster_plan is not None
    # print("Got cluster plan")

    if cluster_plan is None:
        # print("Cluster plan is None")
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
    # print(f"Got {len(device_plans)} device plans")

    for device_plan in device_plans:
        if device_plan:
            # print(f"Device {device_plan.device_id}:")
            # print(
            #     f"  Total energy: {sum(e for e in device_plan.energy_profile.elements if e is not None)} Joules"
            # )
            # print(f"  Instruction profile: {device_plan.instruction_profile}")
            pass

    assert len(energy_profile.elements) == target_metadata.nr_of_timesteps
    # print("Test completed successfully!")


if __name__ == "__main__":
    test_planning_service_impl_with_nocontrol_devices()
