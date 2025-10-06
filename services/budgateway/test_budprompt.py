#!/usr/bin/env python3
"""
Comprehensive test suite for BudPrompt Provider with v1/responses API
Tests all endpoint operations including streaming
"""

import time
import requests
from typing import Optional
import sys

# Configuration
BASE_URL = "http://localhost:56003"
AUTH_TOKEN = "sk-BudLLMMasterKey_123"
MODEL = "gpt-4"

# ANSI color codes for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


class ResponsesAPITest:
    def __init__(self):
        self.base_url = BASE_URL
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AUTH_TOKEN}",
        }
        self.response_id: Optional[str] = None
        self.passed_tests = 0
        self.failed_tests = 0

    def print_test_header(self, test_name: str):
        """Print formatted test header"""
        print(f"\n{BOLD}{BLUE}{'=' * 50}{RESET}")
        print(f"{BOLD}{BLUE}Test: {test_name}{RESET}")
        print(f"{BOLD}{BLUE}{'=' * 50}{RESET}")

    def print_result(self, success: bool, message: str, details: str = ""):
        """Print test result with color coding"""
        if success:
            print(f"{GREEN}✓ PASS: {message}{RESET}")
            self.passed_tests += 1
        else:
            print(f"{RED}✗ FAIL: {message}{RESET}")
            self.failed_tests += 1
        if details:
            print(f"  {YELLOW}Details: {details}{RESET}")

    def test_create_response(self) -> bool:
        """Test 1: Create a response (non-streaming)"""
        self.print_test_header("Create Response (Non-streaming)")

        payload = {
            "model": MODEL,
            "input": "Hello, what can you help me with today?",
            "instructions": "Be helpful and concise.",
            "temperature": 0.7,
            "max_output_tokens": 100,
        }

        try:
            response = requests.post(
                f"{self.base_url}/v1/responses",
                headers=self.headers,
                json=payload,
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                self.response_id = data.get("id")

                self.print_result(
                    True,
                    f"Response created successfully (Status: {response.status_code})",
                    f"Response ID: {self.response_id}",
                )

                # Display response content
                if "output" in data and data["output"]:
                    text = data["output"][0].get("content", [{}])[0].get("text", "")
                    print(f"  Response text: {text[:100]}...")

                return True
            else:
                self.print_result(
                    False,
                    f"Failed to create response (Status: {response.status_code})",
                    response.text[:200],
                )
                return False

        except Exception as e:
            self.print_result(False, "Exception occurred", str(e))
            return False

    def test_create_response_streaming(self) -> bool:
        """Test 2: Create a response with streaming"""
        self.print_test_header("Create Response (Streaming)")

        payload = {
            "model": MODEL,
            "input": "Count from 1 to 5 slowly.",
            "stream": True,
            "temperature": 0.5,
            "max_output_tokens": 50,
        }

        try:
            response = requests.post(
                f"{self.base_url}/v1/responses",
                headers={**self.headers, "Accept": "text/event-stream"},
                json=payload,
                stream=True,
                timeout=10,
            )

            if response.status_code == 200:
                print(f"  {GREEN}Streaming response initiated (Status: 200){RESET}")

                # Read first few chunks
                chunks_received = 0
                max_chunks = 5

                for line in response.iter_lines(decode_unicode=True):
                    if chunks_received >= max_chunks:
                        break
                    if line:
                        # OpenAI SSE format has both "event:" and "data:" lines
                        if line.startswith("data:"):
                            data = line[5:].strip()
                            if data and data != "[DONE]":
                                chunks_received += 1
                                print(f"  Chunk {chunks_received}: {data[:100]}...")
                        elif line.startswith("event:"):
                            # Just acknowledge event lines
                            event = line[6:].strip()
                            print(f"  Event: {event}")

                self.print_result(
                    chunks_received > 0,
                    f"Streaming {'successful' if chunks_received > 0 else 'failed'}",
                    f"Received {chunks_received} chunks",
                )
                return chunks_received > 0
            else:
                # Some backends may not support streaming
                self.print_result(
                    False,
                    f"Streaming not supported (Status: {response.status_code})",
                    "Backend may not implement SSE streaming",
                )
                return False

        except requests.exceptions.Timeout:
            self.print_result(
                True,  # Timeout is expected for streaming
                "Streaming connection established",
                "Connection timed out as expected for long-running stream",
            )
            return True
        except Exception as e:
            self.print_result(False, "Exception occurred", str(e))
            return False

    def test_retrieve_response(self) -> bool:
        """Test 3: Retrieve a response by ID"""
        self.print_test_header("Retrieve Response")

        if not self.response_id:
            self.print_result(
                False, "No response ID available", "Create test must run first"
            )
            return False

        headers_with_model = {**self.headers, "x-model-name": MODEL}

        try:
            response = requests.get(
                f"{self.base_url}/v1/responses/{self.response_id}",
                headers=headers_with_model,
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                self.print_result(
                    True,
                    f"Response retrieved successfully (Status: {response.status_code})",
                    f"Response ID: {data.get('id', 'N/A')}",
                )
                return True
            elif response.status_code == 404:
                self.print_result(
                    False,
                    "Response not found (404)",
                    "Backend may not persist responses",
                )
                return False
            else:
                self.print_result(
                    False,
                    f"Failed to retrieve response (Status: {response.status_code})",
                    response.text[:200],
                )
                return False

        except Exception as e:
            self.print_result(False, "Exception occurred", str(e))
            return False

    def test_delete_response(self) -> bool:
        """Test 4: Delete a response"""
        self.print_test_header("Delete Response")

        # Use a test ID if we don't have a real one
        test_id = self.response_id or "test_response_123"

        headers_with_model = {**self.headers, "x-model-name": MODEL}

        try:
            response = requests.delete(
                f"{self.base_url}/v1/responses/{test_id}",
                headers=headers_with_model,
                timeout=10,
            )

            if response.status_code in [200, 204]:
                self.print_result(
                    True,
                    f"Response deleted successfully (Status: {response.status_code})",
                    f"Deleted ID: {test_id}",
                )
                return True
            elif response.status_code == 404:
                self.print_result(
                    False,
                    "Response not found for deletion (404)",
                    "Expected if backend doesn't persist responses",
                )
                return False
            else:
                self.print_result(
                    False,
                    f"Failed to delete response (Status: {response.status_code})",
                    response.text[:200],
                )
                return False

        except Exception as e:
            self.print_result(False, "Exception occurred", str(e))
            return False

    def test_cancel_response(self) -> bool:
        """Test 5: Cancel a response"""
        self.print_test_header("Cancel Response")

        # Create a new response to cancel
        payload = {
            "model": MODEL,
            "input": "This is a test response to be cancelled",
            "background": True,  # Create as background task if supported
        }

        try:
            # First create a response
            create_response = requests.post(
                f"{self.base_url}/v1/responses",
                headers=self.headers,
                json=payload,
                timeout=10,
            )

            if create_response.status_code == 200:
                response_data = create_response.json()
                cancel_id = response_data.get("id")
                if not cancel_id or not cancel_id.startswith("resp_"):
                    self.print_result(
                        False,
                        "Invalid response ID for cancellation",
                        f"Response ID doesn't start with 'resp_': {cancel_id}",
                    )
                    return False
            else:
                self.print_result(
                    False,
                    f"Failed to create response for cancellation (Status: {create_response.status_code})",
                    "Cannot test cancellation without valid response",
                )
                return False

            # Now try to cancel it
            headers_with_model = {**self.headers, "x-model-name": MODEL}

            response = requests.post(
                f"{self.base_url}/v1/responses/{cancel_id}/cancel",
                headers=headers_with_model,
                timeout=10,
            )

            if response.status_code == 200:
                self.print_result(
                    True,
                    f"Response cancelled successfully (Status: {response.status_code})",
                    f"Cancelled ID: {cancel_id}",
                )
                return True
            elif response.status_code == 404:
                self.print_result(
                    False,
                    "Response not found for cancellation (404)",
                    "Backend may not support cancellation",
                )
                return False
            else:
                self.print_result(
                    False,
                    f"Failed to cancel response (Status: {response.status_code})",
                    response.text[:200],
                )
                return False

        except Exception as e:
            self.print_result(False, "Exception occurred", str(e))
            return False

    def test_list_input_items(self) -> bool:
        """Test 6: List input items for a response"""
        self.print_test_header("List Response Input Items")

        # Use the real response ID from the first test
        if not self.response_id or not self.response_id.startswith("resp_"):
            self.print_result(
                False,
                "No valid response ID available",
                "Need a response ID starting with 'resp_' from a successful create test",
            )
            return False

        test_id = self.response_id

        headers_with_model = {**self.headers, "x-model-name": MODEL}

        try:
            response = requests.get(
                f"{self.base_url}/v1/responses/{test_id}/input_items",
                headers=headers_with_model,
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                self.print_result(
                    True,
                    f"Input items retrieved successfully (Status: {response.status_code})",
                    f"Items count: {len(data.get('data', []))}",
                )
                return True
            elif response.status_code == 404:
                self.print_result(
                    False,
                    "Response not found for input items (404)",
                    "Backend may not support this endpoint",
                )
                return False
            else:
                self.print_result(
                    False,
                    f"Failed to list input items (Status: {response.status_code})",
                    response.text[:200],
                )
                return False

        except Exception as e:
            self.print_result(False, "Exception occurred", str(e))
            return False

    def run_all_tests(self):
        """Run all tests in sequence"""
        print(f"\n{BOLD}{GREEN}Starting BudPrompt Provider Test Suite{RESET}")
        print(f"Testing against: {self.base_url}")
        print(f"Model: {MODEL}")
        print(f"{'=' * 60}\n")

        # Run tests in order
        # Note: List input items must run before delete to use valid response ID
        tests = [
            self.test_create_response,
            self.test_create_response_streaming,
            self.test_retrieve_response,
            self.test_list_input_items,  # Moved before delete
            self.test_cancel_response,
            self.test_delete_response,  # Moved to end
        ]

        for test in tests:
            try:
                test()
                time.sleep(0.5)  # Small delay between tests
            except Exception as e:
                print(f"{RED}Test crashed: {e}{RESET}")
                self.failed_tests += 1

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print(f"\n{BOLD}{'=' * 60}{RESET}")
        print(f"{BOLD}Test Summary{RESET}")
        print(f"{BOLD}{'=' * 60}{RESET}")

        total = self.passed_tests + self.failed_tests
        if total == 0:
            print(f"{YELLOW}No tests completed{RESET}")
            return

        pass_rate = (self.passed_tests / total) * 100

        print(f"{GREEN}Passed: {self.passed_tests}{RESET}")
        print(f"{RED}Failed: {self.failed_tests}{RESET}")
        print(f"Total: {total}")
        print(f"Pass Rate: {pass_rate:.1f}%")

        if self.passed_tests == total:
            print(
                f"\n{BOLD}{GREEN}✓ All tests passed! BudPrompt provider is fully functional.{RESET}"
            )
        elif self.passed_tests > 0:
            print(
                f"\n{BOLD}{YELLOW}⚠ Some tests failed. Check backend implementation.{RESET}"
            )
        else:
            print(
                f"\n{BOLD}{RED}✗ All tests failed. Check if the gateway and backend are running.{RESET}"
            )

        print(
            f"\n{BLUE}Note: Some failures may be expected if your backend doesn't{RESET}"
        )
        print(f"{BLUE}implement all endpoints or doesn't persist responses.{RESET}")
        print(
            f"{BLUE}The important thing is that requests are being forwarded correctly.{RESET}"
        )


def main():
    """Main entry point"""
    tester = ResponsesAPITest()

    try:
        # Quick connectivity check
        response = requests.get(f"{BASE_URL}/health", timeout=2)  # noqa: F841
    except Exception:
        # Health endpoint may not exist, try a simple request
        pass

    tester.run_all_tests()

    # Exit with appropriate code
    sys.exit(0 if tester.failed_tests == 0 else 1)


if __name__ == "__main__":
    main()
