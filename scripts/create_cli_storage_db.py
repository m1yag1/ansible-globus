#!/usr/bin/env python3
"""
Create a globus-cli compatible storage.db from S3 tokens.

This script downloads tokens from S3 and creates a SQLite database that
mimics the globus-cli's token storage format. This enables the Ansible
modules to use the 'cli' auth method in CI environments.

Usage:
    python scripts/create_cli_storage_db.py

Environment Variables Required:
    S3_TOKEN_BUCKET: S3 bucket containing tokens
    S3_TOKEN_KEY: S3 object key (default: globus/ci-tokens.json)
    S3_TOKEN_NAMESPACE: Token namespace in S3 (default: DEFAULT)
    AWS_REGION: AWS region

Optional:
    GLOBUS_SDK_ENVIRONMENT: Target environment (default: test)
    GLOBUS_CLI_STORAGE_PATH: Override storage.db path (default: ~/.globus/cli/storage.db)
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

# Add tests directory to path for s3_token_storage import
tests_path = Path(__file__).parent.parent / "tests"
sys.path.insert(0, str(tests_path))

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("ERROR: boto3 not installed: pip install boto3")
    sys.exit(1)


def get_tokens_from_s3(
    bucket: str, key: str, namespace: str, region: str | None
) -> dict:
    """Download tokens from S3."""
    s3 = boto3.client("s3", region_name=region)

    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")
        all_data = json.loads(content)

        if namespace not in all_data:
            print(f"ERROR: Namespace '{namespace}' not found in S3 tokens")
            print(f"Available namespaces: {list(all_data.keys())}")
            sys.exit(1)

        return all_data[namespace]

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print(f"ERROR: Token file not found: s3://{bucket}/{key}")
        else:
            print(f"ERROR: Failed to download from S3: {e}")
        sys.exit(1)


def create_storage_db(db_path: str, tokens: dict, environment: str) -> None:
    """Create a globus-cli compatible storage.db file."""
    # Ensure parent directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # Remove existing database if present
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables matching globus-cli schema
    cursor.execute(
        """
        CREATE TABLE config_storage (
            namespace VARCHAR NOT NULL,
            config_name VARCHAR NOT NULL,
            config_data_json VARCHAR NOT NULL,
            PRIMARY KEY (namespace, config_name)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE token_storage (
            namespace VARCHAR NOT NULL,
            resource_server VARCHAR NOT NULL,
            token_data_json VARCHAR NOT NULL,
            PRIMARY KEY (namespace, resource_server)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE sdk_storage_adapter_internal (
            attribute VARCHAR NOT NULL,
            value VARCHAR NOT NULL,
            PRIMARY KEY (attribute)
        )
    """
    )

    # Build namespace for CLI format: userprofile/{environment}
    cli_namespace = f"userprofile/{environment}"

    # Insert tokens
    for resource_server, token_data in tokens.items():
        # Convert S3 token format to CLI format
        # S3 has extra fields like 'stored_at' and 'client_id' that CLI doesn't need
        cli_token_data = {
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token"),
            "expires_at_seconds": token_data.get("expires_at_seconds"),
            "resource_server": resource_server,
            "scope": token_data.get("scope"),
            "token_type": token_data.get("token_type", "Bearer"),
        }

        cursor.execute(
            "INSERT INTO token_storage (namespace, resource_server, token_data_json) VALUES (?, ?, ?)",
            (cli_namespace, resource_server, json.dumps(cli_token_data)),
        )

    conn.commit()
    conn.close()

    # Set permissions to match CLI's default (owner read/write only)
    os.chmod(db_path, 0o600)


def main():
    """Create storage.db from S3 tokens."""
    print("Creating globus-cli storage.db from S3 tokens...\n")

    # Get configuration from environment
    bucket = os.getenv("S3_TOKEN_BUCKET")
    key = os.getenv("S3_TOKEN_KEY", "globus/ci-tokens.json")
    namespace = os.getenv("S3_TOKEN_NAMESPACE", "DEFAULT")
    region = os.getenv("AWS_REGION")
    environment = os.getenv("GLOBUS_SDK_ENVIRONMENT", "test")
    db_path = os.getenv(
        "GLOBUS_CLI_STORAGE_PATH",
        os.path.expanduser("~/.globus/cli/storage.db"),
    )

    # Validate required vars
    if not bucket:
        print("ERROR: S3_TOKEN_BUCKET environment variable not set")
        sys.exit(1)

    print("Configuration:")
    print(f"  S3 Bucket: {bucket}")
    print(f"  S3 Key: {key}")
    print(f"  S3 Namespace: {namespace}")
    print(f"  AWS Region: {region}")
    print(f"  Globus Environment: {environment}")
    print(f"  Storage DB Path: {db_path}")
    print()

    # Download tokens from S3
    print("Downloading tokens from S3...")
    tokens = get_tokens_from_s3(bucket, key, namespace, region)
    print(f"OK: Found {len(tokens)} token(s)\n")

    # Display token info
    print("Tokens:")
    for rs in tokens:
        print(f"  - {rs}")
    print()

    # Create storage.db
    print(f"Creating storage.db at {db_path}...")
    create_storage_db(db_path, tokens, environment)
    print("OK: storage.db created successfully!\n")

    # Verify
    print("Verifying storage.db...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT namespace, resource_server FROM token_storage")
    rows = cursor.fetchall()
    conn.close()

    print(f"OK: Found {len(rows)} token entries:")
    for ns, rs in rows:
        print(f"  - {ns} -> {rs}")

    print("\nStorage.db is ready for CLI auth!")
    print(
        f"Tests can now use auth_method=cli with GLOBUS_SDK_ENVIRONMENT={environment}"
    )


if __name__ == "__main__":
    main()
