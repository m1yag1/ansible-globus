#!/usr/bin/env python3
"""
Setup script for storing Globus OAuth tokens in S3.

This script performs an interactive OAuth flow to obtain Globus tokens
(including refresh tokens) and stores them in S3 for use in CI/CD pipelines.

Usage:
    # Interactive mode (prompts for all values)
    python scripts/setup_oauth_tokens.py

    # With environment variables
    export GLOBUS_CLIENT_ID="your-client-id"
    export S3_TOKEN_BUCKET="your-bucket"
    export S3_TOKEN_KEY="globus/ci-tokens.json"
    export AWS_REGION="us-east-1"
    python scripts/setup_oauth_tokens.py

    # With command line arguments
    python scripts/setup_oauth_tokens.py \
        --client-id YOUR_CLIENT_ID \
        --bucket my-tokens \
        --key globus/tokens.json \
        --region us-east-1 \
        --environment test \
        --kms-key arn:aws:kms:...

Required Scopes (all environments):
    - transfer.api.globus.org:all
    - groups.api.globus.org:all
    - compute.api.globus.org (HTTPS URL scope)
    - flows.api.globus.org (HTTPS URL scope)

Prerequisites:
    1. Register a Native App at https://developers.globus.org
       - Set redirect URI to: http://localhost:8080
       - Note your Client ID
    2. Configure AWS credentials (IAM role or environment variables)
    3. Ensure S3 bucket exists with appropriate permissions
"""

import argparse
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from globus_sdk import NativeAppAuthClient
from globus_sdk.scopes import (
    AuthScopes,
    ComputeScopes,
    FlowsScopes,
    GroupsScopes,
    TimersScopes,
    TransferScopes,
)

# Add tests directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))
from s3_token_storage import S3TokenStorage  # noqa: E402

# Required scopes for all Ansible modules (works across all environments)
REQUIRED_SCOPES = [
    TransferScopes.all,
    GroupsScopes.all,
    ComputeScopes.all,
    FlowsScopes.all,
    TimersScopes.timer,
    AuthScopes.manage_projects,
]

# OAuth redirect handling
auth_code_received = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    def do_GET(self) -> None:
        """Handle GET request with OAuth code."""
        global auth_code_received

        # Parse the authorization code from URL
        query = urlparse(self.path).query
        params = parse_qs(query)

        if "code" in params:
            auth_code_received = params["code"][0]

            # Send success response
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            success_html = """
            <html>
            <head><title>Globus Authentication Successful</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: green;">✓ Authentication Successful!</h1>
                <p>Your Globus tokens have been received.</p>
                <p>You can close this window and return to the terminal.</p>
            </body>
            </html>
            """
            self.wfile.write(success_html.encode())
        else:
            # Handle error
            auth_code_received = None
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            error_html = """
            <html>
            <head><title>Authentication Failed</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: red;">✗ Authentication Failed</h1>
                <p>No authorization code received.</p>
                <p>Please try again.</p>
            </body>
            </html>
            """
            self.wfile.write(error_html.encode())

    def log_message(self, format: str, *args) -> None:
        """Suppress HTTP server logs."""
        pass


def perform_oauth_flow(client_id: str, environment: str = None) -> dict:
    """
    Perform interactive OAuth flow to obtain tokens.

    Args:
        client_id: Globus Native App client ID
        environment: Globus environment (production, test, sandbox, preview, etc.)

    Returns:
        Token response dict with access and refresh tokens
    """
    global auth_code_received

    # Create auth client
    client = NativeAppAuthClient(client_id, environment=environment)

    # Start local HTTP server to receive callback
    redirect_port = 8080
    redirect_uri = f"http://localhost:{redirect_port}"

    print("\n🔐 Starting Globus OAuth Flow")
    print("=" * 60)
    print(f"Client ID: {client_id}")
    print(f"Environment: {environment or 'production'}")
    print(f"Redirect URI: {redirect_uri}")
    print("Scopes requested:")
    for scope in REQUIRED_SCOPES:
        print(f"  - {scope}")
    print("=" * 60)

    # Generate authorization URL
    client.oauth2_start_flow(
        redirect_uri=redirect_uri, requested_scopes=REQUIRED_SCOPES
    )
    authorize_url = client.oauth2_get_authorize_url()

    print("\n📝 Opening browser for authentication...")
    print("If the browser doesn't open automatically, visit:")
    print(f"\n{authorize_url}\n")

    # Open browser
    webbrowser.open(authorize_url)

    # Start HTTP server to receive callback
    print("⏳ Waiting for OAuth callback...")
    server = HTTPServer(("localhost", redirect_port), OAuthCallbackHandler)

    # Wait for one request (the OAuth callback)
    server.handle_request()

    if not auth_code_received:
        print("\n❌ Error: No authorization code received")
        sys.exit(1)

    print("✓ Authorization code received")

    # Exchange code for tokens
    print("🔄 Exchanging authorization code for tokens...")
    token_response = client.oauth2_exchange_code_for_tokens(auth_code_received)

    print("✓ Tokens obtained successfully!")

    # Display token info
    print("\n📋 Token Information:")
    print("=" * 60)
    for resource_server, data in token_response.by_resource_server.items():
        print(f"\n{resource_server}:")
        print(f"  Access Token: {data['access_token'][:20]}...")
        if data.get("refresh_token"):
            print(f"  Refresh Token: {data['refresh_token'][:20]}...")
        print(f"  Expires At: {data.get('expires_at_seconds')}")
        print(f"  Scope: {data.get('scope')}")

    return token_response


