from app.matcher import run_fast_match
from app.models import BreakRule, Record, RecordType
from app.oracle import diff_breaks, run_oracle_match
from app.reconcile import run_daily_close, run_oracle_diff
from app.seed import NUM_ACCOUNTS, TOTAL_RECORDS, generate_daily_close


def test_seed_generates_exactly_40_disjoint_breaches():
    scenario = generate_daily_close(20260910)
    assert len(scenario.book) == TOTAL_RECORDS
    assert len(scenario.expected_breaks) == 40
    by_rule = {}
    for rule in scenario.expected_breaks.values():
        by_rule[rule] = by_rule.get(rule, 0) + 1
    assert by_rule == {"timing": 8, "quantity": 8, "price": 8, "missing": 8, "duplicate": 8}


def test_fast_matcher_missing_record():
    book = [Record("A1", RecordType.POSITION, "SYM-1", "2026-09-09", 100, 50)]
    breaks = run_fast_match(book, [])
    assert len(breaks) == 1
    assert breaks[0].rule == BreakRule.MISSING


def test_fast_matcher_duplicate_record():
    r = Record("A1", RecordType.POSITION, "SYM-1", "2026-09-09", 100, 50)
    breaks = run_fast_match([r], [r, r])
    assert len(breaks) == 1
    assert breaks[0].rule == BreakRule.DUPLICATE


def test_fast_matcher_timing_quantity_price_breaks():
    from dataclasses import replace

    book_rec = Record("A1", RecordType.POSITION, "SYM-1", "2026-09-09", 100, 50)

    timing = run_fast_match([book_rec], [replace(book_rec, as_of_date="2026-09-08")])
    assert timing[0].rule == BreakRule.TIMING

    quantity = run_fast_match([book_rec], [replace(book_rec, quantity=150)])
    assert quantity[0].rule == BreakRule.QUANTITY

    price = run_fast_match([book_rec], [replace(book_rec, price=60)])
    assert price[0].rule == BreakRule.PRICE


def test_fast_matcher_clean_record_is_not_held():
    r = Record("A1", RecordType.POSITION, "SYM-1", "2026-09-09", 100, 50)
    breaks = run_fast_match([r], [r])
    assert breaks == []


def test_full_daily_close_catches_all_seeded_breaks_with_no_false_holds():
    result = run_daily_close()
    assert result["accounts"] == NUM_ACCOUNTS
    assert result["records"] == TOTAL_RECORDS
    assert result["seeded_breaks_caught"] == result["seeded_breaks_total"] == 40
    assert result["false_holds"] == 0
    assert result["total_held"] == 40


def test_oracle_agrees_exactly_with_fast_matcher_over_the_full_population():
    result = run_daily_close()
    diff = run_oracle_diff(result["scenario"], result["fast_breaks"])
    assert diff["mismatches"] == []
    assert diff["fast_break_count"] == diff["oracle_break_count"] == 40


def test_oracle_independently_reimplemented_algorithm_matches_fast_matcher_on_small_fixture():
    from dataclasses import replace

    book = [
        Record("A1", RecordType.POSITION, "SYM-1", "2026-09-09", 100, 50),
        Record("A2", RecordType.CASH, "CASH-0", "2026-09-09", 0, 1000),
    ]
    custodian = [
        replace(book[0], quantity=150),  # quantity break
        book[1],  # clean
    ]
    fast = run_fast_match(book, custodian)
    oracle = run_oracle_match(book, custodian)
    diff = diff_breaks(fast, oracle)
    assert diff["mismatches"] == []
    assert len(fast) == 1 and fast[0].rule == BreakRule.QUANTITY
