from pydantic import BaseModel


class FlexMeasuresBaseModel(BaseModel):
    """Base model for FlexMeasures S2 with arbitrary types allowed."""

    class Config:
        arbitrary_types_allowed = True
