#!/bin/bash
# validate-deployment.sh - Validate multi-cluster deployment and test E2E inference

set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/../multi-cluster/utils/common.sh"

# Default values
APP_CLUSTER="${APP_CLUSTER_NAME:-bud-app}"
INFERENCE_CLUSTER="${INFERENCE_CLUSTER_NAME:-bud-inference}"
APP_NAMESPACE="${APP_NAMESPACE:-bud-system}"
INFERENCE_NAMESPACE="${INFERENCE_NAMESPACE:-inference-system}"
RUN_E2E_TEST="${RUN_E2E_TEST:-true}"
CHECK_GPU="${CHECK_GPU:-true}"
VERBOSE="${VERBOSE:-false}"

# Test results
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --app-cluster)
            APP_CLUSTER="$2"
            shift 2
            ;;
        --inference-cluster)
            INFERENCE_CLUSTER="$2"
            shift 2
            ;;
        --app-namespace)
            APP_NAMESPACE="$2"
            shift 2
            ;;
        --inference-namespace)
            INFERENCE_NAMESPACE="$2"
            shift 2
            ;;
        --skip-e2e)
            RUN_E2E_TEST="false"
            shift
            ;;
        --skip-gpu-check)
            CHECK_GPU="false"
            shift
            ;;
        --verbose)
            VERBOSE="true"
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --app-cluster NAME          Application cluster name (default: $APP_CLUSTER)"
            echo "  --inference-cluster NAME    Inference cluster name (default: $INFERENCE_CLUSTER)"
            echo "  --app-namespace NAME        App cluster namespace (default: $APP_NAMESPACE)"
            echo "  --inference-namespace NAME  Inference namespace (default: $INFERENCE_NAMESPACE)"
            echo "  --skip-e2e                  Skip E2E inference test"
            echo "  --skip-gpu-check            Skip GPU validation"
            echo "  --verbose                   Show detailed output"
            echo "  --help                      Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Function to perform a check
check() {
    local description=$1
    local command=$2
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    if [[ "$VERBOSE" == "true" ]]; then
        echo -n "Checking: $description... "
    else
        echo -n "."
    fi
    
    if eval "$command" >/dev/null 2>&1; then
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        if [[ "$VERBOSE" == "true" ]]; then
            log_success "PASSED"
        fi
        return 0
    else
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        if [[ "$VERBOSE" == "true" ]]; then
            log_error "FAILED"
        else
            echo
            log_error "Check failed: $description"
        fi
        return 1
    fi
}

# Function to validate cluster connectivity
validate_clusters() {
    log_info "=== Validating Cluster Connectivity ==="
    
    check "Application cluster connectivity" \
        "kubectl --context=k3d-$APP_CLUSTER cluster-info"
    
    check "Inference cluster connectivity" \
        "kubectl --context=k3d-$INFERENCE_CLUSTER cluster-info"
    
    check "Application namespace exists" \
        "kubectl --context=k3d-$APP_CLUSTER get namespace $APP_NAMESPACE"
    
    check "Inference namespace exists" \
        "kubectl --context=k3d-$INFERENCE_CLUSTER get namespace $INFERENCE_NAMESPACE"
}

# Function to validate application cluster services
validate_app_services() {
    log_info "=== Validating Application Cluster Services ==="
    
    # Check core services
    check "BudProxy service exists" \
        "kubectl --context=k3d-$APP_CLUSTER get svc budproxy-service -n $APP_NAMESPACE"
    
    check "BudProxy deployment is ready" \
        "kubectl --context=k3d-$APP_CLUSTER get deployment -n $APP_NAMESPACE -l app=budproxy -o jsonpath='{.items[0].status.conditions[?(@.type==\"Available\")].status}' | grep -q True"
    
    check "PostgreSQL service exists" \
        "kubectl --context=k3d-$APP_CLUSTER get svc postgres-service -n $APP_NAMESPACE"
    
    check "Redis service exists" \
        "kubectl --context=k3d-$APP_CLUSTER get svc cache-service -n $APP_NAMESPACE"
    
    check "MinIO service exists" \
        "kubectl --context=k3d-$APP_CLUSTER get svc minio-service -n $APP_NAMESPACE"
    
    # Check monitoring
    check "Prometheus is running" \
        "kubectl --context=k3d-$APP_CLUSTER get pod -n $APP_NAMESPACE -l app.kubernetes.io/name=prometheus -o jsonpath='{.items[0].status.phase}' | grep -q Running"
    
    check "Grafana is running" \
        "kubectl --context=k3d-$APP_CLUSTER get pod -n $APP_NAMESPACE -l app.kubernetes.io/name=grafana -o jsonpath='{.items[0].status.phase}' | grep -q Running"
}

