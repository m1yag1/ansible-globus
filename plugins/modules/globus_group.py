#!/usr/bin/python

DOCUMENTATION = r"""
---
module: globus_group
short_description: Manage Globus Groups
description:
    - Create, update, or delete Globus Groups
    - Manage group membership and permissions
version_added: "1.0.0"
author:
    - Ansible Globus Module Contributors
options:
    name:
        description: Name of the group
        required: true
        type: str
    description:
        description: Description of the group
        required: false
        type: str
    visibility:
        description: Group visibility setting
        required: false
        type: str
        choices: ['public', 'private']
        default: 'private'
    members:
        description:
            - List of group members.
            - Accepts usernames (e.g., user@globusid.org), identity URNs, or UUIDs.
        required: false
        type: list
        elements: str
    admins:
        description:
            - List of group administrators.
            - Accepts usernames (e.g., user@globusid.org), identity URNs, or UUIDs.
        required: false
        type: list
        elements: str
    state:
        description: Desired state of the group
        required: false
        type: str
        choices: ['present', 'absent']
        default: 'present'
extends_documentation_fragment:
    - globus_auth
"""

EXAMPLES = r"""
- name: Create a Globus group
  globus_group:
    name: "research-team"
    description: "Research team collaboration group"
    visibility: "private"
    members:
      - "user1@example.org"
      - "user2@example.org"
    admins:
      - "admin@example.org"
    state: present

- name: Delete a Globus group
  globus_group:
    name: "old-group"
    state: absent
"""

RETURN = r"""
group_id:
    description: ID of the created/managed group
    type: str
    returned: when state=present
name:
    description: Name of the group
    type: str
    returned: always
changed:
    description: Whether the group was changed
    type: bool
    returned: always
"""

from ansible.module_utils.basic import AnsibleModule
from globus_sdk import BatchMembershipActions

from ansible_collections.m1yag1.globus.plugins.module_utils.globus_common import (
    globus_argument_spec,
)
from ansible_collections.m1yag1.globus.plugins.module_utils.globus_sdk_client import (
    GlobusSDKClient,
)


def find_group_by_name(api, name):
    """Find a group by name using SDK."""
    try:
        # Use SDK's get_my_groups() method which works across environments
        response = api.groups_client.get_my_groups()
        for group in response.data:
            if group["name"] == name:
                # Fetch full group details for comparison
                group_id = group["id"]
                full_group = api.groups_client.get_group(group_id)
                return full_group.data
        return None
    except Exception as e:
        api.handle_api_error(e, f"searching for group '{name}'")


def create_group(api, params):
    """Create a new group using SDK."""
    try:
        group_data = {
            "name": params["name"],
            "description": params.get("description", ""),
            "visibility": params.get("visibility", "private"),
        }
        response = api.groups_client.create_group(data=group_data)
        return response.data
    except Exception as e:
        api.handle_api_error(e, "creating group")


def update_group(api, group_id, params, existing_group=None):
    """Update an existing group using SDK."""
    try:
        update_data = {}

        # Only update if values have actually changed
        if existing_group:
            # Check description - only update if explicitly provided and different
            if params.get("description") is not None:
                # Normalize for comparison (API might return None or empty string)
                existing_desc = existing_group.get("description") or ""
                new_desc = params.get("description") or ""
                if new_desc != existing_desc:
                    update_data["description"] = params["description"]

            # Check visibility - only update if explicitly provided and different
            if params.get("visibility") is not None:
                # Normalize for comparison
                existing_vis = existing_group.get("visibility") or "private"
                new_vis = params.get("visibility") or "private"
                if new_vis != existing_vis:
                    update_data["visibility"] = params["visibility"]
        else:
            # If we don't have existing group data, update everything provided
            if params.get("description") is not None:
                update_data["description"] = params["description"]
            if params.get("visibility") is not None:
                update_data["visibility"] = params["visibility"]

        if update_data:
            response = api.groups_client.update_group(group_id, data=update_data)
            return response.data
        return None
    except Exception as e:
        api.handle_api_error(e, f"updating group {group_id}")


