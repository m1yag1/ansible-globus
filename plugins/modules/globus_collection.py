#!/usr/bin/python

DOCUMENTATION = r"""
---
module: globus_collection
short_description: Manage Globus Collections
description:
    - Create, update, or delete Globus Collections
    - Configure collection access and permissions
version_added: "1.0.0"
author:
    - Ansible Globus Module Contributors
options:
    name:
        description: Display name of the collection
        required: true
        type: str
    endpoint_id:
        description: ID of the endpoint hosting this collection
        required: true
        type: str
    collection_type:
        description: Type of collection
        required: false
        type: str
        choices: ['mapped', 'guest']
        default: 'mapped'
    path:
        description: Path on the endpoint for this collection
        required: true
        type: str
    description:
        description: Description of the collection
        required: false
        type: str
    organization:
        description: Organization name
        required: false
        type: str
    contact_email:
        description: Contact email for the collection
        required: false
        type: str
    public:
        description: Whether the collection should be public
        required: false
        type: bool
        default: false
    keywords:
        description: Keywords for the collection
        required: false
        type: list
        elements: str
    identity_id:
        description: Identity ID for guest collections
        required: false
        type: str
    user_credential_id:
        description: User credential ID for guest collections
        required: false
        type: str
    state:
        description: Desired state of the collection
        required: false
        type: str
        choices: ['present', 'absent']
        default: 'present'
extends_documentation_fragment:
    - globus_auth
"""

EXAMPLES = r"""
# Basic mapped collection
- name: Create a mapped collection
  globus_collection:
    name: "Research Data Collection"
    endpoint_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    collection_type: "mapped"
    path: "/data/research/"
    description: "Shared research data repository"
    organization: "University Research Lab"
    contact_email: "admin@university.edu"
    public: true
    keywords:
      - "research"
      - "data"
    state: present

# Genomics data collection with comprehensive metadata
- name: Create genomics data collection
  globus_collection:
    name: "Genomics Data"
    endpoint_id: "{{ gcs_endpoint.endpoint_id }}"
    path: "/data/genomics"
    collection_type: mapped
    description: "Genomics research data repository for sequencing projects"
    organization: "Biology Department"
    contact_email: "genomics-admin@university.edu"
    public: true
    keywords:
      - genomics
      - research
      - biology
      - sequencing
      - NGS
    state: present

# Private collaboration collection
- name: Create private collaboration collection
  globus_collection:
    name: "Multi-Inst Collaboration Data"
    endpoint_id: "{{ collab_endpoint_id }}"
    path: "/shared/collab"
    collection_type: mapped
    description: "Private data sharing for multi-institutional collaboration"
    organization: "Research Consortium"
    contact_email: "consortium-admin@universities.org"
    public: false
    keywords:
      - collaboration
      - multi-institutional
      - private
    state: present

# Guest collection for user sharing
- name: Create guest collection for user
  globus_collection:
    name: "Personal Data Share - {{ user_name }}"
    endpoint_id: "{{ personal_endpoint_id }}"
    collection_type: "guest"
    path: "/home/{{ user_name }}/shared/"
    identity_id: "{{ user_name }}@university.edu"
    description: "Personal data sharing collection for {{ user_name }}"
    public: false
    state: present

# Multiple collections for GCS deployment
- name: Create storage collections on GCS
  globus_collection:
    name: "{{ item.name }}"
    endpoint_id: "{{ gcs_endpoint.endpoint_id }}"
    path: "{{ item.path }}"
    collection_type: mapped
    description: "{{ item.description }}"
    organization: "Research Computing"
    public: "{{ item.public | default(false) }}"
    keywords: "{{ item.keywords | default([]) }}"
    state: present
  loop:
    - name: "Home Directories"
      path: "/home"
      description: "User home directories"
      public: false
      keywords: ["home", "users"]
    - name: "Shared Research"
      path: "/research/shared"
      description: "Shared research data repository"
      public: true
      keywords: ["research", "shared", "public"]
    - name: "Scratch Space"
      path: "/scratch"
      description: "High-performance scratch storage"
      public: false
      keywords: ["scratch", "temporary", "hpc"]

# Collection with client credentials authentication
- name: Create collection with service credentials
  globus_collection:
    name: "Production Data Repository"
    endpoint_id: "{{ production_endpoint_id }}"
    path: "/data/production"
    collection_type: mapped
    description: "Production data repository with automated management"
    organization: "Research Computing Services"
    contact_email: "data-services@university.edu"
    public: true
    auth_method: client_credentials
    client_id: "{{ vault_globus_client_id }}"
    client_secret: "{{ vault_globus_client_secret }}"
    keywords:
      - production
      - automated
      - research-data
    state: present

# Delete a collection
- name: Delete a collection
  globus_collection:
    name: "Old Collection"
    endpoint_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    path: "/old/path/"
    state: absent
"""

