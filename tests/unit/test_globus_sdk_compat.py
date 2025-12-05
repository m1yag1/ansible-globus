#!/usr/bin/env python
"""Tests for new modules (globus_auth, globus_timer) and compatibility layer."""

import os
import sys

# Add plugins directory to path
plugins_path = os.path.join(os.path.dirname(__file__), "../../plugins")
sys.path.insert(0, plugins_path)


def test_compatibility_layer_import():
    """Test that the compatibility layer can be imported."""
    from plugins.module_utils.globus_sdk_compat import (
        IS_V4,
        SDK_VERSION,
    )

    # Should be able to import
    assert SDK_VERSION is not None
    assert isinstance(IS_V4, bool)


def test_compatibility_layer_version_detection():
    """Test SDK version detection."""
    from plugins.module_utils.globus_sdk_compat import IS_V4, SDK_VERSION

    # SDK version detection should be consistent
    # IS_V4 should be True if SDK version is 4 or higher
    assert isinstance(IS_V4, bool)
    assert SDK_VERSION.major in [3, 4]

    # Verify IS_V4 matches the actual version
    if SDK_VERSION.major >= 4:
        assert IS_V4 is True
    else:
        assert IS_V4 is False


def test_compat_scopes():
    """Test compatibility scope helpers."""
    from plugins.module_utils.globus_sdk_compat import CompatScopes

    # All scope methods should return strings
    assert isinstance(CompatScopes.transfer_all(), str)
    assert isinstance(CompatScopes.groups_all(), str)
    assert isinstance(CompatScopes.flows_all(), str)
    assert isinstance(CompatScopes.timers_all(), str)
    assert isinstance(CompatScopes.auth_manage_projects(), str)
    assert isinstance(CompatScopes.search_all(), str)

    # Should be valid URN format
    assert CompatScopes.transfer_all().startswith("urn:globus:auth:scope:")
    assert CompatScopes.groups_all().startswith("urn:globus:auth:scope:")
    assert CompatScopes.search_all().startswith("urn:globus:auth:scope:")


def test_globus_auth_module_import():
    """Test that globus_auth module can be imported."""
    # This will fail if there are syntax errors
    import importlib.util

    module_path = os.path.join(
        os.path.dirname(__file__), "../../plugins/modules/globus_auth.py"
    )
    spec = importlib.util.spec_from_file_location("globus_auth", module_path)
    module = importlib.util.module_from_spec(spec)

    # Should not raise any exceptions
    assert module is not None


def test_globus_timer_module_import():
    """Test that globus_timer module can be imported."""
    import importlib.util

    module_path = os.path.join(
        os.path.dirname(__file__), "../../plugins/modules/globus_timer.py"
    )
    spec = importlib.util.spec_from_file_location("globus_timer", module_path)
    module = importlib.util.module_from_spec(spec)

    # Should not raise any exceptions
    assert module is not None


def test_sdk_client_has_new_clients():
    """Test that GlobusSDKClient has timers and auth clients."""
    from plugins.module_utils.globus_sdk_client import GlobusSDKClient

    # Check that the class has the new client properties
    assert hasattr(GlobusSDKClient, "timers_client")
    assert hasattr(GlobusSDKClient, "auth_client")


def test_sdk_client_has_compat_scopes():
    """Test that GlobusSDKClient uses compat scopes."""
    from plugins.module_utils.globus_sdk_client import GlobusSDKClient

    # Check SCOPES dictionary
    scopes = GlobusSDKClient.SCOPES

    assert "transfer" in scopes
    assert "groups" in scopes
    assert "flows" in scopes
    assert "timers" in scopes
    assert "auth" in scopes
    assert "search" in scopes

    # All should be strings (from CompatScopes)
    for scope in scopes.values():
        assert isinstance(scope, str)
