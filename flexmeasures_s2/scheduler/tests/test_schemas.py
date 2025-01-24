import pytest
import pandas as pd

from flexmeasures_s2.scheduler.schemas import TNOTargetProfile
from flexmeasures_s2.scheduler.schedulers import S2Scheduler
from flexmeasures_s2.scheduler.tests.joule_profile import get_JouleProfileTarget


@pytest.mark.parametrize(
    "target_profile",
    [
        # todo: port test cases from Java test
        {},
        {
            "start": "2025-01-20T13:00+01",
            "duration": "PT3H",
            "values": [0, 1, 2],
        },
    ],
)
def test_tno_profile_schema(target_profile: dict):
    """Check whether the profile schema"""
    TNOTargetProfile().load(target_profile)
