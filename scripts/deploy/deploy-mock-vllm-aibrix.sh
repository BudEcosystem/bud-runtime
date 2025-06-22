#!/bin/bash
# deploy-mock-vllm-aibrix.sh - Deploy mock vLLM models for AIBrix integration

set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source common utilities
source "$SCRIPT_DIR/../multi-cluster/utils/common.sh"

# Default values
CLUSTER_NAME="${INFERENCE_CLUSTER_NAME:-bud-inference}"
NAMESPACE="${AIBRIX_MODELS_NAMESPACE:-aibrix-models}"
RELEASE_NAME="${MOCK_VLLM_MODELS_RELEASE:-mock-vllm-models}"
HELM_CHART="$PROJECT_ROOT/helm/mock-vllm-models"
VALUES_FILE=""
DRY_RUN=false
ENABLED_MODELS=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --cluster-name)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --release-name)
            RELEASE_NAME="$2"
            shift 2
            ;;
        --values-file)
            VALUES_FILE="$2"
            shift 2
            ;;
        --enable-models)
            ENABLED_MODELS="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --cluster-name NAME      Target cluster name (default: $CLUSTER_NAME)"
            echo "  --namespace NS           Kubernetes namespace (default: $NAMESPACE)"
            echo "  --release-name NAME      Helm release name (default: $RELEASE_NAME)"
            echo "  --values-file FILE       Additional Helm values file (optional)"
            echo "  --enable-models MODELS   Comma-separated list of models to enable"
            echo "                          (e.g., 'llama-2-7b-chat,gpt-4,mistral-7b-instruct')"
            echo "  --dry-run               Show what would be done without executing"
            echo "  --help                  Show this help message"
            echo ""
            echo "Available models:"
            echo "  - llama-2-7b-chat     (Llama 2 7B Chat)"
            echo "  - gpt-4               (GPT-4)"
            echo "  - gpt-3.5-turbo       (GPT-3.5 Turbo)"
            echo "  - mistral-7b-instruct (Mistral 7B Instruct)"
            echo "  - deepseek-coder-6.7b (Deepseek Coder 6.7B)"
            echo "  - qwen-coder-1.5b     (Qwen 2.5 Coder 1.5B)"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Verify cluster exists
verify_cluster() {
    if ! k3d cluster list | grep -q "^$CLUSTER_NAME"; then
        log_error "Cluster '$CLUSTER_NAME' not found. Please run setup-inference-cluster.sh first."
        exit 1
    fi
    
    # Switch to cluster context
    kubectl config use-context "k3d-$CLUSTER_NAME" >/dev/null
    log_info "Using cluster: $CLUSTER_NAME"
}

