"""Cause-classified reconciliation, in SQL, over DuckDB.

The classifier only ever reads what a reconciliation desk would actually
have: each domain's reported value, and three auxiliary observable
feeds (accrued-unsettled trade value from a trade blotter, restricted/
held-away asset value from a side-pocket register, and net external
flow from a cash-activity feed), plus the underlying position-value
parts. It never sees which cells were deliberately seeded; that ground
truth lives only in ``app/generator.py`` and is used purely to score
this module's output.
"""

from __future__ import annotations

import duckdb
import pandas as pd

MATERIALITY = 0.01

SCHEMA_SQL = """
CREATE OR REPLACE TABLE cells (
    account_id TEXT,
    day INTEGER,
    parts DOUBLE[],
    accrued_unsettled_trade_value DOUBLE,
    restricted_asset_value DOUBLE,
    net_external_flow DOUBLE,
    domain_a_value DOUBLE,
    domain_b_value DOUBLE
);
"""

RECONCILE_SQL = """
WITH base AS (
    SELECT
        account_id,
        day,
        domain_a_value,
        domain_b_value,
        accrued_unsettled_trade_value AS accrued,
        restricted_asset_value AS restricted,
        net_external_flow AS flow,
        round(domain_a_value - domain_b_value, 2) AS diff,
        round(
            round(list_sum(parts), 2)
            - list_sum(list_transform(parts, x -> round(x, 2))),
            2
        ) AS rounding_delta
    FROM cells
),
classified AS (
    SELECT
        *,
        CASE
            WHEN abs(diff) <= {materiality} THEN NULL
            WHEN accrued != 0 AND abs(diff - accrued) <= {materiality} THEN 'definition'
            WHEN restricted != 0 AND abs(diff - restricted) <= {materiality} THEN 'scope'
            WHEN flow != 0 AND abs(diff - flow) <= {materiality} THEN 'timing'
            WHEN abs(diff - rounding_delta) <= {materiality} THEN 'rounding'
            ELSE 'unexplained'
        END AS cause
    FROM base
)
SELECT
    account_id,
    day,
    diff,
    cause,
    CASE cause
        WHEN 'definition' THEN diff - accrued
        WHEN 'scope' THEN diff - restricted
        WHEN 'timing' THEN diff - flow
        WHEN 'rounding' THEN diff - rounding_delta
        WHEN 'unexplained' THEN diff
        ELSE 0.0
    END AS residual
FROM classified
WHERE cause IS NOT NULL
ORDER BY account_id, day;
""".format(materiality=MATERIALITY)


def connect(database: str = ":memory:"):
    return duckdb.connect(database)


COLUMNS = [
    "account_id", "day", "parts", "accrued_unsettled_trade_value",
    "restricted_asset_value", "net_external_flow", "domain_a_value", "domain_b_value",
]


def load(con, rows: list[dict]) -> None:
    con.execute(SCHEMA_SQL)
    if not rows:
        return
    # Loading through a pandas DataFrame and one INSERT ... SELECT FROM df,
    # not executemany: 60,000 separate bound statements against this
    # table's LIST(DOUBLE) column measured at over 10 minutes and were
    # killed before finishing; the DataFrame route measured well under a
    # second for the same 60,000 rows (see README Findings).
    df = pd.DataFrame([[r[c] for c in COLUMNS] for r in rows], columns=COLUMNS)
    con.execute("INSERT INTO cells SELECT * FROM df")


def reconcile(con) -> list[dict]:
    cur = con.execute(RECONCILE_SQL)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def total_cells(con) -> int:
    return con.execute("SELECT COUNT(*) FROM cells").fetchone()[0]
