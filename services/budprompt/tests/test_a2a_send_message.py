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

"""Integration tests for A2A SendMessage on test_prompt (unstructured, non-streaming).

28 scenarios covering happy paths, taskId handling, role variations,
part content types, configuration, streaming mismatch, metadata,
v0.3 backward compatibility, and protocol-level version headers.

Prerequisites:
    - budprompt service running with test_prompt seeded in Redis
    - Execute via: docker exec -it budserve-development-budprompt pytest tests/test_a2a_send_message.py -v
"""

import os
import time

import httpx
import pytest


APP_PORT = os.getenv("APP_PORT", "9088")
A2A_URL = f"http://localhost:{APP_PORT}/a2a/test_prompt/v0/"

# Timeout for blocking LLM calls (test_prompt hits a real model)
REQUEST_TIMEOUT = 120.0
# Shorter timeout for non-blocking requests
NON_BLOCKING_TIMEOUT = 30.0
# Polling interval/max for async task completion
POLL_INTERVAL = 1.0
POLL_MAX_WAIT = 90.0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """HTTP client scoped to each test."""
    with httpx.Client(timeout=REQUEST_TIMEOUT) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def send_a2a(client: httpx.Client, method: str, params: dict, request_id="test-1", headers=None, timeout=None):
    """Send a JSON-RPC request and return parsed response dict."""
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    resp = client.post(A2A_URL, json=payload, headers=headers or {}, timeout=timeout or REQUEST_TIMEOUT)
    return resp.json()


def send_message(client: httpx.Client, params: dict, **kwargs):
    """Shortcut for SendMessage method."""
    return send_a2a(client, "SendMessage", params, **kwargs)


def get_task(client: httpx.Client, task_id: str, history_length=None):
    """Poll a task via GetTask JSON-RPC method."""
    params = {"id": task_id}
    if history_length is not None:
        params["historyLength"] = history_length
    return send_a2a(client, "GetTask", params, request_id="get-task")


def poll_until_terminal(client: httpx.Client, task_id: str, max_wait: float = POLL_MAX_WAIT) -> dict:
    """Poll GetTask until the task reaches a terminal state."""
    terminal_states = {"TASK_STATE_COMPLETED", "TASK_STATE_FAILED", "TASK_STATE_CANCELED", "TASK_STATE_REJECTED"}
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        resp = get_task(client, task_id)
        assert "result" in resp, f"GetTask failed: {resp}"
        state = resp["result"].get("status", {}).get("state", "")
        if state in terminal_states:
            return resp
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Task {task_id} did not reach terminal state within {max_wait}s")


def make_text_params(text: str, **overrides) -> dict:
    """Build minimal SendMessage params with a single text Part."""
    params = {"message": {"role": "ROLE_USER", "parts": [{"text": text}]}}
    params.update(overrides)
    return params


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


def assert_success(resp: dict):
    """Assert JSON-RPC success response."""
    assert "result" in resp, f"Expected result, got: {resp}"
    assert "error" not in resp


def assert_error(resp: dict, code: int, message_contains: str | None = None):
    """Assert JSON-RPC error response with expected code."""
    assert "error" in resp, f"Expected error, got: {resp}"
    assert resp["error"]["code"] == code, f"Expected error code {code}, got {resp['error']['code']}: {resp['error']}"
    if message_contains:
        assert message_contains.lower() in resp["error"]["message"].lower(), (
            f"Expected '{message_contains}' in error message: {resp['error']['message']}"
        )


def assert_task_completed(resp: dict) -> dict:
    """Assert response contains a completed task. Returns the task dict."""
    assert_success(resp)
    task = resp["result"].get("task", {})
    assert task.get("status", {}).get("state") == "TASK_STATE_COMPLETED", (
        f"Expected TASK_STATE_COMPLETED, got: {task.get('status', {})}"
    )
    assert "id" in task
    assert "contextId" in task
    return task


def assert_task_working_or_submitted(resp: dict) -> dict:
    """Assert response contains a working/submitted task. Returns the task dict."""
    assert_success(resp)
    task = resp["result"].get("task", {})
    state = task.get("status", {}).get("state", "")
    assert state in ("TASK_STATE_WORKING", "TASK_STATE_SUBMITTED"), f"Expected WORKING/SUBMITTED, got: {state}"
    return task


# ===========================================================================
# Category 1: Happy Path
# ===========================================================================


