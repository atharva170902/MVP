"""
Deploy the diagram search Lambda + API Gateway.

What it does
------------
1. Builds a deployment package (handler.py + numpy) as a zip.
2. Creates or updates the Lambda function (Python 3.12, 512 MB memory).
3. Sets environment variables for S3 bucket/keys.
4. Creates or updates an HTTP API (API Gateway) with a POST /search route.
5. Optionally tests the deployed endpoint.

Prerequisites
-----------
- AWS credentials in .env (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)
- boto3 installed
- numpy already installed locally (we'll include it in the zip)

Usage
-----
    # Dry run: show what would deploy, no AWS changes
    python deploy.py --dry-run

    # Deploy Lambda + API Gateway
    python deploy.py

    # Deploy and test the endpoint
    python deploy.py --test

    # Clean up (delete Lambda + API)
    python deploy.py --destroy

Environment variables (from .env)
---------
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
(Optional) LAMBDA_ROLE_ARN if you have a pre-existing IAM role for Lambda
"""

import argparse
import base64
import hashlib
import io
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("deploy")

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
ENV_PATH = BACKEND_DIR / ".env"

LAMBDA_NAME = "diagram-search"
API_NAME = "diagram-search-api"
ROLE_NAME = "diagram-search-lambda-role"

EMBEDDINGS_BUCKET = "assessment-drafting-engine"
EMBEDDINGS_KEY = "Grade/Grade 3/Subjects/EVS/Embeddings/embeddings.npy"
METADATA_KEY = "Grade/Grade 3/Subjects/EVS/Embeddings/metadata.json"

LAMBDA_TIMEOUT = 60
LAMBDA_MEMORY = 512


# --------------------------------------------------------------------------- #
# .env loading
# --------------------------------------------------------------------------- #
def load_env(env_path: Path) -> None:
    if not env_path.exists():
        logger.warning(".env not found at %s", env_path)
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
        logger.info("Loaded .env from %s", env_path)
        return
    except ImportError:
        pass

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


# --------------------------------------------------------------------------- #
# AWS clients
# --------------------------------------------------------------------------- #
def make_clients(region: str):
    import boto3

    return {
        "lambda": boto3.client("lambda", region_name=region),
        "iam": boto3.client("iam"),
        "apigateway": boto3.client("apigatewayv2", region_name=region),
    }


# --------------------------------------------------------------------------- #
# Deployment package
# --------------------------------------------------------------------------- #
def build_deployment_package(output_path: Path) -> None:
    """Create a zip with handler.py + numpy (and boto3 if needed)."""
    logger.info("Building deployment package...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Copy handler.py
        shutil.copy(HERE / "handler.py", tmpdir / "handler.py")

        # Include numpy. Try to get it from site-packages.
        try:
            import numpy

            numpy_path = Path(numpy.__file__).parent
            logger.info("Including numpy from %s", numpy_path)
            shutil.copytree(numpy_path, tmpdir / "numpy", dirs_exist_ok=True)
        except ImportError:
            logger.warning("numpy not found; assuming it's available in the Lambda runtime.")

        # Create zip
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in tmpdir.rglob("*"):
                if f.is_file():
                    arcname = f.relative_to(tmpdir)
                    zf.write(f, arcname)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info("Deployment package: %s (%.1f MB)", output_path, size_mb)


# --------------------------------------------------------------------------- #
# IAM role
# --------------------------------------------------------------------------- #
def get_or_create_lambda_role(iam, role_name: str) -> str:
    """Get existing role ARN or create a new one with S3 + Bedrock permissions."""
    try:
        role = iam.get_role(RoleName=role_name)
        logger.info("Using existing IAM role: %s", role_name)
        return role["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        pass

    logger.info("Creating IAM role: %s", role_name)
    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    role_resp = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(assume_role_policy),
    )
    role_arn = role_resp["Role"]["Arn"]

    # Attach inline policy for S3 + Bedrock access
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject"],
                "Resource": [
                    f"arn:aws:s3:::{EMBEDDINGS_BUCKET}/Grade/Grade 3/Subjects/EVS/Embeddings/*"
                ],
            },
            {
                "Effect": "Allow",
                "Action": ["bedrock:InvokeModel"],
                "Resource": ["arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0"],
            },
        ],
    }
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="diagram-search-policy",
        PolicyDocument=json.dumps(policy),
    )

    # Role might need a moment before it's usable
    time.sleep(2)
    logger.info("Created role: %s", role_arn)
    return role_arn


