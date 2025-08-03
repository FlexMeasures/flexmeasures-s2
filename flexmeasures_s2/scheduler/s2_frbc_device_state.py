from s2python.frbc import (
    FRBCSystemDescription,
)

from typing import List
from flexmeasures_s2.profile_steering.common.pydantic_base import ReflexBaseModel


class S2FrbcDeviceState(ReflexBaseModel):

    system_descriptions: List[FRBCSystemDescription]
