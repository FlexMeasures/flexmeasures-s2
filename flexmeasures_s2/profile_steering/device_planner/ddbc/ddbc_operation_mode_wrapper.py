from s2python.ddbc import DDBCOperationMode
from s2python.common import CommodityQuantity
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_plan import (
    S2DdbcActuatorConfiguration,
)


class DdbcOperationModeWrapper:
    """Wrapper for DDBC operation modes with utility methods."""

    def __init__(self, operation_mode: DDBCOperationMode):
        self.operation_mode = operation_mode
        self.id = str(operation_mode.id)
        self.diagnostic_label = operation_mode.diagnostic_label

        # Extract supply range
        if operation_mode.supply_range and len(operation_mode.supply_range) > 0:
            supply_range = operation_mode.supply_range[0]
            self.min_supply = supply_range.start_of_range
            self.max_supply = supply_range.end_of_range
        else:
            self.min_supply = 0.0
            self.max_supply = 0.0

        # Extract power ranges
        self.electrical_power_range = None
        self.gas_power_range = None

        for power_range in operation_mode.power_ranges:
            if power_range.commodity_quantity in [
                CommodityQuantity.ELECTRIC_POWER_L1,
                CommodityQuantity.ELECTRIC_POWER_L2,
                CommodityQuantity.ELECTRIC_POWER_L3,
                CommodityQuantity.ELECTRIC_POWER_3_PHASE_SYMMETRIC,
            ]:
                self.electrical_power_range = power_range
            elif (
                power_range.commodity_quantity
                == CommodityQuantity.NATURAL_GAS_FLOW_RATE
            ):
                self.gas_power_range = power_range

    def get_supply_rate(self, factor: float) -> float:
        """Get the supply rate for a given operation mode factor."""
        return self.min_supply + (self.max_supply - self.min_supply) * factor

    def get_electrical_power(self, factor: float) -> float:
        """Get electrical power consumption for a given factor."""
        if self.electrical_power_range is None:
            return 0.0
        return (
            self.electrical_power_range.start_of_range
            + (
                self.electrical_power_range.end_of_range
                - self.electrical_power_range.start_of_range
            )
            * factor
        )

    def get_gas_power(self, factor: float) -> float:
        """Get gas consumption for a given factor."""
        if self.gas_power_range is None:
            return 0.0
        return (
            self.gas_power_range.start_of_range
            + (self.gas_power_range.end_of_range - self.gas_power_range.start_of_range)
            * factor
        )

    def convert_to_actuator_config(self, factor: float) -> S2DdbcActuatorConfiguration:
        """Convert to actuator configuration with the given factor."""
        return S2DdbcActuatorConfiguration(
            operation_mode_id=self.id,
            factor=factor,
        )
