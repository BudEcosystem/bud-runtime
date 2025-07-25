import asyncio
import json
import os
import time
import uuid
from subprocess import TimeoutExpired, run
from typing import Any, AsyncGenerator, Dict, Tuple, Union

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from ..commons.config import app_settings
from .schemas import ChatCompletionRequest, ChatCompletionResponse, ChatMessage, Choice


DEFAULT_TIMEOUT = int(os.getenv("KUBECTL_AI_TIMEOUT", 120))  # seconds
MAX_OUTPUT_BYTES = int(os.getenv("KUBECTL_AI_MAX_OUTPUT", 1 << 20))  # 1 MiB
LINE_CHUNK_SIZE = int(os.getenv("KUBECTL_AI_LINE_CHUNK", 256))
PASS_CONFIRM = os.getenv("KUBECTL_AI_CONFIRM") is None  # auto yes unless var set


class KubeAI:
    @staticmethod
    async def _exec_sync(prompt: str, timeout: int) -> Tuple[int, str, str]:
        """Blocking exec in threadpool (non‑stream)."""
        cmd = ["kubectl-ai", "--llm-provider", "openai", "--model", app_settings.inference_model]
        if PASS_CONFIRM:
            cmd.append("--quiet")
        cmd.append(prompt)

        loop = asyncio.get_running_loop()
        try:
            proc = await loop.run_in_executor(
                None,
                lambda: run(
                    cmd,
                    text=True,
                    capture_output=True,
                    timeout=timeout,
                    env=os.environ.copy(),
                ),
            )
        except FileNotFoundError as exc:
            raise HTTPException(500, "kubectl-ai binary not found in PATH") from exc
        except TimeoutExpired as exc:
            raise HTTPException(504, f"kubectl-ai timed out after {timeout}s") from exc

        return proc.returncode, proc.stdout, proc.stderr

    @staticmethod
    async def _stream_exec(prompt: str, timeout: int) -> AsyncGenerator[bytes, None]:
        cmd = ["kubectl-ai", "--llm-provider", "openai", "--model", app_settings.inference_model]
        if PASS_CONFIRM:
            cmd.append("--quiet")
        cmd.append(prompt)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ.copy(),
        )

        chunk_id = "chatcmpl-" + uuid.uuid4().hex
        created = int(time.time())

        def sse(data: Union[Dict[str, Any], str]) -> bytes:
            return f"data: {json.dumps(data) if isinstance(data, dict) else data}\n\n".encode()

        # First delta (role announcement)
        yield sse(
            {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": "ask-bud",
                "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
            }
        )

        try:
            if proc.stdout is None:
                raise RuntimeError("Failed to get stdout from subprocess")

            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                yield sse(
                    {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": "ask-bud",
                        "choices": [{"index": 0, "delta": {"content": line.decode()}, "finish_reason": None}],
                    }
                )
        except asyncio.CancelledError:
            proc.kill()
            raise

        await proc.wait()
        finish_reason = "stop" if proc.returncode == 0 else "error"

        # send stderr if exists
        stderr = (await proc.stderr.read()).decode() if proc.stderr else ""
        if stderr:
            yield sse(
                {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": "ask-bud",
                    "choices": [{"index": 0, "delta": {"content": "\n[stderr]\n" + stderr}, "finish_reason": None}],
                }
            )

        yield sse(
            {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": "ask-bud",
                "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
            }
        )
        yield b"data: [DONE]\n\n"

    @staticmethod
    async def process_chat_completion(req: ChatCompletionRequest) -> Union[Dict[str, Any], StreamingResponse]:
        """Process a chat completion request and return the appropriate response."""
        user_msg = next(m for m in reversed(req.messages) if m.role == "user")
        prompt = user_msg.content or ""

        if req.stream:
            return StreamingResponse(KubeAI._stream_exec(prompt, DEFAULT_TIMEOUT), media_type="text/event-stream")

        retcode, stdout, stderr = await KubeAI._exec_sync(prompt, DEFAULT_TIMEOUT)
        stdout = stdout[:MAX_OUTPUT_BYTES]
        stderr = stderr[:MAX_OUTPUT_BYTES]

        content = stdout.rstrip()
        if stderr:
            content += "\n[stderr]\n" + stderr.rstrip()

        resp = ChatCompletionResponse(
            id="chatcmpl-" + uuid.uuid4().hex,
            created=int(time.time()),
            model="ask-bud",
            choices=[
                Choice(
                    index=0,
                    message=ChatMessage(role="assistant", content=content),
                    finish_reason="stop" if retcode == 0 else "error",
                )
            ],
        )
        return resp
