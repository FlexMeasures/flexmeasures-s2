from datetime import timedelta


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
        start = fill_level_target_profile.get_start_time()
        for element in fill_level_target_profile.get_elements():
            end = start + timedelta(seconds=element.get_duration())
            elements.append(
                FillLevelTargetElement(
                    start,
                    end,
                    element.get_fill_level_range().get_start_of_range(),
                    element.get_fill_level_range().get_end_of_range(),
                )
            )
            start = end + timedelta(milliseconds=1)
        return elements
