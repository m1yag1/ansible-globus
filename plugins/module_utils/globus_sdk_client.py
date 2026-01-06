#!/usr/bin/python
"""
Globus SDK-based client for Ansible modules.
Supports both Globus SDK v3 and v4 via compatibility layer.
"""

import json
import os
import sqlite3
import typing as t

from globus_sdk import (
    AccessTokenAuthorizer,
    FlowsClient,
    GroupsClient,
    SearchClient,
    TransferClient,
)

from .globus_common import GlobusModuleBase
from .globus_sdk_compat import IS_V4, CompatScopes, get_auth_client

# Import ComputeClient with version awareness
if IS_V4:
    from globus_sdk import ComputeClientV2 as ComputeClient
else:
    from globus_sdk import ComputeClient


class GlobusSDKClient(GlobusModuleBase):
    """Globus SDK client wrapper for Ansible modules."""

    # Define available scopes for each service using compatibility layer
    SCOPES: dict[str, str] = {
        "transfer": CompatScopes.transfer_all(),
        "groups": CompatScopes.groups_all(),
        "compute": CompatScopes.compute_all(),
        "flows": CompatScopes.flows_all(),
        "timers": CompatScopes.timers_all(),
        "auth": CompatScopes.auth_manage_projects(),
        "search": CompatScopes.search_all(),
    }

    def __init__(
        self, module: t.Any, required_services: list[str] | None = None
    ) -> None:
        super().__init__(module)
        self.client_id: str | None = module.params.get("client_id")
        self.client_secret: str | None = module.params.get("client_secret")

        # Auto-detect auth method if not explicitly specified
        # Priority: client_credentials > cli
        explicit_auth_method = module.params.get("auth_method")
        if explicit_auth_method:
            self.auth_method = explicit_auth_method
        elif self.client_id and self.client_secret:
            self.auth_method = "client_credentials"
        else:
            self.auth_method = "cli"

        # Only request scopes for services that are actually needed
        self.required_services = required_services or [
            "transfer",
            "groups",
            "compute",
            "flows",
        ]

        self._auth_client: t.Any = None
        self._transfer_client: TransferClient | None = None
        self._groups_client: GroupsClient | None = None
        self._compute_client: ComputeClient | None = None
        self._flows_client: FlowsClient | None = None
        self._timers_client: t.Any = None
        self._search_client: SearchClient | None = None

        self._authenticate()

    def _authenticate(self) -> None:
        """Authenticate with Globus using SDK (supports v3 and v4)."""
        if self.auth_method == "client_credentials":
            if not self.client_id or not self.client_secret:
                self.fail_json(
                    "client_id and client_secret required for client_credentials auth"
                )

            # Use compatibility layer to get auth client (works with v3 and v4)
            self._auth_client = get_auth_client(self.client_id, self.client_secret)

            # Get tokens for required services only (principle of least privilege)
            # Note: Scopes are requested dynamically - no pre-configuration needed
            requested_scopes = [
                self.SCOPES[service]
                for service in self.required_services
                if service in self.SCOPES
            ]

            # Get tokens (works the same in v3 and v4 thanks to compat layer)
            token_response = self._auth_client.oauth2_client_credentials_tokens(
                requested_scopes=requested_scopes
            )

            # Create authorizers for each requested service
            if (
                "transfer" in self.required_services
                and "transfer.api.globus.org" in token_response.by_resource_server
            ):
                transfer_token = token_response.by_resource_server[
                    "transfer.api.globus.org"
                ]["access_token"]
                self.transfer_authorizer = AccessTokenAuthorizer(transfer_token)

            if (
                "groups" in self.required_services
                and "groups.api.globus.org" in token_response.by_resource_server
            ):
                groups_token = token_response.by_resource_server[
                    "groups.api.globus.org"
                ]["access_token"]
                self.groups_authorizer = AccessTokenAuthorizer(groups_token)

            if (
                "compute" in self.required_services
                and "funcx_service" in token_response.by_resource_server
            ):
                compute_token = token_response.by_resource_server["funcx_service"][
                    "access_token"
                ]
                self.compute_authorizer = AccessTokenAuthorizer(compute_token)

            if (
                "flows" in self.required_services
                and "flows.globus.org" in token_response.by_resource_server
            ):
                flows_token = token_response.by_resource_server["flows.globus.org"][
                    "access_token"
                ]
                self.flows_authorizer = AccessTokenAuthorizer(flows_token)

            # Timers has its own resource server (UUID-based)
            timers_resource_server = "524230d7-ea86-4a52-8312-86065a9e0417"
            if (
                "timers" in self.required_services
                and timers_resource_server in token_response.by_resource_server
            ):
                timer_token = token_response.by_resource_server[timers_resource_server][
                    "access_token"
                ]
                self.timers_authorizer = AccessTokenAuthorizer(timer_token)

            # Auth/Projects uses auth resource server
            if (
                "auth" in self.required_services
                and "auth.globus.org" in token_response.by_resource_server
            ):
                auth_token = token_response.by_resource_server["auth.globus.org"][
                    "access_token"
                ]
                self.auth_authorizer = AccessTokenAuthorizer(auth_token)

            # Search uses search.api.globus.org resource server
            if (
                "search" in self.required_services
                and "search.api.globus.org" in token_response.by_resource_server
            ):
                search_token = token_response.by_resource_server[
                    "search.api.globus.org"
                ]["access_token"]
                self.search_authorizer = AccessTokenAuthorizer(search_token)

        elif self.auth_method == "cli":
            self._authenticate_cli()

        else:
            self.fail_json(f"Unsupported auth method: {self.auth_method}")

    def _authenticate_cli(self) -> None:
        """Authenticate using cached globus-cli tokens from storage.db.

        Reads tokens from ~/.globus/cli/storage.db (the globus-cli token store).
        This enables a seamless experience where users authenticate once via
        'globus login' and subsequent Ansible runs use the cached tokens.

        Environment variables:
            GLOBUS_SDK_ENVIRONMENT: Environment name (production, test, sandbox)
            GLOBUS_PROFILE: Optional profile name for multi-profile setups
        """
        # Determine storage.db path
        db_path = os.path.expanduser("~/.globus/cli/storage.db")

        if not os.path.exists(db_path):
            self.fail_json(
                msg="No globus-cli tokens found. Run 'globus login' first to authenticate."
            )

        # Determine namespace from environment
        environment = os.environ.get("GLOBUS_SDK_ENVIRONMENT", "production")
        profile = os.environ.get("GLOBUS_PROFILE", "")
        namespace = f"userprofile/{environment}" + (f"/{profile}" if profile else "")

        # Map services to resource servers
        resource_servers = {
            "transfer": "transfer.api.globus.org",
            "groups": "groups.api.globus.org",
            "flows": "flows.globus.org",
            "timers": "524230d7-ea86-4a52-8312-86065a9e0417",
            "search": "search.api.globus.org",
            "auth": "auth.globus.org",
            "compute": "funcx_service",
        }

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            for service in self.required_services:
                rs = resource_servers.get(service)
                if not rs:
                    continue

                cursor.execute(
                    "SELECT token_data_json FROM token_storage "
                    "WHERE namespace = ? AND resource_server = ?",
                    (namespace, rs),
                )
                row = cursor.fetchone()

                if not row:
                    self.fail_json(
                        msg=f"No token found for {service} (resource_server={rs}) "
                        f"in namespace '{namespace}'. "
                        f"Run 'globus login' and consent to the required scopes."
                    )

                token_data = json.loads(row[0])
                access_token = token_data.get("access_token")

                if not access_token:
                    self.fail_json(
                        msg=f"Token for {service} has no access_token. "
                        f"Run 'globus login' to refresh tokens."
                    )

                # Create authorizer for this service
                authorizer = AccessTokenAuthorizer(access_token)
                setattr(self, f"{service}_authorizer", authorizer)

            conn.close()

        except sqlite3.Error as e:
            self.fail_json(msg=f"Failed to read globus-cli tokens: {e}")
        except json.JSONDecodeError as e:
            self.fail_json(msg=f"Invalid token data in storage.db: {e}")

    @property
    def transfer_client(self) -> TransferClient | None:
        """Get Transfer API client."""
        if self._transfer_client is None:
            self._transfer_client = TransferClient(authorizer=self.transfer_authorizer)
        return self._transfer_client

    @property
    def groups_client(self) -> GroupsClient | None:
        """Get Groups API client."""
        if self._groups_client is None:
            self._groups_client = GroupsClient(authorizer=self.groups_authorizer)
        return self._groups_client

    @property
    def compute_client(self) -> ComputeClient | None:
        """Get Compute API client."""
        if self._compute_client is None and hasattr(self, "compute_authorizer"):
            self._compute_client = ComputeClient(authorizer=self.compute_authorizer)
        return self._compute_client

    @property
    def flows_client(self) -> FlowsClient | None:
        """Get Flows API client."""
        if self._flows_client is None and hasattr(self, "flows_authorizer"):
            self._flows_client = FlowsClient(authorizer=self.flows_authorizer)
        return self._flows_client

    @property
    def timers_client(self) -> t.Any:
        """Get Timers API client."""
        if self._timers_client is None and hasattr(self, "timers_authorizer"):
            from globus_sdk import TimersClient

            self._timers_client = TimersClient(authorizer=self.timers_authorizer)
        return self._timers_client

    @property
    def auth_client(self) -> t.Any:
        """Get Auth API client for projects/policies management."""
        # For auth operations, we use the auth client created in _authenticate
        # For cli auth, create an AuthClient with the auth_authorizer
        if hasattr(self, "auth_authorizer") and self.auth_method == "cli":
            from globus_sdk import AuthClient

            if self._auth_client is None or not isinstance(
                self._auth_client, AuthClient
            ):
                self._auth_client = AuthClient(authorizer=self.auth_authorizer)
        return self._auth_client

    @property
    def search_client(self) -> SearchClient | None:
        """Get Search API client."""
        if self._search_client is None and hasattr(self, "search_authorizer"):
            self._search_client = SearchClient(authorizer=self.search_authorizer)
        return self._search_client

    # User-friendly hints for common Globus API error codes
    ERROR_HINTS = {
        "SUBSCRIPTION_MUST_BE_SPECIFIED": "Add 'subscription_id' parameter to specify which subscription to use.",
        "NOT_FOUND": "The requested resource may have been deleted or you may not have access.",
        "PERMISSION_DENIED": "Check that your credentials have the required permissions.",
    }

    def handle_api_error(self, error: Exception, operation: str = "API call") -> None:
        """Handle Globus API errors consistently with user-friendly messages."""
        import json

        # Try to parse Globus API error for structured info
        error_code = None
        error_detail = None
        if hasattr(error, "text"):
            try:
                error_data = json.loads(error.text)
                error_code = error_data.get("error", {}).get("code")
                error_detail = error_data.get("error", {}).get("detail")
            except (json.JSONDecodeError, TypeError):
                pass

        # Build user-friendly message
        if error_code and error_code in self.ERROR_HINTS:
            hint = self.ERROR_HINTS[error_code]
            msg = f"{error_detail} {hint}" if error_detail else f"{error_code}: {hint}"
        elif error_detail:
            msg = f"Failed {operation}: {error_detail}"
        elif hasattr(error, "http_status"):
            if error.http_status == 401:
                msg = f"Authentication failed for {operation}. Check your credentials."
            elif error.http_status == 403:
                msg = f"Permission denied for {operation}. Check your access rights."
            elif error.http_status == 404:
                msg = f"Resource not found for {operation}."
            else:
                msg = f"API error during {operation}: {error}"
        else:
            msg = f"Unexpected error during {operation}: {error}"

        self.fail_json(
            msg=msg,
            error_code=error_code,
            http_status=getattr(error, "http_status", None),
        )

    # Special principal values that should be passed through without resolution
    SPECIAL_PRINCIPALS = {"public", "all_authenticated_users"}

    def resolve_principals(
        self,
        principals: list[str],
        authorizer: t.Any = None,
        output_format: str = "urn",
    ) -> list[str]:
        """Resolve a list of principals to the requested format.

        Principals can be:

        - Special values: "public", "all_authenticated_users" (passed through as-is)
        - URNs: "urn:globus:auth:identity:..." or "urn:globus:groups:id:..." (passed through)
        - UUIDs: passed through (for identity IDs)
        - Usernames/emails: resolved to identity URN or ID via AuthClient

        :param principals: List of principal identifiers.
        :param authorizer: Optional authorizer for AuthClient (defaults to groups_authorizer).
        :param output_format: "urn" for URN format, "id" for just the UUID.
        :returns: List of resolved principals in the requested format.
        """
        from globus_sdk import AuthClient

        if not principals:
            return []

        result = []
        usernames_to_resolve = []

        for principal in principals:
            # Special values - pass through
            if principal in self.SPECIAL_PRINCIPALS:
                result.append(principal)
            # Already a URN - pass through
            elif principal.startswith("urn:"):
                if output_format == "id" and "urn:globus:auth:identity:" in principal:
                    # Extract ID from URN
                    result.append(principal.split(":")[-1])
                else:
                    result.append(principal)
            # Looks like a UUID - pass through (or convert to URN)
            elif self._is_uuid(principal):
                if output_format == "urn":
                    result.append(f"urn:globus:auth:identity:{principal}")
                else:
                    result.append(principal)
            # Username/email - needs resolution
            else:
                usernames_to_resolve.append(principal)

        # Resolve usernames if any
        if usernames_to_resolve:
            auth_authorizer = authorizer or getattr(self, "groups_authorizer", None)
            if not auth_authorizer:
                self.fail_json(
                    msg="Cannot resolve usernames: no authorizer available. "
                    "Use URNs or UUIDs instead."
                )

            auth_client = AuthClient(authorizer=auth_authorizer)
            try:
                response = auth_client.get_identities(usernames=usernames_to_resolve)
                identities = response.data.get("identities", [])

                # Build map of username -> identity
                identity_map = {i.get("username"): i for i in identities}

                # Check for unresolved usernames
                resolved_usernames = set(identity_map.keys())
                unresolved = [
                    u for u in usernames_to_resolve if u not in resolved_usernames
                ]
                if unresolved:
                    self.fail_json(
                        msg=f"Could not resolve identities for: {', '.join(unresolved)}. "
                        "Users may not exist or usernames may be incorrect."
                    )

                # Add resolved identities
                for username in usernames_to_resolve:
                    identity = identity_map[username]
                    if output_format == "urn":
                        result.append(f"urn:globus:auth:identity:{identity['id']}")
                    else:
                        result.append(identity["id"])

            except Exception as e:
                self.handle_api_error(e, "resolving usernames to identities")

        return result

    def _is_uuid(self, value: str) -> bool:
        """Check if a string looks like a UUID."""
        import re

        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        return bool(uuid_pattern.match(value))

    def get(
        self, endpoint: str, params: dict[str, t.Any] | None = None
    ) -> dict[str, t.Any]:
        """Make GET request using transfer client."""
        try:
            assert self.transfer_client is not None, "Transfer client not initialized"
            response = self.transfer_client.get(endpoint, query_params=params)
            return response.data if hasattr(response, "data") else response
        except Exception as e:
            self.handle_api_error(e, f"GET {endpoint}")
            return {}

    def post(
        self, endpoint: str, data: dict[str, t.Any] | None = None
    ) -> dict[str, t.Any]:
        """Make POST request using transfer client."""
        try:
            assert self.transfer_client is not None, "Transfer client not initialized"
            response = self.transfer_client.post(endpoint, data=data)
            return response.data if hasattr(response, "data") else response
        except Exception as e:
            self.handle_api_error(e, f"POST {endpoint}")
            return {}

    def put(
        self, endpoint: str, data: dict[str, t.Any] | None = None
    ) -> dict[str, t.Any]:
        """Make PUT request using transfer client."""
        try:
            assert self.transfer_client is not None, "Transfer client not initialized"
            response = self.transfer_client.put(endpoint, data=data)
            return response.data if hasattr(response, "data") else response
        except Exception as e:
            self.handle_api_error(e, f"PUT {endpoint}")
            return {}

    def delete(self, endpoint: str) -> bool | dict[str, t.Any]:
        """Make DELETE request using transfer client."""
        try:
            assert self.transfer_client is not None, "Transfer client not initialized"
            response = self.transfer_client.delete(endpoint)
            return response.data if hasattr(response, "data") else True
        except Exception as e:
            self.handle_api_error(e, f"DELETE {endpoint}")
            return False