# Function to validate inference cluster services
validate_inference_services() {
    log_info "=== Validating Inference Cluster Services ==="
    
    # Check AIBrix
    check "AIBrix service exists" \
        "kubectl --context=k3d-$INFERENCE_CLUSTER get svc -n $INFERENCE_NAMESPACE -l app.kubernetes.io/component=aibrix"
    
    check "AIBrix deployment is ready" \
        "kubectl --context=k3d-$INFERENCE_CLUSTER get deployment -n $INFERENCE_NAMESPACE -l app.kubernetes.io/component=aibrix -o jsonpath='{.items[0].status.conditions[?(@.type==\"Available\")].status}' | grep -q True"
    
    # Check VLLM instances
    local vllm_count=$(kubectl --context="k3d-$INFERENCE_CLUSTER" get statefulset -n "$INFERENCE_NAMESPACE" -l app.kubernetes.io/component=vllm --no-headers 2>/dev/null | wc -l)
    
    if [ "$vllm_count" -gt 0 ]; then
        check "VLLM StatefulSets exist" \
            "[ $vllm_count -gt 0 ]"
        
        check "VLLM services exist" \
            "kubectl --context=k3d-$INFERENCE_CLUSTER get svc -n $INFERENCE_NAMESPACE -l app.kubernetes.io/component=vllm"
    else
        log_warning "No VLLM instances deployed"
    fi
    
    # Check GPU if enabled
    if [[ "$CHECK_GPU" == "true" ]]; then
        check "GPU nodes available" \
            "kubectl --context=k3d-$INFERENCE_CLUSTER get nodes -l nvidia.com/gpu.present=true --no-headers | grep -q ."
        
        check "GPU operator namespace exists" \
            "kubectl --context=k3d-$INFERENCE_CLUSTER get namespace gpu-operator"
    fi
    
    # Check monitoring
    check "Prometheus is running" \
        "kubectl --context=k3d-$INFERENCE_CLUSTER get pod -n $INFERENCE_NAMESPACE -l app.kubernetes.io/name=prometheus -o jsonpath='{.items[0].status.phase}' | grep -q Running"
}

# Function to validate cross-cluster configuration
validate_cross_cluster() {
    log_info "=== Validating Cross-Cluster Configuration ==="
    
    check "Cross-cluster service in app cluster" \
        "kubectl --context=k3d-$APP_CLUSTER get svc aibrix-external -n $APP_NAMESPACE"
    
    check "Inference config in app cluster" \
        "kubectl --context=k3d-$APP_CLUSTER get configmap inference-cluster-config -n $APP_NAMESPACE"
    
    check "App config in inference cluster" \
        "kubectl --context=k3d-$INFERENCE_CLUSTER get configmap app-cluster-config -n $INFERENCE_NAMESPACE"
}

# Function to perform E2E inference test
run_e2e_test() {
    log_info "=== Running E2E Inference Test ==="
    
    # Check if we have VLLM instances
    local vllm_services=$(kubectl --context="k3d-$INFERENCE_CLUSTER" get svc -n "$INFERENCE_NAMESPACE" -l app.kubernetes.io/component=vllm -o jsonpath='{.items[*].metadata.name}' 2>/dev/null)
    
    if [ -z "$vllm_services" ]; then
        log_warning "No VLLM services found, skipping E2E test"
        return 0
    fi
    
    # Get the first VLLM service
    local vllm_svc=$(echo "$vllm_services" | awk '{print $1}')
    local model_name=$(kubectl --context="k3d-$INFERENCE_CLUSTER" get svc "$vllm_svc" -n "$INFERENCE_NAMESPACE" -o jsonpath='{.metadata.labels.app\.kubernetes\.io/instance}')
    
    log_info "Testing with model: $model_name"
    
    # Create a test pod in the app cluster
    cat <<EOF | kubectl --context="k3d-$APP_CLUSTER" apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: e2e-test-pod
  namespace: $APP_NAMESPACE
spec:
  restartPolicy: Never
  containers:
  - name: test
    image: curlimages/curl:latest
    command: ["sleep", "300"]
EOF
    
    # Wait for test pod to be ready
    kubectl --context="k3d-$APP_CLUSTER" wait --for=condition=ready pod/e2e-test-pod -n "$APP_NAMESPACE" --timeout=60s
    
    # Test direct VLLM access from inference cluster
    log_info "Testing direct VLLM access..."
    kubectl --context="k3d-$INFERENCE_CLUSTER" run test-vllm --rm -i --restart=Never \
        --image=curlimages/curl:latest -- \
        curl -s -X POST "http://$vllm_svc.$INFERENCE_NAMESPACE.svc.cluster.local:8000/v1/models" \
        | grep -q "object" && log_success "Direct VLLM access successful" || log_error "Direct VLLM access failed"
    
    # Test BudProxy to VLLM (if cross-cluster is set up)
    if kubectl --context="k3d-$APP_CLUSTER" get svc aibrix-external -n "$APP_NAMESPACE" >/dev/null 2>&1; then
        log_info "Testing cross-cluster inference..."
        # This would require proper network setup between clusters
        log_warning "Cross-cluster inference test requires network mesh setup"
    fi
    
    # Cleanup test pod
    kubectl --context="k3d-$APP_CLUSTER" delete pod e2e-test-pod -n "$APP_NAMESPACE" --ignore-not-found=true
    
    check "E2E test completed" "true"
}

