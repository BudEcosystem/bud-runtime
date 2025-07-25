from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, Iterable, Optional, Union

import aiohttp
import ujson as json
from fastapi.responses import Response, StreamingResponse


class RESTMethods(Enum):
    """Enumeration of HTTP REST methods.

    This enum defines the standard HTTP methods used in RESTful APIs.

    Attributes:
        GET (str): Represents the HTTP GET method, used for retrieving resources.
        POST (str): Represents the HTTP POST method, used for creating new resources.
        DELETE (str): Represents the HTTP DELETE method, used for deleting resources.
        PUT (str): Represents the HTTP PUT method, used for updating existing resources.
    """

    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"
    PUT = "PUT"


class AsyncHTTPClient:
    """An asynchronous HTTP client for making API requests.

    This class provides methods for sending HTTP requests asynchronously using aiohttp.
    It supports various HTTP methods, request parameters, and streaming responses.

    Attributes:
        timeout (aiohttp.ClientTimeout): The timeout for HTTP requests.
        connector (aiohttp.TCPConnector): The TCP connector for managing connections.
        session (Optional[aiohttp.ClientSession]): The aiohttp client session.
    """

    __slots__ = ("timeout", "connector", "session")

    def __init__(self, timeout: Optional[int] = None, max_connections: int = 100) -> None:
        """Initialize the AsyncHTTPClient.

        Args:
            timeout (Optional[int]): The timeout for HTTP requests in seconds.
            max_connections (int): The maximum number of connections to keep in the pool.
        """
        self.timeout = aiohttp.ClientTimeout(timeout)
        self.connector = aiohttp.TCPConnector(limit=max_connections)
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "AsyncHTTPClient":
        """Enter the runtime context and create a new client session.

        Returns:
            AsyncHTTPClient: The instance of the client.
        """
        self.session = aiohttp.ClientSession(timeout=self.timeout, connector=self.connector, json_serialize=json.dumps)
        return self

    async def __aexit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]) -> None:
        """Exit the runtime context and close the client session."""
        if self.session:
            await self.session.close()

    async def send_request(
        self,
        method: str,
        url: str,
        data: Union[bytes, Iterable[bytes], Dict[str, Any], None] = None,
        json: Optional[Dict[str, Any]] = None,
        params: Union[str, Dict[str, Any], None] = None,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        auth: Optional[Callable[..., Any]] = None,
        follow_redirects: bool = False,
        raise_for_status: bool = True,
        redirect_response: bool = False,
        streaming: bool = False,
    ) -> Union[Response, StreamingResponse]:
        """Send an HTTP request asynchronously.

        Args:
            method (str): The HTTP method to use.
            url (str): The URL to send the request to.
            data (Union[bytes, Iterable[bytes], Dict[str, Any], None]): The request body.
            json (Optional[Dict[str, Any]]): JSON data to send in the request body.
            params (Union[str, Dict[str, Any], None]): Query parameters to append to the URL.
            headers (Optional[Dict[str, str]]): Additional headers to send with the request.
            cookies (Optional[Dict[str, str]]): Cookies to send with the request.
            auth (Optional[Callable[..., Any]]): Callable to enable authentication.
            follow_redirects (bool): Whether to follow redirects.
            raise_for_status (bool): Whether to raise an exception for non-2xx status codes.
            redirect_response (bool): Whether to return a redirect response.
            streaming (bool): Whether to return a streaming response.

        Returns:
            Union[Response, StreamingResponse]: The HTTP response.

        Raises:
            AssertionError: If an invalid HTTP method is provided.
        """
        assert hasattr(RESTMethods, method.upper()), f"{method} is not a valid REST method."
        method = RESTMethods(method.upper()).value

        if self.session is None:
            raise RuntimeError("Session is not initialized. Use AsyncHTTPClient as a context manager.")

        async with self.session.request(
            method,
            url,
            data=data,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            allow_redirects=follow_redirects,
        ) as client_response:
            if raise_for_status:
                client_response.raise_for_status()

            if streaming and not redirect_response:
                return self._stream_response(client_response)
            else:
                return await self._build_response(client_response, streaming=streaming, incl_headers=False)

    async def send_streaming_request(self, *args: Any, **kwargs: Any) -> Union[Response, StreamingResponse]:
        """Send a streaming HTTP request.

        This method is a wrapper around send_request with streaming set to True.

        Args:
            *args: Positional arguments to pass to send_request.
            **kwargs: Keyword arguments to pass to send_request.

        Returns:
            Union[Response, StreamingResponse]: The HTTP response.
        """
        kwargs["streaming"] = True
        return await self.send_request(*args, **kwargs)

    async def redirect_streaming_request(self, *args: Any, **kwargs: Any) -> Union[Response, StreamingResponse]:
        """Send a streaming HTTP request that allows redirects.

        This method is a wrapper around send_request with streaming and redirect_response set to True.

        Args:
            *args: Positional arguments to pass to send_request.
            **kwargs: Keyword arguments to pass to send_request.

        Returns:
            Union[Response, StreamingResponse]: The HTTP response.
        """
        kwargs["streaming"] = True
        kwargs["redirect_response"] = True
        return await self.send_request(*args, **kwargs)

    @staticmethod
    async def _build_response(
        client_response: aiohttp.ClientResponse,
        streaming: bool = False,
        incl_headers: bool = False,
    ) -> Union[Response, StreamingResponse]:
        """Build a FastAPI response from an aiohttp ClientResponse.

        Args:
            client_response (aiohttp.ClientResponse): The aiohttp response to convert.
            streaming (bool): Whether to return a streaming response.
            incl_headers (bool): Whether to include headers in the response.

        Returns:
            Union[Response, StreamingResponse]: The FastAPI response.
        """
        content_type = client_response.headers.get("content-type", None)
        if incl_headers:
            response_headers = {k: v for k, v in client_response.headers.items() if k.lower() != "transfer-encoding"}
        else:
            response_headers = {}

        if content_type is not None:
            response_headers["Content-Type"] = content_type

        if not streaming:
            content = await client_response.content.read()
            return Response(
                content=content,
                status_code=client_response.status,
                headers=response_headers or None,
            )
        else:
            # FIXME: Streaming is getting stuck and not getting any results.
            return StreamingResponse(
                content=client_response.content.iter_any(),
                status_code=client_response.status,
                # media_type="text/event-stream",
                headers=response_headers or None,
                # background=BackgroundTask(client_response.close),
            )

    @staticmethod
    async def _stream_response(client_response: aiohttp.ClientResponse) -> AsyncIterator[bytes]:
        """Stream the response content.

        Args:
            client_response (aiohttp.ClientResponse): The aiohttp response to stream.

        Yields:
            bytes: Chunks of the response content.
        """
        async for chunk in client_response.content:
            yield chunk
