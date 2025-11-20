from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile


class S2NoControlPlan:
    def __init__(self, energy: JouleProfile):
        self.energy = energy

    def get_energy(self) -> JouleProfile:
        return self.energy
