@echo off
setlocal enabledelayedexpansion

REM Setup branch protection rules for GitHub repository
REM Run this after creating the repository on GitHub

set REPO=llmletsplay/fire-emblem-gba

echo Setting up branch protection for %REPO%...

REM Check if gh CLI is installed
where gh >nul 2>&1
if errorlevel 1 (
    echo Error: GitHub CLI ^(gh^) is not installed
    echo Install from: https://cli.github.com/
    exit /b 1
)

REM Protect main branch
echo Configuring main branch protection...
gh api ^
  repos/%REPO%/branches/main/protection ^
  --method PUT ^
  --field "required_status_checks={\"strict\":true,\"contexts\":[]}" ^
  --field "enforce_admins=false" ^
  --field "required_pull_request_reviews={\"required_approving_review_count\":2,\"dismiss_stale_reviews\":true}" ^
  --field "restrictions=null" ^
  --field "allow_force_pushes=false" ^
  --field "allow_deletions=false"

if errorlevel 1 (
    echo Failed to configure main branch protection
) else (
    echo Main branch protection configured
)

REM Protect develop branch
echo Configuring develop branch protection...
gh api ^
  repos/%REPO%/branches/develop/protection ^
  --method PUT ^
  --field "required_status_checks={\"strict\":true,\"contexts\":[]}" ^
  --field "enforce_admins=false" ^
  --field "required_pull_request_reviews={\"required_approving_review_count\":1,\"dismiss_stale_reviews\":false}" ^
  --field "restrictions=null" ^
  --field "allow_force_pushes=false" ^
  --field "allow_deletions=false"

if errorlevel 1 (
    echo Failed to configure develop branch protection
) else (
    echo Develop branch protection configured
)

echo.
echo Branch protection setup complete!
echo.
echo Branch rules configured:
echo   main: Requires 2 reviews, dismisses stale reviews
echo   develop: Requires 1 review
echo.
echo To modify these settings, visit:
echo https://github.com/%REPO%/settings/branches
pause