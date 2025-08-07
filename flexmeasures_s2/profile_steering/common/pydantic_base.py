from pydantic import BaseModel
from pydantic.config import ConfigDict


class ReflexBaseModel(BaseModel):
    """Base model for FlexMeasures S2 with arbitrary types allowed."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
