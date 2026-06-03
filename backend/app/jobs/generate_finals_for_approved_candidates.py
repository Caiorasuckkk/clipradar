from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from app.services.approved_generation_service import (
    generation_status,
    run_generation_worker,
    trigger_approved_generation,
)


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-id")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--status-only", action="store_true")
    args = parser.parse_args()

    if args.status_only:
        payload = generation_status()
    elif args.candidate_id:
        payload = trigger_approved_generation(
            candidate_id=args.candidate_id,
            run_async=False,
            force_failed=args.retry_failed,
        )
    else:
        payload = run_generation_worker(force_failed=args.retry_failed)

    print("GENERATE FINALS FOR APPROVED CANDIDATES")
    print(json.dumps(_compact(payload), ensure_ascii=False, indent=2))


def _compact(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {
            key: value
            for key, value in payload.items()
            if key not in {"stdout_tail", "stderr_tail"} or value
        }
    return payload


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
