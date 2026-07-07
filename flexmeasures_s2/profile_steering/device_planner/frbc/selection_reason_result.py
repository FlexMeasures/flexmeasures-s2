from enum import Enum


class SelectionReason(Enum):
    CONGESTION_CONSTRAINT = "C"
    ENERGY_TARGET = "E"
    TARIFF_TARGET = "T"
    MIN_ENERGY = "M"
    NO_ALTERNATIVE = "_"
    EMERGENCY_STATE = "!"


class SelectionResult:
    def __init__(
        self,
        result: bool,
        reason: SelectionReason,
    ):
        self.result = result
        self.reason = reason