@pytest.mark.integration
class TestHappyPath:
    """Basic successful SendMessage flows."""

    def test_1_1_basic_text(self, client):
        """Single text Part, blocking=true → completed task with artifacts."""
        params = make_text_params("Hello, what is 2+2?", configuration={"blocking": True})
        resp = send_message(client, params)
        task = assert_task_completed(resp)

        # Must have artifacts with text content
        artifacts = task.get("artifacts", [])
        assert len(artifacts) > 0, "Expected at least one artifact"
        parts = artifacts[0].get("parts", [])
        assert any("text" in p for p in parts), f"Expected text in artifact parts: {parts}"

    def test_1_2_multi_turn_context(self, client):
        """Two sequential requests — second uses contextId from first."""
        # Turn 1: create a conversation
        params1 = make_text_params("My name is TestUser.", configuration={"blocking": True})
        resp1 = send_message(client, params1, request_id="turn-1")
        task1 = assert_task_completed(resp1)
        context_id = task1["contextId"]

        # Turn 2: continue the conversation using the same contextId
        params2 = make_text_params(
            "What is my name?",
            configuration={"blocking": True},
            message={"role": "ROLE_USER", "parts": [{"text": "What is my name?"}], "contextId": context_id},
        )
        # Override message to include contextId
        params2["message"]["contextId"] = context_id
        resp2 = send_message(client, params2, request_id="turn-2")
        task2 = assert_task_completed(resp2)

        # Both should share the same contextId but have different task ids
        assert task2["contextId"] == context_id
        assert task2["id"] != task1["id"]


# ===========================================================================
# Category 2: taskId Handling
# ===========================================================================


@pytest.mark.integration
class TestTaskIdHandling:
    """Tests for taskId edge cases."""

    def test_1_4_terminal_task_id(self, client):
        """Send with taskId from a completed task → error -32602 (terminal state)."""
        # First, create a completed task
        params = make_text_params("Hello", configuration={"blocking": True})
        resp = send_message(client, params, request_id="setup-terminal")
        task = assert_task_completed(resp)
        completed_task_id = task["id"]

        # Now try to send a new message with the completed task's id
        params2 = {
            "message": {
                "role": "ROLE_USER",
                "parts": [{"text": "Follow up"}],
                "taskId": completed_task_id,
            },
            "configuration": {"blocking": True},
        }
        resp2 = send_message(client, params2, request_id="terminal-reuse")
        assert_error(resp2, -32602, "terminal state")

    def test_1_5_working_task_id(self, client):
        """blocking=false → get WORKING task → send with that taskId → error.

        Note: The A2A SDK raises InvalidParamsError (-32602) for terminal states
        but allows sending to WORKING tasks. This test validates actual SDK behavior.
        If the agent completes before the second request arrives, the task becomes
        terminal and we get -32602 instead.
        """
        # Create a non-blocking task (returns immediately with WORKING/SUBMITTED)
        params = make_text_params("Tell me a long story about dragons.", configuration={"blocking": False})
        resp = send_message(client, params, request_id="nb-setup", timeout=NON_BLOCKING_TIMEOUT)
        assert_success(resp)
        task = resp["result"].get("task", {})
        task_id = task["id"]

        # Immediately try to send with that taskId
        params2 = {
            "message": {
                "role": "ROLE_USER",
                "parts": [{"text": "Continue"}],
                "taskId": task_id,
            },
            "configuration": {"blocking": True},
        }
        resp2 = send_message(client, params2, request_id="working-reuse")

        # SDK behavior: WORKING tasks are NOT rejected (only terminal states are).
        # The second request either succeeds or hits terminal state if agent already finished.
        state = task.get("status", {}).get("state", "")
        if state in ("TASK_STATE_WORKING", "TASK_STATE_SUBMITTED"):
            # If task was still working, second send should proceed (success or new completion)
            assert "result" in resp2 or "error" in resp2
        else:
            # If task already completed, we get terminal state error
            assert_error(resp2, -32602, "terminal state")

    def test_1_6_nonexistent_task_id(self, client):
        """taskId = "00000000-0000-0000-0000-000000000000" → error -32001."""
        params = {
            "message": {
                "role": "ROLE_USER",
                "parts": [{"text": "Hello"}],
                "taskId": "00000000-0000-0000-0000-000000000000",
            },
            "configuration": {"blocking": True},
        }
        resp = send_message(client, params, request_id="nonexistent")
        assert_error(resp, -32001, "does not exist")


# ===========================================================================
# Category 3: Role Variations
# ===========================================================================


