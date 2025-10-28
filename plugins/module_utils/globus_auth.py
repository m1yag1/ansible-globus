#!/usr/bin/python
"""
Authentication utilities for Globus Ansible modules.
"""

import base64
import json
import os
import tempfile
import typing as t

from .globus_common import GlobusModuleBase


class GlobusAuth(GlobusModuleBase):
    """Handle Globus authentication."""

    def __init__(self, module: t.Any) -> None:
        super().__init__(module)
        self.auth_method: str = module.params.get("auth_method", "cli")
        self.client_id: str | None = module.params.get("client_id")
        self.client_secret: str | None = module.params.get("client_secret")
        self.access_token: str | None = module.params.get("access_token")

    def authenticate(self) -> bool:
        """Perform authentication based on specified method."""
        if self.auth_method == "cli":
            return self._authenticate_cli()
        elif self.auth_method == "client_credentials":
            return self._authenticate_client_credentials()
        elif self.auth_method == "access_token":
            return self._authenticate_access_token()
        else:
            self.fail_json(f"Unsupported auth method: {self.auth_method}")
            # Unreachable but needed for mypy
            return False

    def _authenticate_cli(self) -> bool:
        """Use existing CLI authentication."""
        if not self.is_authenticated():
            self.fail_json(
                "Not authenticated with Globus CLI. Run 'globus login' first."
            )
        return True

    def _authenticate_client_credentials(self) -> bool:
        """Authenticate using client credentials."""
        if not self.client_id or not self.client_secret:
            self.fail_json(
                "client_id and client_secret required for client_credentials auth"
            )

        # Create temporary config with client credentials
        config = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "auth_flow": "client_credentials",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            config_file = f.name

        try:
            # Set environment to use our config
            env = os.environ.copy()
            env["GLOBUS_CONFIG_FILE"] = config_file

            # Test authentication
            rc, stdout, stderr = self.module.run_command(
                ["globus", "whoami"], environ_update=env, check_rc=False
            )

            if rc != 0:
                self.fail_json(f"Authentication failed: {stderr}")

            return True

        finally:
            os.unlink(config_file)

    def _authenticate_access_token(self) -> bool:
        """Authenticate using pre-existing access token."""
        if not self.access_token:
            self.fail_json("access_token required for access_token auth")
        # Token is already provided, no authentication needed
        return True

    def get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for API calls."""
        if self.auth_method == "cli":
            rc, stdout, _ = self.run_command(["globus", "session", "show"])
            session_data = self.parse_json_output(stdout)
            return {"Authorization": f"Bearer {session_data['access_token']}"}
        elif self.auth_method == "access_token":
            return {"Authorization": f"Bearer {self.access_token}"}

        # For client credentials, return basic auth
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        return {"Authorization": f"Basic {credentials}"}