# --------------------------------------------------------------------------- #
# Lambda
# --------------------------------------------------------------------------- #
def deploy_lambda(
    clients: dict,
    zip_path: Path,
    role_arn: str,
    dry_run: bool = False,
) -> str:
    """Create or update the Lambda function."""
    lam = clients["lambda"]
    region = os.environ.get("AWS_REGION", "ap-south-1")

    zip_bytes = zip_path.read_bytes()
    zip_hash = hashlib.md5(zip_bytes).hexdigest()[:8]

    env_vars = {
        "EMBEDDINGS_BUCKET": EMBEDDINGS_BUCKET,
        "EMBEDDINGS_KEY": EMBEDDINGS_KEY,
        "METADATA_KEY": METADATA_KEY,
        "BEDROCK_REGION": region,
        "CORS_ALLOW_ORIGIN": "*",
    }

    if dry_run:
        logger.info("[DRY RUN] Would deploy Lambda function:")
        logger.info("  Name: %s", LAMBDA_NAME)
        logger.info("  Runtime: python3.12")
        logger.info("  Memory: %d MB", LAMBDA_MEMORY)
        logger.info("  Timeout: %d s", LAMBDA_TIMEOUT)
        logger.info("  Role: %s", role_arn)
        logger.info("  Package hash: %s (%d bytes)", zip_hash, len(zip_bytes))
        logger.info("  Environment vars: %s", json.dumps(env_vars, indent=4))
        return f"arn:aws:lambda:{region}:ACCOUNT:{LAMBDA_NAME}"

    # Check if function exists
    try:
        resp = lam.get_function(FunctionName=LAMBDA_NAME)
        logger.info("Updating existing Lambda function: %s", LAMBDA_NAME)
        lam.update_function_code(FunctionName=LAMBDA_NAME, ZipFile=zip_bytes)
        lam.update_function_configuration(
            FunctionName=LAMBDA_NAME,
            Runtime="python3.12",
            Handler="handler.lambda_handler",
            MemorySize=LAMBDA_MEMORY,
            Timeout=LAMBDA_TIMEOUT,
            Environment={"Variables": env_vars},
        )
        func_arn = resp["Configuration"]["FunctionArn"]
    except lam.exceptions.ResourceNotFoundException:
        logger.info("Creating new Lambda function: %s", LAMBDA_NAME)
        resp = lam.create_function(
            FunctionName=LAMBDA_NAME,
            Runtime="python3.12",
            Role=role_arn,
            Handler="handler.lambda_handler",
            Code={"ZipFile": zip_bytes},
            MemorySize=LAMBDA_MEMORY,
            Timeout=LAMBDA_TIMEOUT,
            Environment={"Variables": env_vars},
            Description="Semantic search over extracted diagram embeddings",
        )
        func_arn = resp["FunctionArn"]

    logger.info("Lambda deployment complete: %s", func_arn)
    return func_arn


# --------------------------------------------------------------------------- #
# API Gateway (HTTP API)
# --------------------------------------------------------------------------- #
def deploy_api(clients: dict, lambda_arn: str, dry_run: bool = False) -> str:
    """Create or update HTTP API with POST /search route."""
    apigw = clients["apigateway"]
    lam = clients["lambda"]
    region = os.environ.get("AWS_REGION", "ap-south-1")

    if dry_run:
        logger.info("[DRY RUN] Would create/update HTTP API:")
        logger.info("  Name: %s", API_NAME)
        logger.info("  Route: POST /search")
        logger.info("  Target: %s", lambda_arn)
        api_id = "abc123def456"
        endpoint = f"https://{api_id}.execute-api.{region}.amazonaws.com"
        logger.info("  Endpoint: %s/search", endpoint)
        return endpoint

    # Get or create API
    apis = apigw.get_apis(MaxResults=100)
    api_id = None
    for api in apis.get("Items", []):
        if api["Name"] == API_NAME:
            api_id = api["ApiId"]
            logger.info("Using existing HTTP API: %s (%s)", API_NAME, api_id)
            break

    if not api_id:
        logger.info("Creating new HTTP API: %s", API_NAME)
        api_resp = apigw.create_api(
            Name=API_NAME,
            ProtocolType="HTTP",
            Target=lambda_arn,
            CorsPolicy={
                "AllowOrigins": ["*"],
                "AllowMethods": ["POST", "OPTIONS"],
                "AllowHeaders": ["Content-Type"],
            },
        )
        api_id = api_resp["ApiId"]

    # Ensure Lambda has permission to be invoked by API Gateway
    try:
        lam.add_permission(
            FunctionName=LAMBDA_NAME,
            StatementId=f"apigateway-{api_id[:8]}",
            Action="lambda:InvokeFunction",
            Principal="apigateway.amazonaws.com",
            SourceArn=f"arn:aws:execute-api:{region}:*:{api_id}/*",
        )
    except lam.exceptions.ResourceConflictException:
        pass  # Permission already exists

    # Create or update POST /search route
    routes = apigw.get_routes(ApiId=api_id)
    route_id = None
    for route in routes.get("Items", []):
        if route["RouteKey"] == "POST /search":
            route_id = route["RouteId"]
            logger.info("Using existing route: POST /search")
            break

    if not route_id:
        logger.info("Creating route: POST /search")
        route_resp = apigw.create_route(
            ApiId=api_id,
            RouteKey="POST /search",
            Target=lambda_arn,
        )
        route_id = route_resp["RouteId"]

    # Create a stage if needed (default is "$default")
    try:
        apigw.create_stage(ApiId=api_id, StageName="$default", AutoDeploy=True)
    except apigw.exceptions.ConflictException:
        pass  # Stage already exists

    endpoint = f"https://{api_id}.execute-api.{region}.amazonaws.com"
    logger.info("API Gateway endpoint: %s/search", endpoint)
    return endpoint


