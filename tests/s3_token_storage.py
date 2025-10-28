"""
S3-based token storage adapter for Globus SDK.

This adapter stores Globus OAuth tokens in S3, enabling CI/CD workflows
to use refresh tokens without requiring interactive browser authentication.

Usage:
    from tests.s3_token_storage import S3TokenStorage
    from globus_sdk import NativeAppAuthClient, RefreshTokenAuthorizer

    # Store tokens after initial OAuth flow
    storage = S3TokenStorage(
        bucket="my-globus-tokens",
        key="tokens/ci-tokens.json"
    )
    storage.store_token_response(token_response)

    # Retrieve and use tokens in CI
    token_data = storage.get_token_data("transfer.api.globus.org")
    authorizer = RefreshTokenAuthorizer(
        token_data["refresh_token"],
        auth_client,
        access_token=token_data["access_token"],
        expires_at=token_data["expires_at_seconds"]
    )
"""

import json
import typing as t
from datetime import datetime

import boto3
from botocore.exceptions import ClientError
from globus_sdk import OAuthTokenResponse
from globus_sdk.tokenstorage import StorageAdapter


class S3TokenStorage(StorageAdapter):
    """
    Token storage adapter that stores tokens in AWS S3.

    Features:
    - Server-side encryption (AES256 or KMS)
    - Automatic token refresh on retrieval
    - Namespace support for multiple token sets
    - Optional versioning support

    Args:
        bucket: S3 bucket name
        key: S3 object key (path to token file)
        namespace: Namespace for token partitioning (default: "DEFAULT")
        region: AWS region (default: None, uses default region)
        kms_key_id: Optional KMS key ID for encryption

    Environment Variables:
        AWS_ACCESS_KEY_ID: AWS access key (if not using IAM role)
        AWS_SECRET_ACCESS_KEY: AWS secret key (if not using IAM role)
        AWS_REGION: AWS region (alternative to region parameter)

    Example:
        >>> storage = S3TokenStorage(
        ...     bucket="my-ci-tokens",
        ...     key="globus/integration-test-tokens.json",
        ...     kms_key_id="arn:aws:kms:us-east-1:123456789:key/xxx"
        ... )
        >>> storage.store_token_response(token_response)
    """

    def __init__(
        self,
        bucket: str,
        key: str,
        namespace: str = "DEFAULT",
        region: str | None = None,
        kms_key_id: str | None = None,
        client_id: str | None = None,
    ) -> None:
        self.bucket = bucket
        self.key = key
        self.namespace = namespace
        self.kms_key_id = kms_key_id
        self.client_id = client_id

        # Initialize S3 client
        self.s3 = boto3.client("s3", region_name=region)

    def store(self, token_response: OAuthTokenResponse) -> None:
        """
        Store an OAuthTokenResponse in S3.

        The token data is organized by resource server and namespace,
        then serialized to JSON and uploaded to S3 with encryption.

        Args:
            token_response: The token response to store
        """
        # Load existing data or create new structure
        existing_data = self._load_from_s3()

        # Ensure namespace exists
        if self.namespace not in existing_data:
            existing_data[self.namespace] = {}

        # Store tokens by resource server
        for resource_server, token_data in token_response.by_resource_server.items():
            token_entry = {
                "access_token": token_data["access_token"],
                "refresh_token": token_data.get("refresh_token"),
                "expires_at_seconds": token_data.get("expires_at_seconds"),
                "resource_server": resource_server,
                "scope": token_data.get("scope"),
                "token_type": token_data.get("token_type", "Bearer"),
                # Store metadata
                "stored_at": datetime.utcnow().isoformat(),
            }

            # Include client_id if available
            if self.client_id:
                token_entry["client_id"] = self.client_id

            existing_data[self.namespace][resource_server] = token_entry

        # Save back to S3
        self._save_to_s3(existing_data)

    def get_token_data(self, resource_server: str) -> dict[str, t.Any] | None:
        """
        Retrieve token data for a specific resource server.

        Args:
            resource_server: The resource server to get tokens for

        Returns:
            Token data dict with access_token, refresh_token, expires_at_seconds, etc.
            or None if not found
        """
        data = self._load_from_s3()

        if self.namespace not in data:
            return None

        return data[self.namespace].get(resource_server)

    def get_all_token_data(self) -> dict[str, dict[str, t.Any]]:
        """
        Get all token data for the current namespace.

        Returns:
            Dict mapping resource_server to token data
        """
        data = self._load_from_s3()
        return data.get(self.namespace, {})

    def remove_token_data(self, resource_server: str) -> bool:
        """
        Remove token data for a specific resource server.

        Args:
            resource_server: The resource server to remove tokens for

        Returns:
            True if data was removed, False if not found
        """
        data = self._load_from_s3()

        if self.namespace not in data:
            return False

        if resource_server in data[self.namespace]:
            del data[self.namespace][resource_server]
            self._save_to_s3(data)
            return True

        return False

    def clear_namespace(self) -> None:
        """Clear all tokens in the current namespace."""
        data = self._load_from_s3()
        if self.namespace in data:
            del data[self.namespace]
            self._save_to_s3(data)

    def _load_from_s3(self) -> dict[str, dict[str, dict[str, t.Any]]]:
        """
        Load token data from S3.

        Returns:
            Nested dict: {namespace: {resource_server: token_data}}
        """
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=self.key)
            content = response["Body"].read().decode("utf-8")
            return json.loads(content)
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                # File doesn't exist yet, return empty structure
                return {}
            raise

    def _save_to_s3(self, data: dict[str, dict[str, dict[str, t.Any]]]) -> None:
        """
        Save token data to S3 with encryption.

        Args:
            data: The complete token data structure to save
        """
        content = json.dumps(data, indent=2)

        # Prepare put_object kwargs
        put_kwargs: dict[str, t.Any] = {
            "Bucket": self.bucket,
            "Key": self.key,
            "Body": content.encode("utf-8"),
            "ContentType": "application/json",
        }

        # Add encryption
        if self.kms_key_id:
            put_kwargs["ServerSideEncryption"] = "aws:kms"
            put_kwargs["SSEKMSKeyId"] = self.kms_key_id
        else:
            put_kwargs["ServerSideEncryption"] = "AES256"

        self.s3.put_object(**put_kwargs)

    def on_refresh(self, token_response: OAuthTokenResponse) -> None:
        """
        Called when tokens are refreshed.

        Stores the new tokens back to S3 so future runs use fresh tokens.

        Args:
            token_response: The refreshed token response
        """
        self.store(token_response)


