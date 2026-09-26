"""Fail the Phase 3 check on collision, fallback, or idle intervention."""
import sys
from reflexguard.simulation.models import Result


def verify(result: Result) -> None:
    if result.collision or result.collision_events or result.brain_failures or result.control_failures or result.brain_steps < 1:
        raise ValueError("Pipeline collision or brain communication failure")
    if result.drive == "idle":
        if result.interventions or abs(result.final_forward) > 1e-9 or result.displacement_m > 0.01:
            raise ValueError("Idle wheelchair moved or received an intervention")
    elif result.drive == "forward" and result.displacement_m < 0.1:
        raise ValueError("No meaningful user-commanded movement")
    if result.world == "corridor_demo" and result.drive == "forward" and result.duration_s >= 60:
        if result.passed_obstacles < 7 or result.displacement_m < 50 or result.recoveries < 1 or result.min_pedestrian_travel_m < 5:
            raise ValueError("Demo did not pass the full course and recover user control")


def main():
    try:
        result = Result.model_validate_json(sys.stdin.read(65536))
        verify(result)
    except ValueError:
        print("Pipeline check failed; inspect the scenario result.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
