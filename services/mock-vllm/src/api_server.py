#!/usr/bin/env python3
"""Mock vLLM OpenAI-compatible API server for integration testing."""

import argparse
import json
import logging
import os
import signal
import sys
import tempfile
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_client import make_asgi_app
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.routing import Mount

from .mock_responses import MockResponseGenerator
from .protocol import (
    ChatCompletionRequest,
    ClassificationRequest,
    CompletionRequest,
    DetokenizeRequest,
    EmbeddingRequest,
    ErrorResponse,
    PoolingRequest,
    RerankRequest,
    ScoreRequest,
    TokenizeRequest,
    TranscriptionRequest,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Version info
MOCK_VLLM_VERSION = "0.1.0"


def create_app(args: argparse.Namespace) -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title="Mock vLLM API Server",
        description="Mock vLLM OpenAI-compatible API for integration testing",
        version=MOCK_VLLM_VERSION,
        openapi_url=None if args.disable_fastapi_docs else "/openapi.json",
        docs_url=None if args.disable_fastapi_docs else "/docs",
        redoc_url=None if args.disable_fastapi_docs else "/redoc",
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=args.allowed_origins,
        allow_credentials=args.allow_credentials,
        allow_methods=args.allowed_methods,
        allow_headers=args.allowed_headers,
    )
    
    # Add Prometheus metrics
    if not args.disable_metrics:
        Instrumentator(
            excluded_handlers=["/metrics", "/health", "/ping"],
        ).instrument(app).expose(app)
        
        # Add prometheus asgi middleware to route /metrics requests
        metrics_app = make_asgi_app()
        app.mount("/metrics", metrics_app)
    
    # Initialize response generator
    processing_delay = float(os.getenv("MOCK_PROCESSING_DELAY", "0.1"))
    app.state.generator = MockResponseGenerator(processing_delay)
    
    # Store server info
    app.state.server_load_metrics = 0
    app.state.served_model_name = args.served_model_name or [args.model]
    
    return app


# Create argument parser
parser = argparse.ArgumentParser(description="Mock vLLM OpenAI-Compatible API server.")
parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
parser.add_argument("--model", type=str, default="mock-model", help="Model name")
parser.add_argument("--served-model-name", nargs="+", help="Model name(s) to serve")
parser.add_argument("--uvicorn-log-level", type=str, default="info", help="Uvicorn log level")
parser.add_argument("--allowed-origins", nargs="*", default=["*"], help="Allowed CORS origins")
parser.add_argument("--allow-credentials", action="store_true", help="Allow CORS credentials")
parser.add_argument("--allowed-methods", nargs="*", default=["*"], help="Allowed CORS methods")
parser.add_argument("--allowed-headers", nargs="*", default=["*"], help="Allowed CORS headers")
parser.add_argument("--api-key", type=str, help="API key for authentication")
parser.add_argument("--disable-fastapi-docs", action="store_true", help="Disable FastAPI docs")
parser.add_argument("--disable-metrics", action="store_true", help="Disable Prometheus metrics")
parser.add_argument("--disable-log-requests", action="store_true", help="Disable request logging")

# Parse arguments
args = parser.parse_args()

# Create the application
app = create_app(args)

