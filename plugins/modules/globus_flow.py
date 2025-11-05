#!/usr/bin/python

DOCUMENTATION = r"""
---
module: globus_flow
short_description: Manage Globus Flows
description:
    - Create, update, or delete Globus Flows
    - Deploy and manage workflow automation
version_added: "1.0.0"
author:
    - Ansible Globus Module Contributors
options:
    title:
        description: Title of the flow
        required: true
        type: str
    definition:
        description: Flow definition (JSON or dict)
        required: false
        type: raw
    definition_file:
        description: Path to file containing flow definition
        required: false
        type: path
    subtitle:
        description: Subtitle of the flow
        required: false
        type: str
    description:
        description: Description of the flow
        required: false
        type: str
    keywords:
        description: Keywords for the flow
        required: false
        type: list
        elements: str
    visible_to:
        description: Visibility settings for the flow
        required: false
        type: list
        elements: str
    runnable_by:
        description: Who can run this flow
        required: false
        type: list
        elements: str
    administered_by:
        description: Who can administer this flow
        required: false
        type: list
        elements: str
    input_schema:
        description: Input schema for the flow
        required: false
        type: dict
    flow_id:
        description: ID of existing flow (for updates)
        required: false
        type: str
    state:
        description: Desired state of the flow
        required: false
        type: str
        choices: ['present', 'absent']
        default: 'present'
extends_documentation_fragment:
    - globus_auth
"""

EXAMPLES = r"""
- name: Create a Globus Flow
  globus_flow:
    title: "Data Processing Pipeline"
    subtitle: "Automated data processing and analysis"
    description: "Processes raw data through multiple stages"
    definition:
      Comment: "Simple data processing flow"
      StartAt: "ProcessData"
      States:
        ProcessData:
          Type: "Action"
          ActionUrl: "https://compute.api.globus.org"
          Parameters:
            endpoint: "my-compute-endpoint"
            function: "process_data"
          End: true
    keywords:
      - "data-processing"
      - "automation"
    visible_to:
      - "public"
    runnable_by:
      - "all_authenticated_users"
    state: present

- name: Create flow from file
  globus_flow:
    title: "File Transfer Flow"
    definition_file: "/path/to/flow_definition.json"
    state: present

- name: Delete a flow
  globus_flow:
    title: "Old Flow"
    state: absent
"""

RETURN = r"""
flow_id:
    description: ID of the created/managed flow
    type: str
    returned: when state=present
title:
    description: Title of the flow
    type: str
    returned: always
flow_scope:
    description: Globus Auth scope for this flow (used for timers and external triggering)
    type: str
    returned: when state=present
changed:
    description: Whether the flow was changed
    type: bool
    returned: always
"""

import json
import os

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.m1yag1.globus.plugins.module_utils.globus_common import (
    globus_argument_spec,
)
from ansible_collections.m1yag1.globus.plugins.module_utils.globus_sdk_client import (
    GlobusSDKClient,
)


def find_flow_by_title(api, title):
    """Find a flow by title using SDK."""
    try:
        response = api.flows_client.list_flows()
        for flow in response.data.get("flows", []):
            if flow.get("title") == title:
                # Get full flow details
                flow_id = flow["id"]
                full_flow = api.flows_client.get_flow(flow_id)
                return full_flow.data
        return None
    except Exception as e:
        api.handle_api_error(e, f"searching for flow '{title}'")


def load_flow_definition(module, definition, definition_file):
    """Load flow definition from parameter or file."""
    if definition_file:
        if not os.path.exists(definition_file):
            module.fail_json(msg=f"Flow definition file not found: {definition_file}")

        try:
            with open(definition_file) as f:
                content = f.read()
                return json.loads(content)
        except Exception as e:
            module.fail_json(msg=f"Failed to load flow definition from file: {e}")

    elif definition:
        if isinstance(definition, str):
            try:
                return json.loads(definition)
            except Exception as e:
                module.fail_json(msg=f"Failed to parse flow definition JSON: {e}")
        elif isinstance(definition, dict):
            return definition
        else:
            module.fail_json(msg="Flow definition must be a JSON string or dictionary")

    else:
        module.fail_json(
            msg="Either 'definition' or 'definition_file' must be provided"
        )


def create_flow(api, params):
    """Create a new flow using SDK."""
    try:
        # Prepare SDK method arguments
        create_kwargs = {
            "title": params["title"],
            "definition": params["definition"],
            # input_schema is required by the API - use empty object if not provided or None
            "input_schema": params.get("input_schema") or {},
        }

        # Add optional fields with correct SDK parameter names
        if params.get("subtitle") is not None:
            create_kwargs["subtitle"] = params["subtitle"]
        if params.get("description") is not None:
            create_kwargs["description"] = params["description"]
        if params.get("keywords") is not None:
            create_kwargs["keywords"] = params["keywords"]
        if params.get("visible_to") is not None:
            create_kwargs["flow_viewers"] = params["visible_to"]
        if params.get("runnable_by") is not None:
            create_kwargs["flow_starters"] = params["runnable_by"]
        if params.get("administered_by") is not None:
            create_kwargs["flow_administrators"] = params["administered_by"]

        response = api.flows_client.create_flow(**create_kwargs)
        return response.data
    except Exception as e:
        # Enhanced error reporting for debugging
        import json

        error_msg = f"Failed to create flow: {e}"
        if hasattr(e, "text"):
            error_msg += f"\nAPI Response: {e.text}"
        if hasattr(e, "http_status"):
            error_msg += f"\nHTTP Status: {e.http_status}"
        error_msg += (
            f"\nParameters sent: {json.dumps(create_kwargs, indent=2, default=str)}"
        )
        api.fail_json(msg=error_msg)


