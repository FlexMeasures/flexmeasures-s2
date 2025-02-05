class SelectionReason:
    CONGESTION_CONSTRAINT = "C"
    ENERGY_TARGET = "E"
    TARIFF_TARGET = "T"
    MIN_ENERGY = "M"
    NO_ALTERNATIVE = "_"
    EMERGENCY_STATE = "!"


class SelectionResult:
    def __init__(self, result: bool, reason: SelectionReason, timestep: int, system_description: str, previous_state: str, actuator_configurations: str, fill_level: float, bucket: str, timestep_energy: float):
        self.result = result
        self.reason = reason
        self.timestep = timestep
        self.system_description = system_description
        self.previous_state = previous_state
        self.actuator_configurations = actuator_configurations
        self.fill_level = fill_level
        self.bucket = bucket
        self.timestep_energy = timestep_energy
        
    def get_timestep(self):
        return self.timestep

    def get_system_description(self):
        return self.system_description

    def get_previous_state(self):
        return self.previous_state

    def get_actuator_configurations(self):
        return self.actuator_configurations

    def get_fill_level(self):
        return self.fill_level

    def get_bucket(self):
        return self.bucket

    def get_timestep_energy(self):
        return self.timestep_energy

    def get_sum_squared_distance(self):
        return self.sum_squared_distance

    def get_sum_squared_constraint_violation(self):
        return self.sum_squared_constraint_violation

    def get_sum_energy_cost(self):
        return self.sum_energy_cost

    def get_sum_squared_energy(self):
        return self.sum_squared_energy

    def get_timer_elapse_map(self):
        return self.timer_elapse_map

    def get_device_state(self):
        return self.device_state

    def get_selection_reason(self):
        return self.selection_reason
