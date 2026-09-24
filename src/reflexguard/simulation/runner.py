"""Validate launcher configuration and require a complete simulator result."""
import sys
from pydantic import ValidationError
from reflexguard.simulation.models import Settings, Result


def read_result(log: str) -> Result:
    if any(line.startswith(("ERROR:", "FATAL:", "Traceback (")) for line in log.splitlines()):
        raise ValueError("Simulator reported an error")
    lines = [line.partition("REFLEXGUARD_RESULT=")[2] for line in log.splitlines()
             if line.startswith("REFLEXGUARD_RESULT=")]
    if len(lines) != 1:
        raise ValueError("Simulator result missing or duplicated")
    result = Result.model_validate_json(lines[0])
    if result.drive in ("forward", "reverse") and result.displacement_m < 0.1:
        raise ValueError("Wheelchair did not move")
    if result.collision != (result.collision_events > 0):
        raise ValueError("Inconsistent collision result")
    return result


def main():
    try:
        if len(sys.argv) == 5 and sys.argv[1] == "settings":
            config = Settings(world=sys.argv[2], duration_s=int(sys.argv[3]), drive=sys.argv[4], batch=True)
            print(config.model_dump_json())
        elif sys.argv[1:] == ["result"]:
            print(read_result(sys.stdin.read(4 * 1024 * 1024)).model_dump_json())
        else:
            raise ValueError("Invalid command")
    except (ValueError, ValidationError):
        print("Scenario validation failed; inspect simulator log.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
