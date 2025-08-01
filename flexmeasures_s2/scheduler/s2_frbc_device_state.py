from s2python.frbc import (
    FRBCSystemDescription,
)

from typing import List
from pydantic import BaseModel
from pydantic.config import ConfigDict


class S2FrbcDeviceState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    system_descriptions: List[FRBCSystemDescription]
