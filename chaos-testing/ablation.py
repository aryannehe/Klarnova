"""Ablation summary (Epic I, docs/evaluation.md §5).

Reads per-run records under ``results/`` and prints baseline-vs-full and
ablation-vs-full deltas for the committed metric set. Writes:

- ``results/summary.csv``  - one row per (config x scenario) with all metrics
- ``results/metrics.json`` - machine-readable aggregates per config

Usage: python chaos-testing/ablation.py [--results RESULTS_DIR]
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import metrics

CONFIG_ORDER = ["manual", "threshold-only", "full",
                "no-rag", "no-validation", "no-safety", "no-planning", "no-bandit"]

ABLATION_QUESTION = {
    "no-rag": "how much does grounded precedent improve diagnosis?",
    "no-validation": "how many failed fixes go unnoticed without health checks?",
    "no-safety": "what is the risk cost of removing the policy gate?",
    "no-planning": "does separating planning from reasoning improve action choice?",
    "no-bandit": "does learned action-ranking beat static selection?",
}


def _scenarios_from_records(records):
    return {r["scenario_id"] for r in records}


def per_config_rows(records, scenario_ids):
    """Return {config: {scenario: metrics-dict}} plus overall row."""
    rows = {}
    for config in CONFIG_ORDER:
        cfg_records = [r for r in records if r.get("config") == config]
        if not cfg_records:
            continue
        sc_overrides = {}
        for sid in sorted(scenario_ids):
            runs = [r for r in cfg_records if r.get("scenario_id") == sid]
            if not runs:
                continue
            sc_overrides[sid] = {
                "n": len(runs),
                "diagnosis_accuracy": metrics.mean(
                    1.0 if r.get("diagnosis_matched") else 0.0 for r in runs
                ),
                "retrieval_relevance": metrics.mean(
                    1.0 if r.get("retrieval_hit") else 0.0 for r in runs
                ),
                "action_accuracy": metrics.mean(
                    1.0 if r.get("action_correct") else 0.0 for r in runs
                ),
            }
        rows[config] = {
            "overall": {
                **metrics.aggregate(cfg_records),
                "diagnosis_accuracy": metrics.mean(
                    1.0 if r.get("diagnosis_matched") else 0.0 for r in cfg_records
                ),
                "retrieval_relevance": metrics.mean(
                    1.0 if r.get("retrieval_hit") else 0.0 for r in cfg_records
                ),
                "action_accuracy": metrics.mean(
                    1.0 if r.get("action_correct") else 0.0 for r in cfg_records
                ),
            },
            "scenarios": sc_overrides,
        }
    return rows


def _delta(full, other, key):
    a = full.get(key)
    b = other.get(key)
    if a is None or b is None:
        return None
    return round(b - a, 3)


def format_row(label, values):
    def _fmt(v):
        return "n/a" if v is None else f"{v:.3f}"
    print(
        f"  {label:<22} mttd={_fmt(values.get('mttd_mean_s')):>9} "
        f"mttr={_fmt(values.get('mttr_mean_s')):>9} "
        f"succ={_fmt(values.get('success_rate')):>9} "
        f"esc={_fmt(values.get('escalation_rate')):>9}"
    )


def print_overview(rows):
    print("=== Overall metrics per config (mean over runs) ===")
    header = "  config".ljust(24) + "MTTD(s)   MTTR(s)   success   escal"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for config in CONFIG_ORDER:
        if config in rows:
            format_row(config, rows[config]["overall"])


def print_deltas(rows):
    full = rows.get("full")
    if not full:
        print("no 'full' records found")
        return
    print("\n=== Deltas vs full system (per-component contribution) ===")
    for config in CONFIG_ORDER:
        if config == "full" or config not in rows:
            continue
        other_row = rows[config]
        other = other_row["overall"]
        print(f"\n[{config}]  ({ABLATION_QUESTION.get(config, '')})")
        format_row("delta", {
            "mttd_mean_s": _delta(full["overall"], other, "mttd_mean_s"),
            "mttr_mean_s": _delta(full["overall"], other, "mttr_mean_s"),
            "success_rate": _delta(full["overall"], other, "success_rate"),
            "escalation_rate": _delta(full["overall"], other, "escalation_rate"),
        })
        for sid, sc in sorted(other_row["scenarios"].items()):
            f_sc = full["scenarios"].get(sid, {})
            print(
                f"    {sid}: diag {_fmt(sc.get('diagnosis_accuracy'))} "
                f"({_delta(f_sc, sc, 'diagnosis_accuracy')}) | "
                f"retr {_fmt(sc.get('retrieval_relevance'))} | "
                f"act {_fmt(sc.get('action_accuracy'))}"
            )


def _fmt(v):
    return "n/a" if v is None else f"{v:.2f}"


def _round(v):
    return None if v is None else round(v, 3)


def check_gates(rows, min_success: float, min_diagnosis: float) -> bool:
    """Enforce quality thresholds on the ``full`` config (for CI)."""
    full = rows.get("full")
    if not full:
        print("GATE: no 'full' config in results", file=sys.stderr)
        return False
    overall = full["overall"]
    checks = [
        ("success_rate", overall.get("success_rate"), min_success),
        ("diagnosis_accuracy", overall.get("diagnosis_accuracy"), min_diagnosis),
    ]
    ok = True
    print("\n=== Ablation quality gates (full config) ===")
    for name, value, minimum in checks:
        passed = value is not None and value >= minimum
        ok = ok and passed
        shown = "n/a" if value is None else f"{value:.3f}"
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}: {shown} (min {minimum:.2f})")
    return ok


def write_summary(rows, results_dir: Path):
    with open(results_dir / "summary.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["config", "scenario", "n", "mttd_s", "mttr_s",
                         "success_rate", "escalation_rate",
                         "diagnosis_accuracy", "retrieval_relevance", "action_accuracy"])
        for config, data in rows.items():
            overall = data["overall"]
            writer.writerow([config, "ALL", overall["n"],
                             overall.get("mttd_mean_s"), overall.get("mttr_mean_s"),
                             overall.get("success_rate"), overall.get("escalation_rate"),
                             _round(overall.get("diagnosis_accuracy")),
                             _round(overall.get("retrieval_relevance")),
                             _round(overall.get("action_accuracy"))])
            for sid, sc in data["scenarios"].items():
                writer.writerow([config, sid, sc["n"], "", "", "", "",
                                 sc["diagnosis_accuracy"], sc["retrieval_relevance"],
                                 sc["action_accuracy"]])
    with open(results_dir / "metrics.json", "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, default=str)
    print(f"\nsummary.csv and metrics.json written to {results_dir}")


def main():
    parser = argparse.ArgumentParser(description="Klarnova ablation summary")
    parser.add_argument("--results", default=str(Path(__file__).parent / "results"))
    parser.add_argument("--check", action="store_true",
                        help="exit non-zero if the full config misses quality thresholds")
    parser.add_argument("--min-success", type=float, default=0.95)
    parser.add_argument("--min-diagnosis", type=float, default=0.90)
    args = parser.parse_args()
    results_dir = Path(args.results)
    records = metrics.load_records(results_dir)
    if not records:
        print(f"no records found under {results_dir}", file=sys.stderr)
        sys.exit(1)
    rows = per_config_rows(records, _scenarios_from_records(records))
    print_overview(rows)
    print_deltas(rows)
    write_summary(rows, results_dir)

    if args.check:
        if not check_gates(rows, args.min_success, args.min_diagnosis):
            print("Ablation gates FAILED", file=sys.stderr)
            sys.exit(1)
        print("Ablation gates PASSED")


if __name__ == "__main__":
    main()
