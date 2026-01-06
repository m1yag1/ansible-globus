.. _authentication:

Authentication
==============

CLI
---

The simplest method. Install the Globus CLI and authenticate:

.. code-block:: bash

   pip install globus-cli
   globus login

Modules use these tokens automatically when no credentials are specified.

For multiple identities, use profiles:

.. code-block:: bash

   export GLOBUS_PROFILE=work
   globus login

   GLOBUS_PROFILE=work ansible-playbook playbook.yml

Tokens expire and require re-authentication. For unattended automation,
use client credentials.

Client Credentials
------------------

Register a client at `developers.globus.org <https://developers.globus.org>`_:

1. Click "Register your app with Globus"
2. Choose "Register a service account or application credential"
3. Select "Confidential Client"
4. Save the Client ID and generate a Client Secret

Grant scopes based on the resources you'll manage:

- Transfer: ``urn:globus:auth:scope:transfer.api.globus.org:all``
- Groups: ``urn:globus:auth:scope:groups.api.globus.org:all``
- Flows: ``urn:globus:auth:scope:flows.globus.org:manage_flows``
- Search: ``urn:globus:auth:scope:search.api.globus.org:all``

Pass credentials to modules:

.. code-block:: yaml

   - name: Create endpoint
     globus_endpoint:
       name: "Production Endpoint"
       client_id: "{{ lookup('env', 'GLOBUS_CLIENT_ID') }}"
       client_secret: "{{ lookup('env', 'GLOBUS_CLIENT_SECRET') }}"

Or use Ansible Vault:

.. code-block:: yaml

   # group_vars/all/vault.yml (encrypted)
   vault_globus_client_id: "your-client-id"
   vault_globus_client_secret: "your-client-secret"

   # playbook
   - name: Create endpoint
     globus_endpoint:
       name: "Production Endpoint"
       client_id: "{{ vault_globus_client_id }}"
       client_secret: "{{ vault_globus_client_secret }}"

GCS Module Authentication
-------------------------

The ``globus_gcs`` module manages Globus Connect Server installations. It requires
a client registered as a project administrator.

1. Register a confidential client as above
2. In `app.globus.org <https://app.globus.org>`_, select your project under
   "Administered Projects"
3. Navigate to "Administrators" and add your client UUID with "Project Administrator" role
4. Reference the client in your deployment key file on the server

See the `GCS documentation <https://docs.globus.org/globus-connect-server/v5/>`_
for detailed setup.

Environment Variables
---------------------

``GLOBUS_CLIENT_ID``
   Client ID for client credentials

``GLOBUS_CLIENT_SECRET``
   Client secret for client credentials

``GLOBUS_PROFILE``
   Profile name for CLI authentication

``GLOBUS_SDK_ENVIRONMENT``
   Set to ``sandbox`` or ``test`` for non-production environments

Troubleshooting
---------------

**Token expired**

Re-authenticate with the CLI:

.. code-block:: bash

   globus logout
   globus login

**Permission denied (403)**

- Verify your client has required scopes
- For GCS, ensure client is a project administrator
- Check you're using the correct identity/profile

**Invalid credentials**

- Verify client ID and secret
- Ensure the client hasn't been deleted
- Check environment variables: ``echo $GLOBUS_CLIENT_ID``
