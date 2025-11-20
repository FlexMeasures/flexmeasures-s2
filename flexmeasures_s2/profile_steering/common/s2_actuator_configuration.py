class S2ActuatorConfiguration:
    def __init__(self, operation_mode_id, factor):
        self.operation_mode_id = operation_mode_id
        self.factor = factor

    def get_operation_mode_id(self):
        return self.operation_mode_id

    def get_factor(self):
        return self.factor

    def to_dict(self):
        return {"operationModeId": self.operation_mode_id, "factor": self.factor}

    @staticmethod
    def from_dict(data):
        return S2ActuatorConfiguration(data["operationModeId"], data["factor"])

    def __str__(self):
        return f"S2ActuatorConfiguration [operationModeId={self.operation_mode_id}, factor={self.factor}]"
