from __future__ import annotations
from pydantic import BaseModel


class PowerValue(BaseModel):
    value: float


class Schedule(BaseModel):
    values: list[PowerValue]


class S2FlexModelSchema(BaseModel):
    """Schema for S2 Flex Model validation."""

    def load(self, data):
        """Load and validate data."""
        return data  # Pass-through for now


class TNOFlexContextSchema(BaseModel):
    """Schema for TNO Flex Context validation."""

    def load(self, data):
        """Load and validate data."""
        return data  # Pass-through for now


class TNOTargetProfile(BaseModel):
    """Schema for TNO Target Profile validation."""

    def load(self, data):
        """Load and validate data."""
        return data  # Pass-through for now
