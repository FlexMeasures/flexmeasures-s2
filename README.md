# flexmeasures-s2 - a plugin for FlexMeasures


## Usage


## Installation

1. Add "/path/to/flexmeasures-s2/flexmeasures_s2" to your FlexMeasures (>v0.7.0dev8) config file,
   using the FLEXMEASURES_PLUGINS setting (a list).
   Alternatively, if you installed this plugin as a package (e.g. via `python setup.py install`, `pip install -e` or `pip install flexmeasures_s2` should this project be on Pypi), then "flexmeasures_s2" suffices.

2.  


## Development

We use pre-commit to keep code quality up.

Install necessary tools with:

    pip install pre-commit black flake8 mypy
    pre-commit install

or:

    make install-for-dev

Try it:

    pre-commit run --all-files --show-diff-on-failure
