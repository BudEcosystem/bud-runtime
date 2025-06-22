# Test Deployments

This directory contains minimal test deployments for E2E testing. These are simplified versions of the actual services using test images where the real images are not available.

## Structure

```
deployments/
├── app-cluster/         # Services for the application cluster
│   ├── budproxy.yaml   # TensorZero Gateway (BudProxy)
│   └── README.md       # App cluster deployment notes
└── inference-cluster/   # Services for the inference cluster
    ├── aibrix.yaml     # AIBrix test deployment
    └── README.md       # Inference cluster deployment notes
```

## Usage

### Deploy to App Cluster
```bash
kubectl config use-context k3d-bud-app
kubectl apply -f tests/deployments/app-cluster/
```

### Deploy to Inference Cluster
```bash
kubectl config use-context k3d-bud-inference
kubectl apply -f tests/deployments/inference-cluster/
```

### Clean Up
```bash
# App cluster
kubectl delete -f tests/deployments/app-cluster/

# Inference cluster
kubectl delete -f tests/deployments/inference-cluster/
```

## Notes

- These are minimal deployments for testing infrastructure and connectivity
- Real services should be deployed using the Helm charts once proper images are available
- Test deployments use placeholder images (nginx) where real images don't exist