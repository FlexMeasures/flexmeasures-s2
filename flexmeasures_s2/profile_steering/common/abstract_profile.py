from abc import ABC, abstractmethod
from typing import List, TypeVar, Generic
from datetime import datetime, timedelta
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata

E = TypeVar("E")
PT = TypeVar("PT", bound="AbstractProfile")


class AbstractProfile(ABC, Generic[E, PT]):
    def __init__(self, profile_metadata: ProfileMetadata, elements: List[E]):
        self.metadata = profile_metadata
        self.elements = elements
        self.validate(profile_metadata, elements)

    @abstractmethod
    def validate(self, profile_metadata: ProfileMetadata, elements: List[E]):
        if elements is None:
            raise ValueError("elements cannot be null")
        if (
            24 * 60 * 60 * 1000
        ) % profile_metadata.get_timestep_duration().total_seconds() != 0:
            raise ValueError("A day should be dividable by the timeStepDuration")
        if (
            not self.start_of_current_aligned_date(
                profile_metadata.get_profile_start(),
                profile_metadata.get_timestep_duration(),
            )
            == profile_metadata.get_profile_start()
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
