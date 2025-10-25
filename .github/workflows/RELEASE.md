# Release Workflow Documentation

## Overview

The release orchestrator (`release-orchestrator.yml`) automates the complete release process for the bud-stack platform. It coordinates individual service release workflows, waits for all builds to complete, then updates the Helm chart with the new version.

### Architecture

The release system uses an **orchestrator pattern**:

1. **Individual Release Workflows** (13 total):
   - Each service has its own `*-release-image.yml` workflow
   - Triggered via `workflow_dispatch` with `release_tag` parameter
   - Builds and pushes Docker images with version tag and `latest`
   - Can be run independently for single-service releases

2. **Release Orchestrator Workflow**:
   - Triggers all individual release workflows
   - Monitors their completion
   - Updates Helm chart only after all builds succeed
   - Commits changes back to repository

## Triggers

### 1. GitHub Release (Recommended)
When you create a new release in GitHub:
1. Go to the repository on GitHub
2. Click "Releases" → "Create a new release"
3. Create a new tag (e.g., `v0.25.0` or `0.25.0`)
4. Fill in release notes
5. Click "Publish release"

The orchestrator will automatically:
- Extract the version from the tag (strips `v` prefix if present)
- Trigger all 13 service release workflows
- Monitor their completion (max 30 minutes)
- Update the Helm chart when all builds succeed
- Commit the Helm chart changes

### 2. Manual Workflow Dispatch
For manual releases or testing:
1. Go to Actions → "Release Orchestrator: Build All Services and Update Helm"
2. Click "Run workflow"
3. Enter the version (e.g., `0.25.0` or `v0.25.0`)
4. Click "Run workflow"

### 3. Individual Service Release
To release a single service without a full release:
1. Go to Actions → Select the service workflow (e.g., "BudApp: Build and Push Docker Image")
2. Click "Run workflow"
3. Enter the version tag
4. Click "Run workflow"

**Note:** Individual releases don't update the Helm chart automatically.

## What Gets Built

The workflow builds and pushes Docker images for all services:

### Backend Services (Python/FastAPI)
- `budstudio/budapp:VERSION`
- `budstudio/budcluster:VERSION`
- `budstudio/budsim:VERSION`
- `budstudio/budmodel:VERSION`
- `budstudio/budmetrics:VERSION`
- `budstudio/budnotify:VERSION`
- `budstudio/askbud:VERSION`
- `budstudio/budeval:VERSION`
- `budstudio/buddoc:VERSION`
- `budstudio/budprompt:VERSION`

### Backend Services (Rust)
- `budstudio/budgateway:VERSION`

### Frontend Services (Next.js)
- `budstudio/budadmin:VERSION`
- `budstudio/budplayground:VERSION`

Each image is tagged with:
- The specific version (e.g., `0.25.0`)
- `latest` tag

## What Gets Updated

After all images are built successfully, the orchestrator updates:

### 1. `infra/helm/bud/Chart.yaml`
Uses `yq` to update appVersion:
```yaml
appVersion: "0.25.0"  # Updated to new version
```

### 2. `infra/helm/bud/values.yaml`
Uses `yq` to update all service image tags (works with any existing tag):
```yaml
microservices:
  budadmin:
    image: budstudio/budadmin:0.25.0  # Changed from previous version
  budapp:
    image: budstudio/budapp:0.25.0    # Changed from previous version
  # ... all other services
```

**Important:** The orchestrator uses `yq` (YAML processor) to update image tags, so it works regardless of the current tag value (`:nightly`, `:0.24.0`, etc.).

## Prerequisites

### Required GitHub Secrets

The following secrets must be configured in the repository:

1. **DOCKERHUB_USERNAME**: DockerHub username for pushing images
2. **DOCKERHUB_TOKEN**: DockerHub access token (not password!)
3. **PRIVATE_KEY**: RSA private key for budapp service
4. **PUBLIC_KEY**: RSA public key for budapp service

### Setting Up Secrets

1. Go to repository Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Add each required secret

## Workflow Steps

1. **Prepare** (Job: `prepare`)
   - Extracts and validates the version tag
   - Outputs clean version for subsequent jobs

