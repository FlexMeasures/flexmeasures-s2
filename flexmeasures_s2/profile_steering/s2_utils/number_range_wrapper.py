class NumberRangeWrapper:
    def __init__(self, start_of_range, end_of_range):
        self.start_of_range = start_of_range
        self.end_of_range = end_of_range

    def get_start_of_range(self):
        return self.start_of_range

    def get_end_of_range(self):
        return self.end_of_range

    def __eq__(self, other):
        if not isinstance(other, NumberRangeWrapper):
            return False
        return (
            self.start_of_range == other.start_of_range
            and self.end_of_range == other.end_of_range
        )

    def __hash__(self):
        return hash((self.start_of_range, self.end_of_range))

    def __str__(self):
        return f"NumberRangeWrapper(startOfRange={self.start_of_range}, endOfRange={self.end_of_range})"
