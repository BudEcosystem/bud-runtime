"""Integration test to verify dynamic max-model-len feature works correctly."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_dynamic_max_model_len_logging():
    """Verify that dynamic max-model-len is correctly set in logs."""
    from budcluster.deployment.handler import DeploymentHandler
    from unittest.mock import patch
    import copy

    config = {
        "kubeconfig": "test-config",
        "cluster_name": "test-cluster"
    }

    handler = DeploymentHandler(config)

    node_list = [{
        "name": "test-node",
        "devices": [{
            "name": "test-device",
            "image": "test-image",
            "replica": 1,
            "memory": 32768,
            "type": "cuda",
            "tp_size": 1,
            "concurrency": 10,
            "args": {
                "model": "test-model",
                "port": 8000
            },
            "envs": {}
        }]
    }]

    test_cases = [
        # (input_tokens, output_tokens, expected_max_len, description)
        (4096, 2048, 6758, "Standard context"),
        (100000, 28000, 140800, "Large context (128k)"),
        (None, None, 8192, "No tokens (default)"),
        (4096, None, 8192, "Only input token (default)"),
        (None, 2048, 8192, "Only output token (default)"),
    ]

    for input_tokens, output_tokens, expected_max_len, description in test_cases:
        print(f"\nTesting: {description}")
        print(f"  Input tokens: {input_tokens}, Output tokens: {output_tokens}")
        print(f"  Expected max-model-len: {expected_max_len}")

        with patch("budcluster.deployment.handler.asyncio.run") as mock_run:
            mock_run.side_effect = [True, (True, "http://test-url")]

            # Capture logs to verify
            import logging
            import io

            log_capture = io.StringIO()
            handler_logger = logging.getLogger("budcluster.deployment.handler")
            log_handler = logging.StreamHandler(log_capture)
            log_handler.setLevel(logging.INFO)
            original_handlers = handler_logger.handlers[:]
            handler_logger.handlers = [log_handler]
            handler_logger.setLevel(logging.INFO)

            try:
                kwargs = {
                    "node_list": copy.deepcopy(node_list),
                    "endpoint_name": "test-endpoint",
                    "ingress_url": "http://test-ingress"
                }

                if input_tokens is not None:
                    kwargs["input_tokens"] = input_tokens
                if output_tokens is not None:
                    kwargs["output_tokens"] = output_tokens

                status, namespace, url, nodes, result = handler.deploy(**kwargs)

                # Check logs contain expected max-model-len
                log_contents = log_capture.getvalue()
                assert f"--max-model-len={expected_max_len}" in log_contents, \
                    f"Expected '--max-model-len={expected_max_len}' not found in logs for {description}"
                print(f"  ✓ Verified: --max-model-len={expected_max_len} in logs")

            finally:
                handler_logger.handlers = original_handlers

    print("\n✅ All test cases passed!")

if __name__ == "__main__":
    test_dynamic_max_model_len_logging()
