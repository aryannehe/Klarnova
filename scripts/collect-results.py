"""Aggregate every test layer's results into one CSV for analysis.

Reads whatever exists and writes ``test-reports/all-tests.csv`` with a common
schema so the results can be pivoted by layer/suite/status in a spreadsheet:

    layer,suite,name,status,duration_ms,detail

Layers
------
backend  ``test-reports/backend-tests.csv``   (written by pytest via conftest)
e2e      ``test-reports/e2e-results.csv``      (written by the Playwright reporter)
eval     ``chaos-testing/results/summary.csv`` (written by chaos-testing/ablation.py)

A copy of the eval summary is snapshotted to ``test-reports/latest/chaos-eval.csv``
so the most recent evaluation is committed to the repo.

Usage:
    python scripts/collect-results.py
    python scripts/collect-results.py --backend ... --e2e ... --eval ...
"""
import argparse
import csv
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BACKEND = REPO_ROOT / "test-reports" / "backend-tests.csv"
DEFAULT_E2E = REPO_ROOT / "test-reports" / "e2e-results.csv"
DEFAULT_EVAL = REPO_ROOT / "chaos-testing" / "results" / "summary.csv"
DEFAULT_OUT = REPO_ROOT / "test-reports" / "all-tests.csv"
LATEST_SNAPSHOT = REPO_ROOT / "test-reports" / "latest" / "chaos-eval.csv"

FIELDS = ["layer", "suite", "name", "status", "duration_ms", "detail"]


def _read(path: Path) -> list[dict]:
    if not path.exists():
        print(f"  (skip) {path} not found")
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def collect_backend(path: Path) -> list[dict]:
    rows = []
    for r in _read(path):
        rows.append(
            {
                "layer": "backend",
                "suite": r.get("file", ""),
                "name": r.get("test_id", ""),
                "status": r.get("outcome", ""),
                "duration_ms": r.get("duration_ms", ""),
                "detail": r.get("error", ""),
            }
        )
    return rows


def collect_e2e(path: Path) -> list[dict]:
    rows = []
    for r in _read(path):
        rows.append(
            {
                "layer": "e2e",
                "suite": r.get("scenario") or r.get("spec_file", ""),
                "name": r.get("test_title", ""),
                "status": r.get("status", ""),
                "duration_ms": r.get("duration_ms", ""),
                "detail": r.get("error_message", ""),
            }
        )
    return rows


def collect_eval(path: Path) -> list[dict]:
    rows = []
    for r in _read(path):
        success = r.get("success_rate") or ""
        try:
            status = "ok" if float(success) >= 0.5 else "degraded"
        except (TypeError, ValueError):
            status = ""
        mttr = r.get("mttr_s")
        try:
            duration_ms = round(float(mttr) * 1000, 1)
        except (TypeError, ValueError):
            duration_ms = ""
        detail = (
            f"success={success} escal={r.get('escalation_rate')} "
            f"diag={r.get('diagnosis_accuracy')} "
            f"retr={r.get('retrieval_relevance')} "
            f"act={r.get('action_accuracy')}"
        )
        rows.append(
            {
                "layer": "eval",
                "suite": r.get("config", ""),
                "name": r.get("scenario", ""),
                "status": status,
                "duration_ms": duration_ms,
                "detail": detail,
            }
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description="Aggregate all test-layer results")
    parser.add_argument("--backend", default=str(DEFAULT_BACKEND))
    parser.add_argument("--e2e", default=str(DEFAULT_E2E))
    parser.add_argument("--eval", default=str(DEFAULT_EVAL))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument(
        "--snapshot", default=str(LATEST_SNAPSHOT),
        help="where to copy the eval summary for committing",
    )
    args = parser.parse_args()

    backend_path = Path(args.backend)
    eval_path = Path(args.eval)

    rows = []
    rows += collect_backend(backend_path)
    rows += collect_e2e(Path(args.e2e))
    rows += collect_eval(eval_path)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows -> {out_path}")

    if eval_path.exists():
        snapshot = Path(args.snapshot)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(eval_path, snapshot)
        print(f"snapshot -> {snapshot}")

    by_layer: dict[str, int] = {}
    for r in rows:
        by_layer[r["layer"]] = by_layer.get(r["layer"], 0) + 1
    print("rows per layer:", ", ".join(f"{k}={v}" for k, v in sorted(by_layer.items())))


if __name__ == "__main__":
    main()
