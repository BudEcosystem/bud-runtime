#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""BudUseCases proxy routes - bridges budadmin frontend to budusecases service via Dapr."""

import re
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.commons import logging
from budapp.commons.constants import (
    BudServeWorkflowStepEventName,
    UserStatusEnum,
    WorkflowStatusEnum,
    WorkflowTypeEnum,
)
from budapp.commons.dependencies import get_current_active_user, get_current_user, get_session
from budapp.commons.exceptions import ClientException
from budapp.commons.schemas import ErrorResponse
from budapp.user_ops.schemas import User
from budapp.workflow_ops.crud import WorkflowDataManager
from budapp.workflow_ops.schemas import WorkflowUtilCreate
from budapp.workflow_ops.services import WorkflowService, WorkflowStepService

from .budusecases_service import BudUseCasesService


logger = logging.get_logger(__name__)

budusecases_router = APIRouter(prefix="/budusecases", tags=["budusecases"])

# HTTPBearer that does not auto-error so we can fall back to token-in-URL
_security_optional = HTTPBearer(auto_error=False)

# Headers that must NOT be forwarded when proxying upstream
_HOP_BY_HOP_HEADERS = frozenset(
    {
        "host",
        "authorization",
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-length",
        "content-encoding",
    }
)

# Regex to find the opening <head> tag in HTML for <base> tag injection
_HEAD_TAG_RE = re.compile(rb"(<head[^>]*>)", re.IGNORECASE)


async def _get_current_active_user_or_token(
    request: Request,
    token: Annotated[HTTPAuthorizationCredentials | None, Depends(_security_optional)] = None,
    session: Session = Depends(get_session),
) -> User:
    """Authenticate via Bearer header OR via ``?token=`` query parameter.

    iframes cannot send Authorization headers, so the frontend passes
    the JWT as a query parameter (``?token=<jwt>``).  This dependency
    first checks for a standard Bearer token and, if absent, falls back
    to the query parameter.  It reuses the existing ``get_current_user``
    pipeline which validates the token against Keycloak.
    """
    # 1. Try standard Bearer header
    if token is not None:
        user = await get_current_user(token=token, session=session)
        if user.status != UserStatusEnum.ACTIVE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
        return user

    # 2. Fall back to ?token= query parameter (iframe support)
    query_token = request.query_params.get("token")
    if query_token:
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=query_token)
        user = await get_current_user(token=credentials, session=session)
        if user.status != UserStatusEnum.ACTIVE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required (Bearer header or ?token= query parameter)",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _optional_user_or_token(
    request: Request,
    token: Annotated[HTTPAuthorizationCredentials | None, Depends(_security_optional)] = None,
    session: Session = Depends(get_session),
) -> Optional[User]:
    """Same as ``_get_current_active_user_or_token`` but returns ``None``
    instead of raising 401 when no credentials are present.

    Used by the UI proxy so that the initial HTML page (which carries
    ``?token=``) is authenticated while follow-up sub-resource requests
    (CSS, JS, images, fonts) from the iframe can pass through without
    auth — the deployment UUID is not guessable and the assets contain
    no sensitive data.
    """
    try:
        return await _get_current_active_user_or_token(request, token, session)
    except HTTPException:
        return None


def _rewrite_webpack_public_path(js_bytes: bytes, base_href: str) -> bytes:
    """Rewrite webpack's ``__webpack_require__.p`` (public path) in bundled JS.

    .. deprecated::
        This function is no longer used when subdomain-per-deployment routing
        is active (USECASE_DOMAIN is set).  Kept as fallback for path-based proxy.
    """
    prefix = base_href.rstrip("/") + "/"
    result, count = re.subn(
        rb'((?:^|[^a-zA-Z0-9_$])([a-zA-Z_$])\.p=)"/"',
        rb'\1"' + prefix.encode() + rb'"',
        js_bytes,
        count=1,
    )
    return result if count > 0 else js_bytes


