# OAuth Client Creation Implementation

## Overview

The `globus_auth` module now supports creating and managing OAuth clients (service accounts, desktop apps, etc.) in addition to projects and policies. This implementation follows **Option 5** for credential output, providing credentials in multiple formats with clear warnings about one-time secret retrieval.

## What's Been Implemented

### 1. Module Enhancements (`plugins/modules/globus_auth.py`)

#### New Resource Type: `client`
Added support for `resource_type: client` alongside existing `project` and `policy` types.

#### Supported Client Types
The module can create all 6 types of OAuth clients:

1. **`confidential_client`** - Server-side applications, service accounts
   - Receives client_id + client_secret
   - Used for backend services, automation

2. **`public_installed_client`** - Native applications, desktop apps
   - Receives client_id only (no secret)
   - Used for thick clients that can't securely store secrets

3. **`client_identity`** - Service accounts for automation
   - Receives client_id + client_secret
   - Used for CI/CD pipelines, automated workflows

4. **`resource_server`** - OAuth resource servers
   - Receives client_id + client_secret
   - Used for APIs that need to validate tokens

5. **`globus_connect_server`** - Globus Connect Server endpoints
   - Receives client_id + client_secret
   - Used for GCS v5 deployments

6. **`hybrid_confidential_client_resource_server`** - Combined functionality
   - Receives client_id + client_secret
   - Used for services that act as both client and resource server

#### New Parameters
```yaml
# Required for client creation
resource_type: client
name: "My Client"
project_id: "project-uuid"
client_type: confidential_client  # or any of the 6 types above

# Optional parameters
redirect_uris:
  - "https://myapp.example.com/callback"
visibility: private  # or public
terms_and_conditions: "https://myapp.example.com/terms"
privacy_policy: "https://myapp.example.com/privacy"
required_idp: "idp-uuid"
preselect_idp: "idp-uuid"
credential_output_file: "/path/to/save/credentials.json"
```

### 2. Option 5 Credential Output

When a client with secrets is created, the module returns credentials in **multiple formats**:

#### Return Values
```yaml
client_id: "abc123-def456-..."
client_secret: "secret_xyz..."  # Only for confidential client types

client_credentials:
  client_id: "abc123-def456-..."
  client_secret: "secret_xyz..."

  # Ansible environment variable format
  ansible_env: |
    GLOBUS_CLIENT_ID=abc123-def456-...
    GLOBUS_CLIENT_SECRET=secret_xyz...

  # Shell export command format
  shell_export: |
    export GLOBUS_CLIENT_ID=abc123-def456-...
    export GLOBUS_CLIENT_SECRET=secret_xyz...

  # File path (if credential_output_file was specified)
  json_file: "/path/to/credentials.json"

warning: "IMPORTANT: The client_secret can only be retrieved once..."
```

#### Credential File Format
When `credential_output_file` is specified, credentials are saved as JSON:
```json
{
  "client_id": "abc123-def456-...",
  "client_secret": "secret_xyz...",
  "name": "My Service Account",
  "project_id": "project-uuid",
  "client_type": "confidential_client",
  "created_at": "2025-10-24T16:00:00Z"
}
```

### 3. Integration Tests

Added comprehensive tests in `tests/integration/test_integration.py`:

- `test_auth_project_management()` - Project CRUD operations
- `test_auth_client_confidential()` - Service account creation
- `test_auth_client_public_installed()` - Thick client creation
- `test_auth_client_identity()` - CI/CD client creation
- `test_auth_client_with_file_output()` - Credential file saving

### 4. Token Setup Updates

Updated `scripts/setup_oauth_tokens.py` to include `AuthScopes.manage_projects` scope required for managing OAuth clients.

## Usage Examples

### Example 1: Create Service Account
```yaml
- name: Create service account for automation
  m1yag1.globus.globus_auth:
    resource_type: client
    name: "Automation Service Account"
    project_id: "{{ project_id }}"
    client_type: confidential_client
    redirect_uris:
      - "https://myapp.example.com/callback"
    visibility: private
    state: present
  register: service_account
  no_log: true  # Important: hide secrets from logs

- name: Save credentials to environment file
  copy:
    content: "{{ service_account.client_credentials.shell_export }}"
    dest: ~/.globus_service_account.env
    mode: '0600'
```

### Example 2: Create Desktop Application
```yaml
- name: Create public desktop application client
  m1yag1.globus.globus_auth:
    resource_type: client
    name: "My Desktop App"
    project_id: "{{ project_id }}"
    client_type: public_installed_client
    redirect_uris:
      - "https://auth.globus.org/v2/web/auth-code"
    visibility: public
    state: present
  register: desktop_app
```

