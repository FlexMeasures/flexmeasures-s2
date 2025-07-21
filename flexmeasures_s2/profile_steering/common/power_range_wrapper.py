import math
from typing import Any


class PowerRangeWrapper:
    def __init__(self, unwrapped_range: Any):
        self.start_of_range: float = float(unwrapped_range.start_of_range)
        self.end_of_range: float = float(unwrapped_range.end_of_range)
        self.commodity_quantity: Any = unwrapped_range.commodity_quantity

    def get_start_of_range(self) -> float:
        return self.start_of_range

    def get_end_of_range(self) -> float:
        return self.end_of_range

    def get_commodity_quantity(self) -> Any:
        return self.commodity_quantity

    def get_power(self, factor: float) -> float:
        return ((self.end_of_range - self.start_of_range) * factor) + self.start_of_range

    def __eq__(self, o: object) -> bool:
        if self is o:
            return True
        if not isinstance(o, PowerRangeWrapper):
            return False
        that = o
        return (
            math.isclose(that.start_of_range, self.start_of_range)
            and math.isclose(that.end_of_range, self.end_of_range)
            and self.commodity_quantity == that.commodity_quantity
        )

    def __hash__(self) -> int:
        return hash((self.start_of_range, self.end_of_range, self.commodity_quantity))

    def __str__(self) -> str:
        return (
            f"PowerRangeWrapper("
            f"startOfRange={self.start_of_range}, "
            f"endOfRange={self.end_of_range}, "
            f"commodityQuantity={self.commodity_quantity})"
        )
