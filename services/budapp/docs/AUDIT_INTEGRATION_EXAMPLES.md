# Audit Integration Examples

This document provides comprehensive examples of how to integrate audit logging across all services in the BudApp platform.

## Core Principles

1. **Explicit Control**: Each service decides what to audit based on business context
2. **Non-blocking**: Use background tasks for performance-critical operations
3. **Complete Context**: Log all relevant details for troubleshooting and compliance
4. **Error Handling**: Audit failures should never break the main operation

## Service Integration Examples

### 1. Model Operations

```python
from budapp.audit_ops import log_audit
from budapp.commons.constants import AuditActionEnum, AuditResourceTypeEnum
from fastapi import Request, BackgroundTasks

class ModelService(SessionMixin):

    async def register_model(
        self,
        model_data: Dict[str, Any],
        current_user_id: UUID,
        request: Optional[Request] = None
    ) -> ModelModel:
        """Register a new model with audit logging."""

        # Create the model
        model = await ModelDataManager(self.session).create_model(model_data)

        # Log the model registration
        log_audit(
            session=self.session,
            action=AuditActionEnum.CREATE,
            resource_type=AuditResourceTypeEnum.MODEL,
            resource_id=model.id,
            user_id=current_user_id,
            details={
                "model_name": model.name,
                "model_type": model.model_type,
                "provider": model.provider,
                "version": model.version,
                "source": model.source,
            },
            request=request,
            success=True,
        )

        return model

    async def delete_model(
        self,
        model_id: UUID,
        current_user_id: UUID,
        request: Optional[Request] = None
    ) -> None:
        """Delete a model with audit logging."""

        # Get model details before deletion
        model = await ModelDataManager(self.session).get_model(model_id)
        model_info = {
            "model_name": model.name,
            "provider": model.provider,
            "active_deployments": model.deployment_count,
        }

        # Perform deletion
        await ModelDataManager(self.session).delete_model(model_id)

        # Log the deletion
        log_audit(
            session=self.session,
            action=AuditActionEnum.DELETE,
            resource_type=AuditResourceTypeEnum.MODEL,
            resource_id=model_id,
            user_id=current_user_id,
            details=model_info,
            request=request,
            success=True,
        )
```

### 2. Endpoint Operations

```python
class EndpointService(SessionMixin):

    async def create_endpoint(
        self,
        endpoint_data: Dict[str, Any],
        current_user_id: UUID,
        request: Optional[Request] = None,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> EndpointModel:
        """Create an endpoint with background audit logging."""

        # Create the endpoint
        endpoint = await EndpointDataManager(self.session).create_endpoint(endpoint_data)

        # Log audit in background for performance
        if background_tasks:
            background_tasks.add_task(
                log_audit_async,
                session=self.session,
                action=AuditActionEnum.ENDPOINT_PUBLISHED,
                resource_type=AuditResourceTypeEnum.ENDPOINT,
                resource_id=endpoint.id,
                user_id=current_user_id,
                details={
                    "endpoint_name": endpoint.name,
                    "model_id": str(endpoint.model_id),
                    "cluster_id": str(endpoint.cluster_id),
                    "replicas": endpoint.replicas,
                },
                request=request,
            )
        else:
            # Fallback to synchronous logging
            log_audit(
                session=self.session,
                action=AuditActionEnum.ENDPOINT_PUBLISHED,
                resource_type=AuditResourceTypeEnum.ENDPOINT,
                resource_id=endpoint.id,
                user_id=current_user_id,
                details={
                    "endpoint_name": endpoint.name,
                    "model_id": str(endpoint.model_id),
                    "cluster_id": str(endpoint.cluster_id),
                    "replicas": endpoint.replicas,
                },
                request=request,
            )

        return endpoint

    async def unpublish_endpoint(
        self,
        endpoint_id: UUID,
        current_user_id: UUID,
        request: Optional[Request] = None
    ) -> EndpointModel:
        """Unpublish an endpoint with audit logging."""

        endpoint = await EndpointDataManager(self.session).get_endpoint(endpoint_id)

        # Capture state before unpublishing
        previous_state = {
            "status": endpoint.status,
            "replicas": endpoint.replicas,
        }

        # Unpublish the endpoint
        endpoint = await EndpointDataManager(self.session).update_endpoint(
            endpoint_id, {"status": EndpointStatusEnum.UNPUBLISHED}
        )

        # Log the unpublishing
        log_audit(
            session=self.session,
            action=AuditActionEnum.ENDPOINT_UNPUBLISHED,
            resource_type=AuditResourceTypeEnum.ENDPOINT,
            resource_id=endpoint_id,
            user_id=current_user_id,
            previous_state=previous_state,
            new_state={"status": endpoint.status, "replicas": 0},
            details={"reason": "User requested unpublish"},
            request=request,
        )

        return endpoint
```

