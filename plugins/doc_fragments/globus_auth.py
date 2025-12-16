#!/usr/bin/python

"""Documentation fragment for Globus authentication options."""


class ModuleDocFragment:
    """Documentation fragment for Globus authentication options."""

    DOCUMENTATION = r"""
options:
    auth_method:
        description:
            - Authentication method to use.
            - If not specified, auto-detects based on available credentials.
            - When C(client_id) and C(client_secret) are provided, uses C(client_credentials).
            - Otherwise falls back to C(cli) (reads tokens from globus-cli storage).
        required: false
        type: str
        choices: ['client_credentials', 'cli']
    client_id:
        description:
            - Globus Auth client ID for client_credentials authentication.
            - Can also be set via the C(GLOBUS_CLIENT_ID) environment variable.
        required: false
        type: str
    client_secret:
        description:
            - Globus Auth client secret for client_credentials authentication.
            - Can also be set via the C(GLOBUS_CLIENT_SECRET) environment variable.
        required: false
        type: str
notes:
    - Authentication is required for all Globus API operations.
    - For C(client_credentials) auth, register a confidential client at U(https://developers.globus.org).
    - For C(cli) auth, run C(globus login) first to cache tokens.
    - The C(cli) method reads tokens from C(~/.globus/cli/storage.db).
    - For C(cli) auth with multiple profiles, set C(GLOBUS_PROFILE) environment variable.
    - Set C(GLOBUS_SDK_ENVIRONMENT) to C(sandbox) or C(test) for non-production environments.
seealso:
    - name: Globus Auth Documentation
      description: Official Globus authentication documentation
      link: https://docs.globus.org/api/auth/
    - name: Globus CLI
      description: Command-line interface for Globus
      link: https://docs.globus.org/cli/
"""
