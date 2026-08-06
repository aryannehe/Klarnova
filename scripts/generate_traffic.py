"""Generate HTTP traffic against sample apps (used with the error scenario)."""

from __future__ import annotations

import argparse
import random
import time
import urllib.request

TARGETS = ["/orders", "/orders/new", "/inventory", "/carts"]


def hit(pod_ip: str, port: int, path: str) -> int:
    try:
        with urllib.request.urlopen(f"http://{pod_ip}:{port}{path}", timeout=3) as resp:
            return resp.status
    except Exception:
        return 500


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--qps", type=float, default=10)
    args = parser.parse_args()

    end = time.time() + args.seconds
    sent = errors = 0
    while time.time() < end:
        path = random.choice(TARGETS)
        status = hit(args.host, args.port, path)
        sent += 1
        errors += 1 if status >= 500 else 0
        time.sleep(1.0 / args.qps)
    print(f"traffic done: {sent} requests, {errors} errors")


if __name__ == "__main__":
    main()
