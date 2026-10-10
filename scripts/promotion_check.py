"""Pipeline step: ask Agent Authority whether an agent version may be promoted.

Agreed rule: untested-in-prod blocks; version regression warns (the tenant can switch it
to block). The endpoint is launch gap 11 on Agent Authority's side; until it ships, set
AUTHORITY_PROMOTION_URL empty and this step reports "skipped".

Usage: python scripts/promotion_check.py <agent_id> <version> <target_env>
"""

import json
import os
import sys
import urllib.request


def main() -> int:
    agent_id, version, target = sys.argv[1:4]
    url = os.environ.get("AUTHORITY_PROMOTION_URL", "")
    if not url:
        print("promotion check skipped: AUTHORITY_PROMOTION_URL not set (Agent Authority gap 11)")
        return 0
    req = urllib.request.Request(
        url, method="POST",
        data=json.dumps({"agentId": agent_id, "version": version, "targetEnvironment": target}).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {os.environ['AUTHORITY_INGEST_KEY']}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.load(resp)
    except Exception as exc:  # fail closed: no answer, no promotion
        print(f"promotion check failed closed: {exc}")
        return 1
    for finding in body.get("findings", []):
        print(f"- {finding}")
    outcome = body.get("outcome")
    print(f"promotion check: {outcome}")
    return 0 if outcome in ("pass", "warn") else 1


if __name__ == "__main__":
    sys.exit(main())
