"""Measures the AWS cost of one daily close on real (moto-mocked) Lambda and
DynamoDB, following the `hil-bench-serverless-api` precedent in this
portfolio (moto-mocked Lambda, real boto3 calls against the mock). This
machine has no real AWS account; moto's DynamoDB backend fully implements
CreateTable/BatchWriteItem/GetItem in memory, so every DynamoDB number below
comes from real boto3 calls. moto's Lambda mock validates the real
CreateFunction/Invoke API contract, but does not execute arbitrary packaged
code without Docker, which is not used by this build (BUILDER.md names no
Docker requirement for this machine); see `run_aws_cost_benchmark.py` and
the README's honest framing section for exactly what that means for the
Lambda duration number below.

Pricing: AWS's publicly published on-demand rates (general, not fetched live
during this build, and not region- or account-specific negotiated pricing):
Lambda $0.20 per 1,000,000 requests plus $0.0000166667 per GB-second;
DynamoDB on-demand $1.25 per million write request units (1 WRU = one write
of an item up to 1 KB, rounded up) and $0.25 per million read request units
(1 RRU = one strongly consistent read of an item up to 4 KB, rounded up).
"""
from __future__ import annotations

import json
import time

LAMBDA_PRICE_PER_REQUEST = 0.20 / 1_000_000
LAMBDA_PRICE_PER_GB_SECOND = 0.0000166667
LAMBDA_MEMORY_GB = 0.5  # 512 MB, this pipeline's assumed configured memory size

DYNAMODB_PRICE_PER_MILLION_WRU = 1.25
DYNAMODB_PRICE_PER_MILLION_RRU = 0.25
DYNAMODB_WRITE_UNIT_BYTES = 1024
DYNAMODB_READ_UNIT_BYTES = 4096


def item_wru(item: dict) -> int:
    size = len(json.dumps(item, default=str).encode("utf-8"))
    return max(1, -(-size // DYNAMODB_WRITE_UNIT_BYTES))  # ceil division


def item_rru(item: dict) -> int:
    size = len(json.dumps(item, default=str).encode("utf-8"))
    return max(1, -(-size // DYNAMODB_READ_UNIT_BYTES))  # ceil division, strongly consistent


def lambda_cost(num_invocations: int, total_duration_seconds: float, memory_gb: float = LAMBDA_MEMORY_GB) -> float:
    gb_seconds = total_duration_seconds * memory_gb
    return num_invocations * LAMBDA_PRICE_PER_REQUEST + gb_seconds * LAMBDA_PRICE_PER_GB_SECOND


def dynamodb_cost(total_wru: int, total_rru: int) -> float:
    return (total_wru / 1_000_000) * DYNAMODB_PRICE_PER_MILLION_WRU + (
        total_rru / 1_000_000
    ) * DYNAMODB_PRICE_PER_MILLION_RRU


def run_priced_daily_close(dynamodb_client, table_name: str) -> dict:
    """Runs one full daily close, writes every record's reconciliation
    status to the given (moto-mocked) DynamoDB table via real
    BatchWriteItem calls, reads back every exception via real GetItem calls,
    and returns the measured duration and request-unit totals this
    function's Lambda invocation would be billed for.
    """
    from .reconcile import run_daily_close

    start = time.perf_counter()
    result = run_daily_close()
    scenario = result["scenario"]
    fast_breaks = result["fast_breaks"]
    held_keys = {(b.account, b.record_type.value, b.key): b for b in fast_breaks}

    items = []
    for rec in scenario.book:
        key = rec.match_key()
        held = key in held_keys
        item = {
            "pk": f"{rec.account}#{rec.record_type.value}#{rec.key}",
            "as_of_date": rec.as_of_date,
            "status": "HELD" if held else "MATCHED",
            "rule": held_keys[key].rule.value if held else None,
        }
        items.append(item)

    total_wru = 0
    batch_size = 25
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        request_items = {
            table_name: [{"PutRequest": {"Item": {k: {"S": str(v)} for k, v in item.items() if v is not None}}} for item in batch]
        }
        dynamodb_client.batch_write_item(RequestItems=request_items)
        total_wru += sum(item_wru(item) for item in batch)

    total_rru = 0
    for b in fast_breaks:
        pk = f"{b.account}#{b.record_type.value}#{b.key}"
        resp = dynamodb_client.get_item(TableName=table_name, Key={"pk": {"S": pk}}, ConsistentRead=True)
        total_rru += item_rru(resp.get("Item", {}))

    elapsed = time.perf_counter() - start

    return {
        "duration_seconds": elapsed,
        "items_written": len(items),
        "total_wru": total_wru,
        "exceptions_read": len(fast_breaks),
        "total_rru": total_rru,
        "reconcile_result": result,
    }
