import math
from typing import Any, Optional


class NumberRangeWrapper:
    """Wrapper for CommonNumberRange to provide utility methods."""

    def __init__(
        self,
        unwrapped_range: Any = None,
        start_of_range: Optional[float] = None,
        end_of_range: Optional[float] = None,
    ):
        """Initialize from either an unwrapped range object or explicit values."""
        if unwrapped_range is not None:
            self.start_of_range: float = float(unwrapped_range.start_of_range)
            self.end_of_range: float = float(unwrapped_range.end_of_range)
        else:
            assert (
                start_of_range is not None and end_of_range is not None
            ), "start_of_range and end_of_range must be provided if unwrapped_range is None"
            self.start_of_range = start_of_range
            self.end_of_range = end_of_range

    def get_start_of_range(self) -> float:
        return self.start_of_range

    def get_end_of_range(self) -> float:
        return self.end_of_range

    def __eq__(self, o: object) -> bool:
        if self is o:
            return True
        if not isinstance(o, NumberRangeWrapper):
            return False
        that = o
        return math.isclose(that.start_of_range, self.start_of_range) and math.isclose(
            that.end_of_range, self.end_of_range
        )

    def __hash__(self) -> int:
        return hash((self.start_of_range, self.end_of_range))

    def __str__(self) -> str:
        return (
            f"NumberRangeWrapper("
            f"startOfRange={self.start_of_range}, "
            f"endOfRange={self.end_of_range})"
        )
