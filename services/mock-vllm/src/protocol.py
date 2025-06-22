"""Protocol models for mock vLLM OpenAI-compatible API."""

import time
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


def random_uuid() -> str:
    """Generate a random UUID."""
    import uuid
    return str(uuid.uuid4())


class ErrorResponse(BaseModel):
    object: str = "error"
    message: str
    type: str
    param: Optional[str] = None
    code: int


class ModelPermission(BaseModel):
    id: str = Field(default_factory=lambda: f"modelperm-{random_uuid()}")
    object: str = "model_permission"
    created: int = Field(default_factory=lambda: int(time.time()))
    allow_create_engine: bool = False
    allow_sampling: bool = True
    allow_logprobs: bool = True
    allow_search_indices: bool = False
    allow_view: bool = True
    allow_fine_tuning: bool = False
    organization: str = "*"
    group: Optional[str] = None
    is_blocking: bool = False


class ModelCard(BaseModel):
    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "mock-vllm"
    root: Optional[str] = None
    parent: Optional[str] = None
    max_model_len: Optional[int] = None
    permission: List[ModelPermission] = Field(default_factory=list)


class ModelList(BaseModel):
    object: str = "list"
    data: List[ModelCard]


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class LogProbs(BaseModel):
    text_offset: List[int] = Field(default_factory=list)
    token_logprobs: List[Optional[float]] = Field(default_factory=list)
    tokens: List[str] = Field(default_factory=list)
    top_logprobs: Optional[List[Optional[Dict[str, float]]]] = None


# Chat Completion Models
class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    seed: Optional[int] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    response_format: Optional[Dict[str, Any]] = None


class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None
    logprobs: Optional[LogProbs] = None


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{random_uuid()}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionResponseChoice]
    usage: Usage
    system_fingerprint: Optional[str] = None


class ChatCompletionStreamResponseChoice(BaseModel):
    index: int
    delta: ChatMessage
    finish_reason: Optional[str] = None
    logprobs: Optional[LogProbs] = None


class ChatCompletionStreamResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{random_uuid()}")
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionStreamResponseChoice]
    system_fingerprint: Optional[str] = None


# Completion Models
class CompletionRequest(BaseModel):
    model: str
    prompt: Union[str, List[str]]
    suffix: Optional[str] = None
    max_tokens: Optional[int] = 16
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    logprobs: Optional[int] = None
    echo: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    best_of: Optional[int] = None
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    seed: Optional[int] = None


class CompletionResponseChoice(BaseModel):
    text: str
    index: int
    logprobs: Optional[LogProbs] = None
    finish_reason: Optional[str] = None


class CompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"cmpl-{random_uuid()}")
    object: str = "text_completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[CompletionResponseChoice]
    usage: Usage
    system_fingerprint: Optional[str] = None


class CompletionStreamResponseChoice(BaseModel):
    text: str
    index: int
    logprobs: Optional[LogProbs] = None
    finish_reason: Optional[str] = None


class CompletionStreamResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"cmpl-{random_uuid()}")
    object: str = "text_completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[CompletionStreamResponseChoice]
    system_fingerprint: Optional[str] = None


# Embedding Models
class EmbeddingRequest(BaseModel):
    model: str
    input: Union[str, List[str], List[int], List[List[int]]]
    encoding_format: Optional[Literal["float", "base64"]] = "float"
    user: Optional[str] = None


class EmbeddingResponseData(BaseModel):
    index: int
    embedding: List[float]
    object: str = "embedding"


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[EmbeddingResponseData]
    model: str
    usage: Usage


# Tokenization Models
class TokenizeRequest(BaseModel):
    model: str
    prompt: str
    add_special_tokens: bool = True


class TokenizeResponse(BaseModel):
    tokens: List[int]
    count: int


class DetokenizeRequest(BaseModel):
    model: str
    tokens: List[int]


class DetokenizeResponse(BaseModel):
    prompt: str


# Pooling Models
class PoolingRequest(BaseModel):
    model: str
    prompt: Union[str, List[str]]
    instruction: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None


class PoolingResponseData(BaseModel):
    index: int
    embedding: List[float]
    object: str = "embedding"


class PoolingResponse(BaseModel):
    object: str = "list"
    data: List[PoolingResponseData]
    model: str
    usage: Usage


# Score Models
class ScoreRequest(BaseModel):
    model: str
    text_1: Union[str, List[str]]
    text_2: Union[str, List[str]]


class ScoreResponseData(BaseModel):
    index: int
    score: float
    object: str = "score"


class ScoreResponse(BaseModel):
    object: str = "list"
    data: List[ScoreResponseData]
    model: str
    usage: Usage


# Classification Models
class ClassificationRequest(BaseModel):
    model: str
    prompt: Union[str, List[str]]
    labels: Optional[List[str]] = None


class ClassificationResponseData(BaseModel):
    index: int
    label: str
    score: float
    object: str = "classification"


class ClassificationResponse(BaseModel):
    object: str = "list"
    data: List[ClassificationResponseData]
    model: str
    usage: Usage


# Rerank Models
class RerankDocument(BaseModel):
    text: str
    meta: Optional[Dict[str, Any]] = None


class RerankRequest(BaseModel):
    model: str
    query: str
    documents: Union[List[str], List[RerankDocument]]
    top_n: Optional[int] = None
    return_documents: Optional[bool] = True


class RerankResult(BaseModel):
    index: int
    relevance_score: float
    text: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class RerankResponse(BaseModel):
    object: str = "rerank"
    model: str
    results: List[RerankResult]
    usage: Usage


# Transcription Models
class TranscriptionRequest(BaseModel):
    model: str
    file: Any  # UploadFile in actual usage
    language: Optional[str] = None
    prompt: Optional[str] = None
    response_format: Optional[Literal["json", "text", "srt", "verbose_json", "vtt"]] = "json"
    temperature: Optional[float] = 0.0
    timestamp_granularities: Optional[List[Literal["word", "segment"]]] = None


class TranscriptionResponse(BaseModel):
    text: str