### 3. Cluster Operations

```python
class ClusterService(SessionMixin):

    async def register_cluster(
        self,
        cluster_data: Dict[str, Any],
        current_user_id: UUID,
        request: Optional[Request] = None
    ) -> ClusterModel:
        """Register a new cluster with audit logging."""

        try:
            # Validate and create cluster
            cluster = await ClusterDataManager(self.session).create_cluster(cluster_data)

            # Log successful registration
            log_audit(
                session=self.session,
                action=AuditActionEnum.CREATE,
                resource_type=AuditResourceTypeEnum.CLUSTER,
                resource_id=cluster.id,
                user_id=current_user_id,
                details={
                    "cluster_name": cluster.name,
                    "provider": cluster.provider,
                    "region": cluster.region,
                    "node_count": cluster.node_count,
                    "hardware_type": cluster.hardware_type,
                },
                request=request,
                success=True,
            )

            return cluster

        except Exception as e:
            # Log failed registration attempt
            log_audit(
                session=self.session,
                action=AuditActionEnum.CREATE,
                resource_type=AuditResourceTypeEnum.CLUSTER,
                user_id=current_user_id,
                details={
                    "cluster_name": cluster_data.get("name"),
                    "error": str(e),
                },
                request=request,
                success=False,
            )
            raise
```

### 4. Credential Operations

```python
class CredentialService(SessionMixin):

    async def create_credential(
        self,
        credential_data: Dict[str, Any],
        current_user_id: UUID,
        request: Optional[Request] = None
    ) -> CredentialModel:
        """Create a credential with audit logging (sensitive data masked)."""

        # Create the credential
        credential = await CredentialDataManager(self.session).create_credential(credential_data)

        # Log credential creation (sensitive data will be automatically masked)
        log_audit(
            session=self.session,
            action=AuditActionEnum.CREATE,
            resource_type=AuditResourceTypeEnum.API_KEY,
            resource_id=credential.id,
            user_id=current_user_id,
            details={
                "credential_name": credential.name,
                "credential_type": credential.credential_type,
                "project_id": str(credential.project_id),
                # Don't include actual credential value - it will be masked anyway
            },
            request=request,
        )

        return credential

    async def rotate_credential(
        self,
        credential_id: UUID,
        current_user_id: UUID,
        request: Optional[Request] = None
    ) -> CredentialModel:
        """Rotate a credential with audit logging."""

        credential = await CredentialDataManager(self.session).get_credential(credential_id)

        # Rotate the credential
        new_credential = await CredentialDataManager(self.session).rotate_credential(credential_id)

        # Log the rotation
        log_audit(
            session=self.session,
            action=AuditActionEnum.UPDATE,
            resource_type=AuditResourceTypeEnum.API_KEY,
            resource_id=credential_id,
            user_id=current_user_id,
            details={
                "operation": "rotate",
                "credential_name": credential.name,
                "reason": "Scheduled rotation",
            },
            request=request,
        )

        return new_credential
```

### 5. User Operations

