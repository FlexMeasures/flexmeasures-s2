# flexmeasures-s2 - a plugin for FlexMeasures


## Usage


## Installation

1. Add "/path/to/flexmeasures-s2/flexmeasures_s2" to your FlexMeasures (>v0.7.0dev8) config file,
   using the FLEXMEASURES_PLUGINS setting (a list).
   Alternatively, if you installed this plugin as a package (e.g. via `python setup.py install`, `pip install -e` or `pip install flexmeasures_s2` should this project be on Pypi), then "flexmeasures_s2" suffices.

2. Config settings (during development)

In your `flexmeasures.cfg`, you can set the following config settings for this plugin:

- `FLEXMEASURES_S2_TARGET_MODE`: "energy" or "costs"
- `FLEXMEASURES_S2_PRICE_SENSOR`: sensor ID of the price sensor

To do: move these settings to the db asset (preferred scheduler and flex-context).


## Development

We use pre-commit to keep code quality up.

Install necessary tools with:

    pip install pre-commit black flake8 mypy
    pre-commit install

or:

    make install-for-dev

Try it:

    pre-commit run --all-files --show-diff-on-failure

For profiling, use:

    pyinstrument -o profiling_results.html test_frbc_device.py


## Profile Steering Examples

The `flexmeasures_s2/profile_steering/examples/` directory contains example scripts demonstrating
different aspects of the profile steering algorithm. These examples show how to use the
planning service with different device types.

### Running Examples

All examples can be run directly from the command line. Make sure you're in the project root
directory or have the flexmeasures_s2 package installed.

#### NoControl Device Example

Demonstrates planning with non-controllable devices (e.g., fixed consumption loads):

    python -m flexmeasures_s2.profile_steering.examples.example_schedule_nocontrol

This example creates multiple NoControl devices with fixed power forecasts and generates
a plan that matches a target energy profile.

#### DDBC Simple Example

A simplified DDBC (Demand-Driven Based Control) example:

    python -m flexmeasures_s2.profile_steering.examples.example_schedule_ddbc_simple

This demonstrates basic DDBC device planning without complex system descriptions.

#### DDBC Full Example

Full DDBC example with hybrid heating system (gas boiler + heat pump):

    python -m flexmeasures_s2.profile_steering.examples.example_schedule_ddbc

This example creates a hybrid heating system with:
- Gas boiler actuator (natural gas commodity)
- Heat pump actuator (electricity commodity)
- Average demand rate forecasts
- Tariff-based targets for cost optimization

**Note**: This example requires a FlexMeasures Flask app context. Make sure FlexMeasures
is properly configured before running.

#### FRBC Example

FRBC (Fill Rate Based Control) example with storage devices:

    python -m flexmeasures_s2.profile_steering.examples.example_schedule_frbc

This demonstrates planning for storage devices (e.g., EV batteries) with:
- Fill level targets
- Usage forecasts
- Operation mode optimization

#### ITHO Example

Complex example with ITHO heating system configuration:

    python -m flexmeasures_s2.profile_steering.examples.example_schedule_itho

This is a comprehensive example that may require additional configuration files.
Check the example file and `itho.yaml` for specific requirements.

### Example Outputs

Most examples generate:
- Console output showing planning progress and results
- Plot files in the `flexmeasures_s2/profile_steering/examples/plots/` directory
  (created automatically if it doesn't exist)

The plots show:
- Predicted vs. target energy profiles
- Device-level plans
- Congestion point aggregations

### Prerequisites

Examples require:
- Python 3.8+
- Required dependencies (install via `pip install -e .` or `make install-for-dev`)
- For plotting: matplotlib
- For DDBC/FRBC examples: s2python library
- For Flask-based examples: FlexMeasures installation and configuration

### Troubleshooting

If you encounter import errors:
1. Make sure you're running from the project root or have installed the package
2. Check that all dependencies are installed: `pip install -e .`
3. For Flask examples, ensure FlexMeasures is properly configured

If plots are not generated:
1. Check that matplotlib is installed: `pip install matplotlib`
2. Ensure write permissions for the `plots/` directory
