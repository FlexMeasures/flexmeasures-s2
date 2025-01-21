import pytest

from flask_sqlalchemy import SQLAlchemy

from flexmeasures import Asset, AssetType, Sensor, Account
from flexmeasures.app import create as create_flexmeasures_app
from flexmeasures.auth.policy import ADMIN_ROLE
from flexmeasures.conftest import (  # noqa F401
    db,
    fresh_db,
)  # Use these fixtures to rely on the FlexMeasures database. There might be others in flexmeasures/conftest you want to also re-use
from flexmeasures.data.services.users import create_user

from flexmeasures_s2 import S2_SCHEDULER_SPECS
from flexmeasures_s2.models.const import FRBC_TYPE

from flexmeasures_s2.scheduler.test_frbc_device import test_device_state  # noqa: F401


@pytest.fixture(scope="session")
def app():
    print("APP FIXTURE")

    # Adding this plugin, making sure the name is known (as last part of plugin path)
    test_app = create_flexmeasures_app(env="testing", plugins=["../flexmeasures_s2"])

    # Establish an application context before running the tests.
    ctx = test_app.app_context()
    ctx.push()

    yield test_app

    ctx.pop()

    print("DONE WITH APP FIXTURE")


@pytest.fixture(scope="module")
def setup_admin(db: SQLAlchemy):  # noqa: F811
    account = Account(name="Some FlexMeasures host")
    db.session.add(account)
    create_user(
        username="Test Admin User",
        email="test_admin_user@seita.nl",
        account_name=account.name,
        password="testtest",
        user_roles=dict(name=ADMIN_ROLE, description="A user who can do everything."),
    )
    yield account


@pytest.fixture(scope="module")
def setup_frbc_asset(db: SQLAlchemy, setup_admin):  # noqa: F811
    asset_type = AssetType(name=FRBC_TYPE)
    asset = Asset(
        name="Test FRBC asset",
        generic_asset_type=asset_type,
        owner=setup_admin,
    )
    asset.attributes = {
        "custom-scheduler": S2_SCHEDULER_SPECS,
        "flex-model": {
            "S2-FRBC-device-state": test_device_state,  # ?todo: add serialized state
        },
    }
    db.session.add(asset)
    sensor = Sensor(
        name="power",
        unit="kW",
        event_resolution="PT5M",
        generic_asset=asset,
    )
    db.session.add(sensor)
    db.session.flush()  # assign (asset and sensor) IDs
    yield asset
