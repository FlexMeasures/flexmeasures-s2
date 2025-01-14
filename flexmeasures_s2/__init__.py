__version__ = "Unknown version"


"""
The __init__ for the flexmeasures-s2 FlexMeasures plugin.

FlexMeasures registers the BluePrint objects it finds in here.
"""


from importlib_metadata import version, PackageNotFoundError

from flask import Blueprint

from .utils import ensure_bp_routes_are_loaded_fresh

# Overwriting version (if possible) from the package metadata
# ― if this plugin has been installed as a package.
# This uses importlib.metadata behaviour added in Python 3.8.
# Note that we rely on git tags (via setuptools_scm) to define that version.
try:
    __version__ = version("flexmeasures_s2")
except PackageNotFoundError:
    # package is not installed
    pass

# API
flexmeasures_s2_api_bp: Blueprint = Blueprint(
    "flexmeasures-s2 API", __name__, url_prefix="/flexmeasures-s2/api"
)
ensure_bp_routes_are_loaded_fresh("api.somedata")
from flexmeasures_s2.api import somedata  # noqa: E402,F401
