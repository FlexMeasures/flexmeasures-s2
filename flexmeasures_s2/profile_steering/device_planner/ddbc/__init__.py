"""
DDBC (Demand-Driven Based Control) Device Planner Package.

This package contains the planner and supporting classes for DDBC devices.
DDBC devices are demand-driven systems (e.g., hybrid heating systems) that
respond to average demand rate forecasts by selecting appropriate actuator
operation modes.

Key Components:
- S2DdbcDevicePlanner: Main planner that optimizes actuator operation modes
- S2DdbcDeviceState: Device state with system descriptions and demand forecasts
- DdbcPlanningWindow: State tree for exploring possible device states
- S2DdbcPlan: Plan representation with energy profile and operation modes
- Instruction/Insights profiles: Formats for device control and analysis
"""
