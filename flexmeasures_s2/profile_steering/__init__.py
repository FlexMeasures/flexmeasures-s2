"""
Profile Steering Module for FlexMeasures S2.

This module implements a hierarchical profile steering algorithm for coordinating
energy devices in a cluster. The algorithm optimizes device schedules to match
global energy targets while respecting congestion point constraints.

The algorithm works in three hierarchical levels:
1. RootPlanner: Coordinates global optimization across all congestion points
2. CongestionPointPlanner: Manages devices at each congestion point
3. DevicePlanner: Creates device-specific plans (FRBC, DDBC, NoControl)

The planning process:
1. Create initial plans from all devices
2. Iteratively improve plans by accepting proposals from devices
3. Proposals are evaluated based on improvement criteria (energy, cost, congestion)
4. Best proposals are accepted until convergence or iteration limit

Supported device types:
- FRBC (Fill Rate Based Control): Storage devices with fill level targets
- DDBC (Demand Driven Based Control): Devices with demand forecasts
- NoControl: Non-controllable devices with fixed consumption patterns
"""
