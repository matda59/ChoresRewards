"""Snapshot image pulls, repo traffic, and anonymous install counters.

Run from a GitHub Action with GITHUB_TOKEN set. Without a token it still
records public pull and star counts.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import os

import usage_stats


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    # Actions checks out with a token even for local-looking env names.
    # An empty string should not be sent as a bearer token.
    token = token.strip() or None
    destination = ROOT / "stats" / "usage.json"
    try:
        snapshot = usage_stats.write_snapshot(destination, token)
    except Exception as exc:
        print(f"[usage] {exc}")
        return 1
    pulls = (snapshot.get("pulls") or {}).get("total")
    installs = (snapshot.get("installs") or {}).get("total")
    print(f"[usage] pulls={pulls} installs={installs} wrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
