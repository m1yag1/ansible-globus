.. _concepts:

Key Concepts
============

Module Types
------------

Modules in this collection fall into two categories based on where they execute.

**API modules** communicate with Globus services over HTTPS. They run on your
control machine (typically ``localhost``) and require Globus credentials.

.. code-block:: yaml

   - hosts: localhost
     tasks:
       - name: Create a group
         globus_group:
           name: "research-team"
           state: present

API modules include:

- ``globus_endpoint`` - Transfer endpoints
- ``globus_collection`` - Collections on endpoints
- ``globus_group`` - Groups and membership
- ``globus_flows`` - Automation flows
- ``globus_timer`` - Scheduled transfers
- ``globus_search`` - Search indexes
- ``globus_compute`` - Compute endpoints
- ``globus_auth`` - Auth projects and clients

**The globus_gcs module** is different. It runs commands on a remote Globus Connect
Server host via SSH, executing the ``globus-connect-server`` CLI directly on that
machine.

.. code-block:: yaml

   - hosts: gcs.example.edu
     tasks:
       - name: Configure storage gateway
         globus_gcs:
           resource_type: storage_gateway
           display_name: "POSIX Storage"
           connector: posix

.. warning::

   Don't run ``globus_gcs`` on localhost unless that's your GCS server.
   Don't run API modules on remote hosts—they need credentials available locally.

Authentication
--------------

Modules authenticate using either CLI tokens or client credentials.

**CLI tokens** work for development. Install the Globus CLI and log in:

.. code-block:: bash

   pip install globus-cli
   globus login

Modules automatically use these tokens when no credentials are specified.

**Client credentials** work for automation. Register an application at
`developers.globus.org <https://developers.globus.org>`_, then pass the
credentials to modules:

.. code-block:: yaml

   - name: Create endpoint
     globus_endpoint:
       name: "Production Endpoint"
       client_id: "{{ lookup('env', 'GLOBUS_CLIENT_ID') }}"
       client_secret: "{{ lookup('env', 'GLOBUS_CLIENT_SECRET') }}"

See the :ref:`authentication guide <authentication>` for setup details.