# API key authentication middleware
if args.api_key or os.getenv("VLLM_API_KEY"):
    api_key = args.api_key or os.getenv("VLLM_API_KEY")
    
    @app.middleware("http")
    async def api_key_auth(request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        
        url_path = request.url.path
        if not url_path.startswith("/v1"):
            return await call_next(request)
        
        auth_header = request.headers.get("Authorization")
        if auth_header != f"Bearer {api_key}":
            return JSONResponse(
                content={"error": "Unauthorized"},
                status_code=401
            )
        
        return await call_next(request)


# Request logging middleware
if not args.disable_log_requests:
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        logger.info(f"{request.method} {request.url.path}")
        response = await call_next(request)
        return response


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    error = ErrorResponse(
        message=exc.detail,
        type=exc.__class__.__name__,
        code=exc.status_code
    )
    return JSONResponse(error.model_dump(), status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    error = ErrorResponse(
        message=str(exc),
        type="ValidationError",
        code=400
    )
    return JSONResponse(error.model_dump(), status_code=400)


# Health check endpoints
@app.get("/health")
async def health():
    """Health check endpoint."""
    return Response(status_code=200)


@app.get("/ping")
@app.post("/ping")
async def ping():
    """Ping endpoint (required for SageMaker)."""
    return Response(status_code=200)


@app.get("/version")
async def version():
    """Version endpoint."""
    return {"version": MOCK_VLLM_VERSION}


@app.get("/load")
async def get_server_load():
    """Get server load metrics."""
    return {"server_load": app.state.server_load_metrics}


# Model endpoints
@app.get("/v1/models")
async def list_models():
    """List available models."""
    return app.state.generator.get_model_list().model_dump()


# Chat completions
@app.post("/v1/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest):
    """Create chat completion."""
    app.state.server_load_metrics += 1
    
    result = await app.state.generator.generate_chat_completion(
        request.model_dump(),
        stream=request.stream
    )
    
    if request.stream:
        return StreamingResponse(
            result,
            media_type="text/event-stream"
        )
    else:
        return result.model_dump()


# Text completions
@app.post("/v1/completions")
async def create_completion(request: CompletionRequest):
    """Create text completion."""
    app.state.server_load_metrics += 1
    
    result = await app.state.generator.generate_completion(
        request.model_dump(),
        stream=request.stream
    )
    
    if request.stream:
        return StreamingResponse(
            result,
            media_type="text/event-stream"
        )
    else:
        return result.model_dump()


# Embeddings
@app.post("/v1/embeddings")
async def create_embedding(request: EmbeddingRequest):
    """Create embeddings."""
    app.state.server_load_metrics += 1
    
    result = await app.state.generator.generate_embedding(request.model_dump())
    return result.model_dump()


# Tokenization
@app.post("/tokenize")
async def tokenize(request: TokenizeRequest):
    """Tokenize text."""
    result = await app.state.generator.tokenize(request.model_dump())
    return result.model_dump()


@app.post("/detokenize")
async def detokenize(request: DetokenizeRequest):
    """Detokenize tokens."""
    result = await app.state.generator.detokenize(request.model_dump())
    return result.model_dump()


# Pooling
@app.post("/pooling")
async def create_pooling(request: PoolingRequest):
    """Create pooling response."""
    app.state.server_load_metrics += 1
    
    result = await app.state.generator.generate_pooling(request.model_dump())
    return result.model_dump()


# Classification
@app.post("/classify")
async def create_classification(request: ClassificationRequest):
    """Create classification response."""
    app.state.server_load_metrics += 1
    
    result = await app.state.generator.generate_classification(request.model_dump())
    return result.model_dump()


# Scoring
@app.post("/score")
async def create_score(request: ScoreRequest):
    """Create score response."""
    app.state.server_load_metrics += 1
    
    result = await app.state.generator.generate_score(request.model_dump())
    return result.model_dump()


@app.post("/v1/score")
async def create_score_v1(request: ScoreRequest):
    """Create score response (v1 endpoint for compatibility)."""
    logger.warning(
        "To indicate that Score API is not part of standard OpenAI API, "
        "we have moved it to `/score`. Please update your client accordingly."
    )
    return await create_score(request)


# Reranking
@app.post("/rerank")
async def create_rerank(request: RerankRequest):
    """Create rerank response."""
    app.state.server_load_metrics += 1
    
    result = await app.state.generator.generate_rerank(request.model_dump())
    return result.model_dump()


@app.post("/v1/rerank")
async def create_rerank_v1(request: RerankRequest):
    """Create rerank response (v1 endpoint)."""
    logger.warning(
        "To indicate that the rerank API is not part of the standard OpenAI API, "
        "we have located it at `/rerank`. Please update your client accordingly."
    )
    return await create_rerank(request)


@app.post("/v2/rerank")
async def create_rerank_v2(request: RerankRequest):
    """Create rerank response (v2 endpoint)."""
    return await create_rerank(request)


# Audio transcription
@app.post("/v1/audio/transcriptions")
async def create_transcription(
    file: UploadFile = File(...),
    model: str = Form(...),
    language: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
    response_format: Optional[str] = Form("json"),
    temperature: Optional[float] = Form(0.0),
):
    """Create audio transcription."""
    app.state.server_load_metrics += 1
    
    # Read audio data
    audio_data = await file.read()
    
    # Create request object
    request_data = {
        "model": model,
        "language": language,
        "prompt": prompt,
        "response_format": response_format,
        "temperature": temperature,
    }
    
    result = await app.state.generator.generate_transcription(audio_data, request_data)
    return result.model_dump()


# Signal handler for graceful shutdown
def signal_handler(sig, frame):
    logger.info("Received signal %s, shutting down...", sig)
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def main():
    """Main entry point."""
    logger.info("Starting Mock vLLM API server version %s", MOCK_VLLM_VERSION)
    logger.info("Serving model(s): %s", app.state.served_model_name)
    
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.uvicorn_log_level,
    )


if __name__ == "__main__":
    main()