# flexmeasures-s2 - a plugin for FlexMeasures

Looking for S2 support using FlexMeasures as a Customer Energy Manager (CEM) via WebSockets (WS)? There are two options.

1. Run your CEM as a WS server using the **FlexMeasures Client**, with the FlexMeasures server operating as a smart backend via REST API. Then this repo is not for you, please visit the [FlexMeasures Client docs](https://github.com/FlexMeasures/flexmeasures-client) instead.
2. Run your CEM as a WS server using the **FlexMeasures Server**. Then this repo is the server plugin you'll likely want to use. But be advised, the FlexMeasures Client-based CEM is seeing much more maintenance activity.

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
