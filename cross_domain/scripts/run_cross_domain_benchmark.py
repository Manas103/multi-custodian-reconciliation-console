"""Runs the cross-domain reconciliation over 60,000 account-days: 48
seeded cause-classified breaks, a 1,200-cell clean sample, and a
residual check over everything the classifier actually flags.

    python scripts/run_cross_domain_benchmark.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import generator, reconciler


def main() -> int:
    print("=== Cross-Domain Account Value Reconciliation -- benchmark ===")

    rows = generator.generate(seed=1)
    break_cells = generator.choose_break_cells(seed=1 + 8000)

    print(f"-- claim: 60,000 account-days --")
    print(f"account-days generated: {len(rows)} "
          f"({generator.N_ACCOUNTS} accounts x {generator.N_DAYS} days)")
    print()

    con = reconciler.connect()
    reconciler.load(con, rows)
    results = reconciler.reconcile(con)

    expected = {(r["account_id"], r["day"]): r["seeded_cause"] for r in rows if r["seeded_cause"]}
    got = {(r["account_id"], r["day"]): r for r in results}

    correct = 0
    for cell, cause in expected.items():
        row = got.get(cell)
        if row is not None and row["cause"] == cause:
            correct += 1
        else:
            print(f"  MISSED: {cell} expected={cause} got={row['cause'] if row else None}")

    print("-- claim: every disagreement attributed to a named cause (definition, timing, scope, rounding) --")
    by_cause: dict[str, int] = {}
    for row in results:
        by_cause[row["cause"]] = by_cause.get(row["cause"], 0) + 1
    print(f"causes used: {sorted(by_cause)}")
    print()

    print("-- claim: 48 of 48 seeded breaks landed in the correct class --")
    print(f"correct: {correct} / {len(expected)}")
    unexpected = [cell for cell in got if cell not in expected]
    print(f"unexpected flags (not seeded): {len(unexpected)}")
    print()

    clean_cells = [cell for cell in [(r["account_id"], r["day"]) for r in rows] if cell not in expected]
    rng = random.Random(55)
    sample = rng.sample(clean_cells, 1200)
    false_flags = sum(1 for cell in sample if cell in got)
    print("-- claim: 0 of 1,200 agreeing account-days falsely flagged --")
    print(f"false flags in a 1,200-cell clean sample: {false_flags} / 1200")
    print()

    max_residual = max((abs(row["residual"]) for row in results), default=0.0)
    unexplained = [row for row in results if row["cause"] == "unexplained"]
    print("-- claim: no unexplained residual above one cent --")
    print(f"max |residual| across all {len(results)} flagged account-days: {max_residual:.6f}")
    print(f"cells classified 'unexplained': {len(unexplained)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
