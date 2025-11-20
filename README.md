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
