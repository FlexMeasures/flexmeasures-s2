MSG_EMOJI = {
    # --- Common / lifecycle ---
    "Handshake": "🤝",
    "HandshakeResponse": "🔄",
    "ReceptionStatus": "📶",
    "ResourceManagerDetails": "📝",
    "SessionRequest": "🔐",
    # --- Measurements & forecasts ---
    "PowerMeasurement": "⚡",
    "PowerForecast": "🌤️",
    # --- PEBC ---
    "PEBC.PowerConstraints": "📐",
    "PEBC.EnergyConstraint": "⏳",
    "PEBC.Instruction": "✉️",
    # --- PPBC ---
    "PPBC.PowerProfileDefinition": "📄",
    "PPBC.PowerProfileStatus": "📊",
    "PPBC.ScheduleInstruction": "🗓️",
    "PPBC.StartInterruptionInstruction": "⏯️",
    "PPBC.EndInterruptionInstruction": "⏹️",
    # --- OMBC ---
    "OMBC.SystemDescription": "📋",
    "OMBC.Status": "🔧",
    "OMBC.TimerStatus": "⏲️",
    "OMBC.Instruction": "✉️",
    # --- FRBC ---
    "FRBC.SystemDescription": "📋",
    "FRBC.LeakageBehaviour": "💧",
    "FRBC.StorageStatus": "🔋",
    "FRBC.FillLevelTargetProfile": "🎯",
    "FRBC.ActuatorStatus": "⚙️",
    "FRBC.TimerStatus": "⏲️",
    "FRBC.UsageForecast": "📈",
    "FRBC.Instruction": "✉️",
    # --- DDBC ---
    "DDBC.SystemDescription": "📋",
    "DDBC.AverageDemandRateForecast": "📉",
    "DDBC.TimerStatus": "⏲️",
    "DDBC.ActuatorStatus": "⚙️",
    "DDBC.Instruction": "✉️",
    # --- Instruction status ---
    "InstructionStatusUpdate": "📣",
}

VERBOSE_MESSAGE_TYPES = [
    "PowerForecast",
    # "PEBC.PowerConstraints",
    # "PEBC.EnergyConstraint",
    # "PPBC.PowerProfileDefinition",
    # "FRBC.SystemDescription",
    # "FRBC.LeakageBehaviour",
    # "FRBC.StorageStatus",
    # "FRBC.FillLevelTargetProfile",
    # "FRBC.ActuatorStatus",
    "FRBC.UsageForecast",
    # "OMBC.SystemDescription",
    "DDBC.AverageDemandRateForecast",
]
