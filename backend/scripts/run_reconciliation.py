"""Claims under test: 500 accounts, 250,000 records, 40 of 40 seeded breaks
caught, 0 false holds over 250,000 records, exact agreement with an
independent oracle, differences classified by named rule. Runs the full
seeded daily close once with the fast matcher, then diffs it against the
independent sort-merge oracle over the same full population.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.reconcile import run_daily_close, run_oracle_diff  # noqa: E402


def main() -> int:
    result = run_daily_close()
    print("=== Multi-Custodian Reconciliation -- daily close ===")
    print(f"accounts: {result['accounts']}")
    print(f"records: {result['records']}")
    print()
    print("-- claim: 40 of 40 seeded breaks caught --")
    print(f"seeded breaks caught: {result['seeded_breaks_caught']} / {result['seeded_breaks_total']}")
    print()
    print("-- claim: 0 false holds over 250,000 records --")
    print(f"false holds: {result['false_holds']}")
    print()

    by_rule: dict[str, int] = {}
    for b in result["fast_breaks"]:
        by_rule[b.rule.value] = by_rule.get(b.rule.value, 0) + 1
    print("-- claim: differences classified by named rule --")
    for rule in ("timing", "quantity", "price", "missing", "duplicate"):
        print(f"  {rule}: {by_rule.get(rule, 0)}")
    print()

    diff = run_oracle_diff(result["scenario"], result["fast_breaks"])
    print("-- claim: exact agreement with an independent oracle --")
    print(f"fast matcher breaks: {diff['fast_break_count']}")
    print(f"oracle breaks: {diff['oracle_break_count']}")
    print(f"mismatches: {len(diff['mismatches'])}")
    for m in diff["mismatches"][:10]:
        print(f"  MISMATCH: {m}")

    ok = (
        result["seeded_breaks_caught"] == result["seeded_breaks_total"]
        and result["false_holds"] == 0
        and len(diff["mismatches"]) == 0
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
