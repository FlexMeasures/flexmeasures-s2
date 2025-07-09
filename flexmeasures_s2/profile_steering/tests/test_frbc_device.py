from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from datetime import datetime, timedelta, timezone
import uuid
import logging
import time
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

from flexmeasures_s2.profile_steering.planning_service_impl import (
    PlanningServiceImpl,
    PlanningServiceConfig,
    ClusterState,
    ClusterTarget,
)
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

# Global variables to store IDs for debugging
# make a list of tuples with the ids and the names
ids = []


D = 10  # number of devices
B = 100  # number of buckets
S = 20  # number of stratification layers
T = 288  # number of time steps (288 * 5 minutes = 24 hours)
TIMESTEP_DURATION = 300  # duration of a time step in seconds (5 minutes)



# D = 10  # number of devices
# B = 100  # number of buckets
# S = 20  # number of stratification layers
# T = 288  # number of time steps (5 minutes * 288 = 1440 minutes = 24 hours)
# TIMESTEP_DURATION = 300  # duration of a time step in seconds (5 minutes)
"""
# Ideas for speeding up

- Parallelize device planning
- Precompute UUIDs
"""


def create_ev_device_state(
    device_id: str,
    omloop_starts_at: datetime,
    cet: timezone,
    charge_power_soc_percentage_per_second_night: float,
    charging_power_kw_night: float,
    charge_power_soc_percentage_per_second_day: float,
    charging_power_kw_day: float,
    soc_percentage_before_charging1: float,
    final_fill_level_target1: float,
    recharge_duration1: timedelta,
    start_of_recharge1: datetime,
    drive_duration1: timedelta,
    start_of_drive1: datetime,
    drive_consume_soc_per_second1: float,
    soc_percentage_before_driving1: float,
    soc_percentage_before_charging2: float,
    final_fill_level_target2: float,
    recharge_duration2: timedelta,
    start_of_recharge2: datetime,
) -> S2FrbcDeviceState:
    # Create system description
    (
        recharge_system_description1,
        charge_actuator_status1,
        storage_status1,
    ) = create_recharge_system_description(
        start_of_recharge=start_of_recharge1,
        charge_power_soc_percentage_per_second=charge_power_soc_percentage_per_second_night,
        charging_power_kw=charging_power_kw_night,
        soc_percentage_before_charging=soc_percentage_before_charging1,
    )

    # Create leakage behaviour
    recharge_leakage1 = create_recharge_leakage_behaviour(start_of_recharge1)

    # Create usage forecast
    recharge_usage_forecast1 = create_recharge_usage_forecast(
        start_of_recharge1, recharge_duration1
    )

    # Create fill level target profile
    recharge_fill_level_target1 = create_recharge_fill_level_target_profile(
        start_of_recharge1,
        recharge_duration1,
        final_fill_level_target1,
        soc_percentage_before_charging1,
    )

    (
        drive_system_description1,
        off_actuator_status1,
        storage_status1,
    ) = create_driving_system_description(
        start_of_drive1, soc_percentage_before_driving1
    )
    drive_usage_forecast1 = create_driving_usage_forecast(
        start_of_drive1, drive_duration1, drive_consume_soc_per_second1
    )

    (
        recharge_system_description2,
        charge_actuator_status2,
        storage_status2,
    ) = create_recharge_system_description(
        start_of_recharge2,
        charge_power_soc_percentage_per_second_day,
        charging_power_kw_day,
        soc_percentage_before_charging2,
    )
    recharge_leakage2 = create_recharge_leakage_behaviour(start_of_recharge2)
    recharge_usage_forecast2 = create_recharge_usage_forecast(
        start_of_recharge2, recharge_duration2
    )
    recharge_fill_level_target2 = create_recharge_fill_level_target_profile(
        start_of_recharge2,
        recharge_duration2,
        final_fill_level_target2,
        soc_percentage_before_charging2,
    )

    # Create done state
    done_start = start_of_recharge2 + recharge_duration2
    done_duration = timedelta(hours=4, minutes=10)  # 4 hours & 10 minutes
    done_leakage = create_recharge_leakage_behaviour(done_start)
    (
        done_system_description,
        done_actuator_status,
        done_storage_status,
    ) = create_driving_system_description(done_start, final_fill_level_target2)
    done_usage_forecast = create_recharge_usage_forecast(done_start, done_duration)

    device_state = S2FrbcDeviceState(
        device_id=device_id,
        device_name=device_id,
        connection_id=device_id + "_cid1",
        priority_class=1,
        timestamp=omloop_starts_at,
        energy_in_current_timestep=PowerValue(
            value=0, commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1
        ),
        is_online=True,
        power_forecast=None,
        system_descriptions=[
            recharge_system_description1,
            drive_system_description1,
            recharge_system_description2,
            done_system_description,
        ],
        leakage_behaviours=[recharge_leakage1, recharge_leakage2, done_leakage],
        usage_forecasts=[
            recharge_usage_forecast1,
            drive_usage_forecast1,
            recharge_usage_forecast2,
            done_usage_forecast,
        ],
        fill_level_target_profiles=[
            recharge_fill_level_target1,
            recharge_fill_level_target2,
        ],
        computational_parameters=S2FrbcDeviceState.ComputationalParameters(B, S),
        actuator_statuses=[
            off_actuator_status1,
            charge_actuator_status1,
            charge_actuator_status2,
            done_actuator_status,
        ],
        storage_status=[storage_status1, storage_status2, done_storage_status],
    )
    return device_state


