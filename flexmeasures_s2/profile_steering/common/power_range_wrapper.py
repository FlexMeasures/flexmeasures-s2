from dataclasses import dataclass
import math
from typing import Any


@dataclass(frozen=True)
class PowerRangeWrapper:
    start_of_range: float
    end_of_range: float
    commodity_quantity: Any

    def get_power(self, factor: float) -> float:
        """Calculate the power at a given factor."""
        return (self.end_of_range - self.start_of_range) * factor + self.start_of_range

    def __str__(self) -> str:
        return (
            f"PowerRangeWrapper("
            f"startOfRange={self.start_of_range}, "
            f"endOfRange={self.end_of_range}, "
            f"commodityQuantity={self.commodity_quantity})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PowerRangeWrapper):
            return False
        return (
            math.isclose(self.start_of_range, other.start_of_range)
            and math.isclose(self.end_of_range, other.end_of_range)
            and self.commodity_quantity == other.commodity_quantity
        )

    def __hash__(self) -> int:
        return hash((self.start_of_range, self.end_of_range, self.commodity_quantity))

    @classmethod
    def from_unwrapped(cls, unwrapped_range: Any) -> "PowerRangeWrapper":
        """Factory method to create a PowerRangeWrapper from an unwrapped object."""
        return cls(
            start_of_range=float(unwrapped_range.start_of_range),
            end_of_range=float(unwrapped_range.end_of_range),
            commodity_quantity=unwrapped_range.commodity_quantity,
        )