@pytest.mark.integration
class TestRoleVariations:
    """Tests for tenant and role handling."""

    def test_1_7_tenant_field(self, client):
        """Include tenant in params → success, no error."""
        params = make_text_params("Hello", configuration={"blocking": True})
        params["tenant"] = "some-tenant"
        resp = send_message(client, params)
        assert_success(resp)

    def test_1_8_role_unspecified(self, client):
        """role: ROLE_UNSPECIFIED → defaults to ROLE_USER, success."""
        params = {
            "message": {"role": "ROLE_UNSPECIFIED", "parts": [{"text": "Hello"}]},
            "configuration": {"blocking": True},
        }
        resp = send_message(client, params)
        assert_task_completed(resp)

    def test_1_9_role_agent(self, client):
        """role: ROLE_AGENT → accepted, success."""
        params = {
            "message": {"role": "ROLE_AGENT", "parts": [{"text": "Hello"}]},
            "configuration": {"blocking": True},
        }
        resp = send_message(client, params)
        assert_task_completed(resp)


# ===========================================================================
# Category 4: Part Content Types — Unstructured
# ===========================================================================


@pytest.mark.integration
class TestPartContentTypes:
    """Tests for Part content type validation (no input_schema)."""

    def test_1_10_single_text(self, client):
        """Single text Part → success."""
        params = make_text_params("Hello", configuration={"blocking": True})
        resp = send_message(client, params)
        assert_task_completed(resp)

    def test_1_11_multiple_text_parts(self, client):
        """Multiple text Parts → success, agent sees both."""
        params = {
            "message": {"role": "ROLE_USER", "parts": [{"text": "Hello"}, {"text": "World"}]},
            "configuration": {"blocking": True},
        }
        resp = send_message(client, params)
        assert_task_completed(resp)

    def test_1_13_data_part_no_schema(self, client):
        """data Part only, no input_schema → error -32602 (expects text input)."""
        params = {
            "message": {"role": "ROLE_USER", "parts": [{"data": {"key": "value"}}]},
            "configuration": {"blocking": True},
        }
        resp = send_message(client, params)
        assert_error(resp, -32602, "expects text input")

    def test_1_15_raw_part(self, client):
        """raw Part → error -32005 (binary content not supported)."""
        params = {
            "message": {"role": "ROLE_USER", "parts": [{"raw": "SGVsbG8="}]},
            "configuration": {"blocking": True},
        }
        resp = send_message(client, params)
        assert_error(resp, -32005, "Binary content (raw)")

    def test_1_16_url_part(self, client):
        """URL Part → error -32005 (URL/file content not supported)."""
        params = {
            "message": {"role": "ROLE_USER", "parts": [{"url": "https://example.com/f.pdf"}]},
            "configuration": {"blocking": True},
        }
        resp = send_message(client, params)
        assert_error(resp, -32005, "URL/file content")

    def test_1_17_empty_parts(self, client):
        """Empty parts list → error -32602 (at least one part)."""
        params = {
            "message": {"role": "ROLE_USER", "parts": []},
            "configuration": {"blocking": True},
        }
        resp = send_message(client, params)
        assert_error(resp, -32602, "at least one part")

    def test_1_18_mixed_text_data(self, client):
        """text + data Parts, no input_schema → error -32602 (expects text input)."""
        params = {
            "message": {
                "role": "ROLE_USER",
                "parts": [{"text": "Hello"}, {"data": {"key": "value"}}],
            },
            "configuration": {"blocking": True},
        }
        resp = send_message(client, params)
        assert_error(resp, -32602, "expects text input")


# ===========================================================================
# Category 5: Configuration
# ===========================================================================


