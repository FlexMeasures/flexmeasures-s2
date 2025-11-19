from datetime import timedelta, timezone


class FillLevelTargetElement:
    def __init__(self, start, end, lower_limit, upper_limit):
        self.start = start
        self.end = end
        self.lower_limit = lower_limit
        self.upper_limit = upper_limit

    def split(self, date):
        if self.date_in_element(date):
            return [
                FillLevelTargetElement(
                    self.start, date, self.lower_limit, self.upper_limit
                ),
                FillLevelTargetElement(
                    date, self.end, self.lower_limit, self.upper_limit
                ),
            ]
        return []

    def date_in_element(self, date):
        return self.start <= date <= self.end


class FillLevelTargetUtil:
    @staticmethod
    def from_fill_level_target_profile(fill_level_target_profile):
        elements = []
        start = fill_level_target_profile.start_time.astimezone(timezone.utc)
        for element in fill_level_target_profile.elements:
            # Extract duration value - handle both int and Duration object
            duration = element.duration
            if isinstance(duration, (int, float)):
                duration_ms = int(duration)
            elif hasattr(duration, "root"):
                duration_ms = int(duration.root)
            elif hasattr(duration, "__root__"):
                duration_ms = int(duration.__root__)
            else:
                try:
                    duration_ms = int(duration)
                except (TypeError, ValueError):
                    duration_ms = int(str(duration))

            end = start + timedelta(milliseconds=duration_ms)
            elements.append(
                FillLevelTargetElement(
                    start,
                    end,
                    element.fill_level_range.start_of_range,
                    element.fill_level_range.end_of_range,
                )
            )
            start = end + timedelta(milliseconds=1)
        return elements

    @staticmethod
    def get_elements_in_range(target_profile, start, end):
        elements_in_range = []
        start = start.replace(tzinfo=None)
        end = end.replace(tzinfo=None)
        for element in target_profile:
            element_start = element.start.replace(tzinfo=None)
            element_end = element.end.replace(tzinfo=None)
            if element_start <= end and element_end >= start:
                elements_in_range.append(element)
        return elements_in_range
