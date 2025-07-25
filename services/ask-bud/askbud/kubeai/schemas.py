from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


Role = Literal["system", "user", "assistant", "tool"]


class ChatMessage(BaseModel):
    role: Role
    content: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: bool = False
    temperature: Optional[float] = Field(None, ge=0, le=2)

    @field_validator("messages")
    @classmethod
    def must_have_user(cls, v: List[ChatMessage]) -> List[ChatMessage]:
        """Validate that the messages list contains at least one user message.

        Args:
            cls: The class reference
            v: List of ChatMessage objects to validate

        Returns:
            The validated list of ChatMessage objects

        Raises:
        ValueError: If no user message is found in the list
        """
        if not any(m.role == "user" for m in v):
            raise ValueError("At least one user message required")
        return v


class Choice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Literal["stop", "error"]


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Optional[Dict[str, int]] = None
