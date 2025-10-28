#!/usr/bin/env python
"""
Cleanup script for test resources left behind by failed E2E tests.
"""

import argparse
import logging
import os
import sys

from globus_sdk import (
    AccessTokenAuthorizer,
    ComputeClient,
    ConfidentialAppAuthClient,
    FlowsClient,
    GroupsClient,
    TransferClient,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestResourceCleaner:
    """Clean up test resources from Globus services."""

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self._setup_clients()

    def _setup_clients(self):
        """Set up Globus SDK clients."""
        auth_client = ConfidentialAppAuthClient(self.client_id, self.client_secret)

        # Get tokens
        token_response = auth_client.oauth2_client_credentials_tokens(
            requested_scopes=[
                "urn:globus:auth:scope:transfer.api.globus.org:all",
                "urn:globus:auth:scope:groups.api.globus.org:all",
                "urn:globus:auth:scope:compute.api.globus.org:all",
                "urn:globus:auth:scope:flows.api.globus.org:all",
            ]
        )

        # Create clients
        transfer_token = token_response.by_resource_server["transfer.api.globus.org"][
            "access_token"
        ]
        groups_token = token_response.by_resource_server["groups.api.globus.org"][
            "access_token"
        ]

        self.transfer_client = TransferClient(
            authorizer=AccessTokenAuthorizer(transfer_token)
        )
        self.groups_client = GroupsClient(
            authorizer=AccessTokenAuthorizer(groups_token)
        )

        # Optional clients (may not have permissions)
        try:
            compute_token = token_response.by_resource_server["compute.api.globus.org"][
                "access_token"
            ]
            self.compute_client = ComputeClient(
                authorizer=AccessTokenAuthorizer(compute_token)
            )
        except KeyError:
            self.compute_client = None
            logger.warning("No compute access token available")

        try:
            flows_token = token_response.by_resource_server["flows.api.globus.org"][
                "access_token"
            ]
            self.flows_client = FlowsClient(
                authorizer=AccessTokenAuthorizer(flows_token)
            )
        except KeyError:
            self.flows_client = None
            logger.warning("No flows access token available")

    def find_test_resources(self, test_id=None):
        """Find all test resources, optionally filtered by test ID."""
        test_resources = {
            "endpoints": [],
            "collections": [],
            "groups": [],
            "compute_endpoints": [],
            "flows": [],
        }

        # Find test endpoints
        try:
            endpoints = self.transfer_client.endpoint_search(
                filter_fulltext="e2e-test-endpoint"
            )
            for endpoint in endpoints:
                if test_id is None or test_id in endpoint["display_name"]:
                    test_resources["endpoints"].append(endpoint)
        except Exception as e:
            logger.error(f"Error finding endpoints: {e}")

        # Find test collections
        try:
            for endpoint in test_resources["endpoints"]:
                collections = self.transfer_client.operation_ls(endpoint["id"])
                for collection in collections:
                    if "e2e-test-collection" in collection.get("name", "") and (
                        test_id is None or test_id in collection["name"]
                    ):
                        test_resources["collections"].append(collection)
        except Exception as e:
            logger.error(f"Error finding collections: {e}")

        # Find test groups
        try:
            groups = self.groups_client.get_my_groups()
            for group in groups:
                if (
                    "e2e-research-group" in group["name"]
                    or "idempotency-test" in group["name"]
                ) and (test_id is None or test_id in group["name"]):
                    test_resources["groups"].append(group)
        except Exception as e:
            logger.error(f"Error finding groups: {e}")

        # Find test compute endpoints
        if self.compute_client:
            try:
                compute_endpoints = self.compute_client.get_endpoints()
                for endpoint in compute_endpoints:
                    if "e2e-compute" in endpoint["name"] and (
                        test_id is None or test_id in endpoint["name"]
                    ):
                        test_resources["compute_endpoints"].append(endpoint)
            except Exception as e:
                logger.error(f"Error finding compute endpoints: {e}")

        # Find test flows
        if self.flows_client:
            try:
                flows = self.flows_client.list_flows()
                for flow in flows:
                    if "e2e-test-flow" in flow["title"] and (
                        test_id is None or test_id in flow["title"]
                    ):
                        test_resources["flows"].append(flow)
            except Exception as e:
                logger.error(f"Error finding flows: {e}")

        return test_resources

    def delete_test_resources(self, test_resources, dry_run=False):
        """Delete test resources."""
        deleted = {"success": [], "failed": []}

        # Delete flows first
        for flow in test_resources["flows"]:
            try:
                if not dry_run:
                    self.flows_client.delete_flow(flow["id"])
                logger.info(
                    f"{'Would delete' if dry_run else 'Deleted'} flow: {flow['title']}"
                )
                deleted["success"].append(("flow", flow["title"]))
            except Exception as e:
                logger.error(f"Failed to delete flow {flow['title']}: {e}")
                deleted["failed"].append(("flow", flow["title"], str(e)))

        # Delete collections
        for collection in test_resources["collections"]:
            try:
                if not dry_run:
                    self.transfer_client.delete_endpoint(collection["id"])
                logger.info(
                    f"{'Would delete' if dry_run else 'Deleted'} collection: {collection['name']}"
                )
                deleted["success"].append(("collection", collection["name"]))
            except Exception as e:
                logger.error(f"Failed to delete collection {collection['name']}: {e}")
                deleted["failed"].append(("collection", collection["name"], str(e)))

        # Delete endpoints
        for endpoint in test_resources["endpoints"]:
            try:
                if not dry_run:
                    self.transfer_client.delete_endpoint(endpoint["id"])
                logger.info(
                    f"{'Would delete' if dry_run else 'Deleted'} endpoint: {endpoint['display_name']}"
                )
                deleted["success"].append(("endpoint", endpoint["display_name"]))
            except Exception as e:
                logger.error(
                    f"Failed to delete endpoint {endpoint['display_name']}: {e}"
                )
                deleted["failed"].append(("endpoint", endpoint["display_name"], str(e)))

        # Delete compute endpoints
        for endpoint in test_resources["compute_endpoints"]:
            try:
                if not dry_run:
                    self.compute_client.delete_endpoint(endpoint["uuid"])
                logger.info(
                    f"{'Would delete' if dry_run else 'Deleted'} compute endpoint: {endpoint['name']}"
                )
                deleted["success"].append(("compute_endpoint", endpoint["name"]))
            except Exception as e:
                logger.error(
                    f"Failed to delete compute endpoint {endpoint['name']}: {e}"
                )
                deleted["failed"].append(("compute_endpoint", endpoint["name"], str(e)))

        # Delete groups last
        for group in test_resources["groups"]:
            try:
                if not dry_run:
                    self.groups_client.delete_group(group["id"])
                logger.info(
                    f"{'Would delete' if dry_run else 'Deleted'} group: {group['name']}"
                )
                deleted["success"].append(("group", group["name"]))
            except Exception as e:
                logger.error(f"Failed to delete group {group['name']}: {e}")
                deleted["failed"].append(("group", group["name"], str(e)))

        return deleted

    def list_resources(self, test_id=None):
        """List all test resources."""
        resources = self.find_test_resources(test_id)

        print("Found test resources:")
        print("=" * 50)

        for resource_type, items in resources.items():
            if items:
                print(f"\n{resource_type.upper()}:")
                for item in items:
                    if resource_type == "endpoints":
                        print(f"  - {item['display_name']} ({item['id']})")
                    elif resource_type == "collections" or resource_type == "groups":
                        print(f"  - {item['name']} ({item['id']})")
                    elif resource_type == "compute_endpoints":
                        print(f"  - {item['name']} ({item['uuid']})")
                    elif resource_type == "flows":
                        print(f"  - {item['title']} ({item['id']})")

        total = sum(len(items) for items in resources.values())
        print(f"\nTotal resources found: {total}")

        return resources


def main():
    parser = argparse.ArgumentParser(description="Clean up Globus test resources")
    parser.add_argument(
        "--list", action="store_true", help="List test resources without deleting"
    )
    parser.add_argument(
        "--test-id", type=str, help="Clean resources for specific test ID only"
    )
    parser.add_argument(
        "--all", action="store_true", help="Clean ALL test resources (dangerous!)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--client-id", type=str, help="Globus client ID (or set GLOBUS_CLIENT_ID)"
    )
    parser.add_argument(
        "--client-secret",
        type=str,
        help="Globus client secret (or set GLOBUS_CLIENT_SECRET)",
    )

    args = parser.parse_args()

    # Get credentials
    client_id = args.client_id or os.getenv("GLOBUS_CLIENT_ID")
    client_secret = args.client_secret or os.getenv("GLOBUS_CLIENT_SECRET")

    if not client_id or not client_secret:
        logger.error(
            "Client ID and secret required. Set GLOBUS_CLIENT_ID and GLOBUS_CLIENT_SECRET environment variables or use --client-id and --client-secret"
        )
        sys.exit(1)

    # Create cleaner
    cleaner = TestResourceCleaner(client_id, client_secret)

    if args.list:
        # Just list resources
        cleaner.list_resources(args.test_id)
    else:
        # Find resources to delete
        resources = cleaner.find_test_resources(args.test_id)
        total = sum(len(items) for items in resources.values())

        if total == 0:
            logger.info("No test resources found")
            return

        # Show what will be deleted
        print(f"Found {total} test resources to delete:")
        cleaner.list_resources(args.test_id)

        # Confirm deletion
        if not args.all and not args.dry_run:
            confirm = input(
                "\nAre you sure you want to delete these resources? (yes/no): "
            )
            if confirm.lower() != "yes":
                logger.info("Deletion cancelled")
                return

        # Delete resources
        deleted = cleaner.delete_test_resources(resources, dry_run=args.dry_run)

        print(f"\nDeletion {'simulation' if args.dry_run else 'results'}:")
        print(
            f"Successfully {'would delete' if args.dry_run else 'deleted'}: {len(deleted['success'])}"
        )
        print(f"Failed to delete: {len(deleted['failed'])}")

        if deleted["failed"]:
            print("\nFailed deletions:")
            for resource_type, name, error in deleted["failed"]:
                print(f"  - {resource_type}: {name} - {error}")


if __name__ == "__main__":
    main()
