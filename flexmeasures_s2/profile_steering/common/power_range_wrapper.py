from s2python.common import PowerRange


class PowerRangeWrapper(PowerRange):
    def get_power(self, factor: float) -> float:
        """Calculate the power at a given factor."""
        return (self.end_of_range - self.start_of_range) * factor + self.start_of_range