@staticmethod
def create_recharge_system_description(
    start_of_recharge,
    charge_power_soc_percentage_per_second,
    charging_power_kw,
    soc_percentage_before_charging,
) -> FRBCSystemDescription:
    global charge_actuator_id, id_on_operation_mode, id_off_operation_mode, id_on_to_off_timer, id_off_to_on_timer
    # Create and return a mock system description for recharging
    on_operation_element = FRBCOperationModeElement(
        fill_level_range=NumberRange(start_of_range=0, end_of_range=100),
        fill_rate=NumberRange(
            start_of_range=0,
            end_of_range=charge_power_soc_percentage_per_second,
        ),
        power_ranges=[
            PowerRange(
                start_of_range=charging_power_kw * 0,
                end_of_range=charging_power_kw * 1000,
                commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1,
            )
        ],
    )
    id_on_operation_mode = str(uuid.uuid4())
    logging.debug(f"id_on_operation_mode: {id_on_operation_mode}")
    ids.append((id_on_operation_mode, "charge_on_operation_mode"))
    on_operation_mode = FRBCOperationMode(
        id=id_on_operation_mode,
        diagnostic_label="charge.on",
        elements=[on_operation_element],
        abnormal_condition_only=False,
    )
    off_operation_element = FRBCOperationModeElement(
        fill_level_range=NumberRange(start_of_range=0, end_of_range=100),
        fill_rate=NumberRange(start_of_range=0, end_of_range=0),
        power_ranges=[
            PowerRange(
                start_of_range=0,
                end_of_range=0,
                commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1,
            )
        ],
    )
    id_off_operation_mode = str(uuid.uuid4())
    logging.debug(f"id_off_operation_mode: {id_off_operation_mode}")
    ids.append((id_off_operation_mode, "charge_off_operation_mode"))
    off_operation_mode = FRBCOperationMode(
        id=id_off_operation_mode,
        diagnostic_label="charge.off",
        elements=[off_operation_element],
        abnormal_condition_only=False,
    )

    id_on_to_off_timer = str(uuid.uuid4())
    logging.debug(f"id_on_to_off_timer: {id_on_to_off_timer}")
    ids.append((id_on_to_off_timer, "charge_on_to_off_timer"))
    on_to_off_timer = Timer(
        id=id_on_to_off_timer,
        diagnostic_label="charge_on.to.off.timer",
        duration=Duration(30),
    )
    id_off_to_on_timer = str(uuid.uuid4())
    logging.debug(f"id_off_to_on_timer: {id_off_to_on_timer}")
    ids.append((id_off_to_on_timer, "charge_off_to_on_timer"))
    off_to_on_timer = Timer(
        id=id_off_to_on_timer,
        diagnostic_label="charge_off.to.on.timer",
        duration=Duration(30),
    )
    transition_id_from_on_to_off = str(uuid.uuid4())
    logging.debug(f"transition_id_from_on_to_off: {transition_id_from_on_to_off}")
    ids.append(
        (transition_id_from_on_to_off, "transition_from_charge_on_to_charge_off")
    )
    transition_from_on_to_off = Transition(
        id=transition_id_from_on_to_off,
        **{"from": id_on_operation_mode},
        to=id_off_operation_mode,
        start_timers=[id_off_to_on_timer],
        blocking_timers=[id_on_to_off_timer],
        transition_duration=None,
        abnormal_condition_only=False,
    )
    transition_id_from_off_to_on = str(uuid.uuid4())
    logging.debug(f"transition_id_from_off_to_on: {transition_id_from_off_to_on}")
    ids.append(
        (transition_id_from_off_to_on, "transition_from_charge_off_to_charge_on")
    )
    transition_from_off_to_on = Transition(
        id=transition_id_from_off_to_on,
        **{"from": id_off_operation_mode},
        to=id_on_operation_mode,
        start_timers=[id_on_to_off_timer],
        blocking_timers=[id_off_to_on_timer],
        transition_duration=None,
        abnormal_condition_only=False,
    )
    charge_actuator_id = str(uuid.uuid4())
    logging.debug(f"charge_actuator_id: {charge_actuator_id}")
    ids.append((charge_actuator_id, "charge_actuator"))
    charge_actuator_status = FRBCActuatorStatus(
        message_id=charge_actuator_id,
        actuator_id=charge_actuator_id,
        active_operation_mode_id=id_on_operation_mode,
        operation_mode_factor=0,
    )

    charge_actuator_description = FRBCActuatorDescription(
        id=charge_actuator_id,
        diagnostic_label="charge.actuator",
        operation_modes=[on_operation_mode, off_operation_mode],
        transitions=[transition_from_on_to_off, transition_from_off_to_on],
        timers=[on_to_off_timer, off_to_on_timer],
        supported_commodities=[Commodity.ELECTRICITY],
    )
    storage_status_id = str(uuid.uuid4())
    logging.debug(f"storage_status_id: {storage_status_id}")
    ids.append((storage_status_id, "storage_status"))
    storage_status = FRBCStorageStatus(
        message_id=storage_status_id, present_fill_level=soc_percentage_before_charging
    )

    frbc_storage_description = FRBCStorageDescription(
        diagnostic_label="battery",
        fill_level_label="SoC %",
        provides_leakage_behaviour=False,
        provides_fill_level_target_profile=True,
        provides_usage_forecast=False,
        fill_level_range=NumberRange(start_of_range=0, end_of_range=100),
    )

    frbc_system_description = FRBCSystemDescription(
        message_id=str(uuid.uuid4()),
        valid_from=start_of_recharge,
        actuators=[charge_actuator_description],
        storage=frbc_storage_description,
    )

    return frbc_system_description, charge_actuator_status, storage_status


