#!/usr/bin/env bash
#
# Run integration tests locally with S3 token storage
#
# Usage:
#   ./scripts/test-integration-local.sh
#   ./scripts/test-integration-local.sh -k test_group  # Run specific test
#

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Rebuilding Collection ===${NC}"
echo "This ensures Ansible uses your current source code, not a cached version."

# Build and install the collection to ensure tests use current source
ansible-galaxy collection build --force --output-path /tmp/
COLLECTION_FILE=$(ls -t /tmp/m1yag1-globus-*.tar.gz | head -1)
echo -e "${GREEN}Built: $COLLECTION_FILE${NC}"

ansible-galaxy collection install "$COLLECTION_FILE" --force
echo -e "${GREEN}Installed collection from source${NC}\n"

# Clean up build artifact
rm "$COLLECTION_FILE"

# Unset AWS_VAULT to allow nested aws-vault exec (if already in a session)
unset AWS_VAULT

echo -e "${YELLOW}=== Running Integration Tests ===${NC}\n"

# Run tests with aws-vault and proper environment
aws-vault exec globus-dev -- env \
  S3_TOKEN_BUCKET=m1yag1-ansible-globus-globus-tokens-ci \
  S3_TOKEN_KEY=globus/ci-tokens.json \
  S3_TOKEN_NAMESPACE=ci \
  AWS_REGION=us-east-1 \
  GLOBUS_SDK_ENVIRONMENT=test \
  python -m pytest tests/integration/ -v "$@"
