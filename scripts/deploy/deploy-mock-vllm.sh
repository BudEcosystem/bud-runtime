#!/bin/bash
# deploy-mock-vllm.sh - Deploy mock vLLM service to the inference cluster

set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source common utilities
source "$SCRIPT_DIR/../multi-cluster/utils/common.sh"

# Default values
CLUSTER_NAME="${INFERENCE_CLUSTER_NAME:-bud-inference}"
NAMESPACE="${MOCK_VLLM_NAMESPACE:-vllm-system}"
RELEASE_NAME="${MOCK_VLLM_RELEASE:-mock-vllm}"
HELM_CHART="$PROJECT_ROOT/helm/mock-vllm"
BUILD_IMAGE="${BUILD_IMAGE:-true}"
IMAGE_REGISTRY="${REGISTRY_NAME:-bud-registry}"
IMAGE_REGISTRY_PORT="${REGISTRY_PORT:-5111}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
API_KEY="${MOCK_VLLM_API_KEY:-}"
PROCESSING_DELAY="${MOCK_PROCESSING_DELAY:-0.1}"
VALUES_FILE=""
DRY_RUN=false

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
        --build-image)
            BUILD_IMAGE="$2"
            shift 2
            ;;
        --image-tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --api-key)
            API_KEY="$2"
            shift 2
            ;;
        --processing-delay)
            PROCESSING_DELAY="$2"
            shift 2
            ;;
        --values-file)
            VALUES_FILE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --cluster-name NAME         Target cluster name (default: $CLUSTER_NAME)"
            echo "  --namespace NS              Kubernetes namespace (default: $NAMESPACE)"
            echo "  --release-name NAME         Helm release name (default: $RELEASE_NAME)"
            echo "  --build-image true|false    Build and push Docker image (default: $BUILD_IMAGE)"
            echo "  --image-tag TAG             Docker image tag (default: $IMAGE_TAG)"
            echo "  --api-key KEY               API key for authentication (optional)"
            echo "  --processing-delay SECONDS  Mock processing delay (default: $PROCESSING_DELAY)"
            echo "  --values-file FILE          Additional Helm values file (optional)"
            echo "  --dry-run                   Show what would be done without executing"
            echo "  --help                      Show this help message"
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

# Build and push Docker image
build_and_push_image() {
    if [[ "$BUILD_IMAGE" != "true" ]]; then
        log_info "Skipping image build (--build-image=false)"
        return 0
    fi
    
    log_info "Building mock vLLM Docker image..."
    
    # Check if registry is running
    if ! docker ps | grep -q "$IMAGE_REGISTRY"; then
        log_error "Registry '$IMAGE_REGISTRY' is not running. Please ensure the registry is started."
        exit 1
    fi
    
    local image_name="localhost:$IMAGE_REGISTRY_PORT/mock-vllm:$IMAGE_TAG"
    
    # Build image
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would build image: $image_name"
    else
        cd "$PROJECT_ROOT/services/mock-vllm"
        docker build -t "$image_name" .
        
        # Push to local registry
        log_info "Pushing image to local registry..."
        docker push "$image_name"
        
        cd - >/dev/null
    fi
    
    log_success "Image built and pushed: $image_name"
}

