# TODO: Is this the same as FRBCUsageForecast?


from datetime import datetime, timedelta
from s2python.frbc import FRBCUsageForecast, FRBCUsageForecastElement


class UsageForecastElement:
    def __init__(self, start, end, usage_rate):
        self.start = start
        self.end = end
        self.usage_rate = usage_rate

    def get_usage(self):
        seconds = (self.end - self.start).total_seconds() + 1
        return seconds * self.usage_rate

    def split(self, date):
        if self.date_in_element(date):
            return [
                UsageForecastElement(self.start, date, self.usage_rate),
                UsageForecastElement(date, self.end, self.usage_rate),
            ]
        return []

    def date_in_element(self, date):
        return self.start <= date <= self.end


class UsageForecastUtil:
    @staticmethod
    def from_storage_usage_profile(usage_forecast):
        elements = []
        start = usage_forecast.get_start_time()
        for element in usage_forecast.get_elements():
            end = start + timedelta(seconds=element.get_duration())
            elements.append(
                UsageForecastElement(start, end, element.get_usage_rate_expected())
            )
            start = end + timedelta(milliseconds=1)
        return elements
