import datetime
import uuid

from flexmeasures_s2.scheduler.s2_frbc_device_state import S2FrbcDeviceState

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
)

example_serialized_device_state = None

# Load a JSON serialized FRBC device state from a file
with open("test_frbc_device.json", "r") as file:
    example_serialized_device_state = file.read()


# Define specific ids
charge_on_id = str(uuid.uuid4())
charge_off_id = str(uuid.uuid4())

on_to_off = str(uuid.uuid4())
off_to_on = str(uuid.uuid4())

on_to_off_timer_id = str(uuid.uuid4())
off_to_on_timer_id = str(uuid.uuid4())


# Define the test object
example_deserialized_device_state = S2FrbcDeviceState(
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
                            id=charge_on_id,
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
                            id=charge_off_id,
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
                            id=off_to_on,
                            **{
                                "from": charge_off_id
                            },  # Use a workaround to set 'from' since it's a keyword in Python,
                            to=charge_on_id,
                            start_timers=[on_to_off_timer_id],
                            blocking_timers=[off_to_on_timer_id],
                            abnormal_condition_only=False,
                        ),
                        Transition(
                            id=on_to_off,
                            **{
                                "from": charge_on_id
                            },  # Use a workaround to set 'from' since it's a keyword in Python,
                            to=charge_off_id,
                            start_timers=[off_to_on_timer_id],
                            blocking_timers=[on_to_off_timer_id],
                            abnormal_condition_only=False,
                        ),
                    ],
                    timers=[
                        Timer(
                            id=on_to_off_timer_id,
                            diagnostic_label="on.to.off.timer",
                            duration=30,
                        ),
                        Timer(
                            id=off_to_on_timer_id,
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