### Example 3: Create Client with File Output
```yaml
- name: Create service account with credential file
  m1yag1.globus.globus_auth:
    resource_type: client
    name: "CI/CD Pipeline"
    project_id: "{{ project_id }}"
    client_type: client_identity
    credential_output_file: /secure/path/ci-credentials.json
    state: present
  register: ci_client
```

## Testing the Implementation

### Prerequisites

1. **Regenerate OAuth tokens** with auth management scope:
   ```bash
   # Set your OAuth client ID (from https://developers.globus.org)
   export GLOBUS_CLIENT_ID="your-native-app-client-id"
   export S3_TOKEN_BUCKET="your-token-bucket"

   # Run token setup (will open browser for authentication)
   python scripts/setup_oauth_tokens.py
   ```

2. **Verify auth scope** is included in your tokens:
   - The token must have `https://auth.globus.org/scopes/<uuid>/manage_projects` scope
   - This is now included automatically when running `setup_oauth_tokens.py`

### Run Integration Tests

```bash
# Test project management
pytest tests/integration/test_integration.py::test_auth_project_management -v

# Test confidential client (service account)
pytest tests/integration/test_integration.py::test_auth_client_confidential -v

# Test public installed client (thick client)
pytest tests/integration/test_integration.py::test_auth_client_public_installed -v

# Test client identity
pytest tests/integration/test_integration.py::test_auth_client_identity -v

# Test credential file output
pytest tests/integration/test_integration.py::test_auth_client_with_file_output -v

# Run all auth tests
pytest tests/integration/test_integration.py -k auth -v
```

### Manual Testing

Run the example playbook:
```bash
ansible-playbook examples/auth_client_test.yml
```

This will:
1. Create a test project
2. Create multiple client types (confidential, public, client_identity)
3. Display credentials in all formats
4. Save credentials to file
5. Clean up all resources

## Security Considerations

### ⚠️ Important: Secret Management

1. **One-time Retrieval**
   - Client secrets can **only be retrieved once** at creation time
   - If lost, you must delete the client and create a new one
   - Always save secrets immediately in a secure location

2. **Use `no_log: true`**
   ```yaml
   - name: Create service account
     m1yag1.globus.globus_auth:
       # ...
     register: result
     no_log: true  # Prevents secrets from appearing in logs
   ```

3. **Secure File Permissions**
   ```yaml
   - name: Save credentials with restricted permissions
     copy:
       content: "{{ credentials }}"
       dest: /secure/path/creds.json
       mode: '0600'  # Owner read/write only
   ```

4. **Ansible Vault**
   ```bash
   # Encrypt credential files
   ansible-vault encrypt /secure/path/creds.json
   ```

5. **Environment Variables**
   - Store credentials in environment variables or secrets management systems
   - Never commit credentials to version control

## Implementation Details

### Client Creation Flow

1. **Validate Parameters** - Check required fields (project_id, client_type)
2. **Create Client** - Call `AuthClient.create_client()` with client metadata
3. **Generate Credentials** - Call `AuthClient.create_client_credential()` for confidential types
4. **Format Output** - Generate multiple credential formats (Option 5)
5. **Save to File** - Optionally save JSON credentials to specified path
6. **Return with Warning** - Include warning about one-time secret retrieval

### API Methods Used

```python
# Find existing clients in project
api.auth_client.get_project_clients(project_id)

# Create new client
api.auth_client.create_client(data={
    "project": project_id,
    "name": name,
    "client_type": client_type,
    "redirect_uris": [...],
    "public_client": False,
    # ...
})

# Generate client secret
api.auth_client.create_client_credential(client_id)

# Update client
api.auth_client.update_client(client_id, data={...})

# Delete client
api.auth_client.delete_client(client_id)
```

## Next Steps

1. **Regenerate OAuth Tokens** - Add `manage_projects` scope
2. **Test Integration** - Run integration tests to verify functionality
3. **Document Use Cases** - Add examples for specific workflows
4. **Policy Support** - Add tests for authentication policies
5. **Resource Server Example** - Add example for creating API resource servers

## Reference Documentation

- [Globus Auth API - Client Resource](https://docs.globus.org/api/auth/reference/#client_resource)
- [Globus SDK - AuthClient](https://globus-sdk-python.readthedocs.io/en/stable/clients/auth/)
- [OAuth Client Types](https://docs.globus.org/api/auth/developer-guide/#registering-an-application)
