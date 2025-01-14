import pandas as pd
from flexmeasures import Scheduler


class S2Scheduler(Scheduler):

    __author__ = "TNO"
    __version__ = "1"

    def compute(self, *args, **kwargs):
        """
        Just a dummy scheduler that always plans to consume at maximum capacity.
        (Schedulers return positive values for consumption, and negative values for production)
        """
        return pd.Series(
            self.sensor.get_attribute("capacity_in_mw"),
            index=pd.date_range(
                self.start, self.end, freq=self.resolution, inclusive="left"
            ),
        )

    def deserialize_config(self):
        """Do not care about any flex config sent in."""
        self.config_deserialized = True
