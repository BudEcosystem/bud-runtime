# Migration Guide: budworkflow → budpipeline

**Effective Date**: TBD
**Breaking Change**: Yes
**API Version**: v1.0+

## Overview

The `budworkflow` service has been renamed to `budpipeline` to better reflect its purpose as a pipeline orchestration service. This is a breaking change that requires updates to external consumers.

## What Changed

### Service Name
- **Old**: `budworkflow`
- **New**: `budpipeline`

### API Endpoints
All `/budworkflow` endpoints have been moved to `/budpipeline`:

- **Old**: `POST /api/v1/budworkflow/validate`
- **New**: `POST /api/v1/budpipeline/validate`

Full list of affected endpoints:
- `/api/v1/budpipeline/validate`
- `/api/v1/budpipeline` (list, create)
- `/api/v1/budpipeline/{id}` (get, update, delete)
- `/api/v1/budpipeline/{id}/executions`
- `/api/v1/budpipeline/{id}/schedules`
- `/api/v1/budpipeline/{id}/webhooks`
- `/api/v1/budpipeline/{id}/event-triggers`

### Pub/Sub Topics
- **Old**: `budworkflowEvents`
- **New**: `budpipelineEvents`

### Dapr Service Name
- **Old**: Dapr app-id `budworkflow`
- **New**: Dapr app-id `budpipeline`

### Environment Variables
- **Old**: `BUD_WORKFLOW_APP_ID`
- **New**: `BUD_PIPELINE_APP_ID`

### Frontend Routes
The frontend has implemented 308 permanent redirects:
- `/workflows` → `/pipelines` (redirects automatically)
- `/workflows/new` → `/pipelines/new`
- `/workflows/:id` → `/pipelines/:id`

## Migration Steps

### For API Consumers

1. **Update API endpoint URLs**:
   ```diff
   - POST https://api.bud.studio/api/v1/budworkflow/validate
   + POST https://api.bud.studio/api/v1/budpipeline/validate
   ```

2. **Update all endpoint paths** from `/budworkflow` to `/budpipeline`

3. **Test your integration** in a staging environment before production

### For Pub/Sub Subscribers

1. **Update topic subscriptions**:
   ```diff
   - topic: budworkflowEvents
   + topic: budpipelineEvents
   ```

2. **Update event handlers** to listen on the new topic

### For Dapr Service Invocation

1. **Update service invocation calls**:
   ```diff
   - dapr invoke --app-id budworkflow --method /health
   + dapr invoke --app-id budpipeline --method /health
   ```

2. **Update application code** that uses Dapr service-to-service invocation

### For Helm/Kubernetes Deployments

1. **Update values.yaml**:
   ```diff
   microservices:
   -  budworkflow:
   +  budpipeline:
        enabled: true
   -    image: budstudio/budworkflow:0.4.8
   +    image: budstudio/budpipeline:0.4.8
   -    daprid: budworkflow
   +    daprid: budpipeline
   -    pubsubTopic: budworkflowEvents
   +    pubsubTopic: budpipelineEvents
   ```

2. **Update template references** in your charts

## Backward Compatibility

### What Still Works
- **Frontend redirects**: Old `/workflows` URLs automatically redirect to `/pipelines` with 308 status
- **Terminology**: The term "workflow" is still used in some UI contexts for familiarity

### What Doesn't Work
- **API endpoints**: The old `/api/v1/budworkflow/*` endpoints are **removed**
- **Pub/Sub topics**: The `budworkflowEvents` topic is **no longer published to**
- **Dapr app-id**: The old `budworkflow` app-id is **not available**

## Timeline

- **Announcement**: 7 days before deployment
- **Deployment**: TBD
- **Old endpoints removed**: Immediately (no deprecation period)

## Support

If you encounter issues during migration:
1. Check this guide for the correct new endpoints
2. Verify your configuration matches the new naming
3. Contact the platform team for assistance

## FAQ

**Q: Why was this renamed?**
A: To better reflect the service's purpose as a pipeline orchestration platform and align with industry terminology.

**Q: Will my old API calls still work?**
A: No, you must update your API calls to use the new `/budpipeline` endpoints.

**Q: Are there any changes to the API request/response format?**
A: No, only the endpoint paths have changed. Request and response schemas remain identical.

**Q: Do I need to migrate my existing workflows/pipelines?**
A: No, existing pipeline definitions are compatible. Only the API endpoints have changed.

**Q: What about the Dapr state store?**
A: The state store keys have been updated. Old state is abandoned (per requirements).

## Checklist for External Consumers

- [ ] Update API endpoint URLs in application code
- [ ] Update environment variables
- [ ] Update Dapr service invocation references
- [ ] Update pub/sub topic subscriptions
- [ ] Update Helm charts / Kubernetes manifests
- [ ] Update CI/CD pipelines
- [ ] Update documentation
- [ ] Test in staging environment
- [ ] Deploy to production
- [ ] Monitor for errors after deployment
