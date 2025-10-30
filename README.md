# Ansible Globus Collection

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![Ansible](https://img.shields.io/badge/Ansible-2.16%2B-red.svg)](https://www.ansible.com/)

An Ansible collection for managing Globus infrastructure - endpoints, collections, groups, compute, and automation workflows.

> **Note:** I'm a software engineer at Globus.org who built this to manage Globus infrastructure for development and testing. While it's focused on my workflow, it may help others. Contributions welcome!

## Quick Start

```yaml
---
- hosts: localhost
  tasks:
    - name: Create Globus endpoint
      globus_endpoint:
        name: "My Research Data"
        organization: "University Lab"
        contact_email: "admin@example.edu"
        endpoint_type: server
        hostname: "data.example.edu"
        auth_method: client_credentials
        client_id: "{{ lookup('env', 'GLOBUS_CLIENT_ID') }}"
        client_secret: "{{ lookup('env', 'GLOBUS_CLIENT_SECRET') }}"
        state: present
```

## Features

- **Declarative Infrastructure** - Define Globus resources in YAML
- **Idempotent Operations** - Safe to run repeatedly
- **Multiple Auth Methods** - CLI, client credentials, or access tokens
- **Comprehensive Coverage** - Endpoints, collections, groups, compute, flows
- **Well-Tested** - Unit, integration, and E2E test suites
- **Modern Tooling** - Built with uv, ruff, and Python 3.12+

## Installation

```bash
# Clone the repository
git clone https://github.com/m1yag1/ansible-globus.git
cd ansible-globus

# Install with uv (recommended)
uv sync

# Build and install the collection
ansible-galaxy collection build
ansible-galaxy collection install *.tar.gz --force
```

## Authentication

### For Production (Client Credentials)

1. Register a confidential client at [developers.globus.org](https://developers.globus.org)
2. **Important for GCS:** Add your client as a project administrator ([guide](https://docs.globus.org/globus-connect-server/v5/automated-deployment/))
3. Use credentials in your playbooks:

```yaml
vars:
  globus_client_id: "{{ vault_globus_client_id }}"
  globus_client_secret: "{{ vault_globus_client_secret }}"

tasks:
  - name: Create endpoint
    globus_endpoint:
      name: "Production Endpoint"
      auth_method: client_credentials
      client_id: "{{ globus_client_id }}"
      client_secret: "{{ globus_client_secret }}"
      state: present
```

### For Development (CLI)

```bash
# Install and authenticate
pip install globus-cli
globus login

# Use in playbooks
- name: Create endpoint
  globus_endpoint:
    name: "Dev Endpoint"
    auth_method: cli
    state: present
```

## Available Modules

### `globus_endpoint`
Manage Globus Transfer endpoints for data movement.

```yaml
- name: Create GCS endpoint
  globus_endpoint:
    name: "Research Data Server"
    organization: "University Research Computing"
    endpoint_type: server
    hostname: "data.university.edu"
    public: true
    state: present
```

### `globus_collection`
Manage data collections on endpoints.

```yaml
- name: Create mapped collection
  globus_collection:
    name: "Genomics Data"
    endpoint_id: "{{ endpoint_id }}"
    path: "/data/genomics"
    collection_type: mapped
    public: true
    state: present
```

### `globus_group`
Manage user groups for access control.

```yaml
- name: Create research group
  globus_group:
    name: "genomics-team"
    description: "Genomics researchers"
    members:
      - "researcher@example.edu"
    admins:
      - "pi@example.edu"
    state: present
```

### `globus_compute`
Manage compute endpoints for distributed function execution.

```yaml
- name: Create compute endpoint
  globus_compute:
    name: "hpc-cluster"
    executor_type: HighThroughputExecutor
    max_workers: 16
    provider:
      type: SlurmProvider
      partition: compute
    state: present
```

### `globus_flow`
Manage automation workflows.

```yaml
- name: Create data processing flow
  globus_flow:
    title: "Analysis Pipeline"
    definition_file: flows/analysis.json
    visible_to: ["public"]
    runnable_by: ["{{ group_id }}"]
    state: present
```

## Examples

See the [`docs/examples/`](docs/examples/) directory for complete playbooks:

- **[complete_gcs_deployment.yml](docs/examples/complete_gcs_deployment.yml)** - Full GCS server setup
- **[multi_site_research.yml](docs/examples/multi_site_research.yml)** - Multi-institutional collaboration

## Testing

```bash
# Install dependencies
uv sync

# Run unit tests
uv run pytest tests/unit/

# Run all tests with tox
uv run tox

# Run linting
uv run tox -e lint
```

For integration and E2E tests, see [CONTRIBUTING.md](CONTRIBUTING.md#testing).

## Troubleshooting

### Authentication Errors

```bash
# CLI auth: Re-authenticate
globus logout && globus login

# Client credentials: Verify environment
echo $GLOBUS_CLIENT_ID
echo $GLOBUS_CLIENT_SECRET
```

### Permission Denied (403)

For GCS endpoints, ensure your client application is added as a **project administrator**:
1. Go to [app.globus.org](https://app.globus.org)
2. Select your project
3. Navigate to "Administrators" → "Add Administrator"
4. Add your client UUID
5. Grant "Project Administrator" role

See [Globus documentation](https://docs.globus.org/globus-connect-server/v5/automated-deployment/) for details.

### Module Not Found

```bash
# Verify collection is installed
ansible-galaxy collection list | grep globus

# Reinstall if needed
ansible-galaxy collection install *.tar.gz --force
```

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development setup with `uv` and `tox`
- Code standards and testing requirements
- Contribution workflow and guidelines

Quick contributor setup:

```bash
git clone https://github.com/m1yag1/ansible-globus.git
cd ansible-globus
uv sync
uv run pre-commit install
uv run tox
```

## Publishing to Ansible Galaxy

This collection can be published to [Ansible Galaxy](https://galaxy.ansible.com) for distribution.

### Prerequisites

Install git-cliff (one time):
```bash
# macOS:
brew install git-cliff

# Linux/Other:
# See: https://github.com/orhun/git-cliff/releases
```

### Release Process

This project uses [conventional commits](https://www.conventionalcommits.org/) for automated version bumping and changelog generation.

**Step 1: Prepare Release**

```bash
# Auto-detect version from commits (feat → minor, fix → patch)
tox -e prepare-release

# Or manually specify version
tox -e prepare-release -- 0.2.0
tox -e prepare-release -- --minor
tox -e prepare-release -- --patch
```

This will:
- Analyze conventional commits since last tag
- Suggest version bump (or use your override)
- Generate CHANGELOG.md with git-cliff
- Update galaxy.yml version
- Stage files for review

**Step 2: Review & Edit (Optional)**

Review the generated changes and edit if needed:
```bash
# Edit CHANGELOG.md to add context, reword entries, etc.
vim CHANGELOG.md

# Verify version is correct
grep "^version:" galaxy.yml
```

**Step 3: Complete Release**

```bash
tox -e release
```

This will:
- Validate changes are ready
- Run `tox -e galaxy-test` to verify build
- Commit changes
- Create git tag
- Push to GitHub (triggers automated Galaxy publish)

**GitHub Actions will automatically publish to Ansible Galaxy when the tag is pushed.**

### Manual Testing

```bash
# Test build locally
tox -e galaxy-test

# Build without installing
tox -e galaxy-build
```

## Requirements

- **Python**: 3.12+
- **Ansible**: 2.16+ (ansible-core)
- **Globus SDK**: 3.0+
- **Authentication**: Globus account with appropriate permissions

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Resources

- [Globus Documentation](https://docs.globus.org)
- [Ansible Documentation](https://docs.ansible.com)
- [Issue Tracker](https://github.com/m1yag1/ansible-globus/issues)

---

*Making research data management simple, automated, and reliable.*
