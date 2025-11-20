"""
Device Planner Module for Profile Steering.

This module contains device planners that implement the DevicePlanner interface
for different device types. Each device type has its own planner that understands
the device's capabilities and constraints.

Supported Device Types:
- FRBC (Fill Rate Based Control): Storage devices with fill level targets
- DDBC (Demand-Driven Based Control): Demand-driven systems with actuators
- NoControl: Non-controllable devices with fixed consumption patterns

Each device planner:
1. Creates initial plans based on device state
2. Creates improved plans (proposals) that optimize toward targets
3. Manages plan state (accepted vs. proposed plans)
4. Converts plans to instruction profiles for device control

The planners are used by CongestionPointPlanner to coordinate device-level
planning within the hierarchical profile steering algorithm.
"""
