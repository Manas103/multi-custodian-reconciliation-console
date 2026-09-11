"""Orchestrates one daily close: generate the seeded scenario, run the fast
matcher, and score it against the seeded expectations. This module has no
AWS dependency; `lambda_handler.py` and `aws_cost.py` build on top of it.
"""
from __future__ import annotations

from .matcher import run_fast_match
from .models import Break
from .oracle import run_oracle_match, diff_breaks
from .seed import NUM_ACCOUNTS, TOTAL_RECORDS, generate_daily_close


def run_daily_close(seed: int = 20260910) -> dict:
    scenario = generate_daily_close(seed)
    fast_breaks = run_fast_match(scenario.book, scenario.custodian)

    seeded_keys = set(scenario.expected_breaks.keys())
    fast_by_key = {(b.account, b.record_type.value, b.key): b for b in fast_breaks}

    seeded_caught = 0
    for key, rule in scenario.expected_breaks.items():
        found = fast_by_key.get(key)
        if found is not None and found.rule.value == rule:
            seeded_caught += 1

    false_holds = [b for b in fast_breaks if (b.account, b.record_type.value, b.key) not in seeded_keys]

    return {
        "accounts": NUM_ACCOUNTS,
        "records": TOTAL_RECORDS,
        "seeded_breaks_total": len(seeded_keys),
        "seeded_breaks_caught": seeded_caught,
        "false_holds": len(false_holds),
        "total_held": len(fast_breaks),
        "scenario": scenario,
        "fast_breaks": fast_breaks,
        "false_hold_breaks": false_holds,
    }


def run_oracle_diff(scenario, fast_breaks: list[Break]) -> dict:
    oracle_breaks = run_oracle_match(scenario.book, scenario.custodian)
    return diff_breaks(fast_breaks, oracle_breaks)
