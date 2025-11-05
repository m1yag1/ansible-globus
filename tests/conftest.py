"""
Shared pytest fixtures for ansible-globus tests.

This module provides fixtures for authentication and token management
across unit, integration, and E2E tests.
"""

import os
import sys
from pathlib import Path

import pytest

# Add plugins and tests directories to Python path for imports
plugins_path = Path(__file__).parent.parent / "plugins"
tests_path = Path(__file__).parent
sys.path.insert(0, str(plugins_path))
sys.path.insert(0, str(tests_path))


@pytest.fixture(scope="session")
def globus_auth_config():
    """
    Determine authentication configuration based on environment.

    Returns a dict with auth method and credentials:
    - For CI with S3 tokens: {"method": "s3_tokens", "bucket": "...", "key": "..."}
    - For CI with client creds: {"method": "client_credentials", "client_id": "...", "client_secret": "..."}
    - For local CLI: {"method": "cli"}

    Priority:
    1. S3 token storage (if S3_TOKEN_BUCKET is set)
    2. Client credentials (if GLOBUS_CLIENT_ID and GLOBUS_CLIENT_SECRET are set)
    3. CLI authentication (fallback for local development)
    """
    # Check for S3 token storage
    s3_bucket = os.getenv("S3_TOKEN_BUCKET")
    print(f"DEBUG: S3_TOKEN_BUCKET = {s3_bucket}")
    if s3_bucket:
        config = {
            "method": "s3_tokens",
            "bucket": s3_bucket,
            "key": os.getenv("S3_TOKEN_KEY", "globus/ci-tokens.json"),
            "namespace": os.getenv("S3_TOKEN_NAMESPACE", "DEFAULT"),
            "region": os.getenv("AWS_REGION"),
        }
        print(f"DEBUG: Using S3 tokens auth: {config}")
        return config

    # Check for client credentials
    client_id = os.getenv("GLOBUS_CLIENT_ID")
    client_secret = os.getenv("GLOBUS_CLIENT_SECRET")
    print(f"DEBUG: GLOBUS_CLIENT_ID = {client_id is not None}")
    if client_id and client_secret:
        config = {
            "method": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        print("DEBUG: Using client credentials auth")
        return config

    # Fallback to CLI (local development)
    print("DEBUG: Falling back to CLI auth")
    return {"method": "cli"}


@pytest.fixture(scope="session")
def globus_tokens(globus_auth_config):
    """
    Provide Globus access tokens for testing.

    This fixture handles token retrieval from various sources:
    - S3 token storage (for CI with OAuth tokens)
    - Client credentials flow (for CI with service accounts)
    - CLI tokens (for local development)

    Returns:
        Dict mapping resource_server to token_data
    """
    auth_method = globus_auth_config["method"]
    print(f"DEBUG: globus_tokens using auth_method = {auth_method}")

    if auth_method == "s3_tokens":
        print("DEBUG: Calling _get_tokens_from_s3")
        return _get_tokens_from_s3(globus_auth_config)
    elif auth_method == "client_credentials":
        print("DEBUG: Calling _get_tokens_from_client_credentials")
        return _get_tokens_from_client_credentials(globus_auth_config)
    elif auth_method == "cli":
        print("DEBUG: Calling _get_tokens_from_cli")
        return _get_tokens_from_cli()
    else:
        pytest.skip(f"Unknown auth method: {auth_method}")


def _get_tokens_from_s3(config):
    """Retrieve tokens from S3 token storage and refresh if needed."""
    import time

    try:
        from s3_token_storage import S3TokenStorage
    except ImportError:
        pytest.skip("boto3 not installed (required for S3 token storage)")

    try:
        storage = S3TokenStorage(
            bucket=config["bucket"],
            key=config["key"],
            namespace=config["namespace"],
            region=config.get("region"),
        )

        # Get all tokens for this namespace
        tokens = storage.get_all_token_data()

        if not tokens:
            pytest.skip(
                f"No tokens found in S3: s3://{config['bucket']}/{config['key']} "
                f"namespace={config['namespace']}"
            )

        # Check if any tokens are expired and refresh them
        from globus_sdk import NativeAppAuthClient

        # Get the native client ID from tokens (stored in metadata if available)
        # For now, try to get it from environment
        client_id = os.getenv("GLOBUS_CLIENT_ID")
        if not client_id:
            # Try to extract from first token's metadata if available
            for _resource_server, token_data in tokens.items():
                if "client_id" in token_data:
                    client_id = token_data["client_id"]
                    break

        if not client_id:
            pytest.skip("GLOBUS_CLIENT_ID not set and not found in token metadata")

        auth_client = NativeAppAuthClient(client_id)
        needs_save = False

        # Check each token and refresh if expired
        for resource_server, token_data in tokens.items():
            expires_at = token_data.get("expires_at_seconds", 0)
            current_time = time.time()

            # Refresh if token expires within next 5 minutes
            if expires_at - current_time < 300:
                refresh_token = token_data.get("refresh_token")
                if not refresh_token:
                    pytest.skip(
                        f"Token for {resource_server} is expired and no refresh token available"
                    )

                # Refresh the token
                try:
                    token_response = auth_client.oauth2_refresh_token(refresh_token)

                    # Update the token data
                    refreshed_data = token_response.by_resource_server.get(
                        resource_server
                    )
                    if refreshed_data:
                        tokens[resource_server].update(
                            {
                                "access_token": refreshed_data["access_token"],
                                "expires_at_seconds": refreshed_data.get(
                                    "expires_at_seconds"
                                ),
                                "refresh_token": refreshed_data.get(
                                    "refresh_token", refresh_token
                                ),
                            }
                        )
                        needs_save = True

                except Exception as e:
                    pytest.skip(f"Failed to refresh token for {resource_server}: {e}")

        # Save refreshed tokens back to S3
        if needs_save:
            from globus_sdk import OAuthTokenResponse

            # Reconstruct token response for storage
            token_dict = {"by_resource_server": tokens}
            token_response = OAuthTokenResponse(token_dict)
            storage.store(token_response)

        return tokens

    except Exception as e:
        pytest.skip(f"Failed to retrieve tokens from S3: {e}")


def _get_tokens_from_client_credentials(config):
    """Get tokens using client credentials flow."""
    from globus_sdk import ConfidentialAppAuthClient

    try:
        client = ConfidentialAppAuthClient(config["client_id"], config["client_secret"])

        # Request all required scopes
        scopes = [
            "urn:globus:auth:scope:transfer.api.globus.org:all",
            "urn:globus:auth:scope:groups.api.globus.org:all",
            "urn:globus:auth:scope:compute.api.globus.org:all",
            "urn:globus:auth:scope:flows.api.globus.org:all",
        ]

        token_response = client.oauth2_client_credentials_tokens(
            requested_scopes=scopes
        )

        # Convert to dict format expected by tests
        tokens = {}
        for resource_server, data in token_response.by_resource_server.items():
            tokens[resource_server] = {
                "access_token": data["access_token"],
                "expires_at_seconds": data.get("expires_at_seconds"),
                "scope": data.get("scope"),
                "token_type": data.get("token_type", "Bearer"),
            }

        return tokens

    except Exception as e:
        pytest.skip(f"Failed to get tokens via client credentials: {e}")


def _get_tokens_from_cli():
    """Get tokens from Globus CLI."""
    import json
    import subprocess

    # Check if Globus CLI is available
    try:
        subprocess.run(["globus", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("Globus CLI not available")

    # Check if authenticated
    try:
        result = subprocess.run(
            ["globus", "session", "show"], check=True, capture_output=True, text=True
        )
        json.loads(result.stdout)

        # Extract token from session
        # Note: CLI stores tokens differently, may need adjustment
        pytest.skip("CLI token extraction not yet implemented")

    except subprocess.CalledProcessError:
        pytest.skip("Not authenticated with Globus CLI - run 'globus login'")


def _get_auth_params_for_service(globus_auth_config, globus_tokens, service):
    """
    Helper function to generate auth params for a specific service.

    Args:
        globus_auth_config: Auth configuration dict
        globus_tokens: Token dict mapping resource_server to token_data
        service: Service name (e.g., 'groups', 'transfer', 'flows', 'compute')

    Returns:
        YAML-formatted string with authentication parameters
    """
    auth_method = globus_auth_config["method"]

    # Map service names to resource servers
    service_to_resource_server = {
        "groups": "groups.api.globus.org",
        "transfer": "transfer.api.globus.org",
        "flows": "flows.globus.org",
        "compute": "funcx_service",
        "timers": "524230d7-ea86-4a52-8312-86065a9e0417",  # Timers have their own resource server
        "auth": "auth.globus.org",  # Auth/Projects use auth resource server
    }

    if auth_method == "s3_tokens" or auth_method == "cli":
        # Use access token for the specific service
        resource_server = service_to_resource_server.get(service)
        if not resource_server:
            pytest.skip(f"Unknown service: {service}")

        token_data = globus_tokens.get(resource_server, {})
        access_token = token_data.get("access_token")

        if access_token:
            return f"""auth_method: access_token
        access_token: {access_token}"""
        else:
            pytest.skip(f"No {service} token available")

    elif auth_method == "client_credentials":
        return f"""auth_method: client_credentials
        client_id: {globus_auth_config['client_id']}
        client_secret: {globus_auth_config['client_secret']}"""

    return "auth_method: cli"


@pytest.fixture
def ansible_playbook_auth_params(globus_auth_config, globus_tokens):
    """
    Generate Ansible playbook authentication parameters for groups service.

    Returns YAML string that can be inserted into playbook task parameters.

    For backwards compatibility, this returns groups auth params.
    Use service-specific fixtures for other services.
    """
    return _get_auth_params_for_service(globus_auth_config, globus_tokens, "groups")


@pytest.fixture
def ansible_playbook_auth_params_transfer(globus_auth_config, globus_tokens):
    """Generate Ansible playbook authentication parameters for transfer service."""
    return _get_auth_params_for_service(globus_auth_config, globus_tokens, "transfer")


@pytest.fixture
def ansible_playbook_auth_params_flows(globus_auth_config, globus_tokens):
    """Generate Ansible playbook authentication parameters for flows service."""
    return _get_auth_params_for_service(globus_auth_config, globus_tokens, "flows")


@pytest.fixture
def ansible_playbook_auth_params_compute(globus_auth_config, globus_tokens):
    """Generate Ansible playbook authentication parameters for compute service."""
    return _get_auth_params_for_service(globus_auth_config, globus_tokens, "compute")


@pytest.fixture
def ansible_playbook_auth_params_timers(globus_auth_config, globus_tokens):
    """Generate Ansible playbook authentication parameters for timers service."""
    return _get_auth_params_for_service(globus_auth_config, globus_tokens, "timers")


@pytest.fixture
def ansible_playbook_auth_params_auth(globus_auth_config, globus_tokens):
    """Generate Ansible playbook authentication parameters for auth service (projects/policies)."""
    return _get_auth_params_for_service(globus_auth_config, globus_tokens, "auth")
