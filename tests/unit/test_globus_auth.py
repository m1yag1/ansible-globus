#!/usr/bin/env python

import os
import sys
import unittest.mock as mock

from ansible.module_utils.basic import AnsibleModule

# Add both the plugins directory and module_utils to the path
plugins_path = os.path.join(os.path.dirname(__file__), "../../plugins")
sys.path.insert(0, plugins_path)

from plugins.module_utils.globus_auth import GlobusAuth


def create_mock_module(params=None):
    """Create a mock Ansible module with default or custom parameters."""
    mock_module = mock.MagicMock(spec=AnsibleModule)
    default_params = {
        "auth_method": "cli",
        "client_id": None,
        "client_secret": None,
    }
    if params:
        default_params.update(params)
    mock_module.params = default_params
    return mock_module


def test_init_cli_auth():
    mock_module = create_mock_module()
    auth = GlobusAuth(mock_module)

    assert auth.auth_method == "cli"
    assert auth.client_id is None
    assert auth.client_secret is None


def test_init_client_credentials_auth():
    mock_module = create_mock_module(
        {
            "auth_method": "client_credentials",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
        }
    )

    auth = GlobusAuth(mock_module)

    assert auth.auth_method == "client_credentials"
    assert auth.client_id == "test_client_id"
    assert auth.client_secret == "test_client_secret"


@mock.patch.object(GlobusAuth, "is_authenticated")
def test_authenticate_cli_success(mock_is_authenticated):
    mock_is_authenticated.return_value = True
    mock_module = create_mock_module()
    auth = GlobusAuth(mock_module)

    result = auth.authenticate()

    assert result is True
    mock_is_authenticated.assert_called_once()


@mock.patch.object(GlobusAuth, "is_authenticated")
def test_authenticate_cli_failure(mock_is_authenticated):
    mock_is_authenticated.return_value = False
    mock_module = create_mock_module()
    auth = GlobusAuth(mock_module)

    auth.authenticate()

    mock_module.fail_json.assert_called_once()
    call_args = mock_module.fail_json.call_args[1]
    assert "Not authenticated with Globus CLI" in call_args["msg"]


def test_authenticate_client_credentials_missing_params():
    mock_module = create_mock_module({"auth_method": "client_credentials"})
    # Make fail_json raise an exception like it would in real Ansible
    mock_module.fail_json.side_effect = SystemExit("fail_json called")
    auth = GlobusAuth(mock_module)

    # The authenticate should raise SystemExit due to fail_json
    import pytest

    with pytest.raises(SystemExit):
        auth.authenticate()

    mock_module.fail_json.assert_called_once()
    call_args = mock_module.fail_json.call_args[1]
    assert "client_id and client_secret required" in call_args["msg"]


@mock.patch("tempfile.NamedTemporaryFile")
@mock.patch("os.unlink")
def test_authenticate_client_credentials_success(mock_unlink, mock_tempfile):
    # Setup mock tempfile
    mock_file = mock.MagicMock()
    mock_file.name = "/tmp/test_config.json"
    mock_tempfile.return_value.__enter__.return_value = mock_file

    # Setup module params
    mock_module = create_mock_module(
        {
            "auth_method": "client_credentials",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
        }
    )

    # Mock successful whoami command
    mock_module.run_command.return_value = (0, '{"id": "user123"}', "")

    auth = GlobusAuth(mock_module)
    result = auth.authenticate()

    assert result is True
    mock_unlink.assert_called_once_with("/tmp/test_config.json")


@mock.patch("tempfile.NamedTemporaryFile")
@mock.patch("os.unlink")
def test_authenticate_client_credentials_failure(mock_unlink, mock_tempfile):
    # Setup mock tempfile
    mock_file = mock.MagicMock()
    mock_file.name = "/tmp/test_config.json"
    mock_tempfile.return_value.__enter__.return_value = mock_file

    # Setup module params
    mock_module = create_mock_module(
        {
            "auth_method": "client_credentials",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
        }
    )

    # Mock failed whoami command
    mock_module.run_command.return_value = (1, "", "Authentication failed")

    auth = GlobusAuth(mock_module)
    auth.authenticate()

    mock_module.fail_json.assert_called_once()
    call_args = mock_module.fail_json.call_args[1]
    assert "Authentication failed" in call_args["msg"]
    mock_unlink.assert_called_once_with("/tmp/test_config.json")


def test_authenticate_unsupported_method():
    mock_module = create_mock_module({"auth_method": "unsupported"})
    auth = GlobusAuth(mock_module)

    auth.authenticate()

    mock_module.fail_json.assert_called_once()
    call_args = mock_module.fail_json.call_args[1]
    assert "Unsupported auth method" in call_args["msg"]


@mock.patch.object(GlobusAuth, "run_command")
@mock.patch.object(GlobusAuth, "parse_json_output")
def test_get_auth_headers_cli(mock_parse_json, mock_run_command):
    mock_run_command.return_value = (0, "session_output", "")
    mock_parse_json.return_value = {"access_token": "test_token"}

    mock_module = create_mock_module()
    auth = GlobusAuth(mock_module)
    headers = auth.get_auth_headers()

    assert headers == {"Authorization": "Bearer test_token"}
    mock_run_command.assert_called_once_with(["globus", "session", "show"])


def test_get_auth_headers_client_credentials():
    mock_module = create_mock_module(
        {
            "auth_method": "client_credentials",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
        }
    )

    auth = GlobusAuth(mock_module)
    headers = auth.get_auth_headers()

    # Check that we get basic auth header
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("Basic ")

    # Decode and verify the credentials
    import base64

    encoded_creds = headers["Authorization"].split(" ")[1]
    decoded_creds = base64.b64decode(encoded_creds).decode()
    assert decoded_creds == "test_client_id:test_client_secret"
