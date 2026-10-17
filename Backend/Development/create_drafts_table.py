"""
DynamoDB Table Provisioning Script
==================================

Creates the `paper-drafts` table used to persist in-progress question papers.

Run once (idempotent — it skips creation if the table already exists):

    python create_drafts_table.py

Table design
------------
- Partition key: userId (S)   -> scopes drafts to a user; enables cheap "list my drafts"
- Sort key:      draftId (S)  -> unique id per draft within a user
- GSI: draftId-index          -> direct lookup by draftId when userId isn't known
- TTL: expiresAt (Number)     -> auto-delete abandoned drafts (~90 days after last update)

Billing mode is PAY_PER_REQUEST (on-demand) so there's nothing to capacity-plan
for an MVP and cost tracks actual usage.
"""

import os
import sys
import time

# Load .env if python-dotenv is available (so AWS creds/region resolve locally).
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import boto3
from botocore.exceptions import ClientError

AWS_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "ap-south-1"))
TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "paper-drafts")


def table_exists(client, name: str) -> bool:
    try:
        client.describe_table(TableName=name)
        return True
    except client.exceptions.ResourceNotFoundException:
        return False


def create_table():
    client = boto3.client("dynamodb", region_name=AWS_REGION)

    if table_exists(client, TABLE_NAME):
        print(f"[skip] Table '{TABLE_NAME}' already exists in {AWS_REGION}.")
        return

    print(f"[create] Creating table '{TABLE_NAME}' in {AWS_REGION} ...")
    client.create_table(
        TableName=TABLE_NAME,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "userId", "AttributeType": "S"},
            {"AttributeName": "draftId", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "userId", "KeyType": "HASH"},   # partition key
            {"AttributeName": "draftId", "KeyType": "RANGE"},  # sort key
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "draftId-index",
                "KeySchema": [
                    {"AttributeName": "draftId", "KeyType": "HASH"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )

    # Wait until the table is active before enabling TTL.
    print("[wait] Waiting for table to become ACTIVE ...")
    waiter = client.get_waiter("table_exists")
    waiter.wait(TableName=TABLE_NAME)

    # Enable TTL on expiresAt. Retry briefly since TTL update can race table activation.
    for attempt in range(5):
        try:
            client.update_time_to_live(
                TableName=TABLE_NAME,
                TimeToLiveSpecification={"Enabled": True, "AttributeName": "expiresAt"},
            )
            print("[ttl] Enabled TTL on attribute 'expiresAt'.")
            break
        except ClientError as e:
            print(f"[ttl] Attempt {attempt + 1} failed: {e}. Retrying ...")
            time.sleep(3)
    else:
        print("[ttl] WARNING: could not enable TTL automatically. Enable it manually in the console.")

    print(f"[done] Table '{TABLE_NAME}' is ready.")


if __name__ == "__main__":
    try:
        create_table()
    except ClientError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)