2. **Trigger Builds** (Job: `trigger-builds`)
   - Triggers all 13 individual release workflows via GitHub CLI
   - Waits 30 seconds for workflows to start
   - Monitors workflow completion every 30 seconds
   - Fails if any workflow fails or timeout (30 minutes) occurs

3. **Update Helm** (Job: `update-helm`)
   - Only runs if all builds succeed
   - Uses `yq` to update Chart.yaml appVersion
   - Uses `yq` to update all service image tags in values.yaml
   - Shows git diff for review
   - Commits and pushes changes
   - Creates detailed summary report

## Version Format

The workflow accepts versions with or without the `v` prefix:
- `v0.25.0` → cleaned to `0.25.0`
- `0.25.0` → used as-is `0.25.0`

## After Release

Once the orchestrator completes:

1. **Verify DockerHub**: Check that all images are published with the correct tags
   - Visit: https://hub.docker.com/u/budstudio
   - Verify each service has the new version tag and `latest`

2. **Verify Helm Chart**: Check the commit that updated the Helm chart
   - The orchestrator commits changes with message: `chore: update helm chart to version X.X.X`
   - Pull the latest changes: `git pull origin main`

3. **Deploy**: Use the updated Helm chart to deploy
   ```bash
   # Pull latest changes first
   git pull origin main

   # Deploy with Helm
   helm upgrade bud infra/helm/bud/ --install --namespace bud-stack
   ```

## Monitoring the Release

1. Go to Actions tab in GitHub
2. Click on "Release Orchestrator: Build All Services and Update Helm"
3. Monitor the jobs:
   - **Prepare**: Should complete in seconds
   - **Trigger Builds**: Takes 15-30 minutes (monitors all 13 workflows)
     - Check logs to see each workflow's status
     - ✅ Green checkmarks mean workflow completed
     - ⏳ Yellow dots mean workflow is running
     - ❌ Red X means workflow failed
   - **Update Helm**: Only runs after all builds succeed
     - Shows the git diff of changes
     - Commits and pushes Helm chart updates
4. Check the summary at the bottom for complete overview
5. Optionally, monitor individual service workflows in the Actions tab

## Troubleshooting

### Build Failures
If a service fails to build:
1. Check the individual workflow logs in Actions tab
2. The orchestrator will fail the `trigger-builds` job and show which workflow failed
3. Fix the issue in the service's Dockerfile or code
4. Re-run the individual service workflow OR create a new release

**Quick fix for single service:**
```bash
# Trigger just the failed service workflow
Go to Actions → [Service Name]: Build and Push → Run workflow
Enter the same version tag
```

### Orchestrator Timeout
If the orchestrator times out (30 minutes):
1. Check which workflows are still running in Actions tab
2. Individual workflows might be stuck or queued
3. Cancel the orchestrator run
4. Check GitHub Actions runners availability
5. Re-run the release when runners are available

### Helm Update Failures
If the Helm chart update fails:
1. Check for merge conflicts in Chart.yaml or values.yaml
2. Ensure the repository isn't protected against bot commits
3. Verify GitHub token has write permissions
4. Check that `yq` is properly installed in the workflow

### Missing Images
If some images aren't pushed:
1. Check DockerHub credentials in secrets (DOCKERHUB_USERNAME, DOCKERHUB_TOKEN)
2. Verify the service name matches the values.yaml
3. Check individual workflow logs for authentication issues
4. Ensure DockerHub rate limits aren't exceeded

### Individual Workflow Not Triggered
If a service workflow doesn't trigger:
1. Check the workflow file exists: `.github/workflows/[service]-release-image.yml`
2. Verify workflow has `workflow_dispatch` with `release_tag` input
3. Check GitHub token permissions
4. Look for typos in the orchestrator's trigger list

## Best Practices

1. **Use Semantic Versioning**: Follow semver (MAJOR.MINOR.PATCH)
   - MAJOR: Breaking changes
   - MINOR: New features (backward compatible)
   - PATCH: Bug fixes

2. **Test Before Release**: Use the manual workflow dispatch to test releases
   ```
   Run workflow with version: 0.25.0-rc1
   ```

