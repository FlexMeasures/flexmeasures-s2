# TODO: Is this the same as FRBCUsageForecast?


from datetime import timedelta, timezone
from typing import List


class UsageForecastElement:
    def __init__(self, start, end, usage_rate):
        self.start = start.replace(tzinfo=None)
        self.end = end.replace(tzinfo=None)
        self.usage_rate = usage_rate

    def get_usage(self):
        seconds = (
            self.end - self.start
        ).total_seconds() + 0.001  # one milisecond added for the offeset from total_Seconds()
        return seconds * self.usage_rate

    def split(self, date):
        if self.date_in_element(date):
            return [
                UsageForecastElement(self.start, date, self.usage_rate),
                UsageForecastElement(date, self.end, self.usage_rate),
            ]
        # If the date is not within the range, return the element itself twice to avoid index errors
        return [self, self]

    def date_in_element(self, date):
        # Ensure both self.start and self.end are offset-naive or offset-aware
        if self.start.tzinfo is None and self.end.tzinfo is None:
            # Make date offset-naive
            date = date.replace(tzinfo=None)
        elif self.start.tzinfo is not None and self.end.tzinfo is not None:
            # Make date offset-aware with the same timezone as self.start
            date = date.astimezone(self.start.tzinfo)
        else:
            # If there's a mismatch, raise an error or handle it appropriately
            raise ValueError("Mismatch between offset-naive and offset-aware datetimes")

        return self.start <= date <= self.end


class UsageForecastUtil:
    @staticmethod
    def from_storage_usage_profile(usage_forecast):
        elements = []
        start = usage_forecast.start_time
        start = start.astimezone(timezone.utc)
        for element in usage_forecast.elements:
            end = start + timedelta(seconds=element.duration.__root__)
            elements.append(
                UsageForecastElement(start, end, element.usage_rate_expected)
            )
            start = end + timedelta(milliseconds=1)
        return elements

    @staticmethod
    def sub_profile(
        usage_forecast: List[UsageForecastElement], time_step_start, time_step_end
    ):
        if usage_forecast is None:
            return 0

        usage = 0
        time_step_start = time_step_start.replace(tzinfo=None)
        time_step_end = time_step_end.replace(tzinfo=None)

        for element in usage_forecast:
            element_start = element.start.replace(tzinfo=None)
            element_end = element.end.replace(tzinfo=None)

            if element_start < time_step_start < element_end < time_step_end:
                # case 1: ....s.....e
                # case 1: |-------|..
                split = element.split(time_step_start)
                usage += split[1].get_usage()
            elif element_start > time_step_start and element_end < time_step_end:
                # case 2: s...........e
                # case 2: ..|-------|..
                usage += element.get_usage()
            elif time_step_start < element_start < time_step_end < element_end:
                # case 3: s.....e....
                # case 3: ..|-------|
                split = element.split(time_step_end)
                usage += split[0].get_usage()
            elif element_start < time_step_start and element_end > time_step_end:
                # case 4: ....s...e....
                # case 4: |-----------|
                split1 = element.split(time_step_start)
                split2 = split1[1].split(time_step_end)
                usage += split2[0].get_usage()
            elif element_start == time_step_start and element_end == time_step_end:
                # case 5: s...........e
                # case 5: |-----------|
                usage += element.get_usage()
            elif element_start == time_step_start and element_end > time_step_end:
                # case 6: s.....e......
                # case 6: |-----------|
                split = element.split(time_step_end)
                usage += split[0].get_usage()
            elif element_start == time_step_start and element_end < time_step_end:
                # case 7: s...............e
                # case 7: |-----------|....
                usage += element.get_usage()
            elif element_start < time_step_start and element_end == time_step_end:
                # case 8: ......s.....e
                # case 8: |-----------|
                split = element.split(time_step_start)
                usage += split[1].get_usage()
            elif element_start > time_step_start and element_end == time_step_end:
                # case 9: s...........e
                # case 9: ...|--------|
                usage += element.get_usage()

        return usage