def store_tokens_in_s3(
    token_response: dict,
    bucket: str,
    key: str,
    region: str = None,
    kms_key_id: str = None,
    namespace: str = "DEFAULT",
    client_id: str = None,
) -> None:
    """
    Store tokens in S3.

    Args:
        token_response: Token response from OAuth flow
        bucket: S3 bucket name
        key: S3 object key
        region: AWS region
        kms_key_id: Optional KMS key for encryption
        namespace: Token namespace
        client_id: Globus client ID (for token refresh)
    """
    print("\n☁️  Storing tokens in S3...")
    print("=" * 60)
    print(f"Bucket: {bucket}")
    print(f"Key: {key}")
    print(f"Namespace: {namespace}")
    if region:
        print(f"Region: {region}")
    if kms_key_id:
        print(f"KMS Key: {kms_key_id}")
    print("=" * 60)

    storage = S3TokenStorage(
        bucket=bucket,
        key=key,
        namespace=namespace,
        region=region,
        kms_key_id=kms_key_id,
        client_id=client_id,
    )

    storage.store(token_response)

    print("✓ Tokens stored successfully!")

    # Verify storage
    print("\n🔍 Verifying stored tokens...")
    for resource_server in token_response.by_resource_server:
        retrieved = storage.get_token_data(resource_server)
        if retrieved:
            print(f"  ✓ {resource_server}")
        else:
            print(f"  ✗ {resource_server} (FAILED)")

    print("\n✅ Setup complete!")
    print("\nNext steps:")
    print("1. Configure GitHub Actions secrets:")
    print(f"   - S3_TOKEN_BUCKET={bucket}")
    print(f"   - S3_TOKEN_KEY={key}")
    print(f"   - S3_TOKEN_NAMESPACE={namespace}")
    if region:
        print(f"   - AWS_REGION={region}")
    print("2. Ensure GitHub Actions has IAM permissions to read from S3")
    print("3. Run integration tests in CI!")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Setup Globus OAuth tokens for CI/CD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--client-id",
        default=os.getenv("GLOBUS_CLIENT_ID"),
        help="Globus Native App Client ID (default: $GLOBUS_CLIENT_ID)",
    )

    parser.add_argument(
        "--bucket",
        default=os.getenv("S3_TOKEN_BUCKET"),
        help="S3 bucket name (default: $S3_TOKEN_BUCKET)",
    )

    parser.add_argument(
        "--key",
        default=os.getenv("S3_TOKEN_KEY", "globus/ci-tokens.json"),
        help="S3 object key (default: $S3_TOKEN_KEY or 'globus/ci-tokens.json')",
    )

    parser.add_argument(
        "--namespace",
        default=os.getenv("S3_TOKEN_NAMESPACE", "DEFAULT"),
        help="Token namespace (default: $S3_TOKEN_NAMESPACE or 'DEFAULT')",
    )

    parser.add_argument(
        "--region",
        default=os.getenv("AWS_REGION"),
        help="AWS region (default: $AWS_REGION)",
    )

    parser.add_argument(
        "--kms-key",
        default=os.getenv("KMS_KEY_ID"),
        help="KMS key ID for encryption (default: $KMS_KEY_ID, uses AES256 if not set)",
    )

    parser.add_argument(
        "--environment",
        default=os.getenv("GLOBUS_SDK_ENVIRONMENT"),
        help="Globus environment: production, test, sandbox, preview (default: $GLOBUS_SDK_ENVIRONMENT or production)",
    )

    args = parser.parse_args()

    # Validate required arguments
    if not args.client_id:
        print("❌ Error: --client-id is required")
        print("\nGet a Client ID by registering a Native App at:")
        print("https://developers.globus.org")
        print("\nSet redirect URI to: http://localhost:8080")
        sys.exit(1)

    if not args.bucket:
        print("❌ Error: --bucket is required")
        sys.exit(1)

    # Perform OAuth flow
    token_response = perform_oauth_flow(args.client_id, environment=args.environment)

    # Store in S3
    store_tokens_in_s3(
        token_response=token_response,
        bucket=args.bucket,
        key=args.key,
        region=args.region,
        kms_key_id=args.kms_key,
        namespace=args.namespace,
        client_id=args.client_id,
    )


if __name__ == "__main__":
    main()
