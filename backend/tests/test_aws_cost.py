import boto3
from moto import mock_aws

from app.aws_cost import dynamodb_cost, item_rru, item_wru, lambda_cost


def test_item_wru_rounds_up_to_the_nearest_1kb_write_unit():
    assert item_wru({"a": "x"}) == 1  # tiny item, still costs a minimum of 1 WRU
    big_item = {"a": "x" * 2000}
    assert item_wru(big_item) == 2  # just over 1KB rounds up to 2 WRU


def test_item_rru_rounds_up_to_the_nearest_4kb_read_unit():
    assert item_rru({"a": "x"}) == 1
    big_item = {"a": "x" * 5000}
    assert item_rru(big_item) == 2


def test_lambda_cost_formula():
    # 1 invocation, 1 second at 0.5 GB: request cost + GB-second cost
    cost = lambda_cost(1, 1.0, memory_gb=0.5)
    expected = (0.20 / 1_000_000) * 1 + 0.5 * 0.0000166667
    assert abs(cost - expected) < 1e-12


def test_dynamodb_cost_formula():
    cost = dynamodb_cost(1_000_000, 1_000_000)
    assert abs(cost - (1.25 + 0.25)) < 1e-9


@mock_aws
def test_real_batch_write_and_get_item_against_moto_dynamodb():
    dynamodb = boto3.client("dynamodb", region_name="us-east-1")
    dynamodb.create_table(
        TableName="test-table",
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    dynamodb.batch_write_item(
        RequestItems={
            "test-table": [
                {"PutRequest": {"Item": {"pk": {"S": "A#POSITION#SYM-1"}, "status": {"S": "MATCHED"}}}},
            ]
        }
    )
    resp = dynamodb.get_item(TableName="test-table", Key={"pk": {"S": "A#POSITION#SYM-1"}}, ConsistentRead=True)
    assert resp["Item"]["status"]["S"] == "MATCHED"