# Deploy mock vLLM using Helm
deploy_mock_vllm() {
    log_info "Deploying mock vLLM to namespace: $NAMESPACE"
    
    # Create namespace if it doesn't exist
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would create namespace: $NAMESPACE"
    else
        create_namespace_if_not_exists "$NAMESPACE" "k3d-$CLUSTER_NAME"
    fi
    
    # Prepare Helm values
    local helm_args=(
        "--namespace" "$NAMESPACE"
        "--set" "image.repository=k3d-$IMAGE_REGISTRY:$IMAGE_REGISTRY_PORT/mock-vllm"
        "--set" "image.tag=$IMAGE_TAG"
        "--set" "config.processingDelay=$PROCESSING_DELAY"
    )
    
    # Add API key if provided
    if [[ -n "$API_KEY" ]]; then
        helm_args+=("--set" "config.apiKey=$API_KEY")
    fi
    
    # Add custom values file if provided
    if [[ -n "$VALUES_FILE" ]] && [[ -f "$VALUES_FILE" ]]; then
        helm_args+=("--values" "$VALUES_FILE")
    fi
    
    # Add dry-run flag if needed
    if [[ "$DRY_RUN" == "true" ]]; then
        helm_args+=("--dry-run" "--debug")
    fi
    
    # Deploy using Helm
    log_info "Installing/upgrading mock vLLM..."
    helm upgrade --install "$RELEASE_NAME" "$HELM_CHART" \
        "${helm_args[@]}" \
        --wait \
        --timeout 5m
    
    if [[ "$DRY_RUN" != "true" ]]; then
        log_success "Mock vLLM deployed successfully!"
        
        # Show deployment status
        echo
        log_info "Deployment status:"
        kubectl get all -n "$NAMESPACE" -l "app.kubernetes.io/name=mock-vllm"
        
        # Show service endpoint
        echo
        log_info "Service endpoint:"
        local service_info=$(kubectl get svc -n "$NAMESPACE" "$RELEASE_NAME" -o json 2>/dev/null || echo "{}")
        local cluster_ip=$(echo "$service_info" | jq -r '.spec.clusterIP // "pending"')
        local port=$(echo "$service_info" | jq -r '.spec.ports[0].port // "8000"')
        
        log_info "Internal endpoint: http://$RELEASE_NAME.$NAMESPACE.svc.cluster.local:$port"
        log_info "Cluster IP: http://$cluster_ip:$port"
        
        # Show how to test
        echo
        log_info "To test the deployment:"
        log_info "1. Port forward: kubectl port-forward -n $NAMESPACE svc/$RELEASE_NAME 8000:$port"
        log_info "2. Test health: curl http://localhost:8000/health"
        log_info "3. List models: curl http://localhost:8000/v1/models"
    fi
}

# Create integration test job
create_test_job() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would create test job"
        return 0
    fi
    
    log_info "Creating integration test job..."
    
    cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: mock-vllm-test-$(date +%s)
  namespace: $NAMESPACE
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: test
        image: curlimages/curl:latest
        command:
        - sh
        - -c
        - |
          echo "Testing mock vLLM service..."
          
          # Test health endpoint
          echo "Testing /health endpoint..."
          curl -f http://$RELEASE_NAME:8000/health || exit 1
          echo
          
          # Test models endpoint
          echo "Testing /v1/models endpoint..."
          curl -f http://$RELEASE_NAME:8000/v1/models || exit 1
          echo
          
          # Test chat completion
          echo "Testing /v1/chat/completions endpoint..."
          curl -f -X POST http://$RELEASE_NAME:8000/v1/chat/completions \
            -H "Content-Type: application/json" \
            -d '{
              "model": "gpt-3.5-turbo",
              "messages": [{"role": "user", "content": "Hello"}]
            }' || exit 1
          echo
          
          echo "All tests passed!"
  backoffLimit: 1
EOF
    
    # Wait for job to complete
    log_info "Waiting for test job to complete..."
    kubectl wait --for=condition=complete job -n "$NAMESPACE" -l "job-name" --timeout=60s 2>/dev/null || true
    
    # Show job logs
    local job_name=$(kubectl get jobs -n "$NAMESPACE" --sort-by=.metadata.creationTimestamp -o json | jq -r '.items[-1].metadata.name')
    if [[ -n "$job_name" ]]; then
        echo
        log_info "Test job logs:"
        kubectl logs -n "$NAMESPACE" "job/$job_name"
    fi
}

# Main execution
main() {
    log_info "Mock vLLM Deployment Script"
    log_info "=========================="
    
    # Verify prerequisites
    verify_prerequisites || exit 1
    verify_cluster
    
    # Build and push image if requested
    build_and_push_image
    
    # Deploy mock vLLM
    deploy_mock_vllm
    
    # Run integration test if not dry-run
    if [[ "$DRY_RUN" != "true" ]]; then
        echo
        read -p "Run integration test job? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            create_test_job
        fi
    fi
    
    log_success "Deployment completed!"
}

# Run main function
main "$@"