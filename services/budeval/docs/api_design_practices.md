# 🚀 API Design Practices

Building a robust and scalable API is like cooking up a gourmet meal—every ingredient (or line of code) matters! Here's
how you can whip up a tasty API while following the best design practices.

## 🛑 Keep `main.py` Clean!

**Rule #1**: No routes in `main.py`! This file is your entry point and should be used exclusively for mounting your
routers. All routes should be defined in separate modules as `APIRouter` endpoints following the folder structure laid
out in the [Microservice Guidelines](./microservice_guidelines.md).

Here’s a quick example of how to mount routers in `main.py` from the core package:

```python
from fastapi import FastAPI

from .core.auth_routes import auth_router
from .core.dummy_routes import dummy_router

app = FastAPI()

app.include_router(auth_router)
app.include_router(dummy_router)
```

If you’re curious about the nitty-gritty, check out
the [FastAPI docs](https://fastapi.tiangolo.com/reference/apirouter).

## 📦 Mandatory Routers: `sync_routes` and `meta_routes`

Your `main.py` must include two routers:

- `core.sync_routes`: Handles endpoints for syncing configurations and secrets.
- `core.meta_routes`: Provides endpoints for fetching API metadata.

These routers are mandatory for every microservice. If you need to override the metadata API, go ahead, but make sure it
uses the same response classes to maintain consistency across your services.

## 🧩 Custom Responses? Extend ResponseBase!

Your microservice should use standardized response classes for consistency. The commons.schema module provides base
classes for success and error responses:

```python
class SuccessResponse(ResponseBase):
    object: str
    message: Optional[str]
    type: Optional[str]
    param: Optional[str] = None
    code: int

    @model_validator(mode="before")
    @classmethod
    def root_validator(cls, data: dict):
        data["message"] = data.get("message") or HTTPStatus(data["code"]).description

        return data

```

```python
class ErrorResponse(ResponseBase):
    object: constr(to_lower=True) = "error"
    code: int

    @model_validator(mode="before")
    @classmethod
    def root_validator(cls, data: dict):
        suffix = "Error" if data.get("object", "").lower() == "error" else ""
        data["type"] = data.get("type") or cls.to_pascal_case(HTTPStatus(data["code"]).phrase, suffix)
        data["message"] = data.get("message") or HTTPStatus(data["code"]).description

        return data

```

These should be your go-to response classes for generic success and error responses. If you need something custom,
create a new class that extends `ResponseBase`:

### 🛠️ Example: Custom Response in `core/schemas.py`

```python
from pyguard.commons.schemas import ResponseBase


class CustomResponse(ResponseBase):
    object: str = "custom_response"
    custom_field: str
```

When defining custom responses, set the object field to a unique, lowercase, snake_case name that represents the
response.

### 🎯 Using Responses in Your API

To use these response classes as API returns, do the following:

```python
return SuccessResponse(message="Success example", code=status.HTTP_200_OK).to_http_response()

return ErrorResponse(message="Error example", code=status.HTTP_503_SERVICE_UNAVAILABLE).to_http_response()
```

Always use `fastapi.status` to specify the response status code.

## 📝 Defining API Endpoints: The Right Way

When writing an API endpoint, make sure to include:

- **Response model**: Define the response class.
- **Status code**: Use `fastapi.status`.
- **Description**: Provide a brief description of what the endpoint does.
- **Tags**: Use tags for organizing endpoints.
- **Responses**: Specify any additional response classes.

Here's an example:

```python
@sync_router.get(
    "/sync/configurations",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to a misconfigured configuration store",
        }
    },
    description="API endpoint to sync microservice configuration from a supported configstore.",
    tags=["Sync"],
)
async def sync_configurations() -> Response:
    if app_settings.configstore_name:
        # Sync logic here...
        return SuccessResponse(
            message=f"{len(values)}/{len(fields_to_sync)} configuration(s) synced.",
            code=status.HTTP_200_OK,
        ).to_http_response()
    else:
        return ErrorResponse(
            message="Config store is not configured.",
            code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ).to_http_response()

```

## 🚀 Extra Design Practices

- **Modularize Your Code**: Break down complex logic into separate functions or modules to keep your routes clean and
  manageable. Follow the structure outlines in the Microservice Guidelines to keep everything organized and
  maintainable.
- **Use Dependency Injection**: FastAPI’s dependency injection system is powerful—use it to manage configurations,
  database connections, and other shared resources.
- **Document Your APIs**: Make sure your endpoints are well-documented using description, summary, and tags. This helps
  keep your API user-friendly and self-explanatory.
- **Error Handling**: Always provide meaningful error messages that can help in debugging.
- **Security First**: Sanitize all inputs and avoid exposing sensitive information in responses.