import argparse
import sys

from insureagent_domain.events import DomainEvent
from pydantic import ValidationError


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate one metadata-only event from stdin")
    parser.add_argument("--validate-event", action="store_true", required=True)
    parser.parse_args()
    try:
        # Size cap and generic diagnostics: invalid payloads may contain sensitive data.
        payload = sys.stdin.buffer.read(65537)
        if len(payload) > 65536:
            raise ValueError("Oversized event")
        DomainEvent.model_validate_json(payload)
    except (ValidationError, ValueError):
        print("Invalid event; payload omitted", file=sys.stderr)
        return 2
    print("Event valid; execution is not implemented")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
