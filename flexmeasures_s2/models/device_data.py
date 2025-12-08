from dataclasses import dataclass, field
from logging import Logger

from s2python.frbc import (
    FRBCSystemDescription,
    FRBCFillLevelTargetProfile,
    FRBCStorageStatus,
    FRBCActuatorStatus,
    FRBCInstruction,
    FRBCUsageForecast,
    FRBCLeakageBehaviour,
)


@dataclass
class FRBCDeviceData:
    """Data store for FRBC device data received from RM."""

    resource_id: str | None = None
    system_description: FRBCSystemDescription | None = None
    storage_status: FRBCStorageStatus | None = None
    # status per actuator_id
    actuator_statuses: dict[str, FRBCActuatorStatus] = field(default_factory=dict)
    fill_level_target_profile: FRBCFillLevelTargetProfile | None = None
    usage_forecast: FRBCUsageForecast | None = None
    leakage_behaviour: FRBCLeakageBehaviour | None = None
    # list of instructions
    instructions: list[FRBCInstruction] = field(default_factory=list)
    # internal / non-init field
    logger: Logger | None = field(default=None, init=False, repr=False)

    def is_complete(self) -> bool:
        """Check if we have received all necessary data to generate instructions."""

        # System description and storage status are always required
        if self.system_description is None or self.storage_status is None:
            return False

        # Fill level target profile OR usage forecast should be provided (at least one)
        # Both are optional individually, but at least one should exist for meaningful planning
        if not (
            self.fill_level_target_profile is not None
            or self.usage_forecast is not None
        ):
            return False

        # Check that we have actuator status for ALL actuators in system description
        if self.system_description.actuators:
            required_ids = {str(a.id) for a in self.system_description.actuators}
            received_ids = set(self.actuator_statuses.keys())
            return required_ids.issubset(received_ids)

        return True