def _inject_base_tag(html_bytes: bytes, base_href: str) -> bytes:
    """Inject a ``<base>`` tag and rewrite root-absolute asset URLs.

    .. deprecated::
        This function is no longer used when subdomain-per-deployment routing
        is active (USECASE_DOMAIN is set).  Kept as fallback for path-based proxy.
    """
    prefix = base_href.rstrip("/")
    result = re.sub(
        rb"""((?:src|href)\s*=\s*)(["'])/(?!/)""",
        rb"\1\2" + prefix.encode() + rb"/",
        html_bytes,
    )

    prefix_bytes = base_href.encode()
    spa_proxy = (
        b"<script>"
        b"(function(){"
        b'var B="' + prefix_bytes + b'",'
        b"P=B.slice(0,-1);"
        b"window.routerBase=B;"
        b"var _f=window.fetch;"
        b"window.fetch=function(u,o){"
        b'if(typeof u==="string"&&u.charAt(0)==="/"&&u.charAt(1)!=="/"&&u.indexOf(P)!==0)'
        b"u=P+u;"
        b"return _f.call(this,u,o)"
        b"};"
        b"var _x=XMLHttpRequest.prototype.open;"
        b"XMLHttpRequest.prototype.open=function(m,u){"
        b'if(typeof u==="string"&&u.charAt(0)==="/"&&u.charAt(1)!=="/"&&u.indexOf(P)!==0)'
        b"arguments[1]=P+u;"
        b"return _x.apply(this,arguments)"
        b"};"
        b"})()"
        b"</script>"
    )
    tag = f'<base href="{base_href}">'.encode()
    inject = tag + spa_proxy
    result, count = _HEAD_TAG_RE.subn(rb"\1" + inject, result, count=1)
    if count == 0:
        return html_bytes

    return result


# =============================================================================
# Template Routes (specific routes MUST come before parameterized routes)
# =============================================================================


