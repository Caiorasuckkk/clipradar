from __future__ import annotations

import sys

from app.services.reference_clip_benchmark_service import ReferenceClipBenchmarkService


def main() -> None:
    configure_output()
    service = ReferenceClipBenchmarkService()
    references = service.list_references()
    print("REFERENCE CLIP BENCHMARK")
    print(f"Referências: {len(references)}")
    print(f"Checklist editorial: {', '.join(service.expected_checklist())}")
    print("")
    for index, reference in enumerate(references, start=1):
        print(f"{index}. {reference['url']}")
        print(f"label={reference['label']} style={reference['style']} source={reference['source']}")
        print(f"notes={reference['notes']}")
        features = reference.get("features", {})
        filled = {
            key: value
            for key, value in features.items()
            if value is not None
        }
        print(f"features_preenchidas={filled if filled else '{}'}")
        print("")


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
