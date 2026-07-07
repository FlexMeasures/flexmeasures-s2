from s2python.frbc import (
    FRBCSystemDescription,
)

from typing import List
from pydantic import BaseModel


class S2FrbcDeviceState(BaseModel):
    system_descriptions: List[FRBCSystemDescription]