@budusecases_router.get(
    "/templates",
    response_class=JSONResponse,
    description="List use case templates",
)
async def list_templates(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    page: Optional[int] = Query(default=None, description="Page number"),
    page_size: Optional[int] = Query(default=None, description="Items per page"),
    category: Optional[str] = Query(default=None, description="Filter by category"),
    tag: Optional[str] = Query(default=None, description="Filter by tag"),
    source: Optional[str] = Query(default=None, description="Filter by source"),
):
    """List use case templates with optional filtering."""
    try:
        params: Dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["page_size"] = page_size
        if category is not None:
            params["category"] = category
        if tag is not None:
            params["tag"] = tag
        if source is not None:
            params["source"] = source
        result = await BudUseCasesService(session).list_templates(params=params or None, user_id=str(current_user.id))
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to list templates: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list templates"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budusecases_router.get(
    "/templates/by-name/{name}",
    response_class=JSONResponse,
    description="Get a template by name",
)
async def get_template_by_name(
    name: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Get a template by name."""
    try:
        result = await BudUseCasesService(session).get_template_by_name(name)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to get template by name: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get template by name"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budusecases_router.post(
    "/templates/sync",
    response_class=JSONResponse,
    description="Sync templates from YAML files",
)
async def sync_templates(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Sync templates from YAML files."""
    try:
        result = await BudUseCasesService(session).sync_templates()
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to sync templates: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to sync templates"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budusecases_router.post(
    "/templates",
    response_class=JSONResponse,
    description="Create a custom template",
)
async def create_template(
    request_body: Dict[str, Any],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Create a custom template."""
    try:
        result = await BudUseCasesService(session).create_template(data=request_body, user_id=str(current_user.id))
        return JSONResponse(content=result, status_code=status.HTTP_201_CREATED)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to create template: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to create template"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budusecases_router.get(
    "/templates/{template_id}",
    response_class=JSONResponse,
    description="Get a template by ID",
)
async def get_template(
    template_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Get a template by ID."""
    try:
        result = await BudUseCasesService(session).get_template(template_id)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to get template: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get template"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budusecases_router.put(
    "/templates/{template_id}",
    response_class=JSONResponse,
    description="Update a template",
)
async def update_template(
    template_id: str,
    request_body: Dict[str, Any],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Update a template."""
    try:
        result = await BudUseCasesService(session).update_template(template_id, request_body)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to update template: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to update template"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budusecases_router.delete(
    "/templates/{template_id}",
    response_class=JSONResponse,
    description="Delete a template",
)
async def delete_template(
    template_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Delete a template."""
    try:
        await BudUseCasesService(session).delete_template(template_id)
        return JSONResponse(content={}, status_code=status.HTTP_204_NO_CONTENT)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to delete template: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to delete template"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# =============================================================================
# Deployment Route Publishing Helpers
# =============================================================================


# Statuses that indicate the deployment is actively running and should have
# its route published to Redis so budgateway can proxy API traffic to it.
_RUNNING_STATUSES = frozenset({"running", "completed"})


async def _maybe_publish_deployment_route(
    service: BudUseCasesService,
    deployment_id: str,
    deployment_result: Dict[str, Any],
) -> None:
    """Publish deployment route to Redis if the deployment is running with API access.

    This is intentionally non-blocking: if Redis publish fails the main
    operation still succeeds, matching the pattern used for model endpoint
    publishing in ``endpoint_ops/services.py``.

    Args:
        service: The BudUseCasesService instance (carries the DB session).
        deployment_id: The deployment ID.
        deployment_result: The deployment response dict from budusecases.
    """
    try:
        dep_status = str(deployment_result.get("status", "")).lower()
        if dep_status not in _RUNNING_STATUSES:
            return

        access_config = deployment_result.get("access_config") or {}
        api_config = access_config.get("api") or {}
        gateway_url = deployment_result.get("gateway_url")

        if api_config.get("enabled") and gateway_url:
            await service.publish_deployment_route(
                deployment_id=str(deployment_id),
                project_id=str(deployment_result.get("project_id", "")),
                gateway_url=gateway_url,
            )
    except Exception as e:
        logger.error(f"Failed to publish deployment route for {deployment_id}: {e}")


async def _maybe_delete_deployment_route(
    service: BudUseCasesService,
    deployment_id: str,
) -> None:
    """Delete deployment route from Redis before stopping or deleting.

    This is intentionally non-blocking: if Redis delete fails the main
    operation still succeeds.

    Args:
        service: The BudUseCasesService instance.
        deployment_id: The deployment ID whose route should be removed.
    """
    try:
        await service.delete_deployment_route(deployment_id)
    except Exception as e:
        logger.error(f"Failed to delete deployment route for {deployment_id}: {e}")


# =============================================================================
# Deployment Routes (specific routes MUST come before parameterized routes)
# =============================================================================


@budusecases_router.get(
    "/deployments",
    response_class=JSONResponse,
    description="List use case deployments",
)
async def list_deployments(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    page: Optional[int] = Query(default=None, description="Page number"),
    page_size: Optional[int] = Query(default=None, description="Items per page"),
    status_filter: Optional[str] = Query(default=None, alias="status", description="Filter by status"),
    cluster_id: Optional[str] = Query(default=None, description="Filter by cluster ID"),
    template_name: Optional[str] = Query(default=None, description="Filter by template name"),
    project_id: Optional[str] = Query(default=None, description="Filter by project ID"),
):
    """List use case deployments with optional filtering."""
    try:
        params: Dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["page_size"] = page_size
        if status_filter is not None:
            params["status"] = status_filter
        if cluster_id is not None:
            params["cluster_id"] = cluster_id
        if template_name is not None:
            params["template_name"] = template_name
        if project_id is not None:
            params["project_id"] = project_id
        result = await BudUseCasesService(session).list_deployments(
            params=params or None, user_id=str(current_user.id)
        )

        # Enrich deployments with budapp workflow_ids for CommonStatus progress tracking
        try:
            items = result.get("items") or []
            deployment_ids = [str(item.get("id")) for item in items if item.get("id")]
            if deployment_ids:
                workflow_map = WorkflowDataManager(session).find_workflows_by_deployment_ids(
                    deployment_ids=deployment_ids,
                    workflow_type=WorkflowTypeEnum.USECASE_DEPLOYMENT.value,
                )
                for item in items:
                    dep_id = str(item.get("id", ""))
                    if dep_id in workflow_map:
                        item["workflow_id"] = str(workflow_map[dep_id])
        except Exception as e:
            logger.warning("Failed to enrich deployments with workflow_ids: %s", e)

        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to list deployments: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list deployments"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budusecases_router.post(
    "/deployments",
    response_class=JSONResponse,
    description="Create a new deployment",
)
async def create_deployment(
    request_body: Dict[str, Any],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Create a new deployment."""
    try:
        # Extract project_id from request body (if provided by frontend)
        project_id = request_body.get("project_id")
        result = await BudUseCasesService(session).create_deployment(
            data=request_body,
            user_id=str(current_user.id),
            project_id=project_id,
        )
        return JSONResponse(content=result, status_code=status.HTTP_201_CREATED)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to create deployment: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to create deployment"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budusecases_router.get(
    "/deployments/{deployment_id}/progress",
    response_class=JSONResponse,
    description="Get deployment progress",
)
async def get_deployment_progress(
    deployment_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Get deployment progress from pipeline execution."""
    try:
        result = await BudUseCasesService(session).get_deployment_progress(deployment_id)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to get deployment progress: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get deployment progress"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budusecases_router.post(
    "/deployments/{deployment_id}/start",
    response_class=JSONResponse,
    description="Start a deployment",
)
async def start_deployment(
    deployment_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Start a deployment with real-time progress via CommonStatus + Novu.

    Creates a budapp workflow with pre-built step events, then starts the
    deployment via budusecases, passing notification parameters so that
    budpipeline dual-publishes events to Novu and budapp's callback topic.
    """
    try:
        service = BudUseCasesService(session)

        # 1. Fetch deployment to get component structure
        deployment = await service.get_deployment(deployment_id)
        components = deployment.get("components", [])

        # 2. Pre-build step events (must match DAG step IDs from dag_builder.py)
        pre_built_steps = [
            {
                "id": "cluster_health",
                "title": "Cluster Health Check",
                "description": "Verifying cluster readiness",
                "payload": {},
            },
        ]
        for comp in components:
            comp_name = comp.get("component_name", "unknown")
            pre_built_steps.append(
                {
                    "id": f"deploy_{comp_name}",
                    "title": f"Deploy {comp_name}",
                    "description": f"Deploying {comp_name} to cluster",
                    "payload": {},
                }
            )
        pre_built_steps.append(
            {
                "id": "notify_complete",
                "title": "Finalize",
                "description": "Completing deployment",
                "payload": {},
            },
        )

        # 3. Create budapp workflow
        workflow_create = WorkflowUtilCreate(
            workflow_type=WorkflowTypeEnum.USECASE_DEPLOYMENT,
            title=deployment.get("name", "Use Case Deployment"),
            total_steps=1,
            tag="Use Case",
        )
        workflow_svc = WorkflowService(session)
        db_workflow = await workflow_svc.retrieve_or_create_workflow(None, workflow_create, current_user.id)

        # 4. Save pre-built step events (done BEFORE pipeline trigger to prevent race conditions)
        event_name = BudServeWorkflowStepEventName.USECASE_DEPLOYMENT_EVENTS.value
        deployment_events_data = {
            "object": "workflow_metadata",
            "status": "PENDING",
            "workflow_id": None,
            "workflow_name": f"usecase-{deployment.get('name', '')}",
            "progress_type": event_name,
            "deployment_id": deployment_id,
            "steps": pre_built_steps,
        }
        events_data = {
            event_name: deployment_events_data,
            "workflow_execution_status": {"status": "running", "message": "Starting deployment..."},
        }
        workflow_step_svc = WorkflowStepService(session)
        await workflow_step_svc.create_or_update_next_workflow_step(db_workflow.id, 1, events_data)

        # Update workflow.progress for the workflow list API
        await WorkflowDataManager(session).update_by_fields(
            db_workflow,
            {
                "progress": deployment_events_data,
                "current_step": 1,
                "status": WorkflowStatusEnum.IN_PROGRESS,
            },
        )

        # 5. Start deployment, passing notification params
        logger.info(
            "Starting usecase deployment %s with notification_workflow_id=%s",
            deployment_id,
            str(db_workflow.id),
        )
        result = await service.start_deployment(
            deployment_id,
            notification_workflow_id=str(db_workflow.id),
        )

        # 6. Update events with pipeline execution_id
        execution_id = result.get("pipeline_execution_id")
        if execution_id:
            deployment_events_data["workflow_id"] = execution_id
            events_data[event_name] = deployment_events_data
            await workflow_step_svc.create_or_update_next_workflow_step(db_workflow.id, 1, events_data)

        # 7. Publish deployment route to Redis if API access is enabled
        await _maybe_publish_deployment_route(service, deployment_id, result)

        # 8. Include workflow_id in response for frontend
        result["workflow_id"] = str(db_workflow.id)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to start deployment: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to start deployment"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budusecases_router.post(
    "/deployments/{deployment_id}/stop",
    response_class=JSONResponse,
    description="Stop a deployment",
)
async def stop_deployment(
    deployment_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Stop a deployment."""
    try:
        service = BudUseCasesService(session)

        # Delete deployment route from Redis BEFORE stopping the service
        # so budgateway stops routing traffic before the backend goes down.
        await _maybe_delete_deployment_route(service, deployment_id)

        result = await service.stop_deployment(deployment_id)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to stop deployment: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to stop deployment"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budusecases_router.post(
    "/deployments/{deployment_id}/sync",
    response_class=JSONResponse,
    description="Sync deployment status",
)
async def sync_deployment_status(
    deployment_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Sync deployment status from BudCluster."""
    try:
        service = BudUseCasesService(session)
        result = await service.sync_deployment_status(deployment_id)

        # After syncing, the deployment may have transitioned to RUNNING.
        # If so, publish its route to Redis for budgateway.
        await _maybe_publish_deployment_route(service, deployment_id, result)

        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to sync deployment status: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to sync deployment status"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budusecases_router.post(
    "/deployments/{deployment_id}/retry-gateway",
    response_class=JSONResponse,
    description="Retry gateway route creation for a deployment",
)
async def retry_gateway_route(
    deployment_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Retry HTTPRoute creation for a deployment missing a gateway URL."""
    try:
        service = BudUseCasesService(session)
        result = await service.retry_gateway_route(deployment_id)

        # After retrying, the deployment may now have a gateway URL.
        # Publish its route to Redis for budgateway.
        await _maybe_publish_deployment_route(service, deployment_id, result)

        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to retry gateway route: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to retry gateway route"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budusecases_router.get(
    "/deployments/{deployment_id}",
    response_class=JSONResponse,
    description="Get a deployment by ID",
)
async def get_deployment(
    deployment_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Get a deployment by ID."""
    try:
        result = await BudUseCasesService(session).get_deployment(deployment_id)

        # Enrich with budapp workflow_id for CommonStatus progress tracking
        try:
            workflow = WorkflowDataManager(session).find_workflow_by_deployment_id(
                deployment_id=deployment_id,
                workflow_type=WorkflowTypeEnum.USECASE_DEPLOYMENT.value,
            )
            if workflow:
                result["workflow_id"] = str(workflow.id)
        except Exception as e:
            logger.warning("Failed to enrich deployment with workflow_id: %s", e)

        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to get deployment: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get deployment"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budusecases_router.delete(
    "/deployments/{deployment_id}",
    response_class=JSONResponse,
    description="Delete a deployment",
)
async def delete_deployment(
    deployment_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Delete a deployment."""
    try:
        service = BudUseCasesService(session)

        # Delete deployment route from Redis BEFORE deleting the deployment
        # so budgateway stops routing traffic before the backend goes down.
        await _maybe_delete_deployment_route(service, deployment_id)

        await service.delete_deployment(deployment_id)
        return JSONResponse(content={}, status_code=status.HTTP_204_NO_CONTENT)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to delete deployment: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to delete deployment"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# =============================================================================
# UI Reverse Proxy Routes
# =============================================================================


@budusecases_router.get(
    "/usecases/{deployment_id}/ui",
    description="Redirect bare UI path to trailing-slash version",
    include_in_schema=False,
)
async def redirect_usecase_ui_root(
    deployment_id: str,
    request: Request,
    current_user: Annotated[User, Depends(_get_current_active_user_or_token)],
):
    """Redirect ``/usecases/{deployment_id}/ui`` to ``/usecases/{deployment_id}/ui/``.

    Many web UIs expect their root to end with a slash.  Without the
    redirect, relative asset paths in the HTML would resolve one level
    too high.
    """
    # Preserve query params (including ?token=) on redirect
    target = str(request.url).rstrip("/") + "/"
    return RedirectResponse(url=target, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@budusecases_router.api_route(
    "/usecases/{deployment_id}/ui/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    description="Reverse proxy to use case UI",
    include_in_schema=False,
)
async def proxy_usecase_ui(
    deployment_id: str,
    path: str,
    request: Request,
    current_user: Annotated[Optional[User], Depends(_optional_user_or_token)],
    session: Annotated[Session, Depends(get_session)],
):
    """Proxy requests to the deployed use case's UI through Envoy Gateway.

    Auth is optional: the initial HTML request carries ``?token=`` for
    authentication, but follow-up sub-resource requests (CSS, JS, images)
    from the iframe cannot carry credentials.  The deployment UUID serves
    as an unguessable capability token for asset access.

    The proxy performs the following steps:
    1. Fetches the deployment record via Dapr to verify it exists and is running.
    2. Checks that UI access is enabled in the deployment's ``access_config``.
    3. Validates the ``gateway_url`` is available.
    4. Sanitises the ``path`` to prevent path-traversal attacks.
    5. Forwards the request (method, headers, body, query params) upstream.
    6. For HTML responses, injects a ``<base>`` tag so relative asset URLs
       resolve correctly under the proxy prefix.
    7. Returns the upstream response to the client.
    """
    service = BudUseCasesService(session)

    # ------------------------------------------------------------------
    # 1. Fetch deployment details
    # ------------------------------------------------------------------
    try:
        deployment = await service.get_deployment(deployment_id)
    except ClientException as e:
        logger.warning("Proxy: deployment lookup failed for %s: %s", deployment_id, e.message)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception:
        logger.exception("Proxy: unexpected error fetching deployment %s", deployment_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch deployment details",
        )

    # ------------------------------------------------------------------
    # 2. Verify the deployment exists and is in a running state
    # ------------------------------------------------------------------
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment not found",
        )

    deployment_status = (deployment.get("status") or "").upper()
    if deployment_status != "RUNNING":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment is not running (status: {deployment_status})",
        )

    # ------------------------------------------------------------------
    # 3. Verify UI access is enabled
    # ------------------------------------------------------------------
    access_config = deployment.get("access_config") or {}
    ui_config = access_config.get("ui") or {}
    if not ui_config.get("enabled"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="UI access is not enabled for this deployment",
        )

    # ------------------------------------------------------------------
    # 4. Verify gateway_url is available
    # ------------------------------------------------------------------
    gateway_url = deployment.get("gateway_url")
    if not gateway_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Gateway route not available for this deployment. "
                "The deployment may need to be redeployed to create the "
                "required gateway route."
            ),
        )

    # ------------------------------------------------------------------
    # 5. Sanitise path to prevent path traversal
    # ------------------------------------------------------------------
    if ".." in path.split("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid path",
        )

    # ------------------------------------------------------------------
    # 6. Construct the target URL
    # ------------------------------------------------------------------
    target_url = f"{gateway_url.rstrip('/')}/usecases/{deployment_id}/ui/{path}"

    # Forward query params, excluding the auth token (it must not leak upstream)
    filtered_params = {k: v for k, v in request.query_params.items() if k != "token"}
    if filtered_params:
        target_url += "?" + urlencode(filtered_params)

    # ------------------------------------------------------------------
    # 7. Proxy the request upstream
    # ------------------------------------------------------------------
    forwarded_headers: Dict[str, str] = {}
    for key, value in request.headers.items():
        if key.lower() not in _HOP_BY_HOP_HEADERS:
            forwarded_headers[key] = value

    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            upstream_response = await client.request(
                method=request.method,
                url=target_url,
                headers=forwarded_headers,
                content=body,
            )
    except httpx.TimeoutException:
        logger.warning("Proxy: upstream timeout for %s", target_url)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Upstream service timed out",
        )
    except httpx.HTTPError as exc:
        logger.exception("Proxy: upstream request failed for %s: %s", target_url, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to reach upstream service",
        )

    # ------------------------------------------------------------------
    # 8. Build response — raw byte forwarding (no HTML/JS rewriting)
    #
    # Subdomain-per-deployment routing (USECASE_DOMAIN) is preferred,
    # making rewriting unnecessary.  This path-based route is kept as
    # a fallback for environments without wildcard DNS/TLS.
    # ------------------------------------------------------------------
    response_content = upstream_response.content

    # Build response headers, filtering out hop-by-hop headers from upstream
    response_headers: Dict[str, str] = {}
    for key, value in upstream_response.headers.items():
        if key.lower() not in _HOP_BY_HOP_HEADERS:
            response_headers[key] = value

    return Response(
        content=response_content,
        status_code=upstream_response.status_code,
        headers=response_headers,
    )
