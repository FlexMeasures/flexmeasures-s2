from datetime import datetime
from typing import List, Dict, Any, Optional


class ClusterState:
    """Class representing the state of a cluster of devices."""

    def __init__(
        self,
        timestamp: datetime,
        device_states: Dict[str, Any] = {},
        congestion_points_by_connection_id: Dict[str, str] = {},
    ):
        self._timestamp = timestamp
        self._device_states = device_states or {}
        self._congestion_points_by_connection_id = (
            congestion_points_by_connection_id or {}
        )

    def set_device_states(self, device_states: Dict[str, Any]):
        self._device_states = device_states or {}

    def get_device_states(self) -> Dict[str, Any]:
        return self._device_states

    def get_congestion_point(self, connection_id: str) -> Optional[str]:
        return self._congestion_points_by_connection_id.get(connection_id)

    def set_congestion_point(self, connection_id: str, congestion_point_id: str):
        self._congestion_points_by_connection_id[connection_id] = congestion_point_id

    def get_congestion_points(self) -> List[str]:
        return list(set(self._congestion_points_by_connection_id.values()))