# Deploy mock vLLM models using Helm
deploy_models() {
    log_info "Deploying mock vLLM models for AIBrix to namespace: $NAMESPACE"
    
    # Prepare Helm values
    local helm_args=(
        "--namespace" "$NAMESPACE"
        "--create-namespace"
        "--set" "global.namespace=$NAMESPACE"
    )
    
    # Add custom values file if provided
    if [[ -n "$VALUES_FILE" ]] && [[ -f "$VALUES_FILE" ]]; then
        helm_args+=("--values" "$VALUES_FILE")
    fi
    
    # Handle model selection
    if [[ -n "$ENABLED_MODELS" ]]; then
        # Create a custom values file for model selection
        local temp_values=$(mktemp)
        cat > "$temp_values" <<EOF
models:
EOF
        
        # Process enabled models
        IFS=',' read -ra MODELS <<< "$ENABLED_MODELS"
        local enabled_list=""
        for model in "${MODELS[@]}"; do
            model=$(echo "$model" | xargs)  # Trim whitespace
            enabled_list="$enabled_list,$model"
        done
        enabled_list="${enabled_list:1}"  # Remove leading comma
        
        # Update each model's enabled status
        for idx in 0 1 2 3 4 5; do
            local model_name=""
            case $idx in
                0) model_name="llama-2-7b-chat" ;;
                1) model_name="gpt-4" ;;
                2) model_name="gpt-3.5-turbo" ;;
                3) model_name="mistral-7b-instruct" ;;
                4) model_name="deepseek-coder-6.7b" ;;
                5) model_name="qwen-coder-1.5b" ;;
            esac
            
            if [[ ",$enabled_list," == *",$model_name,"* ]]; then
                log_info "Enabling model: $model_name"
                echo "  - name: $model_name" >> "$temp_values"
                echo "    enabled: true" >> "$temp_values"
                # Copy other settings from default values
                case $model_name in
                    "llama-2-7b-chat")
                        echo "    modelPath: meta-llama/Llama-2-7b-chat-hf" >> "$temp_values"
                        echo "    processingDelay: \"0.1\"" >> "$temp_values"
                        ;;
                    "gpt-4")
                        echo "    modelPath: openai/gpt-4" >> "$temp_values"
                        echo "    processingDelay: \"0.2\"" >> "$temp_values"
                        ;;
                    "gpt-3.5-turbo")
                        echo "    modelPath: openai/gpt-3.5-turbo" >> "$temp_values"
                        echo "    processingDelay: \"0.1\"" >> "$temp_values"
                        ;;
                    "mistral-7b-instruct")
                        echo "    modelPath: mistralai/Mistral-7B-Instruct-v0.2" >> "$temp_values"
                        echo "    processingDelay: \"0.15\"" >> "$temp_values"
                        ;;
                    "deepseek-coder-6.7b")
                        echo "    modelPath: deepseek-ai/deepseek-coder-6.7b-instruct" >> "$temp_values"
                        echo "    processingDelay: \"0.15\"" >> "$temp_values"
                        ;;
                    "qwen-coder-1.5b")
                        echo "    modelPath: Qwen/Qwen2.5-Coder-1.5B-Instruct" >> "$temp_values"
                        echo "    processingDelay: \"0.08\"" >> "$temp_values"
                        ;;
                esac
                echo "    replicas: 1" >> "$temp_values"
                echo "    resources:" >> "$temp_values"
                echo "      requests:" >> "$temp_values"
                echo "        cpu: 100m" >> "$temp_values"
                echo "        memory: 256Mi" >> "$temp_values"
                echo "      limits:" >> "$temp_values"
                echo "        cpu: 500m" >> "$temp_values"
                echo "        memory: 512Mi" >> "$temp_values"
            else
                echo "  - name: $model_name" >> "$temp_values"
                echo "    enabled: false" >> "$temp_values"
            fi
        done
        
        helm_args+=("--values" "$temp_values")
        
        # Clean up temp file after helm command
        trap "rm -f $temp_values" EXIT
    fi
    
    # Add dry-run flag if needed
    if [[ "$DRY_RUN" == "true" ]]; then
        helm_args+=("--dry-run" "--debug")
    fi
    
    # Deploy using Helm
    log_info "Installing/upgrading mock vLLM models..."
    helm upgrade --install "$RELEASE_NAME" "$HELM_CHART" \
        "${helm_args[@]}" \
        --wait \
        --timeout 5m
    
    if [[ "$DRY_RUN" != "true" ]]; then
        log_success "Mock vLLM models deployed successfully!"
        
        # Show deployment status
        echo
        log_info "Deployment status:"
        kubectl get all -n "$NAMESPACE" -l "model.aibrix.ai/name"
        
        # Show available models
        echo
        log_info "Available models:"
        kubectl get services -n "$NAMESPACE" -l "model.aibrix.ai/name" -o custom-columns=MODEL:.metadata.name,ENDPOINT:.spec.clusterIP,PORT:.spec.ports[0].port
        
        # Show AIBrix discovery labels
        echo
        log_info "AIBrix model discovery labels:"
        kubectl get deployments -n "$NAMESPACE" -o json | jq -r '.items[] | select(.metadata.labels."model.aibrix.ai/name" != null) | "\(.metadata.name): model.aibrix.ai/name=\(.metadata.labels."model.aibrix.ai/name"), port=\(.metadata.labels."model.aibrix.ai/port")"'
    fi
}

# Test model endpoints
test_models() {
    if [[ "$DRY_RUN" == "true" ]]; then
        return 0
    fi
    
    log_info "Testing deployed models..."
    
    # Get list of deployed models
    local models=$(kubectl get services -n "$NAMESPACE" -l "model.aibrix.ai/name" -o jsonpath='{.items[*].metadata.name}')
    
    for model in $models; do
        echo
        log_info "Testing model: $model"
        
        # Test health endpoint
        kubectl run test-$model-$RANDOM --rm -it --restart=Never \
            --namespace="$NAMESPACE" \
            --image=curlimages/curl:latest \
            --command -- sh -c "
                echo 'Testing health endpoint...'
                curl -s http://$model:8000/health || echo 'Health check failed'
                echo
                echo 'Testing chat completion...'
                curl -s -X POST http://$model:8000/v1/chat/completions \
                    -H 'Content-Type: application/json' \
                    -d '{\"model\": \"$model\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}]}' \
                    | grep -q '\"object\":\"chat.completion\"' && echo '✓ Chat completion works' || echo '✗ Chat completion failed'
            " 2>/dev/null || log_warning "Test failed for model: $model"
    done
}

# Main execution
main() {
    log_info "Mock vLLM Models for AIBrix Deployment Script"
    log_info "============================================="
    
    # Verify prerequisites
    verify_prerequisites || exit 1
    verify_cluster
    
    # Deploy models
    deploy_models
    
    # Run tests if not dry-run
    if [[ "$DRY_RUN" != "true" ]]; then
        echo
        read -p "Run endpoint tests for deployed models? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            test_models
        fi
    fi
    
    log_success "Deployment completed!"
    
    if [[ "$DRY_RUN" != "true" ]]; then
        echo
        log_info "Next steps:"
        log_info "1. Deploy AIBrix to discover these models"
        log_info "2. Check AIBrix logs to verify model discovery"
        log_info "3. Use AIBrix API to route requests to these models"
    fi
}

# Run main function
main "$@"