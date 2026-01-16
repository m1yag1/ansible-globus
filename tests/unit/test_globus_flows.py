#!/usr/bin/env python
"""Unit tests for globus_flows module helper functions.

These tests specifically cover the comparison functions used
for idempotency checking.

Note: The functions are copied here to avoid import issues with Ansible
module dependencies. These should be kept in sync with the actual module.
"""

import pytest


# Copy of the helper functions from plugins/modules/globus_flows.py
# These are tested here to ensure idempotency logic is correct
def _normalize_for_comparison(value):
    """Normalize a value for comparison (sort lists, handle None vs empty)."""
    if value is None:
        return None
    if isinstance(value, list):
        # Sort lists for order-independent comparison
        # Handle lists of dicts by converting to sorted tuples
        try:
            return sorted(value)
        except TypeError:
            # Lists contain unhashable types (dicts), compare as-is
            return value
    return value


def _dicts_equal(dict1, dict2, ignore_extra_keys=False):
    """Compare two dicts, optionally ignoring extra keys in dict2.

    Args:
        dict1: The expected/desired dict (from user params)
        dict2: The actual dict (from API response)
        ignore_extra_keys: If True, only check that dict1's keys match in dict2
    """
    if dict1 is None and dict2 is None:
        return True
    if dict1 is None or dict2 is None:
        return False
    if not isinstance(dict1, dict) or not isinstance(dict2, dict):
        return dict1 == dict2

    keys_to_check = set(dict1.keys())

    for key in keys_to_check:
        if key not in dict2:
            return False
        val1 = dict1[key]
        val2 = dict2[key]

        if isinstance(val1, dict):
            if not _dicts_equal(val1, val2, ignore_extra_keys):
                return False
        elif isinstance(val1, list) and isinstance(val2, list):
            # For lists of dicts, compare recursively
            if len(val1) != len(val2):
                return False
            for item1, item2 in zip(val1, val2, strict=True):
                if isinstance(item1, dict):
                    if not _dicts_equal(item1, item2, ignore_extra_keys):
                        return False
                elif item1 != item2:
                    return False
        elif val1 != val2:
            return False

    # If not ignoring extra keys, check dict2 doesn't have extra keys
    return ignore_extra_keys or set(dict2.keys()) == keys_to_check


class TestNormalizeForComparison:
    """Tests for _normalize_for_comparison function."""

    def test_none_value(self):
        """None values should return None."""
        assert _normalize_for_comparison(None) is None

    def test_string_value(self):
        """String values should pass through unchanged."""
        assert _normalize_for_comparison("public") == "public"
        assert (
            _normalize_for_comparison("all_authenticated_users")
            == "all_authenticated_users"
        )

    def test_list_sorting(self):
        """Lists should be sorted for order-independent comparison."""
        assert _normalize_for_comparison(["b", "a", "c"]) == ["a", "b", "c"]
        assert _normalize_for_comparison(["public"]) == ["public"]

    def test_list_with_special_values(self):
        """Lists with special Globus values should sort correctly."""
        input_list = ["all_authenticated_users", "public"]
        expected = ["all_authenticated_users", "public"]  # Already sorted
        assert _normalize_for_comparison(input_list) == expected

    def test_list_with_urns(self):
        """Lists with URNs should sort correctly."""
        input_list = [
            "urn:globus:auth:identity:def",
            "urn:globus:auth:identity:abc",
        ]
        expected = [
            "urn:globus:auth:identity:abc",
            "urn:globus:auth:identity:def",
        ]
        assert _normalize_for_comparison(input_list) == expected

    def test_empty_list(self):
        """Empty lists should remain empty."""
        assert _normalize_for_comparison([]) == []

    def test_dict_value(self):
        """Dict values should pass through unchanged."""
        d = {"key": "value"}
        assert _normalize_for_comparison(d) == d


