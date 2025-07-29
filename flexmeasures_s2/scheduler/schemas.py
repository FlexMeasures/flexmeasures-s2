from __future__ import annotations
from pydantic import BaseModel


class PowerValue(BaseModel):
    value: float


class Schedule(BaseModel):
    values: list[PowerValue]
