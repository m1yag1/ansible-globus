#!/usr/bin/python
"""
Compatibility layer for Globus SDK v3 and v4.

This module provides a unified interface that works with both SDK versions,
allowing gradual migration without breaking existing code.
"""

import typing as t

import globus_sdk
from globus_sdk import ConfidentialAppAuthClient
from packaging import version

# Detect SDK version
SDK_VERSION = version.parse(globus_sdk.__version__)
IS_V4 = SDK_VERSION.major >= 4


def get_auth_client(client_id: str, client_secret: str) -> t.Any:
    """Get ConfidentialAppAuthClient compatible with both v3 and v4.

    ConfidentialAppAuthClient is used for client credentials flow in both versions.
    It has the oauth2_client_credentials_tokens method that AuthClient doesn't have.
    """
    return ConfidentialAppAuthClient(client_id, client_secret)


def get_transfer_client(
    client_id: str, client_secret: str, scopes: list[str] | None = None
) -> t.Any:
    """Get TransferClient compatible with both v3 and v4."""
    if IS_V4:
        from globus_sdk import ClientApp, TransferClient

        app = ClientApp(client_id=client_id, client_secret=client_secret)
        return TransferClient(app=app)
    else:
        from globus_sdk import ConfidentialAppAuthClient, TransferClient

        # In v3, we authenticate separately then create client with authorizer
        auth_client = ConfidentialAppAuthClient(client_id, client_secret)
        scopes = scopes or [TransferClient.scopes.all]
        token_response = auth_client.oauth2_client_credentials_tokens(
            requested_scopes=scopes
        )
        transfer_token = token_response.by_resource_server["transfer.api.globus.org"]
        authorizer = globus_sdk.AccessTokenAuthorizer(transfer_token["access_token"])
        return TransferClient(authorizer=authorizer)


def get_groups_client(
    client_id: str, client_secret: str, scopes: list[str] | None = None
) -> t.Any:
    """Get GroupsClient compatible with both v3 and v4."""
    if IS_V4:
        from globus_sdk import ClientApp, GroupsClient

        app = ClientApp(client_id=client_id, client_secret=client_secret)
        return GroupsClient(app=app)
    else:
        from globus_sdk import ConfidentialAppAuthClient, GroupsClient

        auth_client = ConfidentialAppAuthClient(client_id, client_secret)
        scopes = scopes or [GroupsClient.scopes.all]
        token_response = auth_client.oauth2_client_credentials_tokens(
            requested_scopes=scopes
        )
        groups_token = token_response.by_resource_server["groups.api.globus.org"]
        authorizer = globus_sdk.AccessTokenAuthorizer(groups_token["access_token"])
        return GroupsClient(authorizer=authorizer)


def get_flows_client(
    client_id: str, client_secret: str, scopes: list[str] | None = None
) -> t.Any:
    """Get FlowsClient compatible with both v3 and v4."""
    if IS_V4:
        from globus_sdk import ClientApp, FlowsClient

        app = ClientApp(client_id=client_id, client_secret=client_secret)
        return FlowsClient(app=app)
    else:
        from globus_sdk import ConfidentialAppAuthClient, FlowsClient

        auth_client = ConfidentialAppAuthClient(client_id, client_secret)
        scopes = scopes or [FlowsClient.scopes.all]
        token_response = auth_client.oauth2_client_credentials_tokens(
            requested_scopes=scopes
        )
        flows_token = token_response.by_resource_server["flows.globus.org"]
        authorizer = globus_sdk.AccessTokenAuthorizer(flows_token["access_token"])
        return FlowsClient(authorizer=authorizer)


def get_compute_client(
    client_id: str, client_secret: str, scopes: list[str] | None = None
) -> t.Any:
    """Get ComputeClient compatible with both v3 and v4."""
    # Note: Compute/FuncX has different patterns in v3/v4
    if IS_V4:
        from globus_sdk import ClientApp
        from globus_sdk.services.compute import ComputeClient

        app = ClientApp(client_id=client_id, client_secret=client_secret)
        return ComputeClient(app=app)
    else:
        # v3 doesn't have ComputeClient in the same way
        # Fall back to FuncX client or raise NotImplementedError
        try:
            from funcx import FuncXClient

            return FuncXClient()
        except ImportError:
            raise NotImplementedError(
                "Compute client not available in SDK v3. Upgrade to v4 or use FuncX SDK."
            ) from None