```python
class UserService(SessionMixin):

    async def update_user_role(
        self,
        user_id: UUID,
        new_role: str,
        current_user_id: UUID,
        request: Optional[Request] = None
    ) -> UserModel:
        """Update user role with audit logging."""

        user = await UserDataManager(self.session).get_user(user_id)
        previous_role = user.role

        # Update the role
        user = await UserDataManager(self.session).update_user(
            user_id, {"role": new_role}
        )

        # Log the role change
        log_audit(
            session=self.session,
            action=AuditActionEnum.ROLE_ASSIGNED,
            resource_type=AuditResourceTypeEnum.USER,
            resource_id=user_id,
            user_id=current_user_id,
            previous_state={"role": previous_role},
            new_state={"role": new_role},
            details={
                "target_user_email": user.email,
                "operation": "role_change",
            },
            request=request,
        )

        return user

    async def disable_user(
        self,
        user_id: UUID,
        reason: str,
        current_user_id: UUID,
        request: Optional[Request] = None
    ) -> UserModel:
        """Disable a user account with audit logging."""

        user = await UserDataManager(self.session).get_user(user_id)

        # Disable the user
        user = await UserDataManager(self.session).update_user(
            user_id, {"is_active": False}
        )

        # Log the account disabling
        log_audit(
            session=self.session,
            action=AuditActionEnum.UPDATE,
            resource_type=AuditResourceTypeEnum.USER,
            resource_id=user_id,
            user_id=current_user_id,
            details={
                "operation": "disable_account",
                "user_email": user.email,
                "reason": reason,
            },
            request=request,
        )

        return user
```

### 6. Billing Operations

```python
class BillingService(SessionMixin):

    async def create_subscription(
        self,
        subscription_data: Dict[str, Any],
        current_user_id: UUID,
        request: Optional[Request] = None
    ) -> SubscriptionModel:
        """Create a subscription with audit logging."""

        subscription = await BillingDataManager(self.session).create_subscription(subscription_data)

        # Log subscription creation
        log_audit(
            session=self.session,
            action=AuditActionEnum.CREATE,
            resource_type=AuditResourceTypeEnum.BILLING,
            resource_id=subscription.id,
            user_id=current_user_id,
            details={
                "subscription_type": subscription.type,
                "plan": subscription.plan,
                "billing_cycle": subscription.billing_cycle,
                "amount": subscription.amount,
            },
            request=request,
        )

        return subscription

    async def cancel_subscription(
        self,
        subscription_id: UUID,
        reason: str,
        current_user_id: UUID,
        request: Optional[Request] = None
    ) -> None:
        """Cancel a subscription with audit logging."""

        subscription = await BillingDataManager(self.session).get_subscription(subscription_id)

        # Cancel the subscription
        await BillingDataManager(self.session).cancel_subscription(subscription_id)

        # Log the cancellation
        log_audit(
            session=self.session,
            action=AuditActionEnum.DELETE,
            resource_type=AuditResourceTypeEnum.BILLING,
            resource_id=subscription_id,
            user_id=current_user_id,
            details={
                "subscription_type": subscription.type,
                "plan": subscription.plan,
                "cancellation_reason": reason,
                "remaining_credit": subscription.remaining_credit,
            },
            request=request,
        )
```

### 7. Workflow Operations

```python
class WorkflowService(SessionMixin):

    async def start_workflow(
        self,
        workflow_data: Dict[str, Any],
        current_user_id: UUID,
        request: Optional[Request] = None
    ) -> WorkflowModel:
        """Start a workflow with audit logging."""

        workflow = await WorkflowDataManager(self.session).create_workflow(workflow_data)

        # Start the workflow
        await WorkflowEngine.start(workflow.id)

        # Log workflow start
        log_audit(
            session=self.session,
            action=AuditActionEnum.WORKFLOW_STARTED,
            resource_type=AuditResourceTypeEnum.WORKFLOW,
            resource_id=workflow.id,
            user_id=current_user_id,
            details={
                "workflow_type": workflow.type,
                "workflow_name": workflow.name,
                "parameters": workflow.parameters,
            },
            request=request,
        )

        return workflow

    async def complete_workflow(
        self,
        workflow_id: UUID,
        result: Dict[str, Any],
        current_user_id: Optional[UUID] = None,
        request: Optional[Request] = None
    ) -> None:
        """Complete a workflow with audit logging."""

        workflow = await WorkflowDataManager(self.session).get_workflow(workflow_id)

        # Update workflow status
        await WorkflowDataManager(self.session).update_workflow(
            workflow_id, {"status": "COMPLETED", "result": result}
        )

        # Log workflow completion
        log_audit(
            session=self.session,
            action=AuditActionEnum.WORKFLOW_COMPLETED,
            resource_type=AuditResourceTypeEnum.WORKFLOW,
            resource_id=workflow_id,
            user_id=current_user_id or workflow.created_by,
            details={
                "workflow_type": workflow.type,
                "duration": str(datetime.now() - workflow.created_at),
                "result_summary": result.get("summary"),
            },
            request=request,
        )
```

