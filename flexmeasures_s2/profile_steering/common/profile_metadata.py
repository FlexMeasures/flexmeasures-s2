from datetime import datetime, timedelta
from typing import Optional

class ProfileMetadata:
    NR_OF_TIMESTEPS_KEY = "nrOfTimesteps"
    TIMESTEP_DURATION_KEY = "timestepDurationMs"
    PROFILE_START_KEY = "profileStart"

    def __init__(self, profile_start: datetime, timestep_duration: timedelta, nr_of_timesteps: int):
        self.profile_start = profile_start
        self.timestep_duration = timestep_duration
        self.nr_of_timesteps = nr_of_timesteps
        self.profile_end = profile_start + timestep_duration * nr_of_timesteps
        self.profile_duration = self.profile_end - self.profile_start

    def get_profile_start(self) -> datetime:
        return self.profile_start

    def get_timestep_duration(self) -> timedelta:
        return self.timestep_duration

    def get_nr_of_timesteps(self) -> int:
        return self.nr_of_timesteps

    def get_profile_end(self) -> datetime:
        return self.profile_end

    def get_profile_duration(self) -> timedelta:
        return self.profile_duration

    def get_profile_start_at_timestep(self, i: int) -> datetime:
        if i >= self.nr_of_timesteps or i < 0:
            raise ValueError(f"Expected i to be between 0 <= i < {self.nr_of_timesteps} but was {i}")
        return self.profile_start + self.timestep_duration * i

    def get_starting_step_nr(self, instant: datetime) -> int:
        if instant < self.profile_start:
            return -1
        elif instant >= self.profile_end:
            return self.nr_of_timesteps
        else:
            duration_between_secs = (instant - self.profile_start).total_seconds()
            timestep_duration_secs = self.timestep_duration.total_seconds()
            return int(duration_between_secs // timestep_duration_secs)

    def is_aligned_with(self, other: 'ProfileMetadata') -> bool:
        return (self.timestep_duration == other.timestep_duration and
                (abs((self.profile_start - other.profile_start).total_seconds()) %
                 self.timestep_duration.total_seconds()) == 0)

    def to_dict(self) -> dict:
        return {
            self.PROFILE_START_KEY: int(self.profile_start.timestamp() * 1000),
            self.TIMESTEP_DURATION_KEY: int(self.timestep_duration.total_seconds() * 1000),
            self.NR_OF_TIMESTEPS_KEY: self.nr_of_timesteps
        }

    @staticmethod
    def from_dict(data: dict) -> 'ProfileMetadata':
        profile_start = datetime.fromtimestamp(data[ProfileMetadata.PROFILE_START_KEY] / 1000)
        timestep_duration = timedelta(milliseconds=data[ProfileMetadata.TIMESTEP_DURATION_KEY])
        nr_of_timesteps = data[ProfileMetadata.NR_OF_TIMESTEPS_KEY]
        return ProfileMetadata(profile_start, timestep_duration, nr_of_timesteps)

    def subprofile(self, new_start_date: datetime) -> 'ProfileMetadata':
        if new_start_date < self.profile_start:
            raise ValueError("The new start date should be after the current start date")
        new_start_date = self.next_aligned_date(new_start_date, self.timestep_duration)
        skipped_steps = int((new_start_date - self.profile_start).total_seconds() // self.timestep_duration.total_seconds())
        nr_of_elements = max(0, self.nr_of_timesteps - skipped_steps)
        return ProfileMetadata(new_start_date, self.timestep_duration, nr_of_elements)

    def adjust_nr_of_elements(self, nr_of_elements: int) -> 'ProfileMetadata':
        return ProfileMetadata(self.profile_start, self.timestep_duration, nr_of_elements)

    @staticmethod
    def next_aligned_date(date: datetime, timestep_duration: timedelta) -> datetime:
        # Align the date to the next timestep
        remainder = (date - datetime.min).total_seconds() % timestep_duration.total_seconds()
        if remainder == 0:
            return date
        return date + timedelta(seconds=(timestep_duration.total_seconds() - remainder))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProfileMetadata):
            return False
        return (self.nr_of_timesteps == other.nr_of_timesteps and
                self.profile_start == other.profile_start and
                self.timestep_duration == other.timestep_duration)

    def __hash__(self) -> int:
        return hash((self.nr_of_timesteps, self.profile_start, self.timestep_duration)) 
