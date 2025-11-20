#!/usr/bin/python
"""
Globus SDK-based client for Ansible modules.
Supports both Globus SDK v3 and v4 via compatibility layer.
"""

import typing as t

from globus_sdk import (
    AccessTokenAuthorizer,
    FlowsClient,
    GroupsClient,
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
    }

    def __init__(
        self, module: t.Any, required_services: list[str] | None = None
    ) -> None:
        super().__init__(module)
        self.auth_method: str = module.params.get("auth_method", "client_credentials")
        self.client_id: str | None = module.params.get("client_id")
        self.client_secret: str | None = module.params.get("client_secret")
        self.access_token: str | None = module.params.get("access_token")

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

            # Timers uses the transfer resource server
            if (
                "timers" in self.required_services
                and "transfer.api.globus.org" in token_response.by_resource_server
            ):
                timer_token = token_response.by_resource_server[
                    "transfer.api.globus.org"
                ]["access_token"]
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

        elif self.auth_method == "access_token":
            if not self.access_token:
                self.fail_json("access_token required for access_token auth")

            # Use the same token for all services (assumes it has all required scopes)
            authorizer = AccessTokenAuthorizer(self.access_token)
            self.transfer_authorizer = authorizer
            self.groups_authorizer = authorizer
            self.compute_authorizer = authorizer
            self.flows_authorizer = authorizer
            self.timers_authorizer = authorizer
            self.auth_authorizer = authorizer

        else:
            self.fail_json(f"Unsupported auth method: {self.auth_method}")

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
        # or create one with the auth authorizer if using access_token method
        if hasattr(self, "auth_authorizer") and self.auth_method == "access_token":
            from globus_sdk import AuthClient

            if self._auth_client is None or not isinstance(
                self._auth_client, AuthClient
            ):
                self._auth_client = AuthClient(authorizer=self.auth_authorizer)
        return self._auth_client

    def handle_api_error(self, error: Exception, operation: str = "API call") -> None:
        """Handle Globus API errors consistently."""
        if hasattr(error, "http_status"):
            if error.http_status == 401:
                self.fail_json(f"Authentication failed for {operation}: {error}")
            elif error.http_status == 403:
                self.fail_json(f"Permission denied for {operation}: {error}")
            elif error.http_status == 404:
                self.fail_json(f"Resource not found for {operation}: {error}")
            else:
                self.fail_json(f"API error during {operation}: {error}")
        else:
            self.fail_json(f"Unexpected error during {operation}: {error}")

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
