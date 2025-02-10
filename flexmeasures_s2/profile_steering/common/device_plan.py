from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.soc_profile import SoCProfile
from flexmeasures_s2.profile_steering.common.abstract_profile import AbstractProfile
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata
from typing import Optional


class DevicePlan:
    def __init__(
        self,
        device_id: str,
        device_name: str,
        connection_id: str,
        joule_profile: JouleProfile,
        soc_profile: Optional[SoCProfile] = None,
        extra_info: Optional[AbstractProfile] = None,
    ):
        self.device_id = device_id
        self.device_name = device_name
        self.connection_id = connection_id
        self.joule_profile = joule_profile
        self.soc_profile = soc_profile
        self.extra_info_profile = extra_info

        if soc_profile and not soc_profile.is_compatible(joule_profile):
            raise ValueError("The JouleProfile and the SoC Profile are not compatible")
        if extra_info and not extra_info.is_compatible(joule_profile):
            raise ValueError(
                "The JouleProfile and the extra info profile for reflex are not compatible"
            )

    def get_joule_profile(self) -> JouleProfile:
        return self.joule_profile

    def get_soc_profile(self) -> Optional[SoCProfile]:
        return self.soc_profile

    def get_extra_info_profile(self) -> Optional[AbstractProfile]:
        return self.extra_info_profile

    def get_extra_info_for_insights(self) -> Optional[InsightsProfile]:
        return self.extra_info_for_insights

    def get_device_id(self) -> str:
        return self.device_id

    def get_device_name(self) -> str:
        return self.device_name

    def get_connection_id(self) -> str:
        return self.connection_id

    def get_profile_metadata(self) -> ProfileMetadata:
        return self.joule_profile.get_profile_metadata()

    def is_compatible(self, other: "DevicePlan") -> bool:
        return self.joule_profile.is_compatible(other.joule_profile)

    def subprofile(self, new_start_date) -> "DevicePlan":
        jp = self.joule_profile.subprofile(new_start_date)
        sp = self.soc_profile.subprofile(new_start_date) if self.soc_profile else None
        eip = (
            self.extra_info_profile.subprofile(new_start_date)
            if self.extra_info_profile
            else None
        )
        eip_insights = (
            self.extra_info_for_insights.subprofile(new_start_date)
            if self.extra_info_for_insights
            else None
        )
        return DevicePlan(
            self.device_id,
            self.device_name,
            self.connection_id,
            jp,
            sp,
            eip,
            eip_insights,
        )

    def adjust_nr_of_elements(self, nr_of_elements: int) -> "DevicePlan":
        jp = self.joule_profile.adjust_nr_of_elements(nr_of_elements)
        sp = (
            self.soc_profile.adjust_nr_of_elements(nr_of_elements)
            if self.soc_profile
            else None
        )
        eip = (
            self.extra_info_profile.adjust_nr_of_elements(nr_of_elements)
            if self.extra_info_profile
            else None
        )
        eip_insights = (
            self.extra_info_for_insights.adjust_nr_of_elements(nr_of_elements)
            if self.extra_info_for_insights
            else None
        )
        return DevicePlan(
            self.device_id,
            self.device_name,
            self.connection_id,
            jp,
            sp,
            eip,
            eip_insights,
        )

    def __str__(self) -> str:
        return (
            f"DevicePlan [deviceId={self.device_id}, deviceName={self.device_name}, "
            f"connectionId={self.connection_id}, jouleProfile={self.joule_profile}, "
            f"socProfile={self.soc_profile}, extraInfoProfile={self.extra_info_profile}, "
            f"extraInfoForInsights={self.extra_info_for_insights}]"
        )
