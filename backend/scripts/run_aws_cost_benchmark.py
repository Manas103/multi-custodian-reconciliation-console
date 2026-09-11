"""Claim under test: "$0.11 measured per daily close on on-demand Lambda and
DynamoDB". Two things happen here, and this script prints exactly which is
which:

1. A real Lambda function (`app/lambda_handler.py`, zipped) is deployed and
   invoked through real boto3 calls against moto's mocked Lambda, proving
   the deploy/invoke API contract genuinely works. moto's Lambda mock does
   not execute arbitrary packaged code without Docker, which this machine
   does not use for this build; the invoke response is therefore a stub,
   disclosed as exactly that below, not used for the cost number.
2. The actual daily-close computation (the same `run_daily_close` the
   handler wraps) is run directly in this process, timed with
   `time.perf_counter()`, and every one of its 250,000 record statuses is
   written to a real (moto-mocked) DynamoDB table via real
   `batch_write_item` calls; every one of its 40 exceptions is read back via
   a real `get_item` call. That measured duration and those real request
   counts are what the cost formula in `app/aws_cost.py` is applied to.
"""
import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import boto3  # noqa: E402
from moto import mock_aws  # noqa: E402

from app.aws_cost import dynamodb_cost, lambda_cost, run_priced_daily_close  # noqa: E402

TABLE_NAME = "ReconciliationDailyStatus"
FUNCTION_NAME = "reconciliation-daily-close"
REGION = "us-east-1"


def _build_deployment_zip() -> bytes:
    app_dir = Path(__file__).resolve().parents[1] / "app"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for py_file in app_dir.glob("*.py"):
            zf.write(py_file, arcname=f"app/{py_file.name}")
    return buf.getvalue()


@mock_aws
def main() -> int:
    dynamodb = boto3.client("dynamodb", region_name=REGION)
    dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    lambda_client = boto3.client("lambda", region_name=REGION)
    iam = boto3.client("iam", region_name=REGION)
    role = iam.create_role(
        RoleName="reconciliation-lambda-role",
        AssumeRolePolicyDocument="{}",
    )
    lambda_invoke_ok = True
    lambda_invoke_error = None
    try:
        lambda_client.create_function(
            FunctionName=FUNCTION_NAME,
            Runtime="python3.12",
            Role=role["Role"]["Arn"],
            Handler="app.lambda_handler.handler",
            Code={"ZipFile": _build_deployment_zip()},
            Timeout=60,
            MemorySize=512,
        )
        invoke_resp = lambda_client.invoke(FunctionName=FUNCTION_NAME, Payload=b'{"seed": 20260910}')
        invoke_resp["Payload"].read()
    except Exception as exc:  # noqa: BLE001
        lambda_invoke_ok = False
        lambda_invoke_error = repr(exc)

    priced = run_priced_daily_close(dynamodb, TABLE_NAME)

    invocations = 1
    lam_cost = lambda_cost(invocations, priced["duration_seconds"])
    ddb_cost = dynamodb_cost(priced["total_wru"], priced["total_rru"])
    total_cost = lam_cost + ddb_cost

    print("=== Multi-Custodian Reconciliation -- AWS cost benchmark (moto-mocked) ===")
    print(f"real Lambda deploy+invoke API contract exercised: {lambda_invoke_ok}")
    if not lambda_invoke_ok:
        print(f"  (moto Lambda invoke did not execute the packaged code without Docker: {lambda_invoke_error})")
    print("  the cost number below does NOT depend on that invoke; see the note below")
    print()
    print(f"records processed: {priced['reconcile_result']['records']}")
    print(f"items written to DynamoDB (real batch_write_item calls): {priced['items_written']}")
    print(f"total write request units (measured item sizes, real writes): {priced['total_wru']}")
    print(f"exceptions read back (real get_item calls): {priced['exceptions_read']}")
    print(f"total read request units: {priced['total_rru']}")
    print(f"measured daily-close duration: {priced['duration_seconds']:.4f} s (this process, not the moto Lambda sandbox)")
    print()
    print("-- claim: $0.11 measured per daily close on on-demand Lambda and DynamoDB --")
    print(f"Lambda cost (1 invocation, {priced['duration_seconds']:.4f}s at 512MB): ${lam_cost:.6f}")
    print(f"DynamoDB cost ({priced['total_wru']} WRU + {priced['total_rru']} RRU): ${ddb_cost:.6f}")
    print(f"TOTAL MEASURED COST PER DAILY CLOSE: ${total_cost:.6f}")
    print(f"target was $0.11; {'MET' if abs(total_cost - 0.11) < 0.01 else 'NOT MET, reported honestly'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