def get_timers_client(
    client_id: str, client_secret: str, scopes: list[str] | None = None
) -> t.Any:
    """Get TimersClient compatible with both v3 and v4."""
    if IS_V4:
        from globus_sdk import ClientApp, TimersClient

        app = ClientApp(client_id=client_id, client_secret=client_secret)
        return TimersClient(app=app)
    else:
        from globus_sdk import ConfidentialAppAuthClient, TimersClient

        auth_client = ConfidentialAppAuthClient(client_id, client_secret)
        scopes = scopes or [TimersClient.scopes.timer]
        token_response = auth_client.oauth2_client_credentials_tokens(
            requested_scopes=scopes
        )
        # Timers use transfer resource server
        timer_token = token_response.by_resource_server["transfer.api.globus.org"]
        authorizer = globus_sdk.AccessTokenAuthorizer(timer_token["access_token"])
        return TimersClient(authorizer=authorizer)


def scope_to_string(scope: t.Any) -> str:
    """Convert scope to string, handling both v3 and v4."""
    if IS_V4:
        # In v4, scopes must be explicitly converted to strings
        return str(scope)
    else:
        # In v3, scopes are already strings or can be used directly
        return scope if isinstance(scope, str) else str(scope)


def get_token_storage() -> type[t.Any]:
    """Get JSONTokenStorage with correct import path."""
    if IS_V4:
        from globus_sdk.token_storage import JSONTokenStorage
    else:
        from globus_sdk.tokenstorage import JSONTokenStorage

    return JSONTokenStorage


class ScopeBuilder:
    """Unified scope building interface for both v3 and v4."""

    def __init__(self, base_scope: str):
        """Initialize with base scope string."""
        self.scope = globus_sdk.Scope(base_scope)

    def add_dependency(self, dep_scope: str, optional: bool = False) -> "ScopeBuilder":
        """Add dependency in a version-agnostic way."""
        dep = globus_sdk.Scope(dep_scope, optional=optional)

        if IS_V4:
            # v4: immutable, returns new scope
            self.scope = self.scope.with_dependency(dep)
        else:
            # v3: mutable, modifies in place
            self.scope.add_dependency(dep)

        return self

    def build(self) -> t.Any:
        """Return the built scope."""
        return self.scope


class CompatScopes:
    """Scope constants compatible with both v3 and v4."""

    @staticmethod
    def transfer_all() -> str:
        """Get transfer:all scope as string."""
        return scope_to_string(globus_sdk.TransferClient.scopes.all)

    @staticmethod
    def groups_all() -> str:
        """Get groups:all scope as string."""
        return scope_to_string(globus_sdk.GroupsClient.scopes.all)

    @staticmethod
    def flows_all() -> str:
        """Get flows:all scope as string."""
        return scope_to_string(globus_sdk.FlowsClient.scopes.all)

    @staticmethod
    def flows_run() -> str:
        """Get flows:run scope as string."""
        return scope_to_string(globus_sdk.FlowsClient.scopes.run)

    @staticmethod
    def timers_all() -> str:
        """Get timers scope as string."""
        return scope_to_string(globus_sdk.TimersClient.scopes.timer)

    @staticmethod
    def auth_manage_projects() -> str:
        """Get auth:manage_projects scope as string."""
        return scope_to_string(globus_sdk.AuthClient.scopes.manage_projects)

    @staticmethod
    def auth_openid() -> str:
        """Get auth:openid scope as string."""
        from globus_sdk.scopes import AuthScopes

        return scope_to_string(AuthScopes.openid)

    @staticmethod
    def compute_all() -> str:
        """Get compute:all scope as string."""
        if IS_V4:
            from globus_sdk import ComputeClientV2

            return scope_to_string(ComputeClientV2.scopes.all)
        else:
            # v3 doesn't have standardized compute scopes
            return "https://auth.globus.org/scopes/facd7ccc-c5f4-42aa-916b-a0e270e2c2a9/all"


# Export version information
__all__ = [
    "SDK_VERSION",
    "IS_V4",
    "get_auth_client",
    "get_transfer_client",
    "get_groups_client",
    "get_flows_client",
    "get_compute_client",
    "get_timers_client",
    "scope_to_string",
    "get_token_storage",
    "ScopeBuilder",
    "CompatScopes",
]