@staticmethod
def create_recharge_leakage_behaviour(start_of_recharge):
    leakage_id = str(uuid.uuid4())
    logging.debug(f"leakage_id: {leakage_id}")
    ids.append((leakage_id, "leakage"))
    return FRBCLeakageBehaviour(
        message_id=leakage_id,
        valid_from=start_of_recharge,
        elements=[
            FRBCLeakageBehaviourElement(
                fill_level_range=NumberRange(start_of_range=0, end_of_range=100),
                leakage_rate=0,
            )
        ],
    )


@staticmethod
def create_recharge_usage_forecast(start_of_recharge, recharge_duration):
    no_usage = FRBCUsageForecastElement(
        duration=int(recharge_duration.total_seconds()), usage_rate_expected=0
    )
    usage_id = str(uuid.uuid4())
    logging.debug(f"usage_id: {usage_id}")
    ids.append((usage_id, "usage"))
    return FRBCUsageForecast(
        message_id=usage_id, start_time=start_of_recharge, elements=[no_usage]
    )


@staticmethod
def create_recharge_fill_level_target_profile(
    start_of_recharge,
    recharge_duration,
    final_fill_level_target,
    soc_percentage_before_charging,
):
    during_charge = FRBCFillLevelTargetProfileElement(
        duration=max(recharge_duration.total_seconds() - 10, 0),
        fill_level_range=NumberRange(
            start_of_range=soc_percentage_before_charging, end_of_range=100
        ),
    )
    end_of_charge = FRBCFillLevelTargetProfileElement(
        duration=min(recharge_duration.total_seconds(), 10),
        fill_level_range=NumberRange(
            start_of_range=final_fill_level_target, end_of_range=100
        ),
    )
    fill_level_id = str(uuid.uuid4())
    logging.debug(f"fill_level_id: {fill_level_id}")
    ids.append((fill_level_id, "fill_level"))
    return FRBCFillLevelTargetProfile(
        message_id=fill_level_id,
        start_time=start_of_recharge,
        elements=[during_charge, end_of_charge],
    )


