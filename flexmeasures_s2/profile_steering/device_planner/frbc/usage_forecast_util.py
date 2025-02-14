# TODO: Is this the same as FRBCUsageForecast?


from datetime import timedelta


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
        start = usage_forecast.start_time
        for element in usage_forecast.elements:
            end = start + timedelta(seconds=element.duration.__root__)
            elements.append(
                UsageForecastElement(start, end, element.usage_rate_expected)
            )
            start = end + timedelta(milliseconds=1)
        return elements

    def sub_profile(usage_forecast, timeStepStart, timeStepEnd):
        if usage_forecast is None:
            return 0
        timeStepEnd -= timedelta(milliseconds=1)
        usage = 0
        timeStepStart = timeStepStart.replace(tzinfo=None)
        timeStepEnd = timeStepEnd.replace(tzinfo=None)
        for element in usage_forecast:
            element_start = element.start.replace(tzinfo=None)
            element_end = element.end.replace(tzinfo=None)
            if element_start <= timeStepEnd and element_end >= timeStepStart:
                usage += element.get_usage()
        return usage
