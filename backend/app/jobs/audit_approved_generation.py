from __future__ import annotations

import json
import sys

from app.services.approved_generation_service import audit_approved_generation


def main() -> None:
    configure_output()
    payload = audit_approved_generation()
    print("AUDIT APPROVED GENERATION")
    print(f"approved_reviews_count: {payload['approved_reviews_count']}")
    print(f"generated_for_approved_count: {payload['generated_for_approved_count']}")
    print(f"missing_generation_count: {payload['missing_generation_count']}")
    print(f"orphan_generated_count: {payload['orphan_generated_count']}")
    print("")
    print("Approved candidates missing final:")
    for candidate_id in payload["missing_candidate_ids"][:50]:
        print(f"- {candidate_id}")
    if len(payload["missing_candidate_ids"]) > 50:
        print(f"... +{len(payload['missing_candidate_ids']) - 50} more")
    print("")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
