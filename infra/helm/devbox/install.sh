#!/bin/sh

set -e
namespace="devbox-prod"
release="sauna"

sops -d ./values.secrets.enc.yaml > ./values.secrets.yaml

for r in $(kubectl get CustomResourceDefinition | grep -Eo '^[^ ]+' | grep cert-manager); do
        kubectl delete CustomResourceDefinition "$r"
done

helm install \
        "$release" jetstack/cert-manager \
        --namespace "$namespace" \
        --create-namespace \
        --version v1.18.2 \
        --set crds.enabled=true \
        --set ingressShim.defaultIssuerName=letsencrypt \
        --set ingressShim.defaultIssuerKind=ClusterIssuer \
        --set ingressShim.defaultIssuerGroup=cert-manager.io

helm uninstall "$release" -n "$namespace"

helm install \
        "$release" . \
        --namespace "$namespace" \
        --create-namespace \
        -f values.secrets.yaml  