# --------------------------------------------------------------------------- #
# Testing
# --------------------------------------------------------------------------- #
def test_endpoint(endpoint: str) -> bool:
    """Test the deployed endpoint with a sample query."""
    logger.info("Testing deployed endpoint: %s/search", endpoint)
    url = f"{endpoint}/search"

    body = json.dumps({"query": "water and rain", "top_k": 3})
    req = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            if resp.status == 200 and "results" in data:
                logger.info("✓ Test successful")
                logger.info("  Query: %s", data.get("query"))
                logger.info("  Results: %d", len(data.get("results", [])))
                if data.get("results"):
                    top = data["results"][0]
                    logger.info("  Top match: %s (score %.4f)", top.get("image_id"), top.get("score", 0))
                return True
            else:
                logger.error("Unexpected response: %s", data)
                return False
    except urllib.error.URLError as e:
        logger.error("Test failed: %s", e)
        return False


# --------------------------------------------------------------------------- #
# Cleanup
# --------------------------------------------------------------------------- #
def destroy(clients: dict, dry_run: bool = False) -> None:
    """Delete Lambda function and API Gateway."""
    lam = clients["lambda"]
    apigw = clients["apigateway"]

    if dry_run:
        logger.info("[DRY RUN] Would delete:")
        logger.info("  Lambda: %s", LAMBDA_NAME)
        logger.info("  API: %s", API_NAME)
        return

    try:
        lam.delete_function(FunctionName=LAMBDA_NAME)
        logger.info("Deleted Lambda function: %s", LAMBDA_NAME)
    except lam.exceptions.ResourceNotFoundException:
        logger.info("Lambda function not found (already deleted?)")

    try:
        apis = apigw.get_apis(MaxResults=100)
        for api in apis.get("Items", []):
            if api["Name"] == API_NAME:
                apigw.delete_api(ApiId=api["ApiId"])
                logger.info("Deleted HTTP API: %s", API_NAME)
                break
    except Exception as e:
        logger.info("API not found or already deleted: %s", e)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main(argv):
    load_env(ENV_PATH)

    ap = argparse.ArgumentParser(description="Deploy diagram search Lambda + API Gateway")
    ap.add_argument("--dry-run", action="store_true", help="Show what would happen, no AWS changes")
    ap.add_argument("--test", action="store_true", help="Test the endpoint after deploy")
    ap.add_argument("--destroy", action="store_true", help="Delete Lambda + API (cleanup)")
    ap.add_argument("--region", default=os.environ.get("AWS_REGION", "ap-south-1"))
    args = ap.parse_args(argv)

    region = args.region
    os.environ.setdefault("AWS_REGION", region)

    clients = make_clients(region)

    if args.destroy:
        destroy(clients, dry_run=args.dry_run)
        return 0

    # Build deployment package
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
        zip_path = Path(tf.name)
    try:
        build_deployment_package(zip_path)

        # Get or create IAM role
        role_arn = get_or_create_lambda_role(clients["iam"], ROLE_NAME)

        # Deploy Lambda
        lambda_arn = deploy_lambda(clients, zip_path, role_arn, dry_run=args.dry_run)

        # Deploy API Gateway
        endpoint = deploy_api(clients, lambda_arn, dry_run=args.dry_run)

        if not args.dry_run:
            logger.info("\n" + "=" * 70)
            logger.info("Deployment complete!")
            logger.info("=" * 70)
            logger.info("Endpoint: %s/search", endpoint)
            logger.info("Query example:")
            logger.info('  curl -X POST %s/search \\', endpoint)
            logger.info('    -H "Content-Type: application/json" \\')
            logger.info('    -d \'{"query": "water and rain", "top_k": 5}\'')

            if args.test:
                logger.info("\nRunning test...")
                time.sleep(2)  # Let the endpoint stabilize
                if test_endpoint(endpoint):
                    logger.info("\n✓ All good! Your search API is live.")
                else:
                    logger.warning("\n⚠ Test failed. The endpoint may not be ready yet; try again in a moment.")
        else:
            logger.info("\nDRY RUN complete. Re-run without --dry-run to deploy.")

        return 0

    finally:
        zip_path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
