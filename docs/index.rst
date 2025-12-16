.. _docsite_root_index:

Ansible Globus Documentation
============================

This collection provides Ansible modules for managing Globus resources:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Service
     - Resources
   * - `Globus Connect Server <https://docs.globus.org/globus-connect-server/>`_
     - Endpoints, nodes, storage gateways, collections
   * - `Globus Groups <https://docs.globus.org/api/groups/>`_
     - Memberships, roles, authentication policies
   * - `Globus Flows <https://docs.globus.org/api/flows/>`_
     - Flows
   * - `Globus Timers <https://docs.globus.org/api/timer/>`_
     - Timers
   * - `Globus Search <https://docs.globus.org/api/search/>`_
     - Indices
   * - `Globus Compute <https://docs.globus.org/compute/>`_
     - Endpoints, functions


Globus resources rarely exist in isolation. Sure, there may be simple use cases
where all you need is a couple of GCS endpoints and transfers between them—this
collection may not be necessary for those. But the author would argue that all
infrastructure for science should follow the same approach that science promotes:
it should be reviewable, reproducible, and recoverable.

Globus based research workflows often require many interconnected pieces: create a group, add
members with the correct roles, configure a timer that triggers a flow that
transfers data to a collection, indexes it for search, and kicks off a compute
function. Setting all of this up through web interfaces and bespoke scripts takes
time—and once it works, nobody wants to touch it again (until the next grad
student inherits it five years later).

With ansible-globus you define Globus infrastructure declaratively and check it
into version control. When something needs to change, update a line of code and
be confident that only what you expected was deployed. YAML is easy to read,
and updates are almost as easy as updating a form and running a single command.
This simplicity is not free; there are no silver bullets. A lot of work has to be
done up front, but the benefits of maintaining the infrastructure over time will
pay dividends.

.. important::

   This is an unofficial Spike Lee joint created by a software engineer at Globus to
   aid with development and testing. He hopes that it proves as useful for you as
   it has been for him. Feedback, contributions, and hate mail are welcome.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   getting-started/index

.. toctree::
   :maxdepth: 2
   :caption: Module Reference

   collections/m1yag1/globus/index

.. toctree::
   :maxdepth: 1
   :caption: Reference

   collections/environment_variables
