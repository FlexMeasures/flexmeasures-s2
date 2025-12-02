from dataclasses import dataclass
from typing import Optional


@dataclass
class S2ActuatorConfiguration:
    operation_mode_id: str
    factor: Optional[float]
