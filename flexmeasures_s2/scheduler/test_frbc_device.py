import datetime
import uuid

from s2_frbc_device_state import S2FrbcDeviceState

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


# Define the test object
test_device_state = S2FrbcDeviceState(
    system_descriptions=[
        FRBCSystemDescription(
            valid_from=datetime.datetime.now(tz=datetime.timezone.utc),
            actuators=[
                FRBCActuatorDescription(
                    id=uuid.uuid4(),
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
                            from_="charge.off",
                            to="charge.on",
                            start_timers=["on.to.off.timer"],
                            blocking_timers=["off.to.on.timer"],
                            abnormal_condition_only=False,
                        ),
                        Transition(
                            id="on.to.off",
                            from_="charge.on",
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
