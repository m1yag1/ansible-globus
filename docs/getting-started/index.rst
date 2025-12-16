.. _getting_started:

Getting Started
===============

Prerequisites
-------------

- Python 3.12+
- Ansible 2.16+
- A Globus account at `globus.org <https://www.globus.org>`_

Installation
------------

From Ansible Galaxy:

.. code-block:: bash

   ansible-galaxy collection install m1yag1.globus

From source:

.. code-block:: bash

   git clone https://github.com/m1yag1/ansible-globus.git
   cd ansible-globus
   ansible-galaxy collection build
   ansible-galaxy collection install m1yag1-globus-*.tar.gz

Verify the installation:

.. code-block:: bash

   ansible-galaxy collection list | grep globus

.. toctree::
   :maxdepth: 2
   :caption: In this section:

   concepts
   authentication
   first-playbook