def manage_members(module, api, group_id, members, role="member"):
    """Manage group members or admins using SDK (declarative).

    Ensures the group membership matches the specified list exactly.
    Members not in the list will be removed, and members in the list
    will be added.

    :param module: AnsibleModule instance for errors
    :param api: GlobusSDKClient instance
    :param group_id: The group ID to manage
    :param members: List of usernames. If None, no changes are made.
    :param role: Role for the members ("member" or "admin")
    :return: True if membership was changed, False otherwise
    """
    if members is None:
        return False

    # Get the current service client ID to exclude from removal
    # (the service client that created/manages the group can't be removed)
    current_client_id = module.params.get("client_id")

    try:
        # Get current group membership
        group_with_members = api.groups_client.get_group(
            group_id, include="memberships"
        )
        memberships = group_with_members.data.get("memberships", [])

        # Filter current members by role, excluding the current service client
        current_members_with_role = {
            m["identity_id"]
            for m in memberships
            if m.get("role") == role and m.get("identity_id") != current_client_id
        }

        # Handle empty members list - remove all members with this role
        if not members:
            if not current_members_with_role:
                return False
            batch = BatchMembershipActions()
            batch.remove_members(list(current_members_with_role))
            api.groups_client.batch_membership_action(group_id, batch)
            return True

        # Use shared utility to resolve usernames to identity IDs
        # This handles usernames, UUIDs, and URNs consistently
        resolved_ids = api.resolve_principals(members, output_format="id")
        desired_identity_ids = set(resolved_ids)

        # Find members to add and remove
        to_add = desired_identity_ids - current_members_with_role
        to_remove = current_members_with_role - desired_identity_ids

        if not to_add and not to_remove:
            return False

        # Use BatchMembershipActions to add/remove members
        batch = BatchMembershipActions()
        if to_add:
            batch.add_members(list(to_add), role=role)
        if to_remove:
            batch.remove_members(list(to_remove))

        api.groups_client.batch_membership_action(group_id, batch)
        return True

    except Exception as e:
        api.handle_api_error(e, f"managing members for group {group_id}")


def delete_group(api, group_id):
    """Delete a group using SDK."""
    try:
        api.groups_client.delete_group(group_id)
        return True
    except Exception as e:
        api.handle_api_error(e, f"deleting group {group_id}")


def main():
    argument_spec = globus_argument_spec()
    argument_spec.update(
        name={"type": "str", "required": True},
        description={"type": "str"},
        visibility={
            "type": "str",
            "choices": ["public", "private"],
            "default": "private",
        },
        members={"type": "list", "elements": "str"},
        admins={"type": "list", "elements": "str"},
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    api = GlobusSDKClient(module, required_services=["groups"])

    name = module.params["name"]
    state = module.params["state"]

    existing_group = find_group_by_name(api, name)

    if state == "present":
        if existing_group:
            # Update existing group
            changed = False

            # Update group properties
            update_result = update_group(
                api, existing_group["id"], module.params, existing_group
            )
            if update_result:
                changed = True

            # Manage members
            if manage_members(
                module, api, existing_group["id"], module.params.get("members")
            ):
                changed = True

            # Manage admins
            if manage_members(
                module, api, existing_group["id"], module.params.get("admins"), "admin"
            ):
                changed = True

            module.exit_json(changed=changed, group_id=existing_group["id"], name=name)
        else:
            # Create new group
            if module.check_mode:
                module.exit_json(changed=True, name=name)

            group = create_group(api, module.params)
            group_id = group["id"]

            # Add members
            manage_members(module, api, group_id, module.params.get("members"))
            manage_members(module, api, group_id, module.params.get("admins"), "admin")

            module.exit_json(changed=True, group_id=group_id, name=name)

    elif state == "absent":
        if existing_group:
            if module.check_mode:
                module.exit_json(changed=True, name=name)

            delete_group(api, existing_group["id"])
            module.exit_json(changed=True, name=name)
        else:
            module.exit_json(changed=False, name=name)


if __name__ == "__main__":
    main()
