import pytest
from datetime import datetime, timedelta, timezone
import uuid

from s2python.frbc.frbc_actuator_description import FRBCActuatorDescription
from s2python.frbc.frbc_fill_level_target_profile_element import (
    FRBCFillLevelTargetProfileElement,
)
from s2python.frbc.frbc_leakage_behaviour_element import \
    FRBCLeakageBehaviourElement
from s2python.frbc.frbc_operation_mode import FRBCOperationMode
from s2python.frbc.frbc_usage_forecast_element import FRBCUsageForecastElement
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_planner import (
    S2FrbcDevicePlanner,
)
from flexmeasures_s2.profile_steering.device_planner.frbc.s2_frbc_device_state import (
    S2FrbcDeviceState,
)
from flexmeasures_s2.profile_steering.common.profile_metadata import \
    ProfileMetadata
from s2python.frbc import FRBCSystemDescription
from s2python.frbc import FRBCUsageForecast
from s2python.frbc import FRBCFillLevelTargetProfile
from s2python.frbc import FRBCLeakageBehaviour
from s2python.frbc import FRBCOperationModeElement
from s2python.frbc import FRBCActuatorStatus, FRBCStorageStatus, \
    FRBCStorageDescription
from s2python.common import PowerRange
from s2python.common import NumberRange
from s2python.common import CommodityQuantity
from s2python.common import Transition
from s2python.common import Timer
from s2python.common import PowerValue
from s2python.common import Commodity
from joule_profile_example import get_JouleProfileTarget


def test_connexxion_ev_bus_baseline_byd_225():
    # Arrange
    device_id = "01-01-70.225"
    omloop_starts_at = datetime.fromtimestamp(3600)
    cet = timezone(timedelta(hours=1))
    charge_power_soc_percentage_per_second_night = 0.0054012349
    charging_power_kw_night = 28

    charge_power_soc_percentage_per_second_day = 0.01099537114
    charging_power_kw_day = 57

    # Create system descriptions and forecasts

    start_of_recharge1 = omloop_starts_at.astimezone(cet)
    recharge_duration1 = timedelta(hours=7, minutes=13)
    soc_percentage_before_charging1 = 0
    final_fill_level_target1 = 100

    # Create system description
    recharge_system_description1 = create_recharge_system_description(
        start_of_recharge=start_of_recharge1,
        charge_power_soc_percentage_per_second=charge_power_soc_percentage_per_second_night,
        charging_power_kw=charging_power_kw_night,
        soc_percentage_before_charging=soc_percentage_before_charging1,
    )

    # Create leakage behaviour
    recharge_leakage1 = create_recharge_leakage_behaviour(
        start_of_recharge1)

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

    # Create system description for driving

    start_of_drive1 = start_of_recharge1 + recharge_duration1
    drive_duration1 = timedelta(hours=4, minutes=36)
    drive_consume_soc_per_second1 = 0.00375927565821256038647342995169
    soc_percentage_before_driving1 = 100

    drive_system_description1 = create_driving_system_description(
        start_of_drive1, soc_percentage_before_driving1
    )
    drive_usage_forecast1 = create_driving_usage_forecast(
        start_of_drive1, drive_duration1, drive_consume_soc_per_second1
    )

    start_of_recharge2 = start_of_drive1 + drive_duration1
    recharge_duration2 = timedelta(hours=1, minutes=1)
    soc_percentage_before_charging2 = 37.7463951
    final_fill_level_target2 = 94.4825134

    recharge_system_description2 = create_recharge_system_description(
        start_of_recharge2,
        charge_power_soc_percentage_per_second_day,
        charging_power_kw_day,
        soc_percentage_before_charging2,
    )
    recharge_leakage2 = create_recharge_leakage_behaviour(
        start_of_recharge2)
    recharge_usage_forecast2 = create_recharge_usage_forecast(
        start_of_recharge2, recharge_duration2
    )
    recharge_fill_level_target2 = create_recharge_fill_level_target_profile(
        start_of_recharge2,
        recharge_duration2,
        final_fill_level_target2,
        soc_percentage_before_charging2,
    )

    device_state = S2FrbcDeviceState(
        device_id="bat1",
        device_name="bat1",
        connection_id="cid1",
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
        ],
        leakage_behaviours=[recharge_leakage1, recharge_leakage2],
        usage_forecasts=[
            recharge_usage_forecast1,
            drive_usage_forecast1,
            recharge_usage_forecast2,
        ],
        fill_level_target_profiles=[
            recharge_fill_level_target1,
            recharge_fill_level_target2,
        ],
        computational_parameters=S2FrbcDeviceState.ComputationalParameters(
            1000, 20
        ),
    )
    target_metadata = ProfileMetadata(
        profile_start=omloop_starts_at, timestep_duration=timedelta(seconds=300),
        nr_of_timesteps=288
    )

    plan_due_by_date = target_metadata.get_profile_start() + timedelta(seconds=10)

    planner = S2FrbcDevicePlanner(device_state, target_metadata,
                                  plan_due_by_date)
    planning = planner.create_initial_planning(plan_due_by_date)

    assert planning == get_JouleProfileTarget()


