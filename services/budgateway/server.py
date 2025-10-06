from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
import os
import uvicorn

app = FastAPI()

# OpenAI API base URL
OPENAI_API_URL = "https://api.openai.com/v1/responses"
API_KEY_BYPASSED = ""


@app.post("/v1/responses")
async def responses_endpoint(request: Request):
    """
    Proxy endpoint for OpenAI Responses API.
    Accepts any JSON payload and forwards it to OpenAI's /v1/responses endpoint.
    Handles both streaming and non-streaming responses.
    """
    try:
        # Get the JSON payload from the request
        payload = await request.json()
        # remove model from payload
        print("++++++ payload ++++++")
        print(payload)
        print("++++++ payload ++++++")

        if not payload:
            raise HTTPException(status_code=400, detail="No JSON payload provided")

        # Extract Authorization header (required)
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            raise HTTPException(
                status_code=401, detail="Authorization header is required"
            )

        # Extract the token from "Bearer <token>" format
        api_key = auth_header.replace("Bearer ", "").strip()

        if not api_key:
            raise HTTPException(
                status_code=401, detail="Invalid authorization header format"
            )

        # Check if streaming is requested
        is_streaming = payload.get("stream", False)

        # Use the API key from the Authorization header (no override)
        # api_key already extracted from auth_header above

        if is_streaming:
            # Handle streaming response
            async def generate_stream():
                async with httpx.AsyncClient() as client:
                    async with client.stream(
                        "POST",
                        OPENAI_API_URL,
                        json=payload,
                        headers={
                            "Authorization": f"Bearer {API_KEY_BYPASSED}",
                            "Content-Type": "application/json",
                        },
                        timeout=60.0,
                    ) as response:
                        if response.status_code >= 200 and response.status_code < 300:
                            async for line in response.aiter_lines():
                                if line:
                                    # SSE lines already come properly formatted from OpenAI
                                    # Just forward them with a single newline
                                    yield f"{line}\n"
                                else:
                                    # Empty line indicates SSE event separator, preserve it
                                    yield "\n"
                        else:
                            # Send error as SSE event
                            error_data = await response.aread()
                            yield f"data: {error_data.decode()}\n\n"

            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        else:
            # Handle non-streaming response
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    OPENAI_API_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {API_KEY_BYPASSED}",
                        "Content-Type": "application/json",
                    },
                    timeout=60.0,
                )

            # Check if the request was successful
            if response.status_code >= 200 and response.status_code < 300:
                # Return the successful response
                return JSONResponse(
                    content=response.json(), status_code=response.status_code
                )
            else:
                # Return error response from OpenAI
                return JSONResponse(
                    content=response.json()
                    if response.text
                    else {"error": {"message": "Unknown error from OpenAI"}},
                    status_code=response.status_code,
                )

    except httpx.RequestError as e:
        # Handle network errors
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": f"Network error: {str(e)}",
                    "type": "network_error",
                }
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        # Handle any other errors
        raise HTTPException(
            status_code=500, detail={"error": {"message": str(e), "type": "api_error"}}
        )


@app.get("/v1/responses/{response_id}")
async def get_response(response_id: str, request: Request):
    """
    Proxy endpoint for retrieving a response by ID from OpenAI.
    """
    # Extract Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header is required")

    # Note: Using API_KEY_BYPASSED instead of extracting from header

    # Make actual call to OpenAI API
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.openai.com/v1/responses/{response_id}",
            headers={
                "Authorization": f"Bearer {API_KEY_BYPASSED}",
            },
            timeout=30.0,
        )

    # Return OpenAI's response
    if response.status_code >= 200 and response.status_code < 300:
        return JSONResponse(content=response.json(), status_code=response.status_code)
    else:
        # Return error response from OpenAI
        return JSONResponse(
            content=response.json()
            if response.text
            else {"error": {"message": "Unknown error from OpenAI"}},
            status_code=response.status_code,
        )


@app.delete("/v1/responses/{response_id}")
async def delete_response(response_id: str, request: Request):
    """
    Proxy endpoint for deleting a response from OpenAI.
    """
    # Extract Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header is required")

    # Note: Using API_KEY_BYPASSED instead of extracting from header

    # Make actual DELETE call to OpenAI API
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"https://api.openai.com/v1/responses/{response_id}",
            headers={
                "Authorization": f"Bearer {API_KEY_BYPASSED}",
            },
            timeout=30.0,
        )

    # Handle the response
    if response.status_code == 204:
        # Return 204 No Content
        from fastapi import Response

        return Response(status_code=204)
    elif response.status_code >= 200 and response.status_code < 300:
        return JSONResponse(
            content=response.json() if response.text else {},
            status_code=response.status_code,
        )
    else:
        # Return error response from OpenAI
        return JSONResponse(
            content=response.json()
            if response.text
            else {"error": {"message": "Unknown error from OpenAI"}},
            status_code=response.status_code,
        )


@app.post("/v1/responses/{response_id}/cancel")
async def cancel_response(response_id: str, request: Request):
    """
    Proxy endpoint for cancelling a response from OpenAI.
    """
    # Extract Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header is required")

    # Note: Using API_KEY_BYPASSED instead of extracting from header

    # Make actual POST call to OpenAI API to cancel
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.openai.com/v1/responses/{response_id}/cancel",
            headers={
                "Authorization": f"Bearer {API_KEY_BYPASSED}",
            },
            timeout=30.0,
        )

    # Return OpenAI's response
    if response.status_code >= 200 and response.status_code < 300:
        return JSONResponse(content=response.json(), status_code=response.status_code)
    else:
        # Return error response from OpenAI
        return JSONResponse(
            content=response.json()
            if response.text
            else {"error": {"message": "Unknown error from OpenAI"}},
            status_code=response.status_code,
        )


@app.get("/v1/responses/{response_id}/input_items")
async def list_input_items(response_id: str, request: Request):
    """
    Proxy endpoint for listing input items of a response from OpenAI.
    """
    # Extract Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header is required")

    # Note: Using API_KEY_BYPASSED instead of extracting from header

    # Make actual GET call to OpenAI API for input items
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.openai.com/v1/responses/{response_id}/input_items",
            headers={
                "Authorization": f"Bearer {API_KEY_BYPASSED}",
            },
            timeout=30.0,
        )

    # Return OpenAI's response
    if response.status_code >= 200 and response.status_code < 300:
        return JSONResponse(content=response.json(), status_code=response.status_code)
    else:
        # Return error response from OpenAI
        return JSONResponse(
            content=response.json()
            if response.text
            else {"error": {"message": "Unknown error from OpenAI"}},
            status_code=response.status_code,
        )


@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    # Run the FastAPI server with uvicorn
    # Default port is 5000, you can change it as needed
    port = int(os.getenv("PORT", 5000))

    print(f"Starting FastAPI server on port {port}")
    print(f"Responses API endpoint: http://localhost:{port}/v1/responses")
    print(f"API documentation: http://localhost:{port}/docs")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        reload=os.getenv("DEBUG", "false").lower() == "true",
    )