@staticmethod
def create_driving_system_description(start_of_drive, soc_percentage_before_driving):
    global off_actuator_id, id_off_operation_mode
    off_operation_element = FRBCOperationModeElement(
        fill_level_range=NumberRange(start_of_range=0, end_of_range=100),
        fill_rate=NumberRange(start_of_range=0, end_of_range=0),
        power_ranges=[
            PowerRange(
                start_of_range=0,
                end_of_range=0,
                commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1,
            )
        ],
    )
    id_off_operation_mode = str(uuid.uuid4())
    logging.debug(f"operation_mode_driving: {id_off_operation_mode}")
    ids.append((id_off_operation_mode, "operation_mode_driving"))
    off_operation_mode = FRBCOperationMode(
        id=id_off_operation_mode,
        diagnostic_label="off",
        elements=[off_operation_element],
        abnormal_condition_only=False,
    )
    off_actuator_id = str(uuid.uuid4())
    logging.debug(f"actuator_driving: {off_actuator_id}")
    ids.append((off_actuator_id, "actuator_driving"))
    off_actuator_status = FRBCActuatorStatus(
        message_id=str(uuid.uuid4()),
        actuator_id=off_actuator_id,
        active_operation_mode_id=id_off_operation_mode,
        operation_mode_factor=0,
    )
    off_actuator = FRBCActuatorDescription(
        id=off_actuator_id,
        diagnostic_label="off",
        operation_modes=[off_operation_mode],
        transitions=[],
        timers=[],
        supported_commodities=[Commodity.ELECTRICITY],
    )
    storage_status = FRBCStorageStatus(
        message_id=str(uuid.uuid4()), present_fill_level=soc_percentage_before_driving
    )
    storage_description = FRBCStorageDescription(
        diagnostic_label="battery",
        fill_level_label="SoC %",
        provides_leakage_behaviour=False,
        provides_fill_level_target_profile=True,
        provides_usage_forecast=False,
        fill_level_range=NumberRange(start_of_range=0, end_of_range=100),
    )
    return (
        FRBCSystemDescription(
            message_id=str(uuid.uuid4()),
            valid_from=start_of_drive,
            actuators=[off_actuator],
            storage=storage_description,
        ),
        off_actuator_status,
        storage_status,
    )


