# Inference Cluster Test Deployments

This directory contains test deployments for the inference cluster.

## Services

### AIBrix
Three deployment options available:

#### Option 1: Placeholder Deployment
- **File**: `aibrix.yaml`
- **Image**: `nginx:latest` (placeholder)
- **Port**: 8080
- **Status**: ✅ Quick testing without building
- **Purpose**: Basic connectivity testing

#### Option 2: Static Deployment with Redis
- **File**: `aibrix-with-redis.yaml`
- **Images**: Uses pre-built images (update image tags as needed)
- **Components**: Controller Manager, Gateway Plugins, Redis
- **Status**: ✅ Full deployment without building
- **Purpose**: Testing with pre-built images

#### Option 3: Build from Source
- **Script**: `build-aibrix.sh`
- **Images**: Built from `/services/aibrix` source code
- **Components**: Controller Manager, Gateway Plugins, Redis
- **Features**: Auto-detects Go, handles Redis, fixes registry paths
- **Status**: ✅ Full AIBrix functionality
- **Purpose**: Development and testing with code changes

## Deployment

### Quick Deployment (Placeholder)
```bash
kubectl config use-context k3d-bud-inference
kubectl apply -f aibrix.yaml
```

### Build and Deploy from Source
```bash
# Build AIBrix from source and deploy
./build-aibrix.sh
```

This will:
1. Build all AIBrix Docker images from source
2. Push to local k3d registry
3. Deploy to inference cluster
4. Install all required dependencies

## Access

### Placeholder AIBrix
```bash
# Port forward
kubectl port-forward -n inference-system svc/aibrix-service 8891:8080

# Test
curl http://localhost:8891
```

### Built AIBrix
```bash
# Controller Manager metrics
kubectl port-forward -n aibrix-system svc/aibrix-controller-manager 8080:8080

# Gateway plugins
kubectl port-forward -n aibrix-system svc/aibrix-gateway-plugins 50051:50051

# View logs
kubectl logs -n aibrix-system -l app=aibrix -f
```

## Development Workflow

1. Make changes to AIBrix source code in `/services/aibrix`
2. Run `./build-aibrix.sh` to rebuild and redeploy
3. Test your changes immediately

## Notes

- The placeholder deployment uses nginx for quick testing without building
- The build script uses the local k3d registry for fast iteration
- AIBrix dependencies (KubeRay, etc.) are automatically installed
- Both deployments can coexist in different namespaces