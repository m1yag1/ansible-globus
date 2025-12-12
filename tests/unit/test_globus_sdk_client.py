#!/usr/bin/env python
"""Unit tests for GlobusSDKClient auth method auto-detection."""

import os
import sys
import unittest.mock as mock

from ansible.module_utils.basic import AnsibleModule

# Add both the plugins directory and module_utils to the path
plugins_path = os.path.join(os.path.dirname(__file__), "../../plugins")
sys.path.insert(0, plugins_path)


def create_mock_module(params=None):
    """Create a mock Ansible module with default or custom parameters."""
    mock_module = mock.MagicMock(spec=AnsibleModule)
    default_params = {
        "auth_method": None,
        "client_id": None,
        "client_secret": None,
        "access_token": None,
    }
    if params:
        default_params.update(params)
    mock_module.params = default_params
    return mock_module


class TestAuthMethodAutoDetection:
    """Test auth method auto-detection in GlobusSDKClient."""

    @mock.patch("plugins.module_utils.globus_sdk_client.GlobusSDKClient._authenticate")
    @mock.patch("plugins.module_utils.globus_sdk_client.GlobusModuleBase.__init__")
    def test_explicit_auth_method_takes_precedence(
        self, mock_base_init, mock_authenticate
    ):
        """Test that explicit auth_method is used even when credentials are present."""
        mock_base_init.return_value = None

        from plugins.module_utils.globus_sdk_client import GlobusSDKClient

        mock_module = create_mock_module(
            {
                "auth_method": "cli",  # Explicit cli even with credentials
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
            }
        )

        client = GlobusSDKClient(mock_module, required_services=["transfer"])

        assert client.auth_method == "cli"

    @mock.patch("plugins.module_utils.globus_sdk_client.GlobusSDKClient._authenticate")
    @mock.patch("plugins.module_utils.globus_sdk_client.GlobusModuleBase.__init__")
    def test_auto_detect_client_credentials(self, mock_base_init, mock_authenticate):
        """Test auto-detection of client_credentials when both client_id and secret provided."""
        mock_base_init.return_value = None

        from plugins.module_utils.globus_sdk_client import GlobusSDKClient

        mock_module = create_mock_module(
            {
                "auth_method": None,  # Not specified
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
            }
        )

        client = GlobusSDKClient(mock_module, required_services=["transfer"])

        assert client.auth_method == "client_credentials"

    @mock.patch("plugins.module_utils.globus_sdk_client.GlobusSDKClient._authenticate")
    @mock.patch("plugins.module_utils.globus_sdk_client.GlobusModuleBase.__init__")
    def test_auto_detect_access_token(self, mock_base_init, mock_authenticate):
        """Test auto-detection of access_token auth when only access_token provided."""
        mock_base_init.return_value = None

        from plugins.module_utils.globus_sdk_client import GlobusSDKClient

        mock_module = create_mock_module(
            {
                "auth_method": None,  # Not specified
                "access_token": "test_access_token",
            }
        )

        client = GlobusSDKClient(mock_module, required_services=["transfer"])

        assert client.auth_method == "access_token"

    @mock.patch("plugins.module_utils.globus_sdk_client.GlobusSDKClient._authenticate")
    @mock.patch("plugins.module_utils.globus_sdk_client.GlobusModuleBase.__init__")
    def test_auto_detect_cli_fallback(self, mock_base_init, mock_authenticate):
        """Test fallback to cli auth when no credentials provided."""
        mock_base_init.return_value = None

        from plugins.module_utils.globus_sdk_client import GlobusSDKClient

        mock_module = create_mock_module(
            {
                "auth_method": None,
                "client_id": None,
                "client_secret": None,
                "access_token": None,
            }
        )

        client = GlobusSDKClient(mock_module, required_services=["transfer"])

        assert client.auth_method == "cli"

    @mock.patch("plugins.module_utils.globus_sdk_client.GlobusSDKClient._authenticate")
    @mock.patch("plugins.module_utils.globus_sdk_client.GlobusModuleBase.__init__")
    def test_client_id_alone_falls_back_to_cli(self, mock_base_init, mock_authenticate):
        """Test that client_id without client_secret falls back to cli."""
        mock_base_init.return_value = None

        from plugins.module_utils.globus_sdk_client import GlobusSDKClient

        mock_module = create_mock_module(
            {
                "auth_method": None,
                "client_id": "test_client_id",  # Only client_id, no secret
                "client_secret": None,
            }
        )

        client = GlobusSDKClient(mock_module, required_services=["transfer"])

        # Should fall back to cli since both client_id AND secret are required
        assert client.auth_method == "cli"

    @mock.patch("plugins.module_utils.globus_sdk_client.GlobusSDKClient._authenticate")
    @mock.patch("plugins.module_utils.globus_sdk_client.GlobusModuleBase.__init__")
    def test_client_credentials_takes_priority_over_access_token(
        self, mock_base_init, mock_authenticate
    ):
        """Test that client_credentials takes priority over access_token."""
        mock_base_init.return_value = None

        from plugins.module_utils.globus_sdk_client import GlobusSDKClient

        mock_module = create_mock_module(
            {
                "auth_method": None,
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
                "access_token": "test_access_token",  # Both provided
            }
        )

        client = GlobusSDKClient(mock_module, required_services=["transfer"])

        # client_credentials should take priority
        assert client.auth_method == "client_credentials"
