"""Epic I experiment orchestrator (docs/evaluation.md §5).

    python chaos-testing/run_experiments.py --offline --n 5
    python chaos-testing/run_experiments.py --live --scenarios S1 --n 1

Offline mode runs the real agent pipeline against a scenario-aware mock
cluster; live mode injects failures into a running cluster and records real
wall-clock metrics through the Klarnova API.

Run order per protocol: manual baseline -> threshold-only -> full -> ablations,
with a randomised sequence within each config. Fresh ablation state is applied
per run.
"""
import argparse
import os
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

import metrics
import offline

DEFAULT_RESULTS = Path(__file__).resolve().parent / "results"

CONFIG_ORDER = ["manual", "threshold-only", "full",
                "no-rag", "no-validation", "no-safety", "no-planning", "no-bandit"]


def _as_ratio(values) -> float | None:
    return metrics.mean(1.0 if v else 0.0 for v in values)


def evaluate_gates(records: list[dict], min_success: float, min_diagnosis: float) -> bool:
    """Enforce quality thresholds on the ``full`` config. Returns True if met.

    Before this gate the harness only *recorded* results (always exit 0); CI had
    no way to catch a regression that silently dropped diagnosis accuracy.
    """
    full = [r for r in records if r.get("config") == "full"]
    if not full:
        print("GATE: no 'full' records to evaluate", file=sys.stderr)
        return False

    success = _as_ratio(r.get("is_resolved") for r in full)
    diagnosis = _as_ratio(r.get("diagnosis_matched") for r in full)

    checks = [
        ("success_rate", success, min_success),
        ("diagnosis_accuracy", diagnosis, min_diagnosis),
    ]
    ok = True
    print("\n=== Quality gates (full config) ===")
    for name, value, minimum in checks:
        passed = value is not None and value >= minimum
        ok = ok and passed
        shown = "n/a" if value is None else f"{value:.3f}"
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}: {shown} (min {minimum:.2f})")
    return ok


def run_offline_matrix(
    scenarios: dict,
    configs: list[str],
    n: int,
    results_dir: Path,
    human_approves: bool,
    use_llm: bool,
    seed: int,
):
    rng = random.Random(seed)
    produced: list[dict] = []
    for config in CONFIG_ORDER:
        if config not in configs:
            continue
        runs = [(sid, i) for sid in scenarios for i in range(n)]
        rng.shuffle(runs)
        for sid, i in runs:
            scenario = scenarios[sid]
            run_id = f"{i:03d}"
            if config == "manual":
                rec = offline.run_manual_baseline(scenario, f"{sid}-{run_id}")
            elif config == "threshold-only":
                rec = offline.run_threshold_baseline(scenario, f"{sid}-{run_id}")
            else:
                rec = offline.run_offline(
                    scenario, run_id=run_id, config=config,
                    human_approves=human_approves, use_llm=use_llm,
                )
            offline.write_record(rec, str(results_dir / config))
            produced.append(rec)
            print(f"  [{config}] {sid} run {run_id} -> "
                  f"verdict={rec['decision_verdict']} "
                  f"resolved={rec['is_resolved']} escalated={rec['escalated']}")
    return produced

def main():
    parser = argparse.ArgumentParser(description="Klarnova Epic I evaluation harness")
    parser.add_argument("--offline", action="store_true", help="run offline matrix (default)")
    parser.add_argument("--live", action="store_true", help="inject failures on a live cluster")
    parser.add_argument("--n", type=int, default=5, help="runs per (config x scenario)")
    parser.add_argument("--scenarios", default=None,
                        help="comma-separated scenario ids (default: all)")
    parser.add_argument("--configs", default=None,
                        help="comma-separated configs (default: all)")
    parser.add_argument("--results", default=str(DEFAULT_RESULTS), help="results dir")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--human-approves", action="store_true", default=True)
    parser.add_argument("--no-human-approves", dest="human_approves", action="store_false")
    parser.add_argument("--use-llm", action="store_true",
                        help="use the real Ollama LLM for diagnosis (offline)")
    parser.add_argument("--gate", action="store_true",
                        help="exit non-zero if quality thresholds are not met")
    parser.add_argument("--min-success", type=float, default=0.95,
                        help="minimum success rate for the full config (with --gate)")
    parser.add_argument("--min-diagnosis", type=float, default=0.90,
                        help="minimum diagnosis accuracy for the full config (with --gate)")
    args = parser.parse_args()

    scenarios = offline.load_scenarios(str(REPO_ROOT / "chaos-testing" / "scenarios.yaml"))
    if args.scenarios:
        wanted = {s.strip() for s in args.scenarios.split(",")}
        scenarios = {k: v for k, v in scenarios.items() if k in wanted}

    configs = CONFIG_ORDER
    if args.configs:
        configs = [c.strip() for c in args.configs.split(",")]

    results_dir = Path(args.results)

    if args.live:
        from live import run_live_matrix
        run_live_matrix(scenarios, configs, args.n, results_dir)
        return

    print(f"Offline matrix: {len(configs)} configs x {len(scenarios)} scenarios x {args.n} runs")
    produced = run_offline_matrix(
        scenarios, configs, args.n, results_dir,
        human_approves=args.human_approves, use_llm=args.use_llm, seed=args.seed,
    )
    print(f"Records written to {results_dir}")

    if args.gate:
        if not evaluate_gates(produced, args.min_success, args.min_diagnosis):
            print("Quality gates FAILED", file=sys.stderr)
            sys.exit(1)
        print("Quality gates PASSED")


if __name__ == "__main__":
    main()
