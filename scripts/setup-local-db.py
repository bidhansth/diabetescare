#!/usr/bin/env python3
import os
import boto3

ENDPOINT = os.getenv("DYNAMODB_ENDPOINT_URL", "http://localhost:8000")
TABLE_NAME = os.getenv("DYNAMODB_TABLE", "DiabetesCare")

client = boto3.client("dynamodb", region_name="us-east-1", endpoint_url=ENDPOINT)

existing = client.list_tables()["TableNames"]
if TABLE_NAME in existing:
    print(f"Table '{TABLE_NAME}' already exists")
else:
    client.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    print(f"Table '{TABLE_NAME}' created")
