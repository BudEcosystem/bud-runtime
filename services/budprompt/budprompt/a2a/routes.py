"""A2A JSON-RPC route handler for budprompt.

Provides POST /a2a/{prompt_id}/v{version}/ dispatching 6 JSON-RPC methods.
"""

import json
import logging
from typing import Optional

from a2a.server.jsonrpc_models import InternalError, InvalidRequestError, JSONParseError, JSONRPCError
from a2a.server.request_handlers.response_helpers import build_error_response
from a2a.utils.errors import A2AError
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from jsonrpc.jsonrpc2 import JSONRPC20Request

from ..commons.exceptions import VersionNotSupportedError
from .dependencies import get_api_key
from .helper import validate_a2a_version
from .services import A2ADispatcherService


logger = logging.getLogger(__name__)

a2a_service = A2ADispatcherService()
a2a_router = APIRouter(prefix="/a2a", tags=["a2a"])


async def initialize_a2a_stores() -> None:
    """Initialize A2A stores via the dispatcher service."""
    await a2a_service.initialize()


async def shutdown_a2a_stores() -> None:
    """Shut down A2A stores via the dispatcher service."""
    await a2a_service.shutdown()


@a2a_router.post("/{prompt_id}/v{version}/")
async def a2a_jsonrpc(
    prompt_id: str, version: int, http_request: Request, api_key: Optional[str] = Depends(get_api_key)
):
    """Manual JSON-RPC dispatch for A2A protocol."""
    request_id = None
    try:
        body = await http_request.json()

        # Extract request_id early for error responses
        if isinstance(body, dict):
            request_id = body.get("id")
            if request_id is not None and not isinstance(request_id, (str, int)):
                request_id = None

        # Validate JSON-RPC 2.0 structure
        try:
            rpc_request = JSONRPC20Request.from_data(body)
        except Exception as e:
            return JSONResponse(build_error_response(request_id, InvalidRequestError(data=str(e))))

        method = rpc_request.method
        request_id = rpc_request._id
        params = rpc_request.params or {}

        # Validate the a2a-version header against supported versions
        validate_a2a_version(http_request)

        return await a2a_service.dispatch(prompt_id, version, method, request_id, params, api_key)
    except json.JSONDecodeError as e:
        return JSONResponse(build_error_response(None, JSONParseError(message=str(e))))
    except VersionNotSupportedError as e:
        return JSONResponse(build_error_response(request_id, JSONRPCError(code=-32008, message=e.message)))
    except A2AError as e:
        return JSONResponse(build_error_response(request_id, e))
    except Exception as e:
        logger.exception("Unexpected error in A2A dispatch")
        return JSONResponse(build_error_response(request_id, InternalError(message=str(e))))
