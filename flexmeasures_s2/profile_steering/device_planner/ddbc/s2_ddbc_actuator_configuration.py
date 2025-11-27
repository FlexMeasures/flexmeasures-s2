from typing import Dict, Optional
from flexmeasures_s2.profile_steering.common.s2_actuator_configuration import (
    S2ActuatorConfiguration,
)


class S2DdbcActuatorConfiguration(S2ActuatorConfiguration):
    """Configuration for a DDBC actuator including power per commodity and supply rate."""

    def __init__(
        self,
        operation_mode_id: str,
        factor: Optional[float],
        supply_rate: Optional[float],
        power_per_commodity_quantity: Dict[str, float],
    ):
        super().__init__(operation_mode_id, factor)
        self.supply_rate = supply_rate
        self.power_per_commodity_quantity = power_per_commodity_quantity

    def get_supply_rate(self) -> Optional[float]:
        return self.supply_rate

    def get_power_per_commodity_quantity(self) -> Dict[str, float]:
        return self.power_per_commodity_quantity

    def to_dict(self) -> Dict:
        return {
            "operationModeId": self.operation_mode_id,
            "factor": self.factor,
            "supplyRate": self.supply_rate,
            "powerPerCommodityQuantity": self.power_per_commodity_quantity,
        }

    @staticmethod
    def from_dict(data: Dict):
        return S2DdbcActuatorConfiguration(
            data["operationModeId"],
            data.get("factor"),
            data.get("supplyRate"),
            data.get("powerPerCommodityQuantity", {}),
        )

    def __str__(self):
        return (
            f"S2DdbcActuatorConfiguration["
            f"operationModeId={self.operation_mode_id}, "
            f"factor={self.factor}, "
            f"supplyRate={self.supply_rate}, "
            f"powerPerCommodityQuantity={self.power_per_commodity_quantity}]"
        )

    def __repr__(self):
        return (
            f"S2DdbcActuatorConfiguration["
            f"operationModeId={self.operation_mode_id}, "
            f"factor={self.factor}, "
            f"supplyRate={self.supply_rate}, "
            f"powerPerCommodityQuantity={self.power_per_commodity_quantity}]"
        )
