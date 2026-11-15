"""Small synthetic contract corpus; not a representative quality acceptance benchmark."""

import json
from pathlib import Path

from insureagent_ai.extraction.model import configured_extract


def main():
    cases = json.loads(Path("evals/fixtures/alpha-cases.json").read_text())
    results = []
    for case in cases:
        try:
            output = configured_extract(case["text"])
            evidence = [c["evidence"] for c in output["candidates"]]
            public = json.dumps(
                [output["redacted_text"], [c["value"] for c in output["candidates"]]]
            )
            grounded = all(
                case["text"][c["start"] : c["end"]] == c["evidence"] for c in output["candidates"]
            )
            passed = (
                output["person_names"] == case["names"]
                and evidence == case["evidence"]
                and grounded
                and all(value not in public for value in case.get("forbidden", []))
            )
            results.append({"id": case["id"], "passed": passed, "processor": output["processor"]})
        except Exception:
            results.append({"id": case["id"], "passed": False, "error": "processing_failed"})
    report = {
        "scope": "synthetic contract regression, not quality gate",
        "total": len(cases),
        "passed": sum(r["passed"] for r in results),
        "cases": results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
