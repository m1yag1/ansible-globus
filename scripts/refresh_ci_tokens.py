#!/usr/bin/env python3
"""
Refresh Globus tokens stored in S3 for CI/CD pipelines.

This script should run as a separate CI step BEFORE tests to ensure
fresh tokens are available.

Usage:
    python scripts/refresh_ci_tokens.py

Environment Variables Required:
    S3_TOKEN_BUCKET: S3 bucket name
    S3_TOKEN_KEY: S3 object key
    S3_TOKEN_NAMESPACE: Token namespace (default: DEFAULT)
    AWS_REGION: AWS region
    GLOBUS_CLIENT_ID: Native app client ID for refresh

Optional:
    AWS_ACCESS_KEY_ID: If not using IAM roles
    AWS_SECRET_ACCESS_KEY: If not using IAM roles
"""

import os
import sys
import time
from pathlib import Path

# Add tests directory to path for s3_token_storage import
tests_path = Path(__file__).parent.parent / "tests"
sys.path.insert(0, str(tests_path))

try:
    from s3_token_storage import S3TokenStorage
except ImportError as e:
    print(f"❌ Failed to import s3_token_storage: {e}")
    print("Ensure boto3 is installed: pip install boto3")
    sys.exit(1)

try:
    from globus_sdk import NativeAppAuthClient
except ImportError:
    print("❌ globus-sdk not installed: pip install globus-sdk")
    sys.exit(1)


def main():
    """Refresh tokens in S3 if they're expired or expiring soon."""
    print("🔄 Refreshing CI tokens from S3...\n")

    # Get configuration from environment
    bucket = os.getenv("S3_TOKEN_BUCKET")
    key = os.getenv("S3_TOKEN_KEY", "globus/ci-tokens.json")
    namespace = os.getenv("S3_TOKEN_NAMESPACE", "DEFAULT")
    region = os.getenv("AWS_REGION")
    client_id = os.getenv("GLOBUS_CLIENT_ID")

    # Validate required vars
    if not bucket:
        print("❌ S3_TOKEN_BUCKET environment variable not set")
        sys.exit(1)

    if not client_id:
        print("❌ GLOBUS_CLIENT_ID environment variable not set")
        sys.exit(1)

    print("Configuration:")
    print(f"  Bucket: {bucket}")
    print(f"  Key: {key}")
    print(f"  Namespace: {namespace}")
    print(f"  Region: {region}")
    print(f"  Client ID: {client_id[:20]}...")
    print()

    # Load tokens from S3
    try:
        storage = S3TokenStorage(
            bucket=bucket,
            key=key,
            namespace=namespace,
            region=region,
            client_id=client_id,
        )
    except Exception as e:
        print(f"❌ Failed to initialize S3TokenStorage: {e}")
        sys.exit(1)

    try:
        tokens = storage.get_all_token_data()
    except Exception as e:
        print(f"❌ Failed to load tokens from S3: {e}")
        sys.exit(1)

    if not tokens:
        print(f"❌ No tokens found in s3://{bucket}/{key} namespace={namespace}")
        print("\nYou need to store initial tokens with refresh tokens.")
        print("Run: python scripts/setup_oauth_tokens.py")
        sys.exit(1)

    print(f"✓ Found {len(tokens)} token(s) in S3\n")

    # Check each token and refresh if needed
    auth_client = NativeAppAuthClient(client_id)
    current_time = time.time()
    refreshed_count = 0
    needs_save = False

    for resource_server, token_data in tokens.items():
        expires_at = token_data.get("expires_at_seconds", 0)
        time_until_expiry = expires_at - current_time

        print(f"📍 {resource_server}:")
        print(f"   Expires in: {time_until_expiry / 3600:.1f} hours")

        # Refresh if expires within next 5 minutes
        if time_until_expiry < 300:
            refresh_token = token_data.get("refresh_token")

            if not refresh_token:
                print("   ❌ EXPIRED with no refresh token!")
                print("   This token cannot be refreshed automatically.")
                print("   You must obtain new tokens with refresh tokens included.")
                print("   Run: python scripts/setup_oauth_tokens.py")
                sys.exit(1)

            # Refresh the token
            print(f"   🔄 Refreshing (expires in {time_until_expiry:.0f}s)...")
            try:
                token_response = auth_client.oauth2_refresh_token(refresh_token)

                # Update the token data
                refreshed_data = token_response.by_resource_server.get(resource_server)
                if refreshed_data:
                    tokens[resource_server].update(
                        {
                            "access_token": refreshed_data["access_token"],
                            "expires_at_seconds": refreshed_data["expires_at_seconds"],
                            "refresh_token": refreshed_data.get(
                                "refresh_token", refresh_token
                            ),
                        }
                    )
                    new_expiry = refreshed_data["expires_at_seconds"] - current_time
                    print(f"   ✓ Refreshed! New expiry: {new_expiry / 3600:.1f} hours")
                    refreshed_count += 1
                    needs_save = True
                else:
                    print(f"   ⚠️  No data for {resource_server} in refresh response")

            except Exception as e:
                print(f"   ❌ Refresh failed: {e}")
                sys.exit(1)
        else:
            print("   ✓ Still valid")

        print()

    # Save refreshed tokens back to S3
    if needs_save:
        print(f"💾 Saving {refreshed_count} refreshed token(s) back to S3...")
        try:
            # Reconstruct the full data structure
            all_data = storage._load_from_s3()  # noqa: SLF001
            all_data[namespace] = tokens
            storage._save_to_s3(all_data)  # noqa: SLF001
            print("✓ Tokens saved to S3")
        except Exception as e:
            print(f"❌ Failed to save tokens: {e}")
            sys.exit(1)
    else:
        print("✓ No tokens needed refresh")

    print("\n✅ Token refresh complete!")
    print("Tests can now use fresh tokens from S3.")


if __name__ == "__main__":
    main()
