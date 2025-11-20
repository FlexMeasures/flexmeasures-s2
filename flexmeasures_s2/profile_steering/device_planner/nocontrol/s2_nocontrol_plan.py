from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile


class S2NoControlPlan:
    """Simple plan wrapper for nocontrol devices.

    Since nocontrol devices cannot be controlled, the plan only contains an
    energy profile derived from the power forecast. The plan is fixed and
    cannot be optimized or changed.

    Attributes:
        energy: Energy profile derived from the device's power forecast
    """

    def __init__(self, energy: JouleProfile):
        self.energy = energy

    def get_energy(self) -> JouleProfile:
        return self.energy
