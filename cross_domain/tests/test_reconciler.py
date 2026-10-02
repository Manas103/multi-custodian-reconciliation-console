import random

from app import generator, reconciler


def _run():
    rows = generator.generate(seed=1)
    con = reconciler.connect()
    reconciler.load(con, rows)
    results = reconciler.reconcile(con)
    expected = {(r["account_id"], r["day"]): r["seeded_cause"] for r in rows if r["seeded_cause"]}
    return rows, results, expected


def test_loads_all_60000_cells():
    rows = generator.generate(seed=1)
    con = reconciler.connect()
    reconciler.load(con, rows)
    assert reconciler.total_cells(con) == 60000


def test_catches_all_48_seeded_breaks_in_the_correct_class():
    rows, results, expected = _run()
    got = {(r["account_id"], r["day"]): r["cause"] for r in results}
    for cell, cause in expected.items():
        assert got.get(cell) == cause, f"{cell} expected {cause}, got {got.get(cell)}"


def test_no_unexpected_flags():
    rows, results, expected = _run()
    unexpected = [(r["account_id"], r["day"]) for r in results
                  if (r["account_id"], r["day"]) not in expected]
    assert unexpected == []


def test_no_residual_above_one_cent():
    rows, results, expected = _run()
    for r in results:
        assert abs(r["residual"]) <= 0.01, r


def test_nothing_classified_unexplained():
    rows, results, expected = _run()
    unexplained = [r for r in results if r["cause"] == "unexplained"]
    assert unexplained == []


def test_1200_clean_sample_has_zero_false_flags():
    rows, results, expected = _run()
    got_cells = {(r["account_id"], r["day"]) for r in results}
    clean_cells = [(r["account_id"], r["day"]) for r in rows
                   if (r["account_id"], r["day"]) not in expected]
    sample = random.Random(99).sample(clean_cells, 1200)
    false_flags = [c for c in sample if c in got_cells]
    assert false_flags == []
