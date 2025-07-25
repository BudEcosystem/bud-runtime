#!/bin/sh

# Get the service account token and CA certificate path
KUBE_TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)
KUBE_CA_CERT="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"


echo "Starting node info collection..."

NODE_NAME=$(kubectl --server=https://$KUBERNETES_SERVICE_HOST:$KUBERNETES_SERVICE_PORT \
  --token=$KUBE_TOKEN --certificate-authority=$KUBE_CA_CERT \
  get pod $HOSTNAME -n $POD_NAMESPACE -o=jsonpath='{.spec.nodeName}')
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "Node name: $NODE_NAME"

echo "Collecting hardware info..."
HARDWARE_INFO=$(python3 /llm-benchmark/fetch_node_info.py 2>/dev/null)


echo "Fetching node status..."
  NODE_STATUS=$(kubectl --server=https://$KUBERNETES_SERVICE_HOST:$KUBERNETES_SERVICE_PORT \
    --token=$KUBE_TOKEN --certificate-authority=$KUBE_CA_CERT \
    get node $NODE_NAME -o=jsonpath='{.status.conditions[?(@.type=="Ready")].status}')

echo "Creating/updating ConfigMap..."
  kubectl --server=https://$KUBERNETES_SERVICE_HOST:$KUBERNETES_SERVICE_PORT \
    --token=$KUBE_TOKEN --certificate-authority=$KUBE_CA_CERT \
    create configmap node-info-collector-$NODE_NAME \
    --namespace=$POD_NAMESPACE \
    --from-literal=timestamp="${TIMESTAMP}" \
    --from-literal=node_name="${NODE_NAME}" \
    --from-literal=node_status="${NODE_STATUS}" \
    --from-literal=devices="${HARDWARE_INFO}" \
    -o yaml --dry-run=client | kubectl --server=https://$KUBERNETES_SERVICE_HOST:$KUBERNETES_SERVICE_PORT \
    --token=$KUBE_TOKEN --certificate-authority=$KUBE_CA_CERT apply -f -

while true; do
  
  echo "ConfigMap creation/update attempted. Sleeping for 300 seconds..."
  sleep 300
  
  TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  
  echo "Fetching node status..."
  NODE_STATUS=$(kubectl --server=https://$KUBERNETES_SERVICE_HOST:$KUBERNETES_SERVICE_PORT \
    --token=$KUBE_TOKEN --certificate-authority=$KUBE_CA_CERT \
    get node $NODE_NAME -o=jsonpath='{.status.conditions[?(@.type=="Ready")].status}')
  
  echo "Creating/updating ConfigMap..."
  kubectl --server=https://$KUBERNETES_SERVICE_HOST:$KUBERNETES_SERVICE_PORT \
    --token=$KUBE_TOKEN --certificate-authority=$KUBE_CA_CERT \
    create configmap node-info-collector-$NODE_NAME \
    --namespace=$POD_NAMESPACE \
    --from-literal=timestamp="${TIMESTAMP}" \
    --from-literal=node_name="${NODE_NAME}" \
    --from-literal=node_status="${NODE_STATUS}" \
    --from-literal=devices="${HARDWARE_INFO}" \
    -o yaml --dry-run=client | kubectl --server=https://$KUBERNETES_SERVICE_HOST:$KUBERNETES_SERVICE_PORT \
    --token=$KUBE_TOKEN --certificate-authority=$KUBE_CA_CERT apply -f -
  
done
