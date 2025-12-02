from dataclasses import dataclass, field
from typing import Any, Optional
from flexmeasures_s2.profile_steering.common.power_range_wrapper import (
    PowerRangeWrapper,
)
from s2python.common import CommodityQuantity, NumberRange


@dataclass
class DdbcOperationModeWrapper:
    """Wrapper for DDBC operation mode to provide utility methods."""

    ddbc_operation_mode: Any
    EPSILON: float = 1e-4
    id: str = field(init=False)
    diagnostic_label: Optional[str] = field(init=False)
    abnormal_condition_only: bool = field(init=False)
    power_ranges: list["PowerRangeWrapper"] = field(init=False, default_factory=list)
    supply_range: NumberRange = field(init=False)
    running_costs: Optional[NumberRange] = field(init=False)
    uses_factor: bool = field(init=False)

    def __post_init__(self):
        # Initialize basic attributes
        self.id = getattr(
            self.ddbc_operation_mode, "Id", getattr(self.ddbc_operation_mode, "id")
        )
        self.diagnostic_label = getattr(
            self.ddbc_operation_mode, "diagnostic_label", None
        )
        self.abnormal_condition_only = getattr(
            self.ddbc_operation_mode, "abnormal_condition_only", False
        )

        # Wrap power ranges
        self.power_ranges = [
            PowerRangeWrapper(**pr.__dict__)
            for pr in self.ddbc_operation_mode.power_ranges
        ]

        # Wrap supply range
        sr = self.ddbc_operation_mode.supply_range
        if isinstance(sr, list):
            self.supply_range = sr[0]
        else:
            self.supply_range = sr

        # Wrap running costs
        self.running_costs = getattr(self.ddbc_operation_mode, "running_costs", None)

        # Determine if this operation mode uses a factor
        self.uses_factor = any(
            abs(r.start_of_range - r.end_of_range) > self.EPSILON
            for r in [self.supply_range, *self.power_ranges]
        )

    @property
    def has_factor(self) -> bool:
        return self.uses_factor

    def get_operation_mode_electrical_power(self, factor: float) -> float:
        """Calculate electrical power consumption for a given factor."""
        electric_commodities = {
            CommodityQuantity.ELECTRIC_POWER_L1,
            CommodityQuantity.ELECTRIC_POWER_L2,
            CommodityQuantity.ELECTRIC_POWER_L3,
            CommodityQuantity.ELECTRIC_POWER_3_PHASE_SYMMETRIC,
        }
        return sum(
            (pr.end_of_range - pr.start_of_range) * factor + pr.start_of_range
            for pr in self.power_ranges
            if pr.commodity_quantity in electric_commodities
        )

    def get_operation_mode_gas_consumption(self, factor: float) -> float:
        """Calculate natural gas consumption (liters per second) for a given factor."""
        return sum(
            (pr.end_of_range - pr.start_of_range) * factor + pr.start_of_range
            for pr in self.power_ranges
            if pr.commodity_quantity == CommodityQuantity.NATURAL_GAS_FLOW_RATE
        )

    def get_operation_mode_supply_rate(self, factor: float) -> float:
        """Calculate supply rate for a given factor."""
        return (
            self.supply_range.end_of_range - self.supply_range.start_of_range
        ) * factor + self.supply_range.start_of_range

    def convert_to_actuator_config(self, factor: float):
        """Convert to S2DdbcActuatorConfiguration."""
        from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_actuator_configuration import (
            S2DdbcActuatorConfiguration,
        )

        power_per_commodity_quantity: dict[str, float] = {
            pr.commodity_quantity.value: pr.get_power(factor)
            for pr in self.power_ranges
        }

        return S2DdbcActuatorConfiguration(
            operation_mode_id=self.id,
            factor=factor,
            supply_rate=self.get_operation_mode_supply_rate(factor),
            power_per_commodity_quantity=power_per_commodity_quantity,
        )