3. **Release Notes**: Always include comprehensive release notes
   - New features
   - Bug fixes
   - Breaking changes
   - Migration guide (if needed)

4. **Coordinate Releases**: Ensure all team members are aware
   - Notify before triggering release
   - Document any manual steps required
   - Update CHANGELOG.md

## Example Release Process

```bash
# 1. Prepare release
git checkout main
git pull origin main

# 2. Update CHANGELOG.md (optional but recommended)
# Add release notes for version 0.25.0

# 3. Create and push release via GitHub UI
# Go to: https://github.com/BudEcosystem/bud-stack/releases/new
# Tag: v0.25.0
# Release title: Release v0.25.0
# Description: [Your release notes]
# Click "Publish release"

# 4. Monitor orchestrator workflow
# Go to: https://github.com/BudEcosystem/bud-stack/actions
# Click on "Release Orchestrator: Build All Services and Update Helm"
# Watch the "Trigger Builds" job - it shows status of all 13 workflows
# Wait for all jobs to complete (15-30 minutes)

# 5. After orchestrator completes, pull the updated Helm chart
git pull origin main

# 6. Verify the Helm chart updates
git log --oneline -1  # Should show: "chore: update helm chart to version 0.25.0"
git diff HEAD~1 infra/helm/bud/Chart.yaml infra/helm/bud/values.yaml

# 7. Deploy to staging/production
helm upgrade bud infra/helm/bud/ --install --namespace bud-stack
```

## Individual Service Release

To release a single service without a full platform release:

```bash
# 1. Go to Actions → [Service]: Build and Push Docker Image
# 2. Click "Run workflow"
# 3. Enter version: 0.25.1-hotfix
# 4. Click "Run workflow"

# This will:
# - Build and push that service's Docker image
# - NOT update the Helm chart automatically
# - Useful for hotfixes or testing

# To deploy the individual service:
# Update values.yaml manually or use helm --set:
helm upgrade bud infra/helm/bud/ \
  --set microservices.budapp.image=budstudio/budapp:0.25.1-hotfix \
  --namespace bud-stack
```

## Rolling Back

If you need to rollback a release:

```bash
# Option 1: Revert the Helm chart commit
git revert <commit-hash>
git push

# Option 2: Deploy previous version
helm upgrade bud infra/helm/bud/ --set microservices.budapp.image=budstudio/budapp:0.24.0

# Option 3: Update values.yaml manually
# Change image tags back to previous version
# Commit and push
```

## CI/CD Integration

The orchestrator can be integrated with deployment pipelines:

```yaml
# Example: Auto-deploy after successful release
name: Deploy After Release

on:
  workflow_run:
    workflows: ["Release Orchestrator: Build All Services and Update Helm"]
    types:
      - completed

jobs:
  deploy-staging:
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Deploy to staging
        run: |
          # Your deployment commands
          helm upgrade bud infra/helm/bud/ --install --namespace staging
```

## Additional Notes

- **Build Time**: Complete release takes ~15-30 minutes depending on service sizes and runner availability
- **Parallel Builds**: All 13 service workflows run in parallel for maximum speed
- **Monitoring**: Orchestrator polls workflow status every 30 seconds
- **Timeout**: Fails if any workflow doesn't complete within 30 minutes
- **Idempotent**: Safe to re-run if it fails partway through
- **Latest Tag**: Every service gets both version tag (e.g., `0.25.0`) and `latest` tag
- **Git History**: Creates a single clean commit for Helm chart updates
- **YAML Safety**: Uses `yq` processor to ensure correct YAML updates
- **Flexibility**: Individual workflows can be triggered independently for hotfixes
- **Rollback Safe**: Previous Helm commits can be easily reverted if needed

## Service List

### Services with Release Workflows

All 13 services have individual release workflows:

**Backend (Python/FastAPI):**
- askbud (ask-bud service)
- budapp
- budcluster
- buddoc
- budeval
- budmetrics
- budmodel
- budnotify
- budprompt
- budsim

**Backend (Rust):**
- budgateway

**Frontend (Next.js):**
- budadmin
- budplayground

**Note:** budcustomer is referenced in values.yaml but doesn't exist as a service in the repository.
