import pandas as pd
from flexmeasures import Scheduler

from flexmeasures_s2.scheduler.schemas import S2FlexModelSchema, TNOFlexContextSchema


class S2Scheduler(Scheduler):

    __author__ = "TNO"
    __version__ = "1"

    def compute(self, *args, **kwargs):
        """
        Just a dummy scheduler that always plans to consume at maximum capacity.
        (Schedulers return positive values for consumption, and negative values for production)
        """
        raise NotImplementedError("todo: implement scheduling logic")
        return pd.Series(
            self.sensor.get_attribute("capacity_in_mw"),
            index=pd.date_range(
                self.start, self.end, freq=self.resolution, inclusive="left"
            ),
        )

    def deserialize_config(self):
        """Do not care about any flex config sent in."""
        # Find flex-model in asset attributes
        self.flex_model = self.asset.attributes.get("flex-model", {})

        self.deserialize_flex_config()
        self.config_deserialized = True

    def deserialize_flex_config(self):
        """Deserialize flex-model and flex-context"""
        # Deserialize flex-model
        self.flex_model = S2FlexModelSchema().load(self.flex_model)

        # Deserialize self.flex_context
        self.flex_context = TNOFlexContextSchema().load(self.flex_context)
