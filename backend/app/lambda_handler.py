"""The AWS Lambda handler this project's daily-close pipeline packages and
deploys. It wraps `reconcile.run_daily_close` and returns a small JSON-safe
summary plus the exception rows a React console renders. This exact
function is what `scripts/run_aws_cost_benchmark.py` zips and deploys to a
real (moto-mocked) Lambda function to prove the deploy/invoke contract; see
that script and the README's honest framing section for exactly how much of
this build's cost measurement ran inside the mocked sandbox versus in this
process directly.
"""
from __future__ import annotations

import json

from .reconcile import run_daily_close


def handler(event, context=None):
    seed = int(event.get("seed", 20260910)) if isinstance(event, dict) else 20260910
    result = run_daily_close(seed)
    exceptions = [b.to_dict() for b in result["fast_breaks"]]
    body = {
        "accounts": result["accounts"],
        "records": result["records"],
        "seeded_breaks_caught": result["seeded_breaks_caught"],
        "seeded_breaks_total": result["seeded_breaks_total"],
        "false_holds": result["false_holds"],
        "exceptions": exceptions,
    }
    return {"statusCode": 200, "body": json.dumps(body)}
