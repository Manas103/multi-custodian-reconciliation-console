from app import generator


def test_60000_account_days():
    rows = generator.generate(seed=1)
    assert len(rows) == generator.N_ACCOUNTS * generator.N_DAYS == 60000


def test_48_break_cells_12_per_cause():
    assignment = generator.choose_break_cells(seed=1 + 8000)
    assert len(assignment) == 48
    by_cause: dict[str, int] = {}
    for cause in assignment.values():
        by_cause[cause] = by_cause.get(cause, 0) + 1
    assert by_cause == {"definition": 12, "timing": 12, "scope": 12, "rounding": 12}


def test_break_cells_are_disjoint():
    assignment = generator.choose_break_cells(seed=1 + 8000)
    assert len(set(assignment)) == 48


def test_deterministic():
    a = generator.generate(seed=5)
    b = generator.generate(seed=5)
    assert a == b


def test_clean_cells_agree_exactly():
    rows = generator.generate(seed=2)
    clean = [r for r in rows if r["seeded_cause"] is None]
    assert len(clean) == 60000 - 48
    for r in clean:
        assert abs(r["domain_a_value"] - r["domain_b_value"]) <= 0.01


def test_seeded_cells_disagree():
    rows = generator.generate(seed=2)
    seeded = [r for r in rows if r["seeded_cause"] is not None]
    assert len(seeded) == 48
    for r in seeded:
        assert abs(r["domain_a_value"] - r["domain_b_value"]) > 0.01