### 8. Dataset Operations

```python
class DatasetService(SessionMixin):

    async def upload_dataset(
        self,
        dataset_data: Dict[str, Any],
        file_path: str,
        current_user_id: UUID,
        request: Optional[Request] = None
    ) -> DatasetModel:
        """Upload a dataset with audit logging."""

        # Create dataset record
        dataset = await DatasetDataManager(self.session).create_dataset(dataset_data)

        # Upload to storage
        await StorageService.upload(file_path, dataset.storage_path)

        # Log dataset upload
        log_audit(
            session=self.session,
            action=AuditActionEnum.CREATE,
            resource_type=AuditResourceTypeEnum.DATASET,
            resource_id=dataset.id,
            user_id=current_user_id,
            details={
                "dataset_name": dataset.name,
                "size_bytes": dataset.size,
                "format": dataset.format,
                "project_id": str(dataset.project_id),
            },
            request=request,
        )

        return dataset
```

## Route Integration Pattern

```python
from fastapi import Request, BackgroundTasks

@router.post("/resource")
async def create_resource(
    request: Request,
    resource_data: ResourceCreateRequest,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Create a resource with audit logging."""

    # Pass request and background_tasks to service
    resource = await ResourceService(session).create_resource(
        resource_data.dict(),
        current_user.id,
        request=request,
        background_tasks=background_tasks,
    )

    return ResourceResponse(resource=resource)

@router.put("/resource/{resource_id}")
async def update_resource(
    request: Request,
    resource_id: UUID,
    update_data: ResourceUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Update a resource with audit logging."""

    resource = await ResourceService(session).update_resource(
        resource_id,
        update_data.dict(),
        current_user.id,
        request=request,
    )

    return ResourceResponse(resource=resource)

@router.delete("/resource/{resource_id}")
async def delete_resource(
    request: Request,
    resource_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Delete a resource with audit logging."""

    await ResourceService(session).delete_resource(
        resource_id,
        current_user.id,
        request=request,
    )

    return SuccessResponse(message="Resource deleted successfully")
```

## Best Practices Checklist

✅ **DO:**
- Log at the service layer where you have full business context
- Include meaningful details that help with troubleshooting
- Use background tasks for high-frequency operations
- Capture both success and failure scenarios
- Pass Request object for IP and user agent tracking
- Log state changes with previous_state and new_state
- Handle exceptions gracefully without breaking operations

❌ **DON'T:**
- Log sensitive data like passwords or API keys (they're automatically masked)
- Create audit entries at the route layer (limited context)
- Block operations if audit logging fails
- Forget to include the user_id who performed the action
- Log excessive details that don't add value

## Migration Guide

If you're migrating from the old decorator-based approach:

1. Remove `@audit_event` decorators from routes
2. Remove audit middleware from application setup
3. Add `request: Request` parameter to route handlers
4. Pass `request` to service methods
5. Add `log_audit()` calls in service methods where needed
6. Use `BackgroundTasks` for performance-critical paths

## Testing Audit Integration

```python
def test_service_creates_audit_log():
    """Test that service methods create audit logs."""

    with patch("budapp.audit_ops.log_audit") as mock_log_audit:
        # Call service method
        service.create_resource(data, user_id, request)

        # Verify audit was logged
        mock_log_audit.assert_called_once()
        call_args = mock_log_audit.call_args[1]

        assert call_args["action"] == AuditActionEnum.CREATE
        assert call_args["resource_type"] == AuditResourceTypeEnum.RESOURCE
        assert call_args["user_id"] == user_id
        assert call_args["request"] == request
```

## Summary

The simple audit logging approach gives you:
- Full control over what gets logged
- Clear, explicit audit calls
- Better performance with background tasks
- Automatic sensitive data protection
- Comprehensive audit trails for compliance

Remember: Audit where you have context, log what matters, and never let audit failures break your application.