RETURN = r"""
collection_id:
    description: ID of the created/managed collection
    type: str
    returned: when state=present
name:
    description: Name of the collection
    type: str
    returned: always
changed:
    description: Whether the collection was changed
    type: bool
    returned: always
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.m1yag1.globus.plugins.module_utils.globus_api import (
    GlobusAPI,
)
from ansible_collections.m1yag1.globus.plugins.module_utils.globus_common import (
    globus_argument_spec,
)


def find_collection_by_name_and_endpoint(api, name, endpoint_id):
    """Find a collection by name and endpoint."""
    try:
        collections = api.get(
            "endpoint_manager/collections",
            params={"filter_endpoint_id": endpoint_id, "filter_display_name": name},
        )
        for collection in collections.get("DATA", []):
            if collection["display_name"] == name:
                return collection
        return None
    except Exception:
        return None


def create_mapped_collection(api, params):
    """Create a new mapped collection."""
    collection_data = {
        "DATA_TYPE": "collection",
        "collection_type": "mapped",
        "display_name": params["name"],
        "mapped_collection_base_path": params["path"],
        "description": params.get("description", ""),
        "organization": params.get("organization", ""),
        "contact_email": params.get("contact_email", ""),
        "public": params.get("public", False),
        "keywords": params.get("keywords", []),
    }

    # Remove empty values
    collection_data = {
        k: v for k, v in collection_data.items() if v or isinstance(v, bool)
    }

    result = api.post(f'endpoint/{params["endpoint_id"]}/collection', collection_data)
    return result


def create_guest_collection(api, params):
    """Create a new guest collection."""
    collection_data = {
        "DATA_TYPE": "collection",
        "collection_type": "guest",
        "display_name": params["name"],
        "guest_collection_base_path": params["path"],
        "description": params.get("description", ""),
        "public": params.get("public", False),
        "keywords": params.get("keywords", []),
    }

    # Add identity information for guest collections
    if params.get("identity_id"):
        collection_data["identity_id"] = params["identity_id"]
    if params.get("user_credential_id"):
        collection_data["user_credential_id"] = params["user_credential_id"]

    # Remove empty values
    collection_data = {
        k: v for k, v in collection_data.items() if v or isinstance(v, bool)
    }

    result = api.post(f'endpoint/{params["endpoint_id"]}/collection', collection_data)
    return result


def update_collection(api, collection_id, params):
    """Update an existing collection."""
    collection_data = {}

    if params.get("description") is not None:
        collection_data["description"] = params["description"]
    if params.get("organization") is not None:
        collection_data["organization"] = params["organization"]
    if params.get("contact_email") is not None:
        collection_data["contact_email"] = params["contact_email"]
    if params.get("public") is not None:
        collection_data["public"] = params["public"]
    if params.get("keywords") is not None:
        collection_data["keywords"] = params["keywords"]

    if collection_data:
        result = api.put(f"collection/{collection_id}", collection_data)
        return result
    return None


def delete_collection(api, collection_id):
    """Delete a collection."""
    api.delete(f"collection/{collection_id}")
    return True


def main():
    argument_spec = globus_argument_spec()
    argument_spec.update(
        name={"type": "str", "required": True},
        endpoint_id={"type": "str", "required": True},
        collection_type={
            "type": "str",
            "choices": ["mapped", "guest"],
            "default": "mapped",
        },
        path={"type": "str", "required": True},
        description={"type": "str"},
        organization={"type": "str"},
        contact_email={"type": "str"},
        public={"type": "bool", "default": False},
        keywords={"type": "list", "elements": "str"},
        identity_id={"type": "str"},
        user_credential_id={"type": "str"},
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    api = GlobusAPI(module, service="transfer")

    name = module.params["name"]
    endpoint_id = module.params["endpoint_id"]
    collection_type = module.params["collection_type"]
    state = module.params["state"]

    existing_collection = find_collection_by_name_and_endpoint(api, name, endpoint_id)

    if state == "present":
        if existing_collection:
            # Update existing collection
            changed = False
            collection_id = existing_collection["id"]

            # Update collection properties
            update_result = update_collection(api, collection_id, module.params)
            if update_result:
                changed = True

            module.exit_json(changed=changed, collection_id=collection_id, name=name)
        else:
            # Create new collection
            if module.check_mode:
                module.exit_json(changed=True, name=name)

            if collection_type == "mapped":
                collection = create_mapped_collection(api, module.params)
            elif collection_type == "guest":
                collection = create_guest_collection(api, module.params)
            else:
                module.fail_json(msg=f"Unsupported collection type: {collection_type}")

            collection_id = collection["id"]

            module.exit_json(changed=True, collection_id=collection_id, name=name)

    elif state == "absent":
        if existing_collection:
            if module.check_mode:
                module.exit_json(changed=True, name=name)

            delete_collection(api, existing_collection["id"])
            module.exit_json(changed=True, name=name)
        else:
            module.exit_json(changed=False, name=name)


if __name__ == "__main__":
    main()
