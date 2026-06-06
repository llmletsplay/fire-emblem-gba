#!/bin/bash

# Setup branch protection rules for GitHub repository
# Run this after creating the repository on GitHub

REPO="llmletsplay/fire-emblem-gba"

echo "Setting up branch protection for $REPO..."

# Protect main branch
echo "Configuring main branch protection..."
gh api \
  repos/$REPO/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":[]}' \
  --field enforce_admins=false \
  --field required_pull_request_reviews='{"required_approving_review_count":2,"dismiss_stale_reviews":true}' \
  --field restrictions=null \
  --field allow_force_pushes=false \
  --field allow_deletions=false

# Protect development branch
echo "Configuring development branch protection..."
gh api \
  repos/$REPO/branches/development/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":[]}' \
  --field enforce_admins=false \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":false}' \
  --field restrictions=null \
  --field allow_force_pushes=false \
  --field allow_deletions=false

echo "Branch protection setup complete!"
echo ""
echo "Branch rules configured:"
echo "  main: Requires 2 reviews, dismisses stale reviews"
echo "  development: Requires 1 review"
echo ""
echo "To modify these settings, visit:"
echo "https://github.com/$REPO/settings/branches"