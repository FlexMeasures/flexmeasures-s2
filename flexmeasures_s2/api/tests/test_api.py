from flask import url_for
from flask_security import decorators as fs_decorators
from rq.job import Job

from flexmeasures.api.tests.test_auth_token import patched_check_token
from flexmeasures.api.tests.utils import UserContext
from flexmeasures.data.services.scheduling import (
    handle_scheduling_exception,
    get_data_source_for_job,
)
from flexmeasures.data.tests.utils import work_on_rq


def test_s2_frbc_api(monkeypatch, app, setup_frbc_asset):
    sensor = setup_frbc_asset.sensors[0]

    with UserContext("test_admin_user@seita.nl") as admin:
        auth_token = admin.get_auth_token()

    monkeypatch.setattr(fs_decorators, "_check_token", patched_check_token)
    with app.test_client() as client:
        trigger_schedule_response = client.post(
            url_for("SensorAPI:trigger_schedule", id=sensor.id),
            json={
                "flex-context": {
                    "target-profile": {},  # add target profile
                }
            },
            headers={"Authorization": auth_token},
        )
        print("Server responded with:\n%s" % trigger_schedule_response.json)
        assert trigger_schedule_response.status_code == 200
        job_id = trigger_schedule_response.json["schedule"]

    # Now that our scheduling job was accepted, we process the scheduling queue
    work_on_rq(app.queues["scheduling"], exc_handler=handle_scheduling_exception)
    job = Job.fetch(job_id, connection=app.queues["scheduling"].connection).is_finished
    assert job.is_finished is True

    # First, make sure the expected scheduler data source is now there
    job.refresh()  # catch meta info that was added on this very instance
    scheduler_source = get_data_source_for_job(job)
    assert scheduler_source.model == "S2Scheduler"

    # try to retrieve the schedule through the /sensors/<id>/schedules/<job_id> [GET] api endpoint
    # todo: to be discussed: the response from the S2Scheduler might get a different format than the FM default
    # get_schedule_response = client.get(
    #     url_for("SensorAPI:get_schedule", id=sensor.id, uuid=job_id),
    #     query_string={"duration": "PT48H"},
    # )
    # print("Server responded with:\n%s" % get_schedule_response.json)
    # assert get_schedule_response.status_code == 200