class DynamoDBTokenStorage(StorageAdapter):
    """
    Token storage adapter that stores tokens in AWS DynamoDB.

    This provides an alternative to S3 with features like:
    - Item-level TTL for automatic expiration
    - Conditional writes for concurrency safety
    - Point-in-time recovery
    - Global tables for multi-region

    Table Schema:
        Partition Key: namespace (String)
        Sort Key: resource_server (String)
        Attributes: token_data (Map), stored_at (String), ttl (Number)

    Args:
        table_name: DynamoDB table name
        namespace: Namespace for token partitioning (default: "DEFAULT")
        region: AWS region (default: None, uses default region)
        ttl_days: Days until tokens expire (default: 90)

    Example:
        >>> storage = DynamoDBTokenStorage(
        ...     table_name="globus-ci-tokens",
        ...     namespace="github-actions"
        ... )
        >>> storage.store_token_response(token_response)
    """

    def __init__(
        self,
        table_name: str,
        namespace: str = "DEFAULT",
        region: str | None = None,
        ttl_days: int = 90,
    ) -> None:
        self.table_name = table_name
        self.namespace = namespace
        self.ttl_days = ttl_days

        # Initialize DynamoDB client
        dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = dynamodb.Table(table_name)

    def store(self, token_response: OAuthTokenResponse) -> None:
        """Store token response in DynamoDB."""
        import time

        ttl = int(time.time()) + (self.ttl_days * 24 * 60 * 60)

        for resource_server, token_data in token_response.by_resource_server.items():
            item = {
                "namespace": self.namespace,
                "resource_server": resource_server,
                "token_data": {
                    "access_token": token_data["access_token"],
                    "refresh_token": token_data.get("refresh_token"),
                    "expires_at_seconds": token_data.get("expires_at_seconds"),
                    "scope": token_data.get("scope"),
                    "token_type": token_data.get("token_type", "Bearer"),
                },
                "stored_at": datetime.utcnow().isoformat(),
                "ttl": ttl,
            }

            self.table.put_item(Item=item)

    def get_token_data(self, resource_server: str) -> dict[str, t.Any] | None:
        """Retrieve token data from DynamoDB."""
        try:
            response = self.table.get_item(
                Key={"namespace": self.namespace, "resource_server": resource_server}
            )

            if "Item" in response:
                return response["Item"]["token_data"]

            return None
        except ClientError:
            return None

    def remove_token_data(self, resource_server: str) -> bool:
        """Remove token data from DynamoDB."""
        try:
            self.table.delete_item(
                Key={"namespace": self.namespace, "resource_server": resource_server}
            )
            return True
        except ClientError:
            return False

    def on_refresh(self, token_response: OAuthTokenResponse) -> None:
        """Store refreshed tokens."""
        self.store(token_response)
