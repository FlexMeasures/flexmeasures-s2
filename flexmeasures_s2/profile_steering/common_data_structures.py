from datetime import datetime
from typing import List, Dict, Any, Optional

from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile


class ClusterState:
    """Class representing the state of a cluster of devices."""

    def __init__(self, device_states: Dict[str, Any] = None):
        self._device_states = device_states or {}
        self._congestion_points = {}  # Map from connection ID to congestion point ID

    def get_device_states(self) -> Dict[str, Any]:
        return self._device_states

    def get_congestion_point(self, connection_id: str) -> Optional[str]:
        return self._congestion_points.get(connection_id)

    def set_congestion_point(self, connection_id: str, congestion_point_id: str):
        self._congestion_points[connection_id] = congestion_point_id

    def get_congestion_points(self) -> List[str]:
        return list(set(self._congestion_points.values()))


class DevicePlan:
    """Class representing a plan for a device."""

    def __init__(self, device_id: str, profile: JouleProfile):
        self._device_id = device_id
        self._profile = profile

    def get_device_id(self) -> str:
        return self._device_id

    def get_connection_id(self) -> str:
        """Get the connection ID for this device plan.

        This is often the same as the device ID but might be different in some cases.

        Returns:
            The connection ID
        """
        return self._device_id

    def get_profile(self) -> JouleProfile:
        return self._profile 
