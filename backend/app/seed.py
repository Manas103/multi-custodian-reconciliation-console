"""Deterministic synthetic data generator: a 500-account book of record and
a custodian feed that agrees with it everywhere except 40 deliberately
seeded breaks, 8 per named rule (timing, quantity, price, missing,
duplicate). Nothing here is a real custodian, account, or position; this is
a labeled synthetic population, same discipline as the sibling repos in this
portfolio (`syntheticSeed.ts` in allocation-affirmation-workflow, `seed.py`
in ontology-grounded-operations-agent).
"""
from __future__ import annotations

from dataclasses import replace

from .models import Record, RecordType

NUM_ACCOUNTS = 500
RECORDS_PER_ACCOUNT = 500  # 500 accounts x 500 records = 250,000 book-of-record rows
TOTAL_RECORDS = NUM_ACCOUNTS * RECORDS_PER_ACCOUNT

SYMBOLS = ["ACME", "GLOB", "NOVA", "ORBT", "TERA", "VELO", "ZEN", "QUAD", "PLUM", "RISE"]
PRICE_TOLERANCE = 0.005  # 0.5% relative tolerance before a price difference is a break

NUM_BREACHES_PER_RULE = 8  # 5 rules x 8 = 40 total, matching "40 of 40 seeded breaks"


def pseudo_random(seed: int):
    """Same LCG family used across this application's other repos
    (allocation-affirmation-workflow's pseudoRandom), reimplemented in
    Python so this repo's synthetic data is reproducible independent of any
    other project's runtime.
    """
    state = seed & 0xFFFFFFFF

    def _next() -> float:
        nonlocal state
        state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
        return state / 4294967296.0

    return _next


def _generate_book(seed: int) -> list[Record]:
    rand = pseudo_random(seed)
    book: list[Record] = []
    for a in range(NUM_ACCOUNTS):
        account = f"ACCT-{a:04d}"
        for r in range(RECORDS_PER_ACCOUNT):
            slot = r % 10
            if slot == 0:
                # A cash sweep line, not one balance per account: real books
                # carry several cash movements per account per day. Keyed by
                # index so every one of the 50-per-account rows is a distinct
                # record, never a repeat of the same key.
                record_type = RecordType.CASH
                key = f"CASH-{r:04d}"
                quantity = 0.0
                price = round(500_000 + rand() * 500_000, 2)
            elif slot < 8:
                # A tax-lot-level position row, not one row per symbol: the
                # same symbol can appear in many distinct lots for the same
                # account, so the key carries the lot index, never just the
                # symbol alone.
                record_type = RecordType.POSITION
                symbol = SYMBOLS[r % len(SYMBOLS)]
                key = f"{symbol}-LOT-{r:04d}"
                quantity = float(100 + int(rand() * 900))
                price = round(10 + rand() * 190, 2)
            else:
                record_type = RecordType.TRANSACTION
                key = f"TXN-{account}-{r:04d}"
                quantity = float(1 + int(rand() * 500))
                price = round(10 + rand() * 190, 2)
            as_of_date = "2026-09-09"
            book.append(Record(account, record_type, key, as_of_date, quantity, price))
    return book


class SeededScenario:
    def __init__(self, book: list[Record], custodian: list[Record], expected_breaks: dict[tuple[str, str, str], str]):
        self.book = book
        self.custodian = custodian
        # keyed by (account, record_type, key) -> rule name, exactly 40 entries
        self.expected_breaks = expected_breaks


def generate_daily_close(seed: int = 20260910) -> SeededScenario:
    book = _generate_book(seed)
    rand = pseudo_random(seed ^ 0xA5A5A5A5)

    custodian: list[Record] = list(book)  # start as an exact mirror
    expected: dict[tuple[str, str, str], str] = {}

    # Pick disjoint indices for each rule's breaches so no record is
    # touched by more than one seeded break.
    pool = list(range(len(book)))
    # deterministic shuffle (Fisher-Yates with the same LCG)
    for i in range(len(pool) - 1, 0, -1):
        j = int(rand() * (i + 1))
        pool[i], pool[j] = pool[j], pool[i]

    idx = 0

    def next_indices(n: int) -> list[int]:
        nonlocal idx
        chosen = pool[idx : idx + n]
        idx += n
        return chosen

    # TIMING: custodian's as-of date disagrees with the book's.
    for i in next_indices(NUM_BREACHES_PER_RULE):
        r = book[i]
        custodian[i] = replace(r, as_of_date="2026-09-08")
        expected[r.match_key()] = "timing"

    # QUANTITY: custodian's quantity disagrees.
    for i in next_indices(NUM_BREACHES_PER_RULE):
        r = book[i]
        custodian[i] = replace(r, quantity=r.quantity + 50)
        expected[r.match_key()] = "quantity"

    # PRICE: custodian's price disagrees by well over the tolerance.
    for i in next_indices(NUM_BREACHES_PER_RULE):
        r = book[i]
        custodian[i] = replace(r, price=round(r.price * 1.10, 2))
        expected[r.match_key()] = "price"

    # MISSING: present in the book, absent from the custodian feed.
    missing_indices = set(next_indices(NUM_BREACHES_PER_RULE))
    for i in missing_indices:
        expected[book[i].match_key()] = "missing"
    custodian = [rec for i, rec in enumerate(custodian) if i not in missing_indices]

    # DUPLICATE: the custodian reports the same record twice.
    duplicate_indices = next_indices(NUM_BREACHES_PER_RULE)
    for i in duplicate_indices:
        custodian.append(book[i])
        expected[book[i].match_key()] = "duplicate"

    assert len(expected) == NUM_BREACHES_PER_RULE * 5, f"expected 40 seeded breaks, built {len(expected)}"
    return SeededScenario(book=book, custodian=custodian, expected_breaks=expected)