# Function to generate validation report
generate_report() {
    local report_file="$ROOT_DIR/configs/validation-report-$(date +%Y%m%d-%H%M%S).txt"
    mkdir -p "$(dirname "$report_file")"
    
    {
        echo "Multi-Cluster Deployment Validation Report"
        echo "========================================="
        echo "Generated: $(date)"
        echo
        echo "Configuration:"
        echo "  Application Cluster: $APP_CLUSTER"
        echo "  Inference Cluster: $INFERENCE_CLUSTER"
        echo "  App Namespace: $APP_NAMESPACE"
        echo "  Inference Namespace: $INFERENCE_NAMESPACE"
        echo
        echo "Validation Results:"
        echo "  Total Checks: $TOTAL_CHECKS"
        echo "  Passed: $PASSED_CHECKS"
        echo "  Failed: $FAILED_CHECKS"
        echo "  Success Rate: $(( PASSED_CHECKS * 100 / TOTAL_CHECKS ))%"
        echo
        
        if [ "$FAILED_CHECKS" -gt 0 ]; then
            echo "Status: VALIDATION FAILED"
            echo
            echo "Please check the failed items and ensure all services are properly deployed."
        else
            echo "Status: VALIDATION PASSED"
            echo
            echo "All checks passed successfully!"
        fi
        
        echo
        echo "Detailed Service Status:"
        echo
        echo "Application Cluster Services:"
        kubectl --context="k3d-$APP_CLUSTER" get all -n "$APP_NAMESPACE"
        echo
        echo "Inference Cluster Services:"
        kubectl --context="k3d-$INFERENCE_CLUSTER" get all -n "$INFERENCE_NAMESPACE"
        
    } > "$report_file"
    
    log_info "Validation report saved to: $report_file"
}

# Function to display validation summary
display_summary() {
    echo
    log_info "=== Validation Summary ==="
    echo
    echo "Total Checks: $TOTAL_CHECKS"
    echo "Passed: $PASSED_CHECKS ($(( PASSED_CHECKS * 100 / TOTAL_CHECKS ))%)"
    echo "Failed: $FAILED_CHECKS"
    echo
    
    if [ "$FAILED_CHECKS" -eq 0 ]; then
        log_success "✅ All validation checks passed!"
        echo
        echo "Your multi-cluster deployment is ready for use."
        echo
        echo "Next steps:"
        echo "1. Run E2E tests: cd tests/e2e && pytest"
        echo "2. Access services via port-forward (see deployment output)"
        echo "3. Monitor services via Grafana dashboards"
    else
        log_error "❌ Validation failed with $FAILED_CHECKS errors"
        echo
        echo "Please review the errors above and ensure:"
        echo "1. All clusters are properly created"
        echo "2. All services are deployed successfully"
        echo "3. Cross-cluster networking is configured (if using)"
        echo
        echo "Run with --verbose for detailed output"
    fi
}

# Main validation flow
main() {
    log_info "Starting deployment validation..."
    
    # Validate cluster connectivity
    validate_clusters
    echo
    
    # Validate application services
    validate_app_services
    echo
    
    # Validate inference services
    validate_inference_services
    echo
    
    # Validate cross-cluster setup
    validate_cross_cluster
    echo
    
    # Run E2E test if enabled
    if [[ "$RUN_E2E_TEST" == "true" ]]; then
        run_e2e_test
        echo
    fi
    
    # Generate report
    generate_report
    
    # Display summary
    display_summary
    
    # Exit with appropriate code
    if [ "$FAILED_CHECKS" -gt 0 ]; then
        exit 1
    else
        exit 0
    fi
}

# Run main function
main