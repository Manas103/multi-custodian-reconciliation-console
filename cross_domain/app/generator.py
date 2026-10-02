"""Deterministic synthetic data for 500 accounts x 120 days (60,000 cells),
each a value computed by two independently modeled domains.

Every cell has an underlying truth (a list of position-value ``parts``)
that both domains are built from, by two genuinely different formulas:

``domain_a`` (the custody book of record): sums every part, adds any
accrued-but-unsettled trade value and any restricted/held-away asset
value the custody ledger counts as part of "position value", and rounds
once at the end.

``domain_b`` (the advisory performance NAV engine): by definition and by
scope, counts neither accrued-unsettled trades nor restricted assets as
part of "account value"; its only other failure modes are a one-day
lag recognizing an external cash flow (12 seeded cells) and, on a
disjoint set of 12 cells, rounding each part to the cent before summing
instead of rounding once at the end.

48 cells (12 per cause: definition, timing, scope, rounding) are chosen,
disjoint, from the full 60,000 and perturbed; every other cell agrees
to the cent by construction.
"""

from __future__ import annotations

import random

N_ACCOUNTS = 500
N_DAYS = 120
N_PARTS = 5
CAUSES = ("definition", "timing", "scope", "rounding")
BREAKS_PER_CAUSE = 12


def account_ids() -> list[str]:
    return [f"ACCT-{i:05d}" for i in range(N_ACCOUNTS)]


def all_cells() -> list[tuple[str, int]]:
    return [(acct, day) for acct in account_ids() for day in range(N_DAYS)]


def choose_break_cells(seed: int = 909) -> dict[tuple[str, int], str]:
    """48 disjoint (account, day) cells mapped to their seeded cause."""
    rng = random.Random(seed)
    cells = all_cells()
    chosen = rng.sample(cells, BREAKS_PER_CAUSE * len(CAUSES))
    assignment: dict[tuple[str, int], str] = {}
    for i, cell in enumerate(chosen):
        cause = CAUSES[i // BREAKS_PER_CAUSE]
        assignment[cell] = cause
    return assignment


def generate(seed: int = 1) -> list[dict]:
    """One row per (account, day) cell: both domains' reported values plus
    the auxiliary observable fields a reconciliation desk would actually
    have (accrued trade value, restricted asset value, net external
    flow, and the underlying parts), so the classifier below works from
    evidence, not from knowing which cells were seeded."""
    rng = random.Random(seed)
    break_cells = choose_break_cells(seed=seed + 8000)
    rows = []
    for acct in account_ids():
        for day in range(N_DAYS):
            cause = break_cells.get((acct, day))
            if cause == "rounding":
                # Each part sits 0.6 cents above a clean 2-decimal dollar
                # value. Summed first then rounded once, that 0.6-cent
                # overhang on 5 parts (3.0 cents) rounds to a 3-cent
                # addition; rounded individually first, each part's 0.6
                # cents rounds up to a full cent before summing (5 cents
                # total). The resulting 2-cent gap is deterministic, not
                # a matter of how the random draws happen to land, which
                # a purely random sub-cent residue was not (see Findings).
                parts = [round(rng.uniform(500, 15000), 2) + 0.006 for _ in range(N_PARTS)]
            else:
                parts = [round(rng.uniform(500, 15000), 4) for _ in range(N_PARTS)]
            true_value = sum(parts)

            accrued = 0.0
            restricted = 0.0
            flow = 0.0

            if cause == "definition":
                accrued = round(rng.uniform(50, 500), 2)
            elif cause == "scope":
                restricted = round(rng.uniform(100, 1000), 2)
            elif cause == "timing":
                sign = rng.choice([1, -1])
                flow = round(rng.uniform(100, 3000) * sign, 2)

            domain_a_value = round(true_value + accrued + restricted, 2)

            if cause == "rounding":
                domain_b_value = round(sum(round(p, 2) for p in parts), 2)
            else:
                domain_b_value = round(true_value, 2)
                if cause == "timing":
                    domain_b_value = round(domain_b_value - flow, 2)

            rows.append({
                "account_id": acct,
                "day": day,
                "parts": parts,
                "accrued_unsettled_trade_value": accrued,
                "restricted_asset_value": restricted,
                "net_external_flow": flow,
                "domain_a_value": domain_a_value,
                "domain_b_value": domain_b_value,
                "seeded_cause": cause,
            })
    return rows
