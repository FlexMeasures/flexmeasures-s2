from typing import List, Any
from datetime import datetime
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from .congestion_point_planner import CongestionPointPlanner
from .proposal import Proposal


class RootPlanner:
    MAX_ITERATIONS = 1000

    def __init__(
        self,
        target: Any,
        energy_iteration_criterion: float,
        cost_iteration_criterion: float,
        context: Any,
    ):
        """
        target: An object that provides a profile.
                It must support a method get_profile_start(),
                have attributes timestep_duration and nr_of_timesteps,
                and (for optimization purposes) support a subtract() method.
        context: In a full implementation, this might be an executor or similar. Here it is passed along.
        """
        self.context = context
        self.target = self.remove_null_values(target)
        self.energy_iteration_criterion = energy_iteration_criterion
        self.cost_iteration_criterion = cost_iteration_criterion
        # Create an empty JouleProfile.
        # We assume that target exposes get_profile_start(), timestep_duration and nr_of_timesteps.
        self.empty_profile = JouleProfile(
            self.target.get_profile_start(),
            self.target.timestep_duration,
            elements=[0] * self.target.nr_of_timesteps,
        )
        self.cp_controllers: List[CongestionPointPlanner] = []
        self.root_ctrl_planning = self.empty_profile

    def remove_null_values(self, target: Any) -> Any:
        # Stub: simply return the target.
        # In a full implementation, you would remove or replace null elements.
        return target

    def add_congestion_point_controller(self, cpc: CongestionPointPlanner):
        self.cp_controllers.append(cpc)

    def get_congestion_point_controller(self, cp_id: str) -> CongestionPointPlanner:
        for cp in self.cp_controllers:
            if cp.congestion_point_id == cp_id:
                return cp
        return None

    def plan(
        self,
        plan_due_by_date: datetime,
        optimize_for_target: bool,
        max_priority_class_external: int,
        multithreaded: bool = False,
    ):
        # Compute an initial plan by summing each congestion point's initial planning.
        self.root_ctrl_planning = self.empty_profile
        for cpc in self.cp_controllers:
            initial_plan = cpc.create_initial_planning(plan_due_by_date)
            self.root_ctrl_planning = self.root_ctrl_planning.add(initial_plan)

        if not optimize_for_target:
            return

        if not self.cp_controllers:
            return

        # Determine maximum and minimum priority classes across congestion points.
        max_priority_class = max(
            cpc.max_priority_class() for cpc in self.cp_controllers
        )
        min_priority_class = min(
            cpc.min_priority_class() for cpc in self.cp_controllers
        )

        # Iterate over the priority classes.
        for priority_class in range(
            min_priority_class, min(max_priority_class, max_priority_class_external) + 1
        ):
            i = 0
            best_proposal = None

            # Simulate a do-while loop: we run at least once.
            while True:
                # Compute the difference profile
                difference_profile = self.target.subtract(self.root_ctrl_planning)
                best_proposal = None

                # Get proposals from each congestion point controller
                for cpc in self.cp_controllers:
                    try:
                        proposal = cpc.create_improved_planning(
                            difference_profile,
                            self.target.get_profile_metadata(),
                            priority_class,
                            plan_due_by_date,
                        )
                        if proposal is not None:
                            if best_proposal is None or proposal.is_preferred_to(
                                best_proposal
                            ):
                                best_proposal = proposal
                    except Exception as e:
                        print(f"Error getting proposal from controller: {e}")
                        continue

                if best_proposal is None:
                    # No proposal could be generated; exit inner loop.
                    break

                # Update the root controller's planning based on the best proposal.
                self.root_ctrl_planning = self.root_ctrl_planning.subtract(
                    best_proposal.get_old_plan()
                )
                self.root_ctrl_planning = self.root_ctrl_planning.add(
                    best_proposal.get_proposed_plan()
                )

                # Let the origin device/controller accept the proposal.
                best_proposal.get_origin().accept_proposal(best_proposal)
                i += 1
                print(
                    f"Root controller: selected best controller '{best_proposal.get_origin().get_device_name()}' with global energy impr {best_proposal.get_global_improvement_value()}, cost impr {best_proposal.get_cost_improvement_value()}, congestion impr {best_proposal.get_congestion_improvement_value()}, iteration {i}."
                )

                # Check stopping criteria: if improvement values are below thresholds or max iterations reached.
                if (
                    best_proposal.get_global_improvement_value()
                    <= self.energy_iteration_criterion
                    and best_proposal.get_cost_improvement_value()
                    <= self.cost_iteration_criterion
                ) or i >= self.MAX_ITERATIONS:
                    break

            print(
                f"Optimizing priority class {priority_class} was done after {i} iterations."
            )
            if i >= self.MAX_ITERATIONS:
                print(
                    f"Warning: Optimization stopped due to iteration limit. Priority class: {priority_class}, Iterations: {i}"
                )