def update_flow(api, flow_id, params):
    """Update an existing flow using SDK."""
    try:
        flow_data = {}

        # Map module parameter names to API field names for updatable fields
        field_mapping = {
            "title": "title",
            "subtitle": "subtitle",
            "description": "description",
            "keywords": "keywords",
            "visible_to": "flow_viewers",
            "runnable_by": "flow_starters",
            "administered_by": "flow_administrators",
        }

        for module_field, api_field in field_mapping.items():
            if params.get(module_field) is not None:
                flow_data[api_field] = params[module_field]

        # Definition updates require special handling
        if params.get("definition") is not None:
            flow_data["definition"] = params["definition"]

        if params.get("input_schema") is not None:
            flow_data["input_schema"] = params["input_schema"]

        if flow_data:
            response = api.flows_client.update_flow(flow_id, data=flow_data)
            return response.data
        return None
    except Exception as e:
        api.handle_api_error(e, f"updating flow {flow_id}")


def delete_flow(api, flow_id):
    """Delete a flow using SDK."""
    try:
        api.flows_client.delete_flow(flow_id)
        return True
    except Exception as e:
        api.handle_api_error(e, f"deleting flow {flow_id}")


def deploy_flow(api, flow_id):
    """Deploy a flow to make it available for execution using SDK."""
    # Note: Flow deployment happens automatically when flow is created
    # There's no separate deploy API call in the FlowsClient SDK
    # Flows are created in a runnable state by default
    return True


def main():
    argument_spec = globus_argument_spec()
    argument_spec.update(
        title={"type": "str", "required": True},
        definition={"type": "raw"},
        definition_file={"type": "path"},
        subtitle={"type": "str"},
        description={"type": "str"},
        keywords={"type": "list", "elements": "str"},
        visible_to={"type": "list", "elements": "str"},
        runnable_by={"type": "list", "elements": "str"},
        administered_by={"type": "list", "elements": "str"},
        input_schema={"type": "dict"},
        flow_id={"type": "str"},
        deploy={"type": "bool", "default": True},
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        mutually_exclusive=[("definition", "definition_file")],
    )

    api = GlobusSDKClient(module, required_services=["flows"])

    title = module.params["title"]
    state = module.params["state"]
    flow_id = module.params.get("flow_id")

    # Load flow definition if provided
    definition = None
    if module.params.get("definition") or module.params.get("definition_file"):
        definition = load_flow_definition(
            module,
            module.params.get("definition"),
            module.params.get("definition_file"),
        )

    # For state=present, we need a definition or flow_id for updates
    if state == "present" and not flow_id and not definition:
        module.fail_json(
            msg="For creating/updating flows, one of 'definition', 'definition_file', or 'flow_id' is required"
        )

    # Find existing flow
    if flow_id:
        try:
            response = api.flows_client.get_flow(flow_id)
            existing_flow = response.data
        except Exception:
            existing_flow = None
    else:
        existing_flow = find_flow_by_title(api, title)

    if state == "present":
        params_with_definition = module.params.copy()
        if definition:
            params_with_definition["definition"] = definition

        if existing_flow:
            # Update existing flow
            changed = False
            flow_id = existing_flow["id"]

            # Update flow properties
            update_result = update_flow(api, flow_id, params_with_definition)
            if update_result:
                changed = True

            # Deploy flow if requested
            if module.params.get("deploy", True):
                deploy_flow(api, flow_id)
                changed = True

            # Generate flow scope for timer/external use
            flow_scope = (
                existing_flow.get("globus_auth_scope")
                or f"https://auth.globus.org/scopes/{flow_id}/flow_{flow_id}_user"
            )

            module.exit_json(
                changed=changed, flow_id=flow_id, title=title, flow_scope=flow_scope
            )
        else:
            # Create new flow
            if module.check_mode:
                module.exit_json(changed=True, title=title)

            if not definition:
                module.fail_json(msg="Flow definition required for creating new flows")

            flow = create_flow(api, params_with_definition)
            flow_id = flow["id"]

            # Deploy flow if requested
            if module.params.get("deploy", True):
                deploy_flow(api, flow_id)

            # Generate flow scope for timer/external use
            flow_scope = (
                flow.get("globus_auth_scope")
                or f"https://auth.globus.org/scopes/{flow_id}/flow_{flow_id}_user"
            )

            module.exit_json(
                changed=True, flow_id=flow_id, title=title, flow_scope=flow_scope
            )

    elif state == "absent":
        if existing_flow:
            if module.check_mode:
                module.exit_json(changed=True, title=title)

            delete_flow(api, existing_flow["id"])
            module.exit_json(changed=True, title=title)
        else:
            module.exit_json(changed=False, title=title)


if __name__ == "__main__":
    main()
