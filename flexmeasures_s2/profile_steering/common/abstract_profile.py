from abc import ABC, abstractmethod
from typing import List, TypeVar, Generic, Optional
from datetime import datetime, timedelta
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata

E = TypeVar("E")
PT = TypeVar("PT", bound="AbstractProfile")


class AbstractProfile(ABC, Generic[E, PT]):
    def __init__(
        self,
        profile_metadata: Optional[ProfileMetadata] = None,
        elements: Optional[List[E]] = None,
        profile_start: Optional[datetime] = None,
        timestep_duration: Optional[timedelta] = None,
        value: Optional[E] = None,
        nr_of_elements: Optional[int] = None,
    ):
        """
        Initialize an AbstractProfile with various parameter combinations.

        Args:
            profile_metadata: ProfileMetadata object containing start time and duration
            elements: List of profile elements
            profile_start: Start time of the profile
            timestep_duration: Duration of each timestep
            value: Single value to fill the entire profile
            nr_of_elements: Number of elements when using a single value
        """
        # Case 1: Initialize with metadata and elements
        if profile_metadata is not None and elements is not None:
            self.metadata = profile_metadata
            self.elements = elements
            self.validate(profile_metadata, elements)
            return

        # Case 2: Initialize with start time, duration and elements
        if (
            profile_start is not None
            and timestep_duration is not None
            and elements is not None
        ):
            self.metadata = ProfileMetadata(
                profile_start, timestep_duration, len(elements)
            )
            self.elements = elements
            self.validate(self.metadata, elements)
            return

        # Case 3: Initialize with start time, duration, single value and number of elements
        if (
            profile_start is not None
            and timestep_duration is not None
            and value is not None
            and nr_of_elements is not None
        ):
            self.elements = [value] * nr_of_elements
            self.metadata = ProfileMetadata(
                profile_start, timestep_duration, nr_of_elements
            )
            self.validate(self.metadata, self.elements)
            return

        # Case 4: Empty initialization (for serialization)
        self.metadata = None
        self.elements = []

    @abstractmethod
    def validate(self, profile_metadata: ProfileMetadata, elements: List[E]):
        if elements is None:
            raise ValueError("elements cannot be null")
        if (
            24 * 60 * 60 * 1000
        ) % profile_metadata.timestep_duration.total_seconds() * 1000 != 0:
            raise ValueError("A day should be dividable by the timeStepDuration")
        if (
            not self.start_of_current_aligned_date(
                profile_metadata.profile_start,
                profile_metadata.timestep_duration,
            )
            == profile_metadata.profile_start
        ):
            raise ValueError(
                "The startTimeDuration should be aligned with the timeStepDuration"
            )

    def get_profile_metadata(self) -> ProfileMetadata:
        return self.metadata

    def get_elements(self) -> List[E]:
        return self.elements

    def get_element_end_date_at(self, index: int) -> datetime:
        return self.metadata.get_profile_start_at_timestep(index + 1)

    def index_at(self, date: datetime) -> int:
        return self.metadata.get_starting_step_nr(date)

    def element_at(self, date: datetime) -> E:
        index = self.index_at(date)
        if index >= 0:
            return self.elements[index]
        raise ValueError(f"No element found at date - index {index} is invalid")

    @staticmethod
    def next_aligned_date(date: datetime, time_step_duration: timedelta) -> datetime:
        time_step_duration_ms = time_step_duration.total_seconds() * 1000
        ms_since_last_aligned_date = (date.timestamp() * 1000) % time_step_duration_ms

        if ms_since_last_aligned_date == 0:
            return date
        else:
            return date + timedelta(
                milliseconds=(time_step_duration_ms - ms_since_last_aligned_date)
            )

    @staticmethod
    def start_of_current_aligned_date(
        date: datetime, time_step_duration: timedelta
    ) -> datetime:
        ms_since_last_aligned_date = (
            (date.timestamp() * 1000) % time_step_duration.total_seconds() * 1000
        )
        if ms_since_last_aligned_date == 0:
            return date
        else:
            return datetime.fromtimestamp(
                date.timestamp() - ms_since_last_aligned_date / 1000
            )

    @staticmethod
    def end_of_current_aligned_date(
        date: datetime, time_step_duration: timedelta
    ) -> datetime:
        return (
            AbstractProfile.start_of_current_aligned_date(date, time_step_duration)
            + time_step_duration
        )

    @staticmethod
    def get_start_of_day(date: datetime) -> datetime:
        return datetime.combine(date.date(), datetime.min.time())

    @abstractmethod
    def subprofile(self, new_start_date: datetime) -> PT:
        pass

    @abstractmethod
    def adjust_nr_of_elements(self, nr_of_elements: int) -> PT:
        pass

    @abstractmethod
    def is_compatible(self, other: PT) -> bool:
        return self.metadata == other.metadata

    @abstractmethod
    def default_value(self) -> E:
        pass
