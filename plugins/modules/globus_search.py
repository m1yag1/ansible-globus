#!/usr/bin/python

DOCUMENTATION = r"""
---
module: globus_search
short_description: Manage Globus Search indexes
description:
    - Create, update, or delete Globus Search indexes
    - Free tier accounts are limited to 3 trial indexes (1 MB each, 30-day auto-deletion)
    - Contact support@globus.org for subscription upgrades
version_added: "0.4.0"
author:
    - Ansible Globus Module Contributors
options:
    name:
        description:
            - Display name of the search index
            - Used to find existing indexes (not a unique identifier)
        required: true
        type: str
    description:
        description:
            - Description of the search index
            - Will be updated if changed on an existing index
        required: false
        type: str
    state:
        description: Desired state of the search index
        required: false
        type: str
        choices: ['present', 'absent']
        default: 'present'
extends_documentation_fragment:
    - globus_auth
notes:
    - Trial indexes are limited to 1 MB and automatically deleted after 30 days
    - Free tier accounts can have up to 3 trial indexes
    - To upgrade an index or get more than 3 indexes, contact support@globus.org
    - Deleting an index is irreversible and removes all indexed data
"""

EXAMPLES = r"""
- name: Create a Globus Search index
  m1yag1.globus.globus_search:
    name: "research-publications"
    description: "Index for research publications metadata"
    client_id: "{{ globus_client_id }}"
    client_secret: "{{ globus_client_secret }}"
    state: present

- name: Update an existing search index description
  m1yag1.globus.globus_search:
    name: "research-publications"
    description: "Updated description for publications index"
    client_id: "{{ globus_client_id }}"
    client_secret: "{{ globus_client_secret }}"
    state: present

- name: Delete a search index
  m1yag1.globus.globus_search:
    name: "old-index"
    client_id: "{{ globus_client_id }}"
    client_secret: "{{ globus_client_secret }}"
    state: absent

- name: Create index with access token
  m1yag1.globus.globus_search:
    name: "my-search-index"
    description: "My search index"
    auth_method: access_token
    access_token: "{{ globus_access_token }}"
    state: present
"""

