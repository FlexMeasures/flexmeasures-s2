from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile
from datetime import datetime, timedelta, timezone
import time
import uuid
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_device_state import (
    S2DdbcDeviceState,
)
from flexmeasures_s2.profile_steering.common.profile_metadata import ProfileMetadata
from s2python.ddbc import (
    DDBCSystemDescription,
    DDBCAverageDemandRateForecast,
    DDBCAverageDemandRateForecastElement,
    DDBCActuatorDescription,
    DDBCActuatorStatus,
    DDBCOperationMode,
)
from s2python.common import NumberRange, PowerRange, CommodityQuantity, Commodity
from decimal import Decimal
from flexmeasures_s2.profile_steering.device_planner.ddbc.s2_ddbc_device_planner import (
    S2DdbcDevicePlanner,
)
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
import matplotlib.pyplot as plt


def test_ddbc_price_tradeoff():
    """Test DDBC planner with price tradeoff between electricity and natural gas."""
    print("Testing DDBC device planner with price tradeoff")

    start_date = datetime(2018, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    step_duration = timedelta(minutes=5)
    profile_length = 3

    profile_metadata = ProfileMetadata(
        profile_start=start_date,
        timestep_duration=step_duration,
        nr_of_timesteps=profile_length,
    )

    demand_rate_forecast = DDBCAverageDemandRateForecast(
        message_id=str(uuid.uuid4()),
        start_time=start_date,
        elements=[
            DDBCAverageDemandRateForecastElement(
                duration=int(profile_metadata.timestep_duration.total_seconds()),
                demand_rate_expected=Decimal("11556.54"),
            ),
            DDBCAverageDemandRateForecastElement(
                duration=int(profile_metadata.timestep_duration.total_seconds()),
                demand_rate_expected=Decimal("11556.54"),
            ),
            DDBCAverageDemandRateForecastElement(
                duration=int(profile_metadata.timestep_duration.total_seconds()),
                demand_rate_expected=Decimal("11556.527159385734"),
            ),
        ],
    )

    gas_id = str(uuid.uuid4())
    gas_work_mode_id = str(uuid.uuid4())
    gas_actuator = DDBCActuatorDescription(
        id=uuid.UUID(gas_id),
        diagnostic_label="gas",
        supported_commodites=[Commodity.GAS],
        operation_modes=[
            DDBCOperationMode(
                Id=gas_work_mode_id,
                id=uuid.UUID(gas_work_mode_id),
                diagnostic_label="gas_work",
                power_ranges=[
                    PowerRange(
                        start_of_range=Decimal.from_float(0.0),
                        end_of_range=Decimal.from_float(0.568720358),
                        commodity_quantity=CommodityQuantity.NATURAL_GAS_FLOW_RATE,
                    )
                ],
                supply_range=[
                    NumberRange(
                        start_of_range=Decimal.from_float(0.0),
                        end_of_range=Decimal.from_float(18 * 1000),
                    )
                ],
                abnormal_condition_only=False,
            )
        ],
        transitions=[],
        timers=[],
    )

    hp_id = str(uuid.uuid4())
    hp_work_mode_id = str(uuid.uuid4())
    heatpump_actuator = DDBCActuatorDescription(
        id=uuid.UUID(hp_id),
        diagnostic_label="heatpump",
        supported_commodites=[Commodity.ELECTRICITY],
        operation_modes=[
            DDBCOperationMode(
                Id=hp_work_mode_id,
                id=uuid.UUID(hp_work_mode_id),
                diagnostic_label="heatpump_work",
                power_ranges=[
                    PowerRange(
                        start_of_range=Decimal.from_float(0.0),
                        end_of_range=Decimal.from_float(1.1 * 1000),
                        commodity_quantity=CommodityQuantity.ELECTRIC_POWER_L1,
                    )
                ],
                supply_range=[
                    NumberRange(
                        start_of_range=Decimal.from_float(0.0),
                        end_of_range=Decimal.from_float(5 * 1000),
                    )
                ],
                abnormal_condition_only=False,
            )
        ],
        transitions=[],
        timers=[],
    )

    actuator_statuses = {
        gas_id: DDBCActuatorStatus(
            message_id=str(uuid.uuid4()),
            actuator_id=gas_id,
            active_operation_mode_id=gas_work_mode_id,
            operation_mode_factor=Decimal.from_float(0.0),
        ),
        hp_id: DDBCActuatorStatus(
            message_id=str(uuid.uuid4()),
            actuator_id=hp_id,
            active_operation_mode_id=hp_work_mode_id,
            operation_mode_factor=Decimal.from_float(0.0),
        ),
    }

    system_description = DDBCSystemDescription(
        message_id=str(uuid.uuid4()),
        valid_from=start_date,
        actuators=[gas_actuator, heatpump_actuator],
        present_demand_rate=NumberRange(
            start_of_range=Decimal.from_float(11556.54),
            end_of_range=Decimal.from_float(11556.54),
        ),
        provides_average_demand_rate_forecast=True,
    )

    device_id = "heatpump1"
    device_state = S2DdbcDeviceState(
        device_id=device_id,
        device_name=device_id,
        connection_id=device_id,
        priority_class=0,
        timestamp=start_date,
        energy_in_current_timestep=0.0,
        is_online=True,
        power_forecast=None,
        system_descriptions=[system_description],
        demand_forecasts=[demand_rate_forecast],
        actuator_statuses=actuator_statuses,
    )

    plan_due_by_date = start_date + timedelta(seconds=5)

    planner = S2DdbcDevicePlanner(
        device_state,
        profile_metadata,
        plan_due_by_date,
        congestion_point_id="",
    )

    print("Creating initial planning...")
    start_time = time.time()
    initial_plan = planner.create_initial_planning(plan_due_by_date)
    end_time = time.time()
    print(f"Initial plan created in {end_time - start_time:.2f} seconds")

    print(f"Initial energy profile: {initial_plan.get_energy().elements}")

    target_elements = [
        TargetProfile.TariffElement(1.02),
        TargetProfile.TariffElement(1.04),
        TargetProfile.TariffElement(1.02),
    ]

    target_profile = TargetProfile(profile_metadata, target_elements)

    diff_to_max_profile = JouleProfile(
        profile_metadata.profile_start,
        profile_metadata.timestep_duration,
        [None] * profile_metadata.nr_of_timesteps,
    )
    diff_to_min_profile = JouleProfile(
        profile_metadata.profile_start,
        profile_metadata.timestep_duration,
        [None] * profile_metadata.nr_of_timesteps,
    )

    print("\nCreating improved planning with tariff targets...")
    start_time = time.time()
    improved_proposal = planner.create_improved_planning(
        target_profile,
        diff_to_max_profile,
        diff_to_min_profile,
        plan_due_by_date,
    )
    end_time = time.time()
    print(f"Improved plan created in {end_time - start_time:.2f} seconds")

    planner.accept_proposal(improved_proposal)

    latest_plan = planner.get_latest_plan()
    energy_profile = latest_plan.get_energy()
    insights = latest_plan.get_s2_ddbc_insights_profile()

    print(f"\nEnergy profile: {energy_profile.elements}")

    if insights:
        supply_rates = [
            e.get_supply_rate() if e else 0 for e in insights.get_elements()
        ]
        demand_rates = [
            e.get_demand_rate_forecast() if e else 0 for e in insights.get_elements()
        ]

        print(f"Target: {[str(e) for e in target_profile.elements]}")
        print(f"Demand rates: {demand_rates}")
        print(f"Supply rates: {supply_rates}")

        factors_hp = []
        factors_gas = []

        for element in insights.get_elements():
            if element:
                actuator_configs = element.get_actuator_configurations()
                hp_config = actuator_configs.get(hp_id)
                gas_config = actuator_configs.get(gas_id)

                factors_hp.append(hp_config.get_factor() if hp_config else 0)
                factors_gas.append(gas_config.get_factor() if gas_config else 0)
            else:
                factors_hp.append(0)
                factors_gas.append(0)

        print(f"Factor HP: {factors_hp}")
        print(f"Factor Gas: {factors_gas}")

        print("\nExpected behavior:")
        print("- Timestep 0 (tariff 1.02): Heatpump should be on (electricity cheaper)")
        print(
            "- Timestep 1 (tariff 1.04): Heatpump should be off (electricity expensive)"
        )
        print("- Timestep 2 (tariff 1.02): Heatpump should be on (electricity cheaper)")

        assert (
            factors_hp[0] > 0.9
        ), f"Expected heatpump on in timestep 0, got factor {factors_hp[0]}"
        assert (
            factors_hp[1] < 0.1
        ), f"Expected heatpump off in timestep 1, got factor {factors_hp[1]}"
        assert (
            factors_hp[2] > 0.9
        ), f"Expected heatpump on in timestep 2, got factor {factors_hp[2]}"

        print("\nTest PASSED!")

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

        timesteps = list(range(profile_length))

        ax1.plot(
            timesteps,
            energy_profile.elements,
            "o-",
            label="Energy (Joules)",
            linewidth=2,
        )
        ax1.set_ylabel("Energy (Joules)")
        ax1.set_title("DDBC Planning Results")
        ax1.legend()
        ax1.grid(True)

        ax2.plot(
            timesteps,
            supply_rates,
            "s-",
            label="Supply Rate",
            linewidth=2,
            color="green",
        )
        ax2.plot(
            timesteps, demand_rates, "x-", label="Demand Rate", linewidth=2, color="red"
        )
        ax2.set_xlabel("Timestep")
        ax2.set_ylabel("Rate")
        ax2.set_title("Supply vs Demand Rates")
        ax2.legend()
        ax2.grid(True)

        plt.tight_layout()
        plt.savefig(
            "flexmeasures_s2/profile_steering/examples/plots/ddbc_test_results.png"
        )
        print(
            "\nPlot saved to flexmeasures_s2/profile_steering/examples/plots/ddbc_test_results.png"
        )


if __name__ == "__main__":
    test_ddbc_price_tradeoff()
