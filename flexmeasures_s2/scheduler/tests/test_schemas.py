import pytest

from flexmeasures_s2.scheduler.schemas import TNOTargetProfile


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
