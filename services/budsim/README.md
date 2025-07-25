# BudSim Service

[![License](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Dapr](https://img.shields.io/badge/Dapr-1.10+-blue.svg)](https://dapr.io/)

An intelligent performance simulation and optimization service for AI/ML model deployments. BudSim uses machine learning to predict performance metrics and genetic algorithms to find optimal deployment configurations across different hardware types (CPU, CUDA, HPU).

## 🚀 Features

- **Performance Prediction**: ML-based prediction of TTFT (Time to First Token), throughput, and latency
- **Multi-Hardware Support**: Optimizes for CPU, CUDA, and HPU deployments
- **Genetic Algorithm Optimization**: Finds optimal configurations using evolutionary algorithms
- **Multi-Engine Support**: Compatible with VLLM, SGLang, LiteLLM, and LLMC engines
- **Pre-trained Models**: Includes XGBoost models trained on real benchmark data
- **Configuration Analysis**: Evaluates different model quantizations and batch sizes
- **Resource Optimization**: Balances performance with resource utilization
- **Real-time Simulation**: Fast prediction without actual deployment

## 📋 Table of Contents

- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Development](#-development)
- [API Documentation](#-api-documentation)
- [Deployment](#-deployment)
- [Testing](#-testing)
- [Troubleshooting](#-troubleshooting)

## 🏗️ Architecture

### Service Structure

```
budsim/
├── budsim/
│   ├── simulator/          # Core simulation logic
│   │   ├── routes.py       # API endpoints
│   │   ├── services.py     # Simulation services
│   │   ├── schemas.py      # Request/response models
│   │   ├── evolution.py    # Genetic algorithms
│   │   └── models.py       # Database models
│   ├── engine_ops/         # Engine-specific operations
│   │   ├── vllm/          # VLLM engine support
│   │   ├── sglang/        # SGLang engine support
│   │   ├── litellm/       # LiteLLM engine support
│   │   └── llmc/          # LLMC engine support
│   ├── model_ops/         # Model analysis
│   │   ├── routes.py
│   │   └── services.py
│   └── commons/           # Shared utilities
├── cache/
│   └── pretrained_models/ # Pre-trained ML models
│       ├── cpu/          # CPU performance models
│       ├── cuda/         # GPU performance models
│       └── hpu/          # HPU performance models
├── scripts/              # Utility scripts
└── tests/               # Test suite
```

### Core Components

- **Simulation Engine**: Predicts performance using XGBoost regressors
- **Evolution Module**: Genetic algorithms for configuration optimization
- **Engine Adapters**: Abstractions for different LLM serving engines
- **Model Analyzer**: Extracts model characteristics for simulation
- **Cache Manager**: Manages pre-trained performance models
- **Workflow Integration**: Dapr workflows for long-running simulations

### ML Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Model Config   │     │ Hardware Specs  │     │ Engine Config   │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                        │
         └───────────────────────┴────────────────────────┘
                                 │
                          ┌──────▼──────┐
                          │   Feature   │
                          │ Engineering │
                          └──────┬──────┘
                                 │
                 ┌───────────────┴───────────────┐
                 │                               │
          ┌──────▼──────┐                ┌──────▼──────┐
          │  XGBoost    │                │   Genetic   │
          │ Regressors  │                │ Algorithms  │
          └──────┬──────┘                └──────┬──────┘
                 │                               │
                 └───────────────┬───────────────┘
                                 │
                          ┌──────▼──────┐
                          │ Performance │
                          │ Predictions │
                          └─────────────┘
```

## 📦 Prerequisites

### Required

- **Python** 3.8+
- **Docker** and Docker Compose
- **Git**

### Service Dependencies

- **PostgreSQL** - Primary database
- **Redis** - Dapr state store and pub/sub
- **Dapr** - Service mesh and workflows

### Python Dependencies

- **XGBoost** - ML model for predictions
- **DEAP** - Genetic algorithm framework
- **NumPy/Pandas** - Data processing
- **Scikit-learn** - ML utilities

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/BudEcosystem/bud-stack.git
cd bud-stack/services/budsim

# Setup environment
cp .env.sample .env
# Edit .env with your configuration
```

### 2. Configure Environment

Edit `.env` file:

```bash
# Database
DATABASE_URL=postgresql://budsim:budsim123@localhost:5432/budsim

# Redis
REDIS_URL=redis://localhost:6379

# Dapr
DAPR_HTTP_PORT=3510
DAPR_GRPC_PORT=50003
DAPR_API_TOKEN=your-token

# Application
APP_NAME=bud-serve-simulator
LOG_LEVEL=INFO

# ML Model Cache
MODEL_CACHE_DIR=/app/cache/pretrained_models
ENABLE_MODEL_UPDATES=true

# Simulation Parameters
DEFAULT_TIMEOUT_SECONDS=300
MAX_EVOLUTION_GENERATIONS=50
POPULATION_SIZE=100
```

### 3. Start Development Environment

```bash
# Start with build
./deploy/start_dev.sh --build

# Or start without rebuild
./deploy/start_dev.sh

# Service will be available at:
# API: http://localhost:9083
# API Docs: http://localhost:9083/docs
```

### 4. Initialize Database

```bash
# Run migrations
alembic upgrade head

# Optional: Load pre-trained models
python scripts/load_pretrained_models.py
```

## 💻 Development

### Code Quality

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
./scripts/install_hooks.sh

# Linting and formatting
ruff check budsim/ --fix
ruff format budsim/

# Type checking
mypy budsim/

# Run all quality checks
./scripts/lint.sh
```

### Database Operations

```bash
# Create migration
alembic revision --autogenerate -m "Add simulation history"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Working with ML Models

```bash
# Train new performance models
python scripts/train_performance_models.py --hardware cuda

# Validate models
python scripts/validate_models.py

# Export models
python scripts/export_models.py --output ./models/
```

## 📚 API Documentation

### Key Endpoints

#### Simulation
- `POST /simulator/run` - Run performance simulation
- `GET /simulator/status/{id}` - Get simulation status
- `GET /simulator/results/{id}` - Get simulation results

#### Model Analysis
- `POST /models/analyze` - Analyze model characteristics
- `GET /models/{id}/info` - Get model information

#### Engine Operations
- `GET /engines` - List supported engines
- `GET /engines/{name}/config` - Get engine configuration

### Simulation Request Example

```json
POST /simulator/run
{
  "model_name": "meta-llama/Llama-2-7b-hf",
  "hardware_type": "cuda",
  "optimization_target": "throughput",
  "constraints": {
    "max_batch_size": 32,
    "max_memory_gb": 24,
    "min_throughput_tokens_per_second": 100
  },
  "engine_preferences": ["vllm", "sglang"],
  "quantization_options": ["none", "int8", "int4"]
}
```

### Simulation Response

```json
{
  "simulation_id": "uuid",
  "status": "completed",
  "optimal_configuration": {
    "engine": "vllm",
    "batch_size": 16,
    "quantization": "int8",
    "num_replicas": 2,
    "hardware_allocation": {
      "gpu_memory_gb": 20,
      "cpu_cores": 8
    }
  },
  "predicted_performance": {
    "throughput_tokens_per_second": 125.5,
    "time_to_first_token_ms": 45.2,
    "p95_latency_ms": 120.8,
    "memory_utilization_percent": 85
  },
  "alternative_configurations": [...],
  "simulation_metadata": {
    "duration_seconds": 2.5,
    "generations_evolved": 35,
    "models_evaluated": 150
  }
}
```

### Genetic Algorithm Parameters

```python
# Evolution configuration
{
  "population_size": 100,
  "generations": 50,
  "crossover_probability": 0.8,
  "mutation_probability": 0.2,
  "tournament_size": 3,
  "elite_size": 10
}
```

## 🚀 Deployment

### Docker Deployment

```bash
# Build image
docker build -t budsim:latest .

# Run with docker-compose
docker-compose up -d
```

### Kubernetes Deployment

```bash
# Deploy with Helm
helm install budsim ./charts/budsim/

# Or as part of full stack
cd ../../infra/helm/bud
helm dependency update
helm install bud .
```

### Production Configuration

```yaml
# values.yaml for Helm
budsim:
  replicas: 2
  resources:
    requests:
      memory: "1Gi"
      cpu: "1000m"
    limits:
      memory: "4Gi"
      cpu: "4000m"
  ml:
    cacheSize: "10Gi"
    enableGPU: true
  env:
    - name: MAX_EVOLUTION_GENERATIONS
      value: "100"
    - name: POPULATION_SIZE
      value: "200"
```

## 🧪 Testing

### Unit Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=budsim --cov-report=html

# Run specific test module
pytest tests/test_evolution.py
```

### Integration Tests

```bash
# With Dapr sidecar
pytest tests/integration/ --dapr-http-port 3510 --dapr-api-token $DAPR_API_TOKEN
```

### Performance Tests

```bash
# Test simulation accuracy
python tests/performance/test_prediction_accuracy.py

# Benchmark evolution speed
python tests/performance/benchmark_evolution.py
```

### ML Model Tests

```bash
# Validate model predictions
pytest tests/ml/test_xgboost_models.py

# Test feature engineering
pytest tests/ml/test_feature_engineering.py
```

## 🔧 Troubleshooting

### Common Issues

#### Missing Pre-trained Models
```bash
# Error: FileNotFoundError: pretrained_models/cuda/xgboost_throughput.pkl
# Solution: Load pre-trained models
python scripts/load_pretrained_models.py
```

#### Evolution Timeout
```bash
# Error: Evolution timeout after 300 seconds
# Solution: Increase timeout or reduce population
export DEFAULT_TIMEOUT_SECONDS=600
export POPULATION_SIZE=50
```

#### Insufficient Memory
```bash
# Error: MemoryError during simulation
# Solution: Reduce batch size or enable pagination
# In .env:
MAX_BATCH_SIZE=16
ENABLE_RESULT_PAGINATION=true
```

#### Model Not Supported
```bash
# Error: Model architecture not supported
# Solution: Check supported models or add new mapping
python scripts/add_model_support.py --model "new-model"
```

### Debug Mode

Enable detailed logging:
```bash
# In .env
LOG_LEVEL=DEBUG
ENABLE_PROFILING=true

# For ML debugging
XGBOOST_VERBOSITY=2
EVOLUTION_VERBOSE=true
```

### Performance Monitoring

```bash
# Check simulation metrics
curl http://localhost:9083/metrics

# Monitor evolution progress
curl http://localhost:9083/simulator/status/{id}/progress

# View cached models
curl http://localhost:9083/models/cache/status
```

## 🤝 Contributing

Please see the main [Bud Stack Contributing Guide](../../CONTRIBUTING.md).

### Service-Specific Guidelines

1. Add tests for new engine support
2. Validate ML model accuracy
3. Document configuration parameters
4. Benchmark optimization algorithms
5. Update pre-trained models regularly

## 📄 License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](../../LICENSE) file for details.

## 🔗 Related Documentation

- [Main Bud Stack README](../../README.md)
- [CLAUDE.md Development Guide](./CLAUDE.md)
- [API Documentation](http://localhost:9083/docs) (when running)
- [ML Model Documentation](./docs/ml-models.md)
- [Engine Compatibility Matrix](./docs/engine-compatibility.md)
- [Performance Benchmarks](./docs/benchmarks.md)