__version__ = "Unknown version"


"""
The __init__ for the flexmeasures-s2 FlexMeasures plugin.

FlexMeasures registers the BluePrint objects it finds in here.
"""


from importlib_metadata import version, PackageNotFoundError

from flask import Blueprint, current_app as app

from flexmeasures.ws import sock

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
    "flexmeasures-s2 API", __name__, url_prefix="/s2"
)
ensure_bp_routes_are_loaded_fresh("api.s2_ws_server")
from flexmeasures_s2.api.s2_ws_server import S2FlaskWSServerSync  # noqa: E402,F401


S2FlaskWSServerSync(app=app, sock=sock)  # noqa: F841

# Use as follows:
# from flexmeasures import Sensor
# from flexmeasures_s2 import S2_SCHEDULER_SPECS
# my_sensor = Sensor.query.filter(
#     Sensor.name == "My power sensor on a flexible asset"
# ).one_or_none()
# my_sensor.attributes["custom-scheduler"] = S2_SCHEDULER_SPECS
S2_SCHEDULER_SPECS = {
    "module": "flexmeasures_s2.scheduler.schedulers",
    "class": "S2Scheduler",
}
