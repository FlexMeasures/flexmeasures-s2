from datetime import datetime, timedelta
from flexmeasures_s2.profile_steering.common.abstract_profile import AbstractProfile


class ProfileMetadata:
    def __init__(
        self,
        profile_start: datetime,
        timestep_duration: timedelta,
        nr_of_timesteps: int,
    ):
        self.profile_start = profile_start
        self.profile_end = profile_start + timestep_duration * nr_of_timesteps
        self.profile_duration = timedelta(milliseconds=timestep_duration.total_seconds() * nr_of_timesteps)
        self.timestep_duration = timestep_duration
        self.nr_of_timesteps = nr_of_timesteps

    def get_profile_start(self) -> datetime:
        return self.profile_start

    def get_profile_end(self) -> datetime:
        return self.profile_start + self.timestep_duration * self.nr_of_timesteps

    def get_timestep_duration(self) -> timedelta:
        return self.timestep_duration

    def get_nr_of_timesteps(self) -> int:
        return self.nr_of_timesteps

    def get_profile_start_at_timestep_nr(self, timestep_nr: int) -> datetime:
        if timestep_nr >= self.get_nr_of_timesteps() or self.get_nr_of_timesteps() < 0:
            raise ValueError(
                f"Expected timestep_nr to be between 0 <= timestep_nr < {self.get_nr_of_timesteps()} but was {timestep_nr}"
            )
        return self.profile_start + self.timestep_duration * timestep_nr

    def get_starting_step_nr(self, instant: datetime) -> int:
        if instant < self.profile_start:
            return -1
        if instant > self.get_profile_end():
            return self.get_nr_of_timesteps()
        return (int)(
            (instant.timestamp() - self.get_profile_start().timestamp()) / self.get_timestep_duration().total_seconds()
        )

    def is_aligned_with(self, other: "ProfileMetadata") -> bool:
        return (
            self.timestep_duration == other.timestep_duration
            and (self.profile_start - other.profile_start).total_seconds() % self.timestep_duration.total_seconds() == 0
        )

    def adjust_nr_of_timesteps(self, nr_of_timesteps: int) -> "ProfileMetadata":
        return ProfileMetadata(self.profile_start, self.timestep_duration, nr_of_timesteps)

    def subprofile(self, new_start_date: datetime) -> "ProfileMetadata":
        if new_start_date < self.profile_start:
            raise ValueError("new_start_date is before profile_start")
        if new_start_date > self.get_profile_end():
            raise ValueError("new_start_date is after profile_end")
        new_start_date = AbstractProfile.next_aligned_date(new_start_date, self.get_timestep_duration())
        skipped_steps = (int)(
            (new_start_date.timestamp() - self.get_profile_start().timestamp())
            / self.get_timestep_duration().total_seconds()
        )
        new_nr_of_timesteps = self.get_nr_of_timesteps() - skipped_steps
        return ProfileMetadata(new_start_date, self.get_timestep_duration(), new_nr_of_timesteps)

    def __eq__(self, other) -> bool:
        if not isinstance(other, ProfileMetadata):
            return False
        return (
            self.profile_start == other.profile_start
            and self.timestep_duration == other.timestep_duration
            and self.nr_of_timesteps == other.nr_of_timesteps
        )

    def __str__(self) -> str:
        return (
            f"ProfileMetadata [profileStart={self.profile_start}, "
            f"timestepDuration={self.timestep_duration}, "
            f"nrOfTimesteps={self.nr_of_timesteps}, "
            f"getProfileEnd()={self.get_profile_end()}]"
        )
