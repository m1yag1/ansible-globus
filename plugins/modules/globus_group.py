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
        description: List of group members
        required: false
        type: list
        elements: str
    admins:
        description: List of group administrators
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

from ansible_collections.community.globus.plugins.module_utils.globus_common import (
    globus_argument_spec,
)
from ansible_collections.community.globus.plugins.module_utils.globus_sdk_client import (
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


def manage_members(api, group_id, members, role="member"):
    """Manage group members or admins."""
    if not members:
        return False

    changed = False
    current_members = api.get(f"groups/{group_id}/members")
    current_member_ids = {m["identity_id"] for m in current_members.get("data", [])}

    # Add new members
    for member in members:
        # Resolve identity
        identity = api.get("identities", params={"usernames": member})
        if identity.get("data"):
            identity_id = identity["data"][0]["id"]
            if identity_id not in current_member_ids:
                api.post(
                    f"groups/{group_id}/members",
                    {"identity_id": identity_id, "role": role},
                )
                changed = True

    return changed


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
            if manage_members(api, existing_group["id"], module.params.get("members")):
                changed = True

            # Manage admins
            if manage_members(
                api, existing_group["id"], module.params.get("admins"), "admin"
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
            manage_members(api, group_id, module.params.get("members"))
            manage_members(api, group_id, module.params.get("admins"), "admin")

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