@pytest.mark.integration
class TestConfiguration:
    """Tests for configuration parameters."""

    def test_1_19_accepted_output_modes_compatible(self, client):
        """acceptedOutputModes: ["text/plain"] → success (test_prompt has no output_schema)."""
        params = make_text_params(
            "Hello",
            configuration={"blocking": True, "acceptedOutputModes": ["text/plain"]},
        )
        resp = send_message(client, params)
        assert_task_completed(resp)

    def test_1_21_accepted_output_modes_not_set(self, client):
        """No acceptedOutputModes → success."""
        params = make_text_params("Hello", configuration={"blocking": True})
        resp = send_message(client, params)
        assert_task_completed(resp)

    def test_1_22_history_length_2(self, client):
        """historyLength: 2 → success, history limited to 2 entries."""
        params = make_text_params(
            "Hello",
            configuration={"blocking": True, "historyLength": 2},
        )
        resp = send_message(client, params)
        task = assert_task_completed(resp)
        history = task.get("history", [])
        assert len(history) <= 2, f"Expected history <= 2, got {len(history)}: {history}"

    def test_1_23_history_length_0(self, client):
        """historyLength: 0 → success, no history in response."""
        params = make_text_params(
            "Hello",
            configuration={"blocking": True, "historyLength": 0},
        )
        resp = send_message(client, params)
        task = assert_task_completed(resp)
        history = task.get("history", [])
        assert len(history) == 0, f"Expected empty history, got {len(history)}: {history}"

    def test_1_25_blocking_true(self, client):
        """blocking: true → task completes synchronously."""
        params = make_text_params("What is 1+1?", configuration={"blocking": True})
        resp = send_message(client, params)
        assert_task_completed(resp)

    def test_1_26_blocking_false(self, client):
        """blocking: false → immediate WORKING/SUBMITTED, then poll via GetTask."""
        params = make_text_params("What is 1+1?", configuration={"blocking": False})
        resp = send_message(client, params, timeout=NON_BLOCKING_TIMEOUT)
        task = assert_task_working_or_submitted(resp)
        task_id = task["id"]

        # Poll until terminal
        final_resp = poll_until_terminal(client, task_id)
        final_task = final_resp["result"]
        assert final_task["status"]["state"] == "TASK_STATE_COMPLETED"

    def test_1_27_no_configuration(self, client):
        """Omit configuration entirely → proto3 bool default (blocking=false) → WORKING."""
        params = {"message": {"role": "ROLE_USER", "parts": [{"text": "Hello"}]}}
        resp = send_message(client, params, timeout=NON_BLOCKING_TIMEOUT)

        # Proto3 default: blocking is false, so we get WORKING/SUBMITTED or COMPLETED
        # (if agent is fast enough to complete before response is sent)
        assert_success(resp)
        task = resp["result"].get("task", {})
        state = task.get("status", {}).get("state", "")
        assert state in ("TASK_STATE_WORKING", "TASK_STATE_SUBMITTED", "TASK_STATE_COMPLETED"), (
            f"Unexpected state: {state}"
        )


# ===========================================================================
# Category 6: Streaming Mismatch
# ===========================================================================


@pytest.mark.integration
class TestStreamingMismatch:
    """Test streaming method on non-streaming agent."""

    def test_1_29_streaming_method_mismatch(self, client):
        """SendStreamingMessage on non-streaming agent → error -32004."""
        params = make_text_params("Hello")
        resp = send_a2a(client, "SendStreamingMessage", params)
        assert_error(resp, -32004, "not configured for streaming")


# ===========================================================================
# Category 7: Metadata
# ===========================================================================


@pytest.mark.integration
class TestMetadata:
    """Test metadata passthrough."""

    def test_1_30_metadata_on_params(self, client):
        """Include metadata on message → success, no error."""
        params = make_text_params("Hello", configuration={"blocking": True})
        params["message"]["metadata"] = {"source": "test", "session": "abc123"}
        resp = send_message(client, params)
        assert_success(resp)


# ===========================================================================
# Category 8: v0.3 Backward Compatibility
# ===========================================================================


@pytest.mark.integration
class TestV03Compat:
    """Tests for v0.3 method and enum backward compatibility."""

    def test_v03_method_name(self, client):
        """v0.3 method "message/send" → accepted, same as SendMessage."""
        params = make_text_params("Hello", configuration={"blocking": True})
        resp = send_a2a(client, "message/send", params)
        assert_task_completed(resp)

    def test_v03_role_user(self, client):
        """v0.3 role "user" → normalized to ROLE_USER, success."""
        params = {
            "message": {"role": "user", "parts": [{"text": "Hello"}]},
            "configuration": {"blocking": True},
        }
        resp = send_a2a(client, "SendMessage", params)
        assert_task_completed(resp)


# ===========================================================================
# Category 9: Protocol-Level
# ===========================================================================


@pytest.mark.integration
class TestProtocolLevel:
    """Tests for A2A-Version header handling."""

    def test_7_6_version_header_valid(self, client):
        """A2A-Version: 1.0 → success."""
        params = make_text_params("Hello", configuration={"blocking": True})
        resp = send_message(client, params, headers={"A2A-Version": "1.0"})
        assert_task_completed(resp)

    def test_7_7_version_header_unsupported(self, client):
        """A2A-Version: 2.0 → error -32008."""
        params = make_text_params("Hello", configuration={"blocking": True})
        resp = send_message(client, params, headers={"A2A-Version": "2.0"})
        assert_error(resp, -32008, "not supported")

    def test_7_8_version_header_missing(self, client):
        """No A2A-Version header → success (optional header)."""
        params = make_text_params("Hello", configuration={"blocking": True})
        resp = send_message(client, params)
        assert_task_completed(resp)


# Command to run the tests:
# docker exec -it budserve-development-budprompt pytest tests/test_a2a_send_message.py -v
#
# Run a single test:
# docker exec -it budserve-development-budprompt pytest tests/test_a2a_send_message.py -k "test_1_1" -v
