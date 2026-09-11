"""The fast matcher: a single hash-indexed pass over the custodian feed,
diffed against the book of record. O(n) in the combined record count.
`oracle.py` is a second, independently written implementation (sort and
merge, not a hash index) that this module is diffed against exactly; see the
README's Validation section for what that diff proves and does not prove.

Every held record names exactly one rule, in a fixed priority order
(duplicate, missing, timing, quantity, price), mirroring the fixed-order
convention this application's sibling repo (allocation-affirmation-workflow)
uses for pre-trade compliance: a caller is never told just "held", only
which rule fired and what the disagreeing value was.
"""
from __future__ import annotations

from collections import defaultdict

from .models import Break, BreakRule, Record, RecordType
from .seed import PRICE_TOLERANCE


def run_fast_match(book: list[Record], custodian: list[Record]) -> list[Break]:
    custodian_by_key: dict[tuple, list[Record]] = defaultdict(list)
    for rec in custodian:
        custodian_by_key[rec.match_key()].append(rec)

    breaks: list[Break] = []
    for b in book:
        matches = custodian_by_key.get(b.match_key(), [])
        brk = _classify(b, matches)
        if brk is not None:
            breaks.append(brk)
    return breaks


def _classify(book_rec: Record, custodian_matches: list[Record]) -> Break | None:
    if len(custodian_matches) > 1:
        return Break(
            account=book_rec.account,
            record_type=book_rec.record_type,
            key=book_rec.key,
            rule=BreakRule.DUPLICATE,
            disagreeing_field="record_count",
            custodian_value=str(len(custodian_matches)),
            book_value="1",
        )
    if len(custodian_matches) == 0:
        return Break(
            account=book_rec.account,
            record_type=book_rec.record_type,
            key=book_rec.key,
            rule=BreakRule.MISSING,
            disagreeing_field="presence",
            custodian_value="absent",
            book_value="present",
        )
    c = custodian_matches[0]
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
