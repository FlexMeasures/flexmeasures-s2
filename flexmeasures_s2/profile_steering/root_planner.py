from typing import List, Any, Optional
from datetime import datetime
from flexmeasures_s2.profile_steering.common.joule_profile import JouleProfile
from .congestion_point_planner import CongestionPointPlanner
from flexmeasures_s2.profile_steering.common.target_profile import TargetProfile


class RootPlanner:
    MAX_ITERATIONS = 1000

    def __init__(
        self,
        target: TargetProfile,
        energy_iteration_criterion: float,
        cost_iteration_criterion: float,
        always_accept_all_proposals: bool,
        context: Any,
    ):
        """
        target: An object that provides a profile.
                It must support a method get_profile_start(),
                have attributes timestep_duration and nr_of_timesteps,
                and (for optimization purposes) support a subtract() method.
        always_accept_all_proposals: If True, accept all valid proposals (for pure cost targets)
        context: In a full implementation, this might be an executor or similar. Here it is passed along.
        """
        self.context = context
        self.target = self.remove_null_values(target)
        self.energy_iteration_criterion = energy_iteration_criterion
        self.cost_iteration_criterion = cost_iteration_criterion
        self.always_accept_all_proposals = always_accept_all_proposals
        # Create an empty JouleProfile.
        # We assume that target exposes get_profile_start(), timestep_duration and nr_of_timesteps.
        self.empty_profile = JouleProfile(
            self.target.metadata.profile_start,
            self.target.metadata.timestep_duration,
            elements=[0] * self.target.metadata.nr_of_timesteps,
        )
        self.cp_controllers: List[CongestionPointPlanner] = []
        self.root_ctrl_planning = self.empty_profile

    def remove_null_values(self, target: Any) -> Any:
        # TODO: Stub: simply return the target.
        # In a full implementation, you would remove or replace null elements.
        return target

    def add_congestion_point_controller(self, cpc: CongestionPointPlanner):
        self.cp_controllers.append(cpc)

    def get_congestion_point_controller(
        self, cp_id: str
    ) -> Optional[CongestionPointPlanner]:
        for cp in self.cp_controllers:
            if cp.congestion_point_id == cp_id:
                return cp
        return None

    def plan(  # noqa: C901
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
                if self.target.nr_of_joule_target_elements() != 0:
                    difference_profile: TargetProfile = self.target.subtract(
                        self.root_ctrl_planning
                    )
                else:
                    difference_profile = self.target
                    # print(
                    #     "difference_profile has no Joule elements, using the target directly"
                    # )

                best_proposal = None

                # Get proposals from each congestion point controller
                proposals = []
                for cpc in self.cp_controllers:
                    # print("Improving------------------------->")
                    try:
                        proposal = cpc.create_improved_planning(
                            difference_profile,
                            priority_class,
                            plan_due_by_date,
                        )
                        if proposal is not None:
                            proposals.append(proposal)
                            if best_proposal is None or proposal.is_preferred_to(
                                best_proposal
                            ):
                                best_proposal = proposal
                    except Exception:
                        # print(f"Error getting proposal from controller: {e}")
                        continue

                if best_proposal is None:
                    # No proposal could be generated; exit inner loop.
                    break

                # Update root controller's own planning
                if self.always_accept_all_proposals:
                    # If we're NOT optimizing for a Joule target or congestion target, we can
                    # accept all proposals for efficiency
                    for proposal in proposals:
                        self._accept_proposal(proposal)
                else:
                    # If we're optimizing for a Joule target or congestion target we only accept
                    # one proposal
                    self._accept_proposal(best_proposal)

                i += 1
                # print(
                #     f"Root controller: selected best controller '{best_proposal.origin.device_name}' with global energy impr {best_proposal.get_global_improvement_value()}, cost impr {best_proposal.get_cost_improvement_value()}, CP impr {best_proposal.get_congestion_improvement_value()}. Accepted {accepted_proposals} proposal(s). Iteration {i}."
                # )

                # Check stopping criteria: if improvement values are below thresholds or max iterations reached.
                if self.always_accept_all_proposals:
                    # For pure cost targets, check cost improvement
                    if (
                        best_proposal.get_cost_improvement_value()
                        <= self.cost_iteration_criterion
                    ) or i >= self.MAX_ITERATIONS:
                        break
                else:
                    # For energy targets, check energy improvement (original behavior)
                    if (
                        best_proposal.get_global_improvement_value()
                        <= self.energy_iteration_criterion
                    ) or i >= self.MAX_ITERATIONS:
                        break

            # print(
            #     f"Optimizing priority class {priority_class} was done after {i} iterations."
            # )
            if i >= self.MAX_ITERATIONS:
                # print(
                #     f"Warning: Optimization stopped due to iteration limit. Priority class: {priority_class}, Iterations: {i}"
                # )
                pass

    def _accept_proposal(self, proposal):
        """Accept a proposal and update the planning accordingly."""
        # Update the root controller's planning based on the proposal.
        self.root_ctrl_planning = self.root_ctrl_planning.subtract(proposal.old_plan)
        self.root_ctrl_planning = self.root_ctrl_planning.add(proposal.proposed_plan)

        # Find the real device object and explicitly update its state.
        # This is crucial for parallel execution as proposal.origin is a copy.
        cp_id_of_origin = proposal.origin.congestion_point_id
        congestion_point_controller = self.get_congestion_point_controller(
            cp_id_of_origin
        )
        if congestion_point_controller is None:
            raise Exception(
                f"Could not find CongestionPointController with id {cp_id_of_origin}"
            )

        real_device = None
        for dev in congestion_point_controller.devices:
            if dev.device_id == proposal.origin.device_id:
                real_device = dev
                break

        if real_device is None:
            raise Exception(
                f"Could not find device with id {proposal.origin.device_id} in CP {cp_id_of_origin}"
            )
        plan_to_accept = proposal.origin.get_latest_plan()
        real_device.set_accepted_plan(plan_to_accept)
