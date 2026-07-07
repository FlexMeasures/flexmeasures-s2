import pandas as pd

from flexmeasures_s2.scheduler.schedulers import S2Scheduler
from flexmeasures_s2.scheduler.tests.joule_profile import get_JouleProfileTarget
from flexmeasures_s2.scheduler.test_frbc_device import (
    example_deserialized_device_state,
)


def test_s2_frbc_scheduler(setup_frbc_asset):
    scheduler = S2Scheduler(
        setup_frbc_asset,
        start=pd.Timestamp("2025-01-20T13:00+01"),
        end=pd.Timestamp("2025-01-20T19:00+01"),
        resolution=pd.Timedelta("PT1H"),
        flex_model={},  # S2Scheduler fetches this from asset attributes
        flex_context={
            "target-profile": get_JouleProfileTarget(),  # todo: port target profile from Java test
        },
    )
    results = scheduler.compute()
    assert results == "todo: check for expected results"


def test_s2_frbc_deserialise(setup_frbc_asset):
    scheduler = S2Scheduler(
        setup_frbc_asset,
        start=pd.Timestamp("2025-01-20T13:00+01"),
        end=pd.Timestamp("2025-01-20T19:00+01"),
        resolution=pd.Timedelta("PT1H"),
        flex_model={},  # S2Scheduler fetches this from asset attributes
        flex_context={},
    )
    assert scheduler.deserialize_config() == example_deserialized_device_state
