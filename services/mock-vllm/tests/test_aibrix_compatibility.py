#!/usr/bin/env python3
"""Test AIBrix compatibility of mock vLLM deployments."""

import json
import subprocess
import sys
from typing import Dict, List


def run_kubectl(cmd: str) -> str:
    """Run kubectl command and return output."""
    result = subprocess.run(
        f"kubectl {cmd}",
        shell=True,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Error running kubectl: {result.stderr}")
        return ""
    return result.stdout


def test_model_labels(namespace: str = "aibrix-models") -> bool:
    """Test if models have correct AIBrix labels."""
    print("\n🔍 Testing Model Labels...")
    
    # Get deployments with AIBrix labels
    output = run_kubectl(
        f"get deployments -n {namespace} -l model.aibrix.ai/name -o json"
    )
    
    if not output:
        print("❌ No deployments found with AIBrix labels")
        return False
    
    data = json.loads(output)
    deployments = data.get("items", [])
    
    if not deployments:
        print("❌ No deployments found")
        return False
    
    all_valid = True
    for deploy in deployments:
        name = deploy["metadata"]["name"]
        labels = deploy["metadata"]["labels"]
        
        # Check required labels
        model_name = labels.get("model.aibrix.ai/name")
        model_port = labels.get("model.aibrix.ai/port")
        
        if model_name != name:
            print(f"❌ {name}: model.aibrix.ai/name ({model_name}) doesn't match deployment name")
            all_valid = False
        elif not model_port:
            print(f"❌ {name}: missing model.aibrix.ai/port label")
            all_valid = False
        else:
            print(f"✅ {name}: labels valid (name={model_name}, port={model_port})")
    
    return all_valid


def test_service_configuration(namespace: str = "aibrix-models") -> bool:
    """Test if services are configured correctly for AIBrix."""
    print("\n🔍 Testing Service Configuration...")
    
    # Get services with AIBrix labels
    output = run_kubectl(
        f"get services -n {namespace} -l model.aibrix.ai/name -o json"
    )
    
    if not output:
        print("❌ No services found with AIBrix labels")
        return False
    
    data = json.loads(output)
    services = data.get("items", [])
    
    all_valid = True
    for svc in services:
        name = svc["metadata"]["name"]
        labels = svc["metadata"]["labels"]
        selector = svc["spec"]["selector"]
        
        # Check service name matches label
        model_name = labels.get("model.aibrix.ai/name")
        if model_name != name:
            print(f"❌ {name}: service name doesn't match model.aibrix.ai/name label")
            all_valid = False
            continue
        
        # Check selector
        selector_name = selector.get("model.aibrix.ai/name")
        if selector_name != name:
            print(f"❌ {name}: selector doesn't match service name")
            all_valid = False
            continue
        
        # Check port
        ports = svc["spec"]["ports"]
        if not ports or ports[0]["port"] != 8000:
            print(f"❌ {name}: port is not 8000")
            all_valid = False
        else:
            print(f"✅ {name}: service configuration valid")
    
    return all_valid


def test_endpoint_health(namespace: str = "aibrix-models") -> bool:
    """Test if model endpoints are healthy."""
    print("\n🔍 Testing Endpoint Health...")
    
    # Get all model services
    output = run_kubectl(
        f"get services -n {namespace} -l model.aibrix.ai/name -o json"
    )
    
    if not output:
        print("❌ No services found")
        return False
    
    data = json.loads(output)
    services = data.get("items", [])
    
    all_healthy = True
    for svc in services:
        name = svc["metadata"]["name"]
        
        # Test health endpoint
        health_cmd = f"run test-health-{name} --rm -it --restart=Never " \
                    f"--namespace={namespace} --image=curlimages/curl:latest " \
                    f"-- curl -s -f http://{name}:8000/health"
        
        result = subprocess.run(
            f"kubectl {health_cmd}",
            shell=True,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✅ {name}: health check passed")
        else:
            print(f"❌ {name}: health check failed")
            all_healthy = False
    
    return all_healthy


def test_model_responses(namespace: str = "aibrix-models") -> bool:
    """Test if models return valid responses."""
    print("\n🔍 Testing Model Responses...")
    
    # Get all model services
    output = run_kubectl(
        f"get services -n {namespace} -l model.aibrix.ai/name -o jsonpath='{{.items[*].metadata.name}}'"
    )
    
    if not output:
        print("❌ No services found")
        return False
    
    models = output.strip().split()
    all_valid = True
    
    for model in models:
        # Test chat completion
        test_cmd = f"""run test-chat-{model} --rm -it --restart=Never \
            --namespace={namespace} --image=curlimages/curl:latest \
            -- curl -s -X POST http://{model}:8000/v1/chat/completions \
            -H 'Content-Type: application/json' \
            -d '{{"model": "{model}", "messages": [{{"role": "user", "content": "test"}}]}}'"""
        
        result = subprocess.run(
            f"kubectl {test_cmd}",
            shell=True,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 and '"object":"chat.completion"' in result.stdout:
            print(f"✅ {model}: chat completion working")
        else:
            print(f"❌ {model}: chat completion failed")
            all_valid = False
    
    return all_valid


def main():
    """Run all AIBrix compatibility tests."""
    print("=" * 60)
    print("AIBrix Compatibility Tests for Mock vLLM")
    print("=" * 60)
    
    # Check if namespace exists
    namespace = "aibrix-models"
    ns_check = run_kubectl(f"get namespace {namespace}")
    if not ns_check:
        print(f"❌ Namespace '{namespace}' not found")
        print("\nPlease deploy mock vLLM models first:")
        print("./scripts/deploy/deploy-mock-vllm-aibrix.sh --enable-models llama-2-7b-chat,gpt-4")
        return 1
    
    # Run tests
    tests = [
        ("Model Labels", test_model_labels),
        ("Service Configuration", test_service_configuration),
        ("Endpoint Health", test_endpoint_health),
        ("Model Responses", test_model_responses),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func(namespace)
            results.append((test_name, passed))
        except Exception as e:
            print(f"❌ {test_name}: Exception - {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All AIBrix compatibility tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())