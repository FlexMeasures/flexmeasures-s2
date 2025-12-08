from typing import Dict, Optional, List

from s2python.frbc import (
    FRBCSystemDescription,
    FRBCFillLevelTargetProfile,
    FRBCStorageStatus,
    FRBCActuatorStatus,
    FRBCInstruction,
    FRBCUsageForecast,
    FRBCLeakageBehaviour,
)


class FRBCDeviceData:
    """Class to store FRBC device data received from Resource Manager."""

    def __init__(self):
        self.system_description: Optional[FRBCSystemDescription] = None
        self.fill_level_target_profile: Optional[FRBCFillLevelTargetProfile] = None
        self.storage_status: Optional[FRBCStorageStatus] = None
        self.actuator_statuses: Dict[
            str, FRBCActuatorStatus
        ] = {}  # Changed to dict by actuator_id
        self.usage_forecast: Optional[FRBCUsageForecast] = None
        self.leakage_behaviour: Optional[FRBCLeakageBehaviour] = None
        self.resource_id: Optional[str] = None
        self.instructions: Optional[List[FRBCInstruction]] = []
        self.logger = None

    def is_complete(self) -> bool:
        """Check if we have received all necessary data to generate instructions."""
        # System description and storage status are always required
        if self.system_description is None or self.storage_status is None:
            return False

        # Fill level target profile OR usage forecast should be provided (at least one)
        # Both are optional individually, but at least one should exist for meaningful planning
        has_fill_level_target = self.fill_level_target_profile is not None
        has_usage_forecast = self.usage_forecast is not None

        if not (has_fill_level_target or has_usage_forecast):
            return False

        # Check that we have actuator status for ALL actuators in system description
        if self.system_description.actuators:
            required_actuator_ids = {
                str(actuator.id) for actuator in self.system_description.actuators
            }
            received_actuator_ids = set(self.actuator_statuses.keys())
            return required_actuator_ids.issubset(received_actuator_ids)

        return True
