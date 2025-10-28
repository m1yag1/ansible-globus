#!/usr/bin/env bash
#
# Run integration tests locally with proper AWS/Globus credentials
#
# Usage:
#   ./scripts/run-integration-tests.sh
#
# Or with specific profile:
#   AWS_VAULT_PROFILE=globus-dev ./scripts/run-integration-tests.sh
#

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Rebuilding Collection ===${NC}"
echo "This ensures Ansible uses your current source code, not a cached version."

# Build and install the collection to ensure tests use current source
ansible-galaxy collection build --force --output-path /tmp/
COLLECTION_FILE=$(ls -t /tmp/community-globus-*.tar.gz | head -1)
echo -e "${GREEN}Built: $COLLECTION_FILE${NC}"

ansible-galaxy collection install "$COLLECTION_FILE" --force
echo -e "${GREEN}Installed collection from source${NC}\n"

# Clean up build artifact
rm "$COLLECTION_FILE"

echo -e "${GREEN}=== Running Integration Tests ===${NC}\n"

# Check if we're already in an aws-vault session
if [ -n "$AWS_VAULT" ]; then
    echo -e "${YELLOW}Already in aws-vault session: $AWS_VAULT${NC}"
    echo "Running tests directly..."

    # Need S3 bucket info
    if [ -z "$S3_TOKEN_BUCKET" ]; then
        echo -e "${RED}ERROR: S3_TOKEN_BUCKET not set${NC}"
        echo "Please set S3_TOKEN_BUCKET environment variable or see TESTING_GUIDE.md"
        exit 1
    fi

    # Run tests
    python -m pytest tests/integration/ -v
else
    # Not in aws-vault, need to exec into it
    PROFILE=${AWS_VAULT_PROFILE:-globus-dev}

    echo "Using AWS profile: $PROFILE"
    echo "Running tests with aws-vault exec..."

    # Check if profile exists
    if ! aws-vault list | grep -q "^$PROFILE"; then
        echo -e "${RED}ERROR: AWS profile '$PROFILE' not found${NC}"
        echo "Available profiles:"
        aws-vault list
        exit 1
    fi

    # Need S3 bucket info
    if [ -z "$S3_TOKEN_BUCKET" ]; then
        echo -e "${RED}ERROR: S3_TOKEN_BUCKET not set${NC}"
        echo ""
        echo "Set it before running:"
        echo "  export S3_TOKEN_BUCKET=your-bucket-name"
        echo "  export S3_TOKEN_KEY=globus/tokens.json"
        echo "  export S3_TOKEN_NAMESPACE=local"
        echo ""
        echo "Or use client credentials:"
        echo "  export GLOBUS_CLIENT_ID=your-client-id"
        echo "  export GLOBUS_CLIENT_SECRET=your-secret"
        echo ""
        exit 1
    fi

    # Run with aws-vault
    aws-vault exec "$PROFILE" -- python -m pytest tests/integration/ -v
fi
