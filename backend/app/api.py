"""A small FastAPI surface serving the break-triage console: the exception
queue the React frontend renders. Every route here serves synthetic demo
data (see the README's honest framing section); the reconciliation itself
runs once, at process start, exactly the same code path
`scripts/run_reconciliation.py` and the Lambda handler use.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .reconcile import run_daily_close

app = FastAPI(title="Multi-Custodian Reconciliation Console API")

# The React console runs on Vite's own dev-server origin, a different origin
# from this API's own OS-assigned port; a permissive CORS policy is what
# makes local development and the Playwright console test work, exactly the
# same tradeoff this application's allocation-affirmation-workflow sibling
# makes for the same reason. Everything served here is synthetic demo data.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_result = run_daily_close()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/summary")
def summary():
    return {
        "accounts": _result["accounts"],
        "records": _result["records"],
        "seeded_breaks_total": _result["seeded_breaks_total"],
        "seeded_breaks_caught": _result["seeded_breaks_caught"],
        "false_holds": _result["false_holds"],
        "total_held": _result["total_held"],
    }


@app.get("/exceptions")
def exceptions():
    return [b.to_dict() for b in _result["fast_breaks"]]
