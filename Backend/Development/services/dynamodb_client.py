"""
DynamoDB Client
===============

Centralizes the boto3 DynamoDB resource + table handle so the rest of the
backend doesn't repeat connection setup. Region and table name come from the
environment (falling back to sensible defaults matching the S3 setup).
"""

import services.env_bootstrap  # noqa: F401  (loads Backend/.env before boto3 clients)

import os
import logging

import boto3

logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "ap-south-1"))
DRAFTS_TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "paper-drafts")

# A single shared resource for the process. boto3 resources are thread-safe
# for read/write item operations, which is all we do here.
_dynamodb_resource = boto3.resource("dynamodb", region_name=AWS_REGION)


def get_drafts_table():
    """Return the DynamoDB Table handle for the drafts table."""
    return _dynamodb_resource.Table(DRAFTS_TABLE_NAME)


def get_dynamodb_resource():
    """Return the shared DynamoDB resource (used by the provisioning script)."""
    return _dynamodb_resource
