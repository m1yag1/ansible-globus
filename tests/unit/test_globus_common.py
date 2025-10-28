#!/usr/bin/env python

import os
import sys
import unittest.mock as mock

from ansible.module_utils.basic import AnsibleModule

# Add both the plugins directory and module_utils to the path
plugins_path = os.path.join(os.path.dirname(__file__), "../../plugins")
sys.path.insert(0, plugins_path)

from plugins.module_utils.globus_common import GlobusModuleBase, globus_argument_spec


def create_mock_module():
    """Create a mock Ansible module."""
    mock_module = mock.MagicMock(spec=AnsibleModule)
    # Make fail_json raise SystemExit like the real AnsibleModule
    mock_module.fail_json.side_effect = SystemExit
    return mock_module


def test_init():
    mock_module = create_mock_module()
    base = GlobusModuleBase(mock_module)

    assert base.module == mock_module
    assert not base.changed
    assert base.result == {"changed": False, "msg": ""}


def test_run_command_success():
    mock_module = create_mock_module()
    mock_module.run_command.return_value = (0, "success", "")
    base = GlobusModuleBase(mock_module)

    rc, stdout, stderr = base.run_command(["test", "command"])

    assert rc == 0
    assert stdout == "success"
    assert stderr == ""
    mock_module.run_command.assert_called_once_with(["test", "command"], check_rc=True)


def test_run_command_failure():
    mock_module = create_mock_module()
    mock_module.run_command.return_value = (1, "", "error")
    base = GlobusModuleBase(mock_module)

    rc, stdout, stderr = base.run_command(["test", "command"], check_rc=False)

    assert rc == 1
    assert stdout == ""
    assert stderr == "error"
    mock_module.run_command.assert_called_once_with(["test", "command"], check_rc=False)


def test_parse_json_output_valid():
    mock_module = create_mock_module()
    base = GlobusModuleBase(mock_module)

    result = base.parse_json_output('{"key": "value"}')

    assert result == {"key": "value"}


def test_parse_json_output_invalid():
    mock_module = create_mock_module()
    base = GlobusModuleBase(mock_module)

    try:
        base.parse_json_output("invalid json")
        raise AssertionError("Should have raised SystemExit")
    except SystemExit:
        pass

    mock_module.fail_json.assert_called_once()
    call_args = mock_module.fail_json.call_args[1]
    assert "Failed to parse JSON output" in call_args["msg"]


def test_check_globus_cli_installed():
    mock_module = create_mock_module()
    mock_module.run_command.return_value = (0, "/usr/bin/globus", "")
    base = GlobusModuleBase(mock_module)

    base.check_globus_cli()

    mock_module.run_command.assert_called_once_with(["which", "globus"], check_rc=False)


def test_check_globus_cli_not_installed():
    mock_module = create_mock_module()
    mock_module.run_command.return_value = (1, "", "not found")
    base = GlobusModuleBase(mock_module)

    try:
        base.check_globus_cli()
        raise AssertionError("Should have raised SystemExit")
    except SystemExit:
        pass

    mock_module.fail_json.assert_called_once()
    call_args = mock_module.fail_json.call_args[1]
    assert "Globus CLI not found" in call_args["msg"]


def test_is_authenticated_true():
    mock_module = create_mock_module()
    mock_module.run_command.return_value = (0, '{"id": "user123"}', "")
    base = GlobusModuleBase(mock_module)

    result = base.is_authenticated()

    assert result
    mock_module.run_command.assert_called_once_with(
        ["globus", "whoami"], check_rc=False
    )


def test_is_authenticated_false():
    mock_module = create_mock_module()
    mock_module.run_command.return_value = (1, "", "not authenticated")
    base = GlobusModuleBase(mock_module)

    result = base.is_authenticated()

    assert not result


def test_exit_json():
    mock_module = create_mock_module()
    base = GlobusModuleBase(mock_module)
    base.changed = True

    base.exit_json(custom_key="value")

    mock_module.exit_json.assert_called_once_with(
        changed=True, msg="", custom_key="value"
    )


def test_fail_json():
    mock_module = create_mock_module()
    base = GlobusModuleBase(mock_module)

    try:
        base.fail_json("Test error message")
        raise AssertionError("Should have raised SystemExit")
    except SystemExit:
        pass

    mock_module.fail_json.assert_called_once_with(msg="Test error message")


def test_globus_argument_spec():
    spec = globus_argument_spec()

    # Check structure
    assert isinstance(spec, dict)
    assert "state" in spec
    assert "auth_method" in spec
    assert "client_id" in spec
    assert "client_secret" in spec

    # Check defaults and choices
    assert spec["state"]["default"] == "present"
    assert spec["state"]["choices"] == ["present", "absent"]
    assert spec["auth_method"]["default"] == "cli"
    assert spec["auth_method"]["choices"] == [
        "cli",
        "client_credentials",
        "access_token",
    ]
    assert spec["client_secret"]["no_log"]
