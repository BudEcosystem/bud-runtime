# AIBrix Build Instructions

## Prerequisites

1. **Install Build Tools** (make, gcc, etc.):
   ```bash
   ./scripts/install-build-tools.sh
   ```

2. **Install Go** (required for building AIBrix):
   ```bash
   ./scripts/install-go.sh
   # Then either start a new terminal or run:
   export PATH=$PATH:/usr/local/go/bin
   ```

3. **Verify k3d registry is running**:
   ```bash
   docker ps | grep registry
   # Should show k3d-bud-registry on port 5111
   ```

## Build and Deploy AIBrix

Once prerequisites are installed, you can build and deploy AIBrix:

```bash
./build-aibrix.sh
```

The build script will:
1. Check for Go installation (auto-adds to PATH if found)
2. Build all AIBrix components
3. Push images to local registry (localhost:5111)
4. Deploy to inference cluster (using k3d-bud-registry:5000)
5. Install dependencies (KubeRay, Envoy Gateway)
6. Deploy Redis for gateway-plugins
7. Configure environment variables

## Manual Build Steps

If you prefer to build manually:

```bash
cd /home/budadmin/bud-runtime/.worktrees/testing-setup/services/aibrix

# Build images
make docker-build-all AIBRIX_CONTAINER_REGISTRY_NAMESPACE="localhost:5111/aibrix"

# Push to registry
make docker-push-all AIBRIX_CONTAINER_REGISTRY_NAMESPACE="localhost:5111/aibrix"

# Deploy
kubectl config use-context k3d-bud-inference
kubectl apply -k config/dependency --server-side
kubectl apply -f /path/to/aibrix-local.yaml
```

## Troubleshooting

1. **"make: command not found"**
   - Install build tools: `./scripts/install-build-tools.sh`

2. **"make: go: No such file or directory"**
   - Install Go using `./scripts/install-go.sh`
   - Make sure Go is in PATH: `export PATH=$PATH:/usr/local/go/bin`

3. **"connection refused" when pushing to registry**
   - Check registry is running: `docker ps | grep registry`
   - Use `localhost:5111` not `k3d-myregistry.localhost:5555`

4. **Build errors**
   - Ensure you have the latest code
   - Check Go version: `go version` (should be 1.21+)
   - Install build-essential: `sudo apt-get install -y build-essential`

## Development Workflow

1. Make changes to AIBrix code
2. Run `./build-aibrix.sh` to rebuild and redeploy
3. Check logs: `kubectl logs -n aibrix-system -l app=aibrix -f`
4. Test your changes