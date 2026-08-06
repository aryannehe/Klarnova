"""Failure-injection tool (KLR-B7).

Usage:
  python scripts/inject_failure.py <scenario> --app checkout [--ns sample]

Scenarios:
  crash       Patch ConfigMap FAIL_MODE=crash + rollout restart -> CrashLoopBackOff
  oom         Repeatedly allocate memory inside the pod -> OOMKilled
  cpu         Spin CPU inside the pod -> CPU saturation
  error       Force 5xx responses + generate traffic -> error-rate alert
  image-pull  Point the deployment at a non-existent image -> ImagePullBackOff
  reset       Restore healthy config (FAIL_MODE empty) + rollout restart
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

TRAFFIC_TARGETS = {
    "checkout": ["/orders", "/orders/new"],
    "inventory": ["/inventory"],
    "cart": ["/carts"],
}


def _run(args: list[str], check: bool = True) -> str:
    result = subprocess.run(args, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise SystemExit(f"kubectl {' '.join(args)} failed:\n{result.stderr}")
    return result.stdout.strip()


def _pod(app: str, ns: str) -> str:
    pods = _run(["kubectl", "get", "pods", "-n", ns, "-l", f"app={app}", "-o", "name"])
    first = pods.splitlines()[0] if pods else ""
    return first.replace("pod/", "")


def _exec(app: str, ns: str, cmd: list[str]) -> None:
    pod = _pod(app, ns)
    if not pod:
        raise SystemExit(f"no running pod found for app={app} in {ns}")
    print(f"[*] exec {pod}: {' '.join(cmd)}")
    _run(["kubectl", "exec", "-n", ns, pod, "--"] + cmd)


def _post_failure(app: str, ns: str, path: str) -> None:
    """POST to a failure endpoint using python inside the pod (no curl needed)."""
    url = f"http://localhost:8000{path}"
    code = (
        "import urllib.request; "
        f"urllib.request.urlopen(urllib.request.Request('{url}', method='POST'))"
    )
    _exec(app, ns, ["python", "-c", code])


def _patch_cm(app: str, ns: str, key: str, value: str) -> None:
    print(f"[*] set ConfigMap {app}-config {key}={value!r}")
    _run(["kubectl", "patch", "configmap", f"{app}-config", "-n", ns, "--type=merge", "-p",
          f'{{"data": {{"{key}": "{value}"}}}}'])


def _restart(app: str, ns: str) -> None:
    print(f"[*] rollout restart deployment/{app}")
    _run(["kubectl", "rollout", "restart", f"deployment/{app}", "-n", ns])
    time.sleep(3)


def scenario_crash(app: str, ns: str) -> None:
    _patch_cm(app, ns, "FAIL_MODE", "crash")
    _restart(app, ns)
    print("[*] waiting 20s for CrashLoopBackOff to appear…")
    time.sleep(20)
    print(_run(["kubectl", "get", "pods", "-n", ns, "-l", f"app={app}"]))


def scenario_oom(app: str, ns: str) -> None:
    pod = _pod(app, ns)
    print(f"[*] injecting OOM on {pod}")
    for _ in range(3):
        _post_failure(app, ns, "/fail/oom")
    time.sleep(15)
    print(_run(["kubectl", "get", "pods", "-n", ns, "-l", f"app={app}"]))


def scenario_cpu(app: str, ns: str) -> None:
    _post_failure(app, ns, "/fail/cpu")
    print("[*] CPU spin started; watch SampleAppHighCPU after ~4m")


def scenario_error(app: str, ns: str, seconds: int) -> None:
    _post_failure(app, ns, "/fail/error")
    path = TRAFFIC_TARGETS[app][0]
    code = (
        "import urllib.request,time\n"
        f"end=time.time()+{seconds}\n"
        "while time.time()<end:\n"
        "  for _ in range(10):\n"
        "    try: urllib.request.urlopen('http://localhost:8000%s',timeout=2)\n"
        "    except Exception: pass\n" % path
    )
    _exec(app, ns, ["python", "-c", code])
    print("[*] error injection complete; SampleAppErrorRateHigh should fire within ~2m")


def scenario_image_pull(app: str, ns: str) -> None:
    print(f"[*] set image deployment/{app} to non-existent tag")
    _run(
        [
            "kubectl",
            "set",
            "image",
            f"deployment/{app}",
            f"{app}=klarnova/{app}:does-not-exist",
            "-n",
            ns,
        ]
    )
    time.sleep(20)
    print(_run(["kubectl", "get", "pods", "-n", ns, "-l", f"app={app}"]))


def scenario_reset(app: str, ns: str) -> None:
    _patch_cm(app, ns, "FAIL_MODE", "")
    _restart(app, ns)
    _post_failure(app, ns, "/fail/reset")
    print(f"[*] reset complete for {app}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=["crash", "oom", "cpu", "error", "image-pull", "reset"])
    parser.add_argument("--app", default="checkout", choices=["checkout", "inventory", "cart"])
    parser.add_argument("--ns", default="sample")
    parser.add_argument("--seconds", type=int, default=30, help="duration of error scenario")
    args = parser.parse_args()

    scenarios = {
        "crash": scenario_crash,
        "oom": scenario_oom,
        "cpu": scenario_cpu,
        "error": lambda a, n: scenario_error(a, n, args.seconds),
        "image-pull": scenario_image_pull,
        "reset": scenario_reset,
    }
    scenarios[args.scenario](args.app, args.ns)


if __name__ == "__main__":
    sys.exit(main())