@staticmethod
def create_recharge_system_description(
        start_of_recharge,
        charge_power_soc_percentage_per_second,
        charging_power_kw,
        soc_percentage_before_charging,
) -> FRBCSystemDescription:
    # Create and return a mock system description for recharging
    on_operation_element = FRBCOperationModeElement(
        fill_level_range=NumberRange(start_of_range=0, end_of_range=100),
        fill_rate=NumberRange(
            start_of_range=charge_power_soc_percentage_per_second,
            end_of_range=charge_power_soc_percentage_per_second,
        ),
        power_ranges=[
            PowerRange(
                start_of_range=charging_power_kw * 1000,
                end_of_range=charging_power_kw * 1000,
                commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1,
            )
        ],
    )
    id_on_operation_mode = str(uuid.uuid4())
    on_operation_mode = FRBCOperationMode(
        id=id_on_operation_mode,
        diagnostic_label="on",
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
    off_operation_mode = FRBCOperationMode(
        id=id_off_operation_mode,
        diagnostic_label="off",
        elements=[off_operation_element],
        abnormal_condition_only=False,
    )

    id_on_to_off_timer = str(uuid.uuid4())
    on_to_off_timer = Timer(
        id=id_on_to_off_timer,
        diagnostic_label="on.to.off.timer",
        duration=int(timedelta(minutes=30).total_seconds()),
    )
    id_off_to_on_timer = str(uuid.uuid4())
    off_to_on_timer = Timer(
        id=id_off_to_on_timer,
        diagnostic_label="off.to.on.timer",
        duration=int(timedelta(minutes=30).total_seconds()),
    )

    transition_from_on_to_off = Transition(
        id=str(uuid.uuid4()),
        **{
            "from": id_on_operation_mode
        },
        to=id_off_operation_mode,
        start_timers=[id_off_to_on_timer],
        blocking_timers=[id_on_to_off_timer],
        transition_duration=None,
        abnormal_condition_only=False

    )
    transition_from_off_to_on = Transition(
        id=str(uuid.uuid4()),
        **{
            "from": id_off_operation_mode
        },
        to=id_on_operation_mode,
        start_timers=[id_on_to_off_timer],
        blocking_timers=[id_off_to_on_timer],
        transition_duration=None,
        abnormal_condition_only=False
    )

    charge_actuator_description = FRBCActuatorDescription(
        id=str(uuid.uuid4()),
        diagnostic_label="charge",
        operation_modes=[on_operation_mode, off_operation_mode],
        transitions=[transition_from_on_to_off, transition_from_off_to_on],
        timers=[on_to_off_timer, off_to_on_timer],
        supported_commodities=[Commodity.ELECTRICITY],
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

    return frbc_system_description


def create_recharge_leakage_behaviour( start_of_recharge):
    return FRBCLeakageBehaviour(
        message_id=str(uuid.uuid4()),
        valid_from=start_of_recharge,
        elements=[
            FRBCLeakageBehaviourElement(
                fill_level_range=NumberRange(start_of_range=0,
                                             end_of_range=100),
                leakage_rate=0,
            )
        ],
    )


def create_recharge_usage_forecast(start_of_recharge,
                                   recharge_duration):
    no_usage = FRBCUsageForecastElement(
        duration=int(recharge_duration.total_seconds()),
        usage_rate_expected=0
    )
    return FRBCUsageForecast(
        message_id=str(uuid.uuid4()), start_time=start_of_recharge,
        elements=[no_usage]
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
            start_of_range=soc_percentage_before_charging,
            end_of_range=100),
    )
    end_of_charge = FRBCFillLevelTargetProfileElement(
        duration=min(recharge_duration.total_seconds(), 10),
        fill_level_range=NumberRange(start_of_range=final_fill_level_target,
                                     end_of_range=100),
    )
    return FRBCFillLevelTargetProfile(
        message_id=str(uuid.uuid4()),
        start_time=start_of_recharge,
        elements=[during_charge, end_of_charge]
    )


@staticmethod
def create_driving_system_description(
        start_of_drive, soc_percentage_before_driving
):
    off_operation_element = FRBCOperationModeElement(
        fill_level_range=NumberRange(start_of_range=0, end_of_range=100),
        fill_rate=NumberRange(start_of_range=0, end_of_range=0),
        power_ranges=[
            PowerRange(start_of_range=0, end_of_range=0,
                       commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1)],
    )
    id_off_operation_mode = str(uuid.uuid4())
    off_operation_mode = FRBCOperationMode(
        id=id_off_operation_mode,
        diagnostic_label="off",
        elements=[off_operation_element],
        abnormal_condition_only=False,
    )
    off_actuator = FRBCActuatorDescription(
        id=str(uuid.uuid4()),
        diagnostic_label="off.to.on.timer",
        operation_modes=[off_operation_mode],
        transitions=[],
        timers=[],
        supported_commodities=[Commodity.ELECTRICITY],
    )
    storage_status = FRBCStorageStatus(message_id=str(uuid.uuid4()),
                                       present_fill_level=soc_percentage_before_driving)
    storage_description = FRBCStorageDescription(
        diagnostic_label="battery",
        fill_level_label="SoC %",
        provides_leakage_behaviour=False,
        provides_fill_level_target_profile=True,
        provides_usage_forecast=False,
        fill_level_range=NumberRange(start_of_range=0, end_of_range=100),
    )
    return FRBCSystemDescription(
        message_id=str(uuid.uuid4()),
        valid_from=start_of_drive,
        actuators=[off_actuator],
        storage=storage_description,
    )


@staticmethod
def create_driving_usage_forecast(
         start_of_driving, next_drive_duration, soc_usage_per_second
):
    no_usage = FRBCUsageForecastElement(
        duration=int(next_drive_duration.total_seconds()),
        usage_rate_expected=(-1 * soc_usage_per_second),
    )
    return FRBCUsageForecast(message_id=str(uuid.uuid4()),
                             start_time=start_of_driving,
                             elements=[no_usage])
