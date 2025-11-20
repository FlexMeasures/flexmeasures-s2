from typing import Optional
from s2python.common import PowerForecast, CommodityQuantity
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata


def convert_power_forecast_to_joule_profile(
    power_forecast: Optional[PowerForecast], profile_metadata: ProfileMetadata
) -> JouleProfile:
    """
    Convert a PowerForecast to a JouleProfile.
    This is a Python port of the Java ConversionTools.convertPowerForecast method.

    Args:
        power_forecast: The power forecast to convert (can be None)
        profile_metadata: The metadata for the output profile

    Returns:
        A JouleProfile with energy values aligned to the profile metadata
    """
    if power_forecast is None:
        return JouleProfile(
            metadata=profile_metadata,
            value=0,
        )

    forecast_start = power_forecast.start_time
    profile_start = profile_metadata.profile_start

    if forecast_start > profile_start:
        current_forecast_element_index = 0
        time_diff = forecast_start - profile_start
        current_profile_step_index = int(
            time_diff.total_seconds()
            / profile_metadata.timestep_duration.total_seconds()
        )
    else:
        current_profile_step_index = 0
        time_diff = profile_start - forecast_start
        seconds_into_forecast = time_diff.total_seconds()
        current_forecast_element_index = 0
        accumulated_seconds = 0

        for i, element in enumerate(power_forecast.elements):
            # element.duration is a Duration object with .root in milliseconds
            # We need to convert to seconds
            element_duration_seconds = element.duration.root / 1000.0
            if accumulated_seconds + element_duration_seconds > seconds_into_forecast:
                current_forecast_element_index = i
                break
            accumulated_seconds += element_duration_seconds
        else:
            current_forecast_element_index = len(power_forecast.elements)

    joule_profile_elements = [0] * profile_metadata.nr_of_timesteps
    forecast_elements = power_forecast.elements

    if (
        0 <= current_profile_step_index < profile_metadata.nr_of_timesteps
        and 0 <= current_forecast_element_index < len(forecast_elements)
    ):
        profile_timestep_duration_seconds = (
            profile_metadata.timestep_duration.total_seconds()
        )
        while (
            current_profile_step_index < profile_metadata.nr_of_timesteps
            and current_forecast_element_index < len(forecast_elements)
        ):
            forecast_element = forecast_elements[current_forecast_element_index]
            power_watts = get_expected_electrical_power(forecast_element)
            # forecast_element.duration is a Duration object with .root in milliseconds
            # We need to convert to seconds
            forecast_element_duration_seconds = forecast_element.duration.root / 1000.0
            energy_joules = int(power_watts * forecast_element_duration_seconds)
            number_of_profile_steps = int(
                forecast_element_duration_seconds / profile_timestep_duration_seconds
            )

            for _ in range(number_of_profile_steps):
                if current_profile_step_index >= profile_metadata.nr_of_timesteps:
                    break
                joule_profile_elements[current_profile_step_index] = int(
                    energy_joules / number_of_profile_steps
                )
                current_profile_step_index += 1

            current_forecast_element_index += 1

    return JouleProfile(
        metadata=profile_metadata,
        elements=joule_profile_elements,  # type: ignore[arg-type]
    )


def get_expected_electrical_power(forecast_element) -> float:
    """
    Get the expected electrical power from a forecast element.
    Sums up all electrical power values from different phases.

    Args:
        forecast_element: The forecast element containing power values

    Returns:
        The total expected electrical power in watts
    """
    expected_power = 0.0
    for power_value in forecast_element.power_values:
        if power_value.commodity_quantity in [
            CommodityQuantity.ELECTRIC_POWER_L1,
            CommodityQuantity.ELECTRIC_POWER_L2,
            CommodityQuantity.ELECTRIC_POWER_L3,
            CommodityQuantity.ELECTRIC_POWER_3_PHASE_SYMMETRIC,
        ]:
            expected_power += power_value.value_expected
    return expected_power
