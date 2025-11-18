from typing import List, Any, Dict, Optional
from flexmeasures_s2.profile_steering.common.power_range_wrapper import (
    PowerRangeWrapper,
)
from flexmeasures_s2.profile_steering.device_planner.ddbc.number_range_wrapper import (
    NumberRangeWrapper,
)
from s2python.common import CommodityQuantity


class DdbcOperationModeWrapper:
    """Wrapper for DDBC operation mode to provide utility methods."""

    EPSILON = 1e-4

    def __init__(self, ddbc_operation_mode: Any):
        """Initialize from a DDBC operation mode."""
        self.id = (
            ddbc_operation_mode.Id
            if hasattr(ddbc_operation_mode, "Id")
            else ddbc_operation_mode.id
        )
        self.diagnostic_label = getattr(ddbc_operation_mode, "diagnostic_label", None)
        self.abnormal_condition_only = getattr(
            ddbc_operation_mode, "abnormal_condition_only", False
        )

        self.power_ranges: List[PowerRangeWrapper] = []
        for unwrapped_power_range in ddbc_operation_mode.power_ranges:
            self.power_ranges.append(PowerRangeWrapper(unwrapped_power_range))

        if isinstance(ddbc_operation_mode.supply_range, list):
            self.supply_range = NumberRangeWrapper(ddbc_operation_mode.supply_range[0])
        else:
            self.supply_range = NumberRangeWrapper(ddbc_operation_mode.supply_range)

        self.running_costs: Optional[NumberRangeWrapper]
        if (
            hasattr(ddbc_operation_mode, "running_costs")
            and ddbc_operation_mode.running_costs is not None
        ):
            self.running_costs = NumberRangeWrapper(ddbc_operation_mode.running_costs)
        else:
            self.running_costs = None

        # Determine if this operation mode uses a factor
        uses_factor = False

        if (
            abs(
                self.supply_range.get_start_of_range()
                - self.supply_range.get_end_of_range()
            )
            > self.EPSILON
        ):
            uses_factor = True

        for power_range in self.power_ranges:
            if (
                abs(power_range.get_start_of_range() - power_range.get_end_of_range())
                > self.EPSILON
            ):
                uses_factor = True

        self.uses_factor = uses_factor

    def get_id(self) -> str:
        # Handle UUID objects with root attribute
        if hasattr(self.id, "root"):
            return str(self.id.root)
        else:
            return str(self.id)

    def get_diagnostic_label(self) -> Optional[str]:
        return self.diagnostic_label

    def get_power_ranges(self) -> List[PowerRangeWrapper]:
        return self.power_ranges

    def get_supply_range(self) -> NumberRangeWrapper:
        return self.supply_range

    def get_running_costs(self) -> Optional[NumberRangeWrapper]:
        return self.running_costs

    def uses_factor_method(self) -> bool:
        return self.uses_factor

    def get_operation_mode_electrical_power(self, factor: float) -> float:
        """Calculate electrical power consumption for a given factor."""
        power_watt = 0.0

        electric_commodities = [
            CommodityQuantity.ELECTRIC_POWER_L1,
            CommodityQuantity.ELECTRIC_POWER_L2,
            CommodityQuantity.ELECTRIC_POWER_L3,
            CommodityQuantity.ELECTRIC_POWER_3_PHASE_SYMMETRIC,
        ]

        for power_range in self.get_power_ranges():
            if power_range.get_commodity_quantity() in electric_commodities:
                start = power_range.get_start_of_range()
                end = power_range.get_end_of_range()
                power_watt += (end - start) * factor + start

        return power_watt

    def get_operation_mode_gas_consumption(self, factor: float) -> float:
        """Calculate natural gas consumption (liters per second) for a given factor."""
        liters_gas_per_second = 0.0

        for power_range in self.get_power_ranges():
            if (
                power_range.get_commodity_quantity()
                == CommodityQuantity.NATURAL_GAS_FLOW_RATE
            ):
                start = power_range.get_start_of_range()
                end = power_range.get_end_of_range()
                liters_gas_per_second += (end - start) * factor + start

        return liters_gas_per_second

    def get_operation_mode_supply_rate(self, factor: float) -> float:
        """Calculate supply rate for a given factor."""
        start = self.get_supply_range().get_start_of_range()
        end = self.get_supply_range().get_end_of_range()
        return (end - start) * factor + start

    def convert_to_actuator_config(self, factor: float):
        """Convert to S2DdbcActuatorConfiguration."""
        from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_actuator_configuration import (
            S2DdbcActuatorConfiguration,
        )

        power_per_commodity_quantity: Dict[str, float] = {}

        for power_range in self.power_ranges:
            commodity_quantity_value = power_range.get_commodity_quantity().value
            power_per_commodity_quantity[
                commodity_quantity_value
            ] = power_range.get_power(factor)

        return S2DdbcActuatorConfiguration(
            operation_mode_id=self.get_id(),
            factor=factor,
            supply_rate=self.get_operation_mode_supply_rate(factor),
            power_per_commodity_quantity=power_per_commodity_quantity,
        )
