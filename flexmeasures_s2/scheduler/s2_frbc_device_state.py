from s2python.frbc import (
    FRBCSystemDescription,
)

from typing import List
from flexmeasures_s2.profile_steering.common.pydantic_base import FlexMeasuresBaseModel


class S2FrbcDeviceState(FlexMeasuresBaseModel):

    system_descriptions: List[FRBCSystemDescription]
