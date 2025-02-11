import pytest
from datetime import datetime, timezone, timedelta
from flexmeasures_s2.profile_steering.frbc.s2_frbc_device_planner import (
    S2FrbcDevicePlanner,
)
from flexmeasures_s2.profile_steering.frbc.s2_frbc_device_state_wrapper import (
    S2FrbcDeviceStateWrapper,
)
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from test_frbc_device import test_device_state
from joule_profile_example import JouleProfileTarget


def test_create_initial_planning():
    # Initialize the necessary objects for the test
    device_state = S2FrbcDeviceStateWrapper(test_device_state)
    epoch_time = datetime(1970, 1, 1, tzinfo=timezone.utc)
    profile_metadata = ProfileMetadata(
        profile_start=epoch_time,
        timestep_duration=timedelta(seconds=300),
        nr_of_timesteps=288,
    )
    plan_due_by_date = profile_metadata.get_profile_start() + timedelta(seconds=10)

    # Initialize the planner
    planner = S2FrbcDevicePlanner(device_state, profile_metadata, plan_due_by_date)

    # Call the method to test
    joule_profile = planner.create_initial_planning(plan_due_by_date)

    # Define the expected JouleProfile
    expected_joule_profile = JouleProfile(
        profile_start=profile_metadata.get_profile_start(),
        timestep_duration=profile_metadata.get_timestep_duration(),
        elements=JouleProfileTarget,
    )

    # Assert that the output matches the expected output
    assert joule_profile == expected_joule_profile
