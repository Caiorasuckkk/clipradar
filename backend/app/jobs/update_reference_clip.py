from __future__ import annotations

import argparse
import sys

from app.services.reference_clip_benchmark_service import ReferenceClipBenchmarkService


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--strong-hook", type=parse_bool)
    parser.add_argument("--clear-context", type=parse_bool)
    parser.add_argument("--complete-thought", type=parse_bool)
    parser.add_argument("--good-pacing", type=parse_bool)
    parser.add_argument("--no-filler", type=parse_bool)
    parser.add_argument("--clear-ending", type=parse_bool)
    parser.add_argument("--viral-potential", type=parse_rating)
    parser.add_argument("--notes")
    args = parser.parse_args()

    features = {
        "strong_hook": args.strong_hook,
        "clear_context": args.clear_context,
        "complete_thought": args.complete_thought,
        "good_pacing": args.good_pacing,
        "no_filler": args.no_filler,
        "clear_ending": args.clear_ending,
        "viral_potential": args.viral_potential,
    }
    service = ReferenceClipBenchmarkService()
    try:
        reference = service.update_reference(args.url, features, args.notes)
    except ValueError as error:
        print(str(error))
        return

    print("REFERENCE CLIP UPDATED")
    print(reference["url"])
    print(f"label={reference['label']} style={reference['style']}")
    print(f"notes={reference['notes']}")
    print("features:")
    for key, value in reference["features"].items():
        if value is not None:
            print(f"- {key}: {value}")


def parse_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes", "sim", "s"}:
        return True
    if lowered in {"false", "0", "no", "nao", "não", "n"}:
        return False
    raise argparse.ArgumentTypeError("use true/false")


def parse_rating(value: str) -> int:
    rating = int(value)
    if rating < 1 or rating > 5:
        raise argparse.ArgumentTypeError("viral-potential deve estar entre 1 e 5")
    return rating


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