@staticmethod
def create_driving_usage_forecast(
    start_of_driving, next_drive_duration, soc_usage_per_second
):
    no_usage = FRBCUsageForecastElement(
        duration=int(next_drive_duration.total_seconds()),
        usage_rate_expected=(-1 * soc_usage_per_second),
    )
    return FRBCUsageForecast(
        message_id=str(uuid.uuid4()), start_time=start_of_driving, elements=[no_usage]
    )


def plot_planning_results(
    timestep_duration,
    nr_of_timesteps,
    predicted_energy_elements,
    target_energy_elements,
):
    """
    Plots the energy, fill level, actuator usage, and operation mode ID lists using matplotlib.

    :param timestep_duration: Duration of each timestep.
    :param nr_of_timesteps: Number of timesteps.
    :param predicted_energy_elements: List of predicted energy values.
    :param target_energy_elements: List of target energy values.
    """
    # Create a figure with a single subplot
    fig, ax = plt.subplots(1, 1, figsize=(12, 8))

    # Generate timestep_start_times
    timestep_start_times = [
        datetime(1970, 1, 1, tzinfo=timezone.utc)
        + timedelta(seconds=i * timestep_duration.total_seconds())
        for i in range(nr_of_timesteps)
    ]

    # Plot both lines on the same subplot
    ax.plot(
        timestep_start_times,
        predicted_energy_elements,
        label="Predicted Energy",
        color="green",
    )
    ax.plot(
        timestep_start_times,
        target_energy_elements,
        label="Target Energy",
        color="red",
        linestyle="dotted",
        linewidth=2,
    )

    # Set labels and grid
    ax.set_ylabel("Energy (Joules)")
    ax.set_title("Predicted vs Target Energy")
    ax.legend(loc="best")
    ax.grid(True)

    # Format the x-axis to show time and set ticks every 30 minutes
    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    fig.autofmt_xdate()

    # Adjust layout
    plt.tight_layout()
    plt.savefig(f"my plot - D = {D} - B = {B} - S = {S} - T = {T}")


def create_device_state(
    device_id: str, omloop_starts_at: datetime, cet: timezone
) -> S2FrbcDeviceState:
    # Device charging parameters
    charge_power_soc_percentage_per_second_night = 0.01099537114
    charging_power_kw_night = 57
    charge_power_soc_percentage_per_second_day = 0.01099537114
    charging_power_kw_day = 57

    # First recharge period
    start_of_recharge1 = omloop_starts_at.astimezone(cet)
    recharge_duration1 = timedelta(hours=7, minutes=15)
    soc_percentage_before_charging1 = 0
    final_fill_level_target1 = 100

    # Driving period
    start_of_drive1 = start_of_recharge1 + recharge_duration1
    drive_duration1 = timedelta(hours=4, minutes=35)
    drive_consume_soc_per_second1 = 0.00375927565821256038647342995169
    soc_percentage_before_driving1 = 100

    # Second recharge period
    start_of_recharge2 = start_of_drive1 + drive_duration1
    recharge_duration2 = timedelta(hours=7)
    soc_percentage_before_charging2 = 37.0
    final_fill_level_target2 = 94.4825134

    # Create the device state
    device_state = create_ev_device_state(
        device_id,
        omloop_starts_at,
        cet,
        charge_power_soc_percentage_per_second_night,
        charging_power_kw_night,
        charge_power_soc_percentage_per_second_day,
        charging_power_kw_day,
        soc_percentage_before_charging1,
        final_fill_level_target1,
        recharge_duration1,
        start_of_recharge1,
        drive_duration1,
        start_of_drive1,
        drive_consume_soc_per_second1,
        soc_percentage_before_driving1,
        soc_percentage_before_charging2,
        final_fill_level_target2,
        recharge_duration2,
        start_of_recharge2,
    )
    return device_state


