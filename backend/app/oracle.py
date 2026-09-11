"""The independent oracle: sorts both feeds by match key and walks them with
a merge join, never building a hash index. This is a deliberately different
algorithm from `matcher.py`'s dict-based lookup, so the two disagreeing would
mean an indexing bug in one of them, not a shared blind spot. `diff_breaks`
compares the two implementations' output field by field over the full
250,000-record population; that diff, not a spot check, is what "exact
agreement with an independent oracle" means in this repo.
"""
from __future__ import annotations

from .models import Break, BreakRule, Record
from .seed import PRICE_TOLERANCE


def run_oracle_match(book: list[Record], custodian: list[Record]) -> list[Break]:
    sorted_book = sorted(book, key=lambda r: r.match_key())
    sorted_custodian = sorted(custodian, key=lambda r: r.match_key())

    breaks: list[Break] = []
    i, j = 0, 0
    n, m = len(sorted_book), len(sorted_custodian)

    while i < n:
        book_rec = sorted_book[i]
        bkey = book_rec.match_key()

        # advance j past any custodian records that sort before this book key
        # (an orphan custodian record with no book counterpart at all; not
        # produced by this repo's seed generator, but handled for correctness)
        while j < m and sorted_custodian[j].match_key() < bkey:
            j += 1

        if j >= m or sorted_custodian[j].match_key() != bkey:
            breaks.append(
                Break(book_rec.account, book_rec.record_type, book_rec.key,
                      BreakRule.MISSING, "presence", "absent", "present")
            )
            i += 1
            continue

        group_start = j
        while j < m and sorted_custodian[j].match_key() == bkey:
            j += 1
        group = sorted_custodian[group_start:j]

        brk = _compare(book_rec, group)
        if brk is not None:
            breaks.append(brk)
        i += 1

    return breaks


def _compare(book_rec: Record, custodian_group: list[Record]) -> Break | None:
    if len(custodian_group) > 1:
        return Break(
            book_rec.account, book_rec.record_type, book_rec.key,
            BreakRule.DUPLICATE, "record_count", str(len(custodian_group)), "1",
        )
    c = custodian_group[0]
    if c.as_of_date != book_rec.as_of_date:
        return Break(
            book_rec.account, book_rec.record_type, book_rec.key,
            BreakRule.TIMING, "as_of_date", c.as_of_date, book_rec.as_of_date,
        )
    if abs(c.quantity - book_rec.quantity) > 1e-9:
        return Break(
            book_rec.account, book_rec.record_type, book_rec.key,
            BreakRule.QUANTITY, "quantity", str(c.quantity), str(book_rec.quantity),
        )
    tolerance = PRICE_TOLERANCE * max(book_rec.price, 1e-9)
    if abs(c.price - book_rec.price) > tolerance:
        return Break(
            book_rec.account, book_rec.record_type, book_rec.key,
            BreakRule.PRICE, "price", str(c.price), str(book_rec.price),
        )
    return None


def diff_breaks(fast_breaks: list[Break], oracle_breaks: list[Break]) -> dict:
    fast_by_key = {(b.account, b.record_type.value, b.key): b for b in fast_breaks}
    oracle_by_key = {(b.account, b.record_type.value, b.key): b for b in oracle_breaks}

    all_keys = set(fast_by_key) | set(oracle_by_key)
    mismatches = []
    for k in all_keys:
        f = fast_by_key.get(k)
        o = oracle_by_key.get(k)
        if (f is None) != (o is None):
            mismatches.append({"key": k, "fast": f.to_dict() if f else None, "oracle": o.to_dict() if o else None})
        elif f is not None and o is not None and f.to_dict() != o.to_dict():
            mismatches.append({"key": k, "fast": f.to_dict(), "oracle": o.to_dict()})

    return {
        "fast_break_count": len(fast_breaks),
        "oracle_break_count": len(oracle_breaks),
        "mismatches": mismatches,
    }