class TestDictsEqual:
    """Tests for _dicts_equal function."""

    def test_both_none(self):
        """Two None values should be equal."""
        assert _dicts_equal(None, None) is True

    def test_one_none(self):
        """One None and one dict should not be equal."""
        assert _dicts_equal(None, {}) is False
        assert _dicts_equal({}, None) is False

    def test_identical_dicts(self):
        """Identical dicts should be equal."""
        d = {"key": "value", "nested": {"a": 1}}
        assert _dicts_equal(d, d) is True
        assert _dicts_equal(d, d.copy()) is True

    def test_different_values(self):
        """Dicts with different values should not be equal."""
        d1 = {"key": "value1"}
        d2 = {"key": "value2"}
        assert _dicts_equal(d1, d2) is False

    def test_missing_key(self):
        """Dict missing a key should not be equal."""
        d1 = {"key": "value"}
        d2 = {}
        assert _dicts_equal(d1, d2) is False

    def test_ignore_extra_keys_true(self):
        """With ignore_extra_keys=True, extra keys in dict2 should be ignored."""
        user_dict = {"StartAt": "TestState"}
        api_dict = {
            "StartAt": "TestState",
            "Version": "1.0",
            "Comment": "Added by API",
        }
        assert _dicts_equal(user_dict, api_dict, ignore_extra_keys=True) is True

    def test_ignore_extra_keys_false(self):
        """With ignore_extra_keys=False (default), extra keys should matter."""
        user_dict = {"StartAt": "TestState"}
        api_dict = {"StartAt": "TestState", "Version": "1.0"}
        assert _dicts_equal(user_dict, api_dict, ignore_extra_keys=False) is False

    def test_nested_dicts(self):
        """Nested dicts should be compared recursively."""
        d1 = {
            "States": {
                "TestState": {
                    "Type": "Action",
                    "End": True,
                }
            }
        }
        d2 = {
            "States": {
                "TestState": {
                    "Type": "Action",
                    "End": True,
                }
            }
        }
        assert _dicts_equal(d1, d2) is True

    def test_nested_dicts_with_extra_keys(self):
        """Nested dicts should respect ignore_extra_keys recursively."""
        user_dict = {
            "States": {
                "TestState": {
                    "Type": "Action",
                }
            }
        }
        api_dict = {
            "States": {
                "TestState": {
                    "Type": "Action",
                    "ResultPath": "$.result",  # Added by API
                }
            },
            "Version": "1.0",  # Added by API
        }
        assert _dicts_equal(user_dict, api_dict, ignore_extra_keys=True) is True

    def test_nested_dicts_different_value(self):
        """Nested dicts with different values should not be equal."""
        d1 = {"States": {"Test": {"Type": "Action"}}}
        d2 = {"States": {"Test": {"Type": "Pass"}}}
        assert _dicts_equal(d1, d2) is False

    def test_list_in_dict(self):
        """Lists inside dicts should be compared correctly."""
        d1 = {"items": [1, 2, 3]}
        d2 = {"items": [1, 2, 3]}
        assert _dicts_equal(d1, d2) is True

    def test_list_in_dict_different_length(self):
        """Lists of different lengths should not be equal."""
        d1 = {"items": [1, 2]}
        d2 = {"items": [1, 2, 3]}
        assert _dicts_equal(d1, d2) is False

    def test_list_of_dicts(self):
        """Lists of dicts should be compared recursively."""
        d1 = {
            "DATA": [
                {"source_path": "/a", "dest_path": "/b"},
            ]
        }
        d2 = {
            "DATA": [
                {"source_path": "/a", "dest_path": "/b"},
            ]
        }
        assert _dicts_equal(d1, d2) is True

    def test_list_of_dicts_with_extra_keys(self):
        """Lists of dicts should respect ignore_extra_keys."""
        user_dict = {
            "DATA": [
                {"source_path": "/a"},
            ]
        }
        api_dict = {
            "DATA": [
                {"source_path": "/a", "recursive": False},  # API adds default
            ]
        }
        assert _dicts_equal(user_dict, api_dict, ignore_extra_keys=True) is True

    def test_flow_definition_realistic(self):
        """Test with a realistic flow definition scenario."""
        # What the user provides
        user_definition = {
            "StartAt": "FailingTransfer",
            "States": {
                "FailingTransfer": {
                    "Type": "Action",
                    "ActionUrl": "https://transfer.actions.test.globuscs.info/transfer",
                    "Parameters": {
                        "source_endpoint": "7707a06d-535c-41fe-bf2b-b69294c334ae",
                        "destination_endpoint": "0dcf98c9-f4b8-4af1-a367-401b333c5818",
                        "DATA": [
                            {
                                "source_path": "/nonexistent/path",
                                "destination_path": "/also/nonexistent",
                            }
                        ],
                    },
                    "End": True,
                }
            },
        }

        # What the API returns (may have additional fields)
        api_definition = {
            "StartAt": "FailingTransfer",
            "States": {
                "FailingTransfer": {
                    "Type": "Action",
                    "ActionUrl": "https://transfer.actions.test.globuscs.info/transfer",
                    "Parameters": {
                        "source_endpoint": "7707a06d-535c-41fe-bf2b-b69294c334ae",
                        "destination_endpoint": "0dcf98c9-f4b8-4af1-a367-401b333c5818",
                        "DATA": [
                            {
                                "source_path": "/nonexistent/path",
                                "destination_path": "/also/nonexistent",
                            }
                        ],
                    },
                    "End": True,
                    "ResultPath": "$.TransferResult",  # API might add this
                }
            },
            "Comment": "Flow definition",  # API might add this
        }

        # Should be equal when ignoring extra keys
        assert (
            _dicts_equal(user_definition, api_definition, ignore_extra_keys=True)
            is True
        )

        # Should not be equal when not ignoring extra keys
        assert (
            _dicts_equal(user_definition, api_definition, ignore_extra_keys=False)
            is False
        )

    def test_input_schema_realistic(self):
        """Test with a realistic input_schema scenario."""
        user_schema = {
            "type": "object",
            "properties": {},
            "additionalProperties": True,
        }

        api_schema = {
            "type": "object",
            "properties": {},
            "additionalProperties": True,
            "$schema": "http://json-schema.org/draft-07/schema#",  # API might add
        }

        assert _dicts_equal(user_schema, api_schema, ignore_extra_keys=True) is True


class TestComparisonIntegration:
    """Integration tests combining both comparison functions."""

    def test_principal_list_comparison(self):
        """Test that principal lists compare correctly regardless of order."""
        user_principals = ["public", "all_authenticated_users"]
        api_principals = ["all_authenticated_users", "public"]  # Different order

        # After normalization, they should be equal
        assert _normalize_for_comparison(user_principals) == _normalize_for_comparison(
            api_principals
        )

    def test_urn_list_comparison(self):
        """Test that URN lists compare correctly regardless of order."""
        user_urns = [
            "urn:globus:auth:identity:user2",
            "urn:globus:auth:identity:user1",
        ]
        api_urns = [
            "urn:globus:auth:identity:user1",
            "urn:globus:auth:identity:user2",
        ]

        assert _normalize_for_comparison(user_urns) == _normalize_for_comparison(
            api_urns
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
