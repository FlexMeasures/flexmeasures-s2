from datetime import datetime
from typing import List, Optional
from s2python.common import PowerForecast, PowerForecastElement, CommodityQuantity
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata


def get_expected_electrical_power(element: PowerForecastElement) -> float:
    """
    Get the expected electrical power from a PowerForecastElement.
    Sums up power values for electrical commodity quantities.

    Args:
        element: PowerForecastElement to extract power from

    Returns:
        Expected power in watts
    """
    expected_power = 0.0
    for power_value in element.power_values:
        commodity = power_value.commodity_quantity
        if commodity in (
            CommodityQuantity.ELECTRIC_POWER_L1,
            CommodityQuantity.ELECTRIC_POWER_L2,
            CommodityQuantity.ELECTRIC_POWER_L3,
            CommodityQuantity.ELECTRIC_POWER_3_PHASE_SYMMETRIC,
        ):
            expected_power += power_value.value_expected
    return expected_power


def find_starting_index_for(forecast: PowerForecast, profile_start: datetime) -> int:
    """
    Find the starting index in the forecast that corresponds to the profile_start time.

    Args:
        forecast: PowerForecast to search
        profile_start: Start time of the profile

    Returns:
        Index of the forecast element that starts at or before profile_start
    """
    current_time = forecast.start_time
    for i, element in enumerate(forecast.elements):
        if current_time >= profile_start:
            return i
        current_time += element.duration.to_timedelta()
    return len(forecast.elements)


def convert_power_forecast(
    forecast: PowerForecast, profile_metadata: ProfileMetadata
) -> JouleProfile:
    """
    Convert a PowerForecast to a JouleProfile.

    Args:
        forecast: PowerForecast to convert
        profile_metadata: Metadata describing the target profile

    Returns:
        JouleProfile with energy values in joules
    """
    forecast_start = forecast.start_time
    current_forecast_element_index: int
    current_profile_step_index: int

    if forecast_start > profile_metadata.profile_start:
        current_forecast_element_index = 0
        current_profile_step_index = profile_metadata.get_starting_step_nr(
            forecast_start
        )
    else:
        current_forecast_element_index = find_starting_index_for(
            forecast, profile_metadata.profile_start
        )
        current_profile_step_index = 0

    joule_profile_elements: List[Optional[int]] = [0] * profile_metadata.nr_of_timesteps

    if (
        0 <= current_profile_step_index < profile_metadata.nr_of_timesteps
        and 0 <= current_forecast_element_index < len(forecast.elements)
    ):
        current_profile_step_start = profile_metadata.get_profile_start_at_timestep(
            current_profile_step_index
        )
        current_forecast_element = forecast.elements[current_forecast_element_index]
        current_forecast_element_start = forecast_start
        for i in range(current_forecast_element_index):
            current_forecast_element_start += forecast.elements[
                i
            ].duration.to_timedelta()

        current_forecast_element_end = (
            current_forecast_element_start
            + current_forecast_element.duration.to_timedelta()
        )

        while (
            current_forecast_element_index < len(forecast.elements)
            and current_profile_step_index < profile_metadata.nr_of_timesteps
        ):
            current_forecast_element = forecast.elements[current_forecast_element_index]
            current_profile_step_end = (
                current_profile_step_start + profile_metadata.timestep_duration
            )

            start_of_fit = max(
                current_profile_step_start, current_forecast_element_start
            )
            end_of_fit: datetime
            profile_fit_index = current_profile_step_index

            if current_forecast_element_end >= current_profile_step_end:
                current_profile_step_index += 1
                if current_profile_step_index < profile_metadata.nr_of_timesteps:
                    current_profile_step_start = current_profile_step_end

            if current_profile_step_end >= current_forecast_element_end:
                end_of_fit = current_forecast_element_end
                current_forecast_element_index += 1
                if current_forecast_element_index < len(forecast.elements):
                    current_forecast_element_start = current_forecast_element_end
                    next_element = forecast.elements[current_forecast_element_index]
                    current_forecast_element_end = (
                        current_forecast_element_start
                        + next_element.duration.to_timedelta()
                    )
            else:
                end_of_fit = current_profile_step_end
                current_forecast_element_start = current_profile_step_end

            overlap_seconds = (end_of_fit - start_of_fit).total_seconds()
            if overlap_seconds > 0:
                expected_power = get_expected_electrical_power(current_forecast_element)
                joule_in_fit = int(round(expected_power * overlap_seconds))
                current_value = joule_profile_elements[profile_fit_index]
                if current_value is None:
                    joule_profile_elements[profile_fit_index] = joule_in_fit
                else:
                    joule_profile_elements[profile_fit_index] = (
                        current_value + joule_in_fit
                    )

    return JouleProfile(
        profile_start=profile_metadata.profile_start,
        timestep_duration=profile_metadata.timestep_duration,
        elements=joule_profile_elements,
    )
