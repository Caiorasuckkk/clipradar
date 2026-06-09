from __future__ import annotations

import json
import sys

from app.services.local_job_runner_service import LocalJobRunnerService


def main() -> None:
    configure_output()
    result = LocalJobRunnerService().cleanup_stale_runs(mark_status="cancelled")
    print("CLEANUP STALE JOB RUNS")
    print(f"updated_count: {result['updated_count']}")
    for run_id in result["updated_run_ids"]:
        print(f"- {run_id}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
