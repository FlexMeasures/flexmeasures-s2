import datetime
import uuid

from flexmeasures_s2.profile_steering.frbc.s2_frbc_device_state import S2FrbcDeviceState

from s2python.frbc import (
    FRBCSystemDescription,
    FRBCActuatorDescription,
    FRBCOperationMode,
    FRBCOperationModeElement,
    FRBCStorageDescription,
)

from s2python.common import (
    Commodity,
    Transition,
    Timer,
    NumberRange,
    PowerRange,
    CommodityQuantity,
    PowerForecast,
    PowerForecastElement,
    PowerForecastValue,
)


# Define the test object
test_device_state = S2FrbcDeviceState(
    device_id=str(uuid.uuid4()),
    device_name="test_device",
    connection_id=str(uuid.uuid4()),
    priority_class=1,
    timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
    energy_in_current_timestep=CommodityQuantity.ELECTRIC_POWER_L1,
    is_online=True,

    system_descriptions=[
        FRBCSystemDescription(
            message_id=str(uuid.uuid4()),
            valid_from=datetime.datetime.now(tz=datetime.timezone.utc),
            actuators=[
                FRBCActuatorDescription(
                    id=str(uuid.uuid4()),  # Ensure id is a string
                    diagnostic_label="charge",
                    supported_commodities=[Commodity.ELECTRICITY],
                    operation_modes=[
                        FRBCOperationMode(
                            id="charge.on",
                            diagnostic_label="charge.on",
                            elements=[
                                FRBCOperationModeElement(
                                    fill_level_range=NumberRange(
                                        start_of_range=0.0,
                                        end_of_range=100.0,
                                    ),
                                    fill_rate=NumberRange(
                                        start_of_range=0.0054012349,
                                        end_of_range=0.0054012349,
                                    ),
                                    power_ranges=[
                                        PowerRange(
                                            start_of_range=28000.0,
                                            end_of_range=28000.0,
                                            commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1,
                                        )
                                    ],
                                )
                            ],
                            abnormal_condition_only=False,
                        ),
                        FRBCOperationMode(
                            id="charge.off",
                            diagnostic_label="charge.off",
                            elements=[
                                FRBCOperationModeElement(
                                    fill_level_range=NumberRange(
                                        start_of_range=0,
                                        end_of_range=100,
                                    ),
                                    fill_rate=NumberRange(
                                        start_of_range=0,
                                        end_of_range=0,
                                    ),
                                    power_ranges=[
                                        PowerRange(
                                            start_of_range=0,
                                            end_of_range=0,
                                            commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1,
                                        )
                                    ],
                                    running_costs=None,
                                )
                            ],
                            abnormal_condition_only=False,
                        ),
                    ],
                    transitions=[
                        Transition(
                            id="off.to.on",
                            **{
                                "from": "charge.off"
                            },  # Use a workaround to set 'from' since it's a keyword in Python,
                            to="charge.on",
                            start_timers=["on.to.off.timer"],
                            blocking_timers=["off.to.on.timer"],
                            abnormal_condition_only=False,
                        ),
                        Transition(
                            id="on.to.off",
                            **{
                                "from": "charge.on"
                            },  # Use a workaround to set 'from' since it's a keyword in Python,
                            to="charge.off",
                            start_timers=["off.to.on.timer"],
                            blocking_timers=["on.to.off.timer"],
                            abnormal_condition_only=False,
                        ),
                    ],
                    timers=[
                        Timer(
                            id="on.to.off.timer",
                            diagnostic_label="on.to.off.timer",
                            duration=30,
                        ),
                        Timer(
                            id="off.to.on.timer",
                            diagnostic_label="off.to.on.timer",
                            duration=30,
                        ),
                    ],
                )
            ],
            storage=FRBCStorageDescription(
                diagnostic_label="battery",
                fill_level_label="SoC %",
                provides_leakage_behaviour=False,
                provides_fill_level_target_profile=True,
                provides_usage_forecast=False,
                fill_level_range=NumberRange(start_of_range=0, end_of_range=100),
            ),
        )
    ],
)