RETURN = r"""
index_id:
    description: UUID of the created/managed search index
    type: str
    returned: when state=present
    sample: "a1b2c3d4-5678-90ef-ghij-klmnopqrstuv"
name:
    description: Display name of the index
    type: str
    returned: always
    sample: "research-publications"
description:
    description: Description of the index
    type: str
    returned: when state=present
    sample: "Index for research publications metadata"
is_trial:
    description: Whether this is a trial index (limited to 1 MB, 30-day lifetime)
    type: bool
    returned: when state=present
    sample: true
trial_count:
    description: Number of trial indexes currently owned (out of 3 maximum)
    type: int
    returned: when creating a trial index
    sample: 2
changed:
    description: Whether the index was changed
    type: bool
    returned: always
    sample: true
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.m1yag1.globus.plugins.module_utils.globus_common import (
    globus_argument_spec,
)
from ansible_collections.m1yag1.globus.plugins.module_utils.globus_sdk_client import (
    GlobusSDKClient,
)


def find_index_by_name(api, name):
    """Find search index by display name (returns first match or None)."""
    try:
        for index in api.search_client.index_list():
            if index.get("display_name") == name:
                return index
        return None
    except Exception as e:
        api.handle_api_error(e, f"searching for index '{name}'")


def get_index_by_id(api, index_id):
    """Get search index by UUID (returns None if not found)."""
    try:
        response = api.search_client.get_index(index_id)
        return response.data if hasattr(response, "data") else response
    except Exception as e:
        if hasattr(e, "http_status") and e.http_status == 404:
            return None
        api.handle_api_error(e, f"retrieving index '{index_id}'")


def check_trial_limit(api):
    """Check trial index count (max 3)."""
    try:
        trial_count = 0
        for index in api.search_client.index_list():
            if index.get("is_trial", False):
                trial_count += 1

        return {"count": trial_count, "limit": 3}
    except Exception as e:
        api.handle_api_error(e, "checking trial index limit")


def create_index(api, params):
    """Create new search index."""
    trial_status = check_trial_limit(api)
    if trial_status["count"] >= trial_status["limit"]:
        api.fail_json(
            msg=f"Cannot create index: You have {trial_status['count']} trial indexes "
            f"(limit: {trial_status['limit']}). New indexes default to trial status. "
            "To upgrade an existing index or increase your limit, contact support@globus.org"
        )

    try:
        response = api.search_client.create_index(
            display_name=params["name"],
            description=params.get("description", ""),
        )
        return response.data if hasattr(response, "data") else response
    except Exception as e:
        api.handle_api_error(e, "creating search index")


def update_index(api, index_id, params, existing_index=None):
    """Update existing search index (idempotent, fails on metadata change)."""
    if not existing_index:
        existing_index = get_index_by_id(api, index_id)
        if not existing_index:
            api.fail_json(f"Index {index_id} not found")

    changed = False
    new_description = params.get("description")

    if new_description is not None:
        existing_desc = existing_index.get("description", "")
        if new_description != existing_desc:
            api.fail_json(
                msg=f"Cannot update index: Globus Search indexes do not support "
                f"metadata updates after creation. Index '{params['name']}' already exists "
                f"with description '{existing_desc}'. To change the description, you must "
                "delete and recreate the index."
            )

    return changed


def delete_index(api, index_id):
    """Delete search index (marks for deletion, trial indexes deleted quickly)."""
    try:
        api.search_client.delete_index(index_id)
        return True
    except Exception as e:
        # If index doesn't exist (404), treat as already deleted
        if hasattr(e, "http_status") and e.http_status == 404:
            return False  # No change needed, already gone
        # If index is already being deleted (409 - delete_pending status), treat as idempotent
        if hasattr(e, "http_status") and e.http_status == 409:
            # Check if it's the delete_pending conflict specifically
            error_msg = str(e)
            if "delete_pending" in error_msg.lower():
                return False  # No change needed, deletion already in progress
        # For other errors, use standard error handling
        api.handle_api_error(e, f"deleting index '{index_id}'")


def main():
    """Main module execution."""
    argument_spec = globus_argument_spec()
    argument_spec.update(
        name={"type": "str", "required": True},
        description={"type": "str", "required": False},
        state={
            "type": "str",
            "default": "present",
            "choices": ["present", "absent"],
        },
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    api = GlobusSDKClient(module, required_services=["search"])

    name = module.params["name"]
    state = module.params["state"]
    changed = False
    result = {"changed": changed, "name": name}

    if state == "present":
        # Find if index with this name already exists
        existing_index = find_index_by_name(api, name)

        if existing_index:
            # Index exists - check for updates
            if module.check_mode:
                # In check mode, just validate we could update
                changed = update_index(
                    api, existing_index["id"], module.params, existing_index
                )
                result.update(
                    {
                        "changed": changed,
                        "index_id": existing_index["id"],
                        "description": existing_index.get("description", ""),
                        "is_trial": existing_index.get("is_trial", True),
                    }
                )
            else:
                # Not in check mode - try to update
                changed = update_index(
                    api, existing_index["id"], module.params, existing_index
                )
                result.update(
                    {
                        "changed": changed,
                        "index_id": existing_index["id"],
                        "description": existing_index.get("description", ""),
                        "is_trial": existing_index.get("is_trial", True),
                    }
                )
        else:
            # Index doesn't exist - create it
            if module.check_mode:
                # In check mode, validate we could create (check trial limit)
                trial_status = check_trial_limit(api)
                if trial_status["count"] >= trial_status["limit"]:
                    module.fail_json(
                        msg=f"Cannot create index: You have {trial_status['count']} trial indexes "
                        f"(limit: {trial_status['limit']}). New indexes default to trial status. "
                        "To upgrade an existing index or increase your limit, contact support@globus.org"
                    )
                # Would create successfully
                changed = True
                result.update(
                    {
                        "changed": changed,
                        "index_id": None,  # Would be created
                        "description": module.params.get("description", ""),
                        "is_trial": True,
                    }
                )
            else:
                # Not in check mode - actually create
                new_index = create_index(api, module.params)
                changed = True

                # Get trial count to include in response
                trial_status = check_trial_limit(api)

                result.update(
                    {
                        "changed": changed,
                        "index_id": new_index["id"],
                        "description": new_index.get("description", ""),
                        "is_trial": new_index.get("is_trial", True),
                        "trial_count": trial_status["count"],
                    }
                )

    elif state == "absent":
        # Find if index with this name exists
        existing_index = find_index_by_name(api, name)

        if existing_index:
            # Index exists - delete it
            if module.check_mode:
                # In check mode, just report that we would delete
                changed = True
                result["changed"] = changed
            else:
                # Not in check mode - actually delete
                changed = delete_index(api, existing_index["id"])
                result["changed"] = changed
        else:
            # Index doesn't exist - already in desired state
            changed = False
            result["changed"] = changed

    module.exit_json(**result)


if __name__ == "__main__":
    main()
