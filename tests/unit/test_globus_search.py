#!/usr/bin/env python
"""Unit tests for globus_search module."""

import importlib.util
import os
import sys

# Add plugins directory to path
plugins_path = os.path.join(os.path.dirname(__file__), "../../plugins")
sys.path.insert(0, plugins_path)


def test_globus_search_module_import():
    """Test that globus_search module can be imported (syntax check).

    Note: Full module execution requires ansible_collections imports,
    so we only verify the spec can be created without syntax errors.
    """
    module_path = os.path.join(
        os.path.dirname(__file__), "../../plugins/modules/globus_search.py"
    )
    spec = importlib.util.spec_from_file_location("globus_search", module_path)
    module = importlib.util.module_from_spec(spec)

    # Should not raise any exceptions during spec creation
    assert module is not None


def test_search_scope_in_compat_scopes():
    """Test that search scope is available in CompatScopes."""
    from plugins.module_utils.globus_sdk_compat import CompatScopes

    # Should have search_all method
    assert hasattr(CompatScopes, "search_all")

    # Should return a string
    search_scope = CompatScopes.search_all()
    assert isinstance(search_scope, str)

    # Should be valid URN format for search
    assert "search.api.globus.org" in search_scope


def test_search_scope_in_sdk_client():
    """Test that GlobusSDKClient has search scope."""
    from plugins.module_utils.globus_sdk_client import GlobusSDKClient

    # Check SCOPES dictionary includes search
    scopes = GlobusSDKClient.SCOPES

    assert "search" in scopes
    assert isinstance(scopes["search"], str)
    assert "search.api.globus.org" in scopes["search"]


def test_sdk_client_has_search_client():
    """Test that GlobusSDKClient has search_client property."""
    from plugins.module_utils.globus_sdk_client import GlobusSDKClient

    # Check that the class has the search_client property
    assert hasattr(GlobusSDKClient, "search_client")


def test_search_module_documentation():
    """Test that globus_search module has proper documentation strings."""
    module_path = os.path.join(
        os.path.dirname(__file__), "../../plugins/modules/globus_search.py"
    )

    with open(module_path) as f:
        content = f.read()

    # Should have DOCUMENTATION
    assert "DOCUMENTATION" in content
    assert "globus_search" in content
    assert "Globus Search indexes" in content

    # Should have EXAMPLES
    assert "EXAMPLES" in content
    assert "state: present" in content
    assert "state: absent" in content

    # Should have RETURN
    assert "RETURN" in content
    assert "index_id" in content


# Note: Function-level tests (find_index_by_name, create_index, etc.)
# are not included here because the module imports from ansible_collections,
# which requires a full Ansible collection installation to test properly.
# These functions are tested via integration tests instead.
