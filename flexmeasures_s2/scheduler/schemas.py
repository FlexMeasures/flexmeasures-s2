from flexmeasures.data.schemas import AwareDateTimeField, DurationField

from marshmallow import Schema, fields


class S2FlexModelSchema(Schema): ...


class TNOTargetProfile(Schema):
    start = AwareDateTimeField()
    duration = DurationField()
    values = fields.List(fields.Float)


class TNOFlexContextSchema(Schema):
    target_profile = fields.Nested(TNOTargetProfile())
