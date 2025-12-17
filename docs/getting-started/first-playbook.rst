.. _first_playbook:

First Playbook
==============

This example creates a Globus group. Groups are self-contained and easy to verify,
making them a good starting point.

Authenticate with the Globus CLI:

.. code-block:: bash

   pip install globus-cli
   globus login

Create ``create_group.yml``:

.. code-block:: yaml

   ---
   - name: Create a Globus group
     hosts: localhost
     gather_facts: false

     tasks:
       - name: Create research team group
         globus_group:
           name: "my-first-ansible-group"
           description: "Created with Ansible"
           visibility: private
           state: present
         register: group_result

       - name: Show result
         ansible.builtin.debug:
           var: group_result

Run it:

.. code-block:: bash

   ansible-playbook create_group.yml

Output:

.. code-block:: text

   TASK [Create research team group] ********************************************
   changed: [localhost]

   TASK [Show result] ***********************************************************
   ok: [localhost] => {
       "group_result": {
           "changed": true,
           "group_id": "abc12345-...",
           "name": "my-first-ansible-group"
       }
   }

Verify at `app.globus.org/groups <https://app.globus.org/groups>`_ or with:

.. code-block:: bash

   globus group list

Run the playbook again. This time you'll see ``ok`` instead of ``changed``—Ansible
detected the group exists and made no changes.

To delete the group, change ``state: present`` to ``state: absent`` and run again.

Next Steps
----------

- :ref:`Authentication options <authentication>` for production
- :doc:`Module reference </collections/index>` for all parameters