def get_target_profile_elements(number_of_elements: int):
    """Create target profile elements with the same pattern as the Java code."""
    target_elements = []
    # First 38 elements of 0
    target_elements.extend([0] * 38)
    # Next 62 elements of 8400000
    target_elements.extend([8400000] * 62)
    # Next 55 elements of 0
    target_elements.extend([0] * 45)
    # Next 18 elements of 8400000
    target_elements.extend([8400000] * 28)
    # Last 115 elements of 176000000
    target_elements.extend([176000000] * 115)
    return target_elements[:number_of_elements]


def test_planning_service_impl_with_ev_device():
    """Test the PlanningServiceImpl with an EV device."""
    print("Test the PlanningServiceImpl with an EV device.")
    # Create 10 device states
    numberOfDevices = D

    # Create profile metadata and target profile
    target_metadata = ProfileMetadata(
        profile_start=datetime(1970, 1, 1, tzinfo=timezone.utc),
        timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
        nr_of_timesteps=T,
    )
    plan_due_by_date = target_metadata.get_profile_start() + timedelta(seconds=10)
    target_profile_elements = get_target_profile_elements(T)

    device_states = [
        create_device_state(
            f"battery{i+1}", datetime.fromtimestamp(3600), timezone(timedelta(hours=1))
        )
        for i in range(numberOfDevices)
    ]

    # Create Dictionary of device states
    device_states_dict = {
        device_state.device_id: device_state for device_state in device_states
    }

    # Create congestion points mapping
    congestion_points_by_connection_id = {
        device_id: "" for device_id in device_states_dict.keys()
    }

    # Create a target profile
    global_target_profile = TargetProfile(
        profile_start=target_metadata.get_profile_start(),
        timestep_duration=target_metadata.get_timestep_duration(),
        elements=target_profile_elements,
    )
    # Create a cluster state using the list of device states
    cluster_state = ClusterState(
        datetime.now(), device_states_dict, congestion_points_by_connection_id
    )

    #  Create an empty map for congestion point targets
    congestion_point_targets = {}

    # Create a cluster target
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
        multithreaded=True,
    )
    print("Generating plan!")

    # Create planning service implementation
    service = PlanningServiceImpl(config)

    # Create cluster target

    cluster_target = ClusterTarget(
        datetime.now(),
        None,
        None,
        global_target_profile=global_target_profile,
        congestion_point_targets=congestion_point_targets,
    )
    # Set due by date for planning
    plan_due_by_date = target_metadata.get_profile_start() + timedelta(seconds=10)
    # Act - Generate a plan
    start_time = time.time()
    cluster_plan = service.plan(
        state=cluster_state,
        target=cluster_target,
        planning_window=TIMESTEP_DURATION * T,  # Full planning window in seconds
        reason="Testing EV planning",
        plan_due_by_date=plan_due_by_date,
        optimize_for_target=True,
        max_priority_class=1,
    )
    end_time = time.time()
    execution_time = end_time - start_time

    # Log information
    print(f"Plan generated in {execution_time:.2f} seconds")

    # Assert
    assert cluster_plan is not None
    print("Got cluster plan")
    if cluster_plan is None:
        print("Cluster plan is None")
        return
    # Get the plan for our device
    device_plans = cluster_plan.get_plan_data().get_device_plans()
    energy_profile = cluster_plan.get_joule_profile()

    plot_planning_results(
        timestep_duration=timedelta(seconds=TIMESTEP_DURATION),
        nr_of_timesteps=T,
        predicted_energy_elements=energy_profile.get_elements(),
        target_energy_elements=target_profile_elements,
    )

    # Get only the non-None plans
    device_plans = [plan for plan in device_plans if plan is not None]

    # Assert that we got a plan for our device
    assert len(device_plans) > 0
    print("Got device plan")
    # Print and verify the energy profile

    # Basic assertion - the energy profile should have the expected number of elements
    assert len(energy_profile.elements) == target_metadata.get_nr_of_timesteps()


# Main function
if __name__ == "__main__":
    test_planning_service_impl_with_ev_device()
