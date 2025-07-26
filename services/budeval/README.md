# BudEval Service

[![License](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Dapr](https://img.shields.io/badge/Dapr-1.10+-blue.svg)](https://dapr.io/)

A comprehensive evaluation service for AI model benchmarking and performance assessment. BudEval provides standardized benchmarks, custom evaluation frameworks, and detailed performance analysis for AI/ML models across various domains and capabilities.

## 🚀 Features

- **Standardized Benchmarks**: Support for popular AI benchmarks (MMLU, HellaSwag, ARC, etc.)
- **Custom Evaluations**: Create and run custom evaluation frameworks
- **Multi-Modal Support**: Text, vision, and multimodal model evaluation
- **Performance Metrics**: Comprehensive metrics including accuracy, latency, throughput
- **Batch Processing**: Efficient evaluation of large datasets
- **Result Analysis**: Detailed statistical analysis and visualization
- **Leaderboard Integration**: Automatic submission to model leaderboards
- **Evaluation Workflows**: Long-running evaluation pipelines with progress tracking
- **Comparison Tools**: Side-by-side model comparison and analysis

## 📋 Table of Contents

- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Development](#-development)
- [API Documentation](#-api-documentation)
- [Benchmarks](#-benchmarks)
- [Deployment](#-deployment)
- [Testing](#-testing)
- [Troubleshooting](#-troubleshooting)

## 🏗️ Architecture

### Service Structure

```
budeval/
├── budeval/
│   ├── evaluators/         # Core evaluation logic
│   │   ├── routes.py       # REST API endpoints
│   │   ├── services.py     # Evaluation services
│   │   ├── models.py       # SQLAlchemy models
│   │   ├── schemas.py      # Pydantic schemas
│   │   └── workflows.py    # Dapr workflows
│   ├── benchmarks/         # Benchmark implementations
│   │   ├── mmlu.py        # MMLU benchmark
│   │   ├── hellaswag.py   # HellaSwag benchmark
│   │   ├── arc.py         # ARC benchmark
│   │   ├── gsm8k.py       # GSM8K benchmark
│   │   └── custom.py      # Custom benchmark framework
│   ├── metrics/            # Evaluation metrics
│   │   ├── accuracy.py    # Accuracy calculations
│   │   ├── performance.py # Performance metrics
│   │   ├── statistical.py # Statistical analysis
│   │   └── visualization.py # Result visualization
│   ├── datasets/           # Dataset management
│   │   ├── loaders.py     # Dataset loaders
│   │   ├── processors.py  # Data preprocessing
│   │   └── validators.py  # Data validation
│   └── commons/            # Shared utilities
│       ├── config.py       # Configuration
│       ├── database.py     # Database setup
│       └── exceptions.py   # Custom exceptions
├── benchmarks/             # Benchmark datasets and configs
│   ├── mmlu/              # MMLU dataset
│   ├── hellaswag/         # HellaSwag dataset
│   ├── arc/               # ARC dataset
│   └── custom/            # Custom benchmarks
├── results/                # Evaluation results storage
├── scripts/                # Utility scripts
├── tests/                  # Test suite
└── deploy/                 # Deployment scripts
```

### Core Components

- **Evaluation Engine**: Orchestrates evaluation runs across different benchmarks
- **Benchmark Manager**: Manages standard and custom benchmark implementations
- **Metrics Calculator**: Computes accuracy, performance, and statistical metrics
- **Dataset Handler**: Loads, preprocesses, and validates evaluation datasets
- **Result Analyzer**: Statistical analysis and visualization of results
- **Workflow Coordinator**: Long-running evaluation pipelines via Dapr

### Evaluation Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Model     │────▶│  Dataset    │────▶│ Evaluation  │
│   Input     │     │   Loader    │     │   Engine    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
            ┌───────▼───────┐        ┌────────▼────────┐        ┌────────▼────────┐
            │   Benchmark   │        │   Performance   │        │   Statistical   │
            │   Execution   │        │    Metrics      │        │    Analysis     │
            └───────┬───────┘        └────────┬────────┘        └────────┬────────┘
                    │                         │                          │
                    └─────────────────────────┼──────────────────────────┘
                                              │
                                    ┌─────────▼─────────┐
                                    │     Results       │
                                    │    Storage &      │
                                    │  Visualization    │
                                    └───────────────────┘
```

## 📦 Prerequisites

### Required

- **Python** 3.8+
- **Docker** and Docker Compose
- **Git**

### Service Dependencies

- **PostgreSQL** - Results and metadata storage
- **Redis** - Dapr state management and caching
- **Dapr** - Service mesh and workflow orchestration

### Optional Dependencies

- **GPU Support** - For accelerated model evaluation
- **Large Storage** - For benchmark datasets and results

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/BudEcosystem/bud-stack.git
cd bud-stack/services/budeval

# Setup environment
cp .env.sample .env
# Edit .env with your configuration
```

### 2. Configure Environment

Edit `.env` file with required configurations:

```bash
# Database
DATABASE_URL=postgresql://budeval:budeval123@localhost:5432/budeval

# Redis
REDIS_URL=redis://localhost:6379

# Dapr
DAPR_HTTP_PORT=3510
DAPR_GRPC_PORT=50008
DAPR_API_TOKEN=your-token

# Application
APP_NAME=bud-serve-eval
LOG_LEVEL=INFO

# Evaluation Settings
MAX_CONCURRENT_EVALUATIONS=5
EVALUATION_TIMEOUT=3600
BENCHMARK_DATA_PATH=/app/benchmarks
RESULTS_STORAGE_PATH=/app/results

# Model Integration
ENABLE_HUGGINGFACE=true
ENABLE_OPENAI=true
ENABLE_ANTHROPIC=true
HUGGINGFACE_API_TOKEN=your-token
OPENAI_API_KEY=your-key

# Performance
BATCH_SIZE=32
USE_GPU=true
GPU_MEMORY_FRACTION=0.8
```

### 3. Start Development Environment

```bash
# Start development environment
./deploy/start_dev.sh

# Service will be available at:
# API: http://localhost:9088
# API Docs: http://localhost:9088/docs
```

### 4. Initialize Database and Benchmarks

```bash
# Run migrations
alembic upgrade head

# Download benchmark datasets
python scripts/download_benchmarks.py --all

# Optional: Validate benchmarks
python scripts/validate_benchmarks.py
```

## 💻 Development

### Code Quality

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
./scripts/install_hooks.sh

# Linting and formatting
ruff check budeval/ --fix
ruff format budeval/

# Type checking
mypy budeval/

# Run all quality checks
./scripts/lint.sh
```

### Benchmark Management

```bash
# Add new benchmark
python scripts/add_benchmark.py --name custom_benchmark --config benchmarks/custom/config.yaml

# Validate benchmark data
python scripts/validate_benchmark.py --benchmark mmlu

# Update benchmark datasets
python scripts/update_benchmarks.py --benchmark all
```

### Custom Evaluations

```bash
# Create custom evaluation
python scripts/create_evaluation.py --name "code_generation" --type "custom"

# Run evaluation
python scripts/run_evaluation.py --model llama-2-7b --benchmark custom_eval

# Analyze results
python scripts/analyze_results.py --evaluation-id eval-123
```

## 📚 API Documentation

### Key Endpoints

#### Evaluation Management
- `POST /evaluations/run` - Start new evaluation
- `GET /evaluations/{id}` - Get evaluation status
- `GET /evaluations/{id}/results` - Get evaluation results
- `DELETE /evaluations/{id}` - Cancel evaluation

#### Benchmark Operations
- `GET /benchmarks` - List available benchmarks
- `GET /benchmarks/{name}` - Get benchmark details
- `POST /benchmarks/validate` - Validate benchmark dataset
- `GET /benchmarks/{name}/leaderboard` - Get benchmark leaderboard

#### Results and Analysis
- `GET /results/{evaluation_id}` - Get detailed results
- `POST /results/compare` - Compare multiple evaluations
- `GET /results/{evaluation_id}/export` - Export results
- `POST /results/analyze` - Statistical analysis

### Evaluation Examples

#### Run Standard Benchmark
```json
POST /evaluations/run
{
  "model": {
    "name": "llama-2-7b",
    "provider": "huggingface",
    "model_id": "meta-llama/Llama-2-7b-hf"
  },
  "benchmark": "mmlu",
  "config": {
    "batch_size": 16,
    "max_samples": 1000,
    "temperature": 0.0
  },
  "metadata": {
    "project_id": "project-123",
    "user_id": "user-456"
  }
}
```

#### Custom Benchmark Evaluation
```json
POST /evaluations/run
{
  "model": {
    "name": "gpt-4",
    "provider": "openai",
    "api_key": "your-api-key"
  },
  "benchmark": "custom",
  "config": {
    "dataset_path": "/app/benchmarks/custom/my_dataset.jsonl",
    "metrics": ["accuracy", "f1_score", "perplexity"],
    "few_shot_examples": 3
  }
}
```

#### Batch Model Comparison
```json
POST /evaluations/batch
{
  "models": [
    {
      "name": "llama-2-7b",
      "provider": "huggingface",
      "model_id": "meta-llama/Llama-2-7b-hf"
    },
    {
      "name": "llama-2-13b",
      "provider": "huggingface",
      "model_id": "meta-llama/Llama-2-13b-hf"
    }
  ],
  "benchmarks": ["mmlu", "hellaswag", "arc"],
  "config": {
    "batch_size": 8,
    "max_samples_per_benchmark": 500
  }
}
```

### Results Format

```json
{
  "evaluation_id": "eval-123",
  "model": "llama-2-7b",
  "benchmark": "mmlu",
  "status": "completed",
  "results": {
    "overall_accuracy": 0.847,
    "category_scores": {
      "abstract_algebra": 0.82,
      "anatomy": 0.91,
      "astronomy": 0.76
    },
    "performance_metrics": {
      "avg_latency_ms": 245,
      "throughput_tokens_per_sec": 127,
      "total_tokens": 125847
    },
    "statistical_analysis": {
      "confidence_interval_95": [0.834, 0.861],
      "standard_deviation": 0.023,
      "significance_tests": {
        "vs_random": "p < 0.001",
        "vs_previous_eval": "p = 0.045"
      }
    }
  },
  "metadata": {
    "duration_seconds": 1847,
    "samples_evaluated": 1000,
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

## 🧪 Benchmarks

### Supported Benchmarks

#### Language Understanding
- **MMLU** - Massive Multitask Language Understanding
- **ARC** - AI2 Reasoning Challenge
- **HellaSwag** - Commonsense reasoning
- **PIQA** - Physical interaction reasoning
- **WinoGrande** - Winograd schema challenge

#### Code & Math
- **GSM8K** - Grade school math problems
- **HumanEval** - Code generation evaluation
- **MBPP** - Mostly Basic Python Problems
- **MathQA** - Mathematical reasoning

#### Safety & Alignment
- **TruthfulQA** - Truthfulness evaluation
- **ToxiGen** - Toxicity detection
- **BOLD** - Bias evaluation

### Custom Benchmark Creation

```python
# Example custom benchmark
from budeval.benchmarks.base import BaseBenchmark

class CustomBenchmark(BaseBenchmark):
    def __init__(self, config):
        super().__init__()
        self.config = config

    def load_dataset(self):
        # Load your custom dataset
        return dataset

    def evaluate_sample(self, model, sample):
        # Evaluate single sample
        response = model.generate(sample['input'])
        score = self.compute_score(response, sample['expected'])
        return {'score': score, 'response': response}

    def compute_metrics(self, results):
        # Compute aggregate metrics
        accuracy = sum(r['score'] for r in results) / len(results)
        return {'accuracy': accuracy}
```

## 🚀 Deployment

### Docker Deployment

```bash
# Build image
docker build -t budeval:latest .

# Run with docker-compose
docker-compose up -d
```

### Kubernetes Deployment

```bash
# Deploy with Helm
helm install budeval ./charts/budeval/

# Or as part of full stack
cd ../../infra/helm/bud
helm dependency update
helm install bud .
```

### Production Configuration

```yaml
# values.yaml for Helm
budeval:
  replicas: 2
  resources:
    requests:
      memory: "2Gi"
      cpu: "1000m"
    limits:
      memory: "8Gi"
      cpu: "4000m"
  gpu:
    enabled: true
    count: 1
    memory: "16Gi"
  storage:
    benchmarks:
      size: 50Gi
    results:
      size: 100Gi
  env:
    - name: MAX_CONCURRENT_EVALUATIONS
      value: "10"
    - name: BATCH_SIZE
      value: "64"
```

## 🧪 Testing

### Unit Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=budeval --cov-report=html

# Run specific test module
pytest tests/test_benchmarks.py
```

### Integration Tests

```bash
# With Dapr sidecar
pytest tests/integration/ --dapr-http-port 3510 --dapr-api-token $DAPR_API_TOKEN
```

### Benchmark Tests

```bash
# Test benchmark implementations
pytest tests/benchmarks/test_mmlu.py

# Validate benchmark data
python scripts/test_benchmark_data.py --benchmark all

# Performance tests
pytest tests/performance/test_evaluation_speed.py
```

### End-to-End Tests

```bash
# Full evaluation pipeline test
python tests/e2e/test_full_evaluation.py

# Multi-model comparison test
python tests/e2e/test_model_comparison.py
```

## 🔧 Troubleshooting

### Common Issues

#### GPU Memory Issues
```bash
# Error: CUDA out of memory
# Solution: Reduce batch size or enable gradient checkpointing
export BATCH_SIZE=8
export USE_GRADIENT_CHECKPOINTING=true

# Check GPU memory usage
nvidia-smi
```

#### Dataset Loading Failed
```bash
# Error: Cannot load benchmark dataset
# Solution: Download missing datasets
python scripts/download_benchmarks.py --benchmark mmlu

# Verify dataset integrity
python scripts/validate_benchmark.py --benchmark mmlu --fix
```

#### Evaluation Timeout
```bash
# Error: Evaluation exceeded timeout
# Solution: Increase timeout or reduce dataset size
export EVALUATION_TIMEOUT=7200
export MAX_SAMPLES_PER_BENCHMARK=500
```

#### Model Loading Failed
```bash
# Error: Cannot load model
# Solution: Check model availability and credentials
export HUGGINGFACE_API_TOKEN=your-token
python scripts/test_model_loading.py --model llama-2-7b
```

### Debug Mode

Enable detailed logging:
```bash
# In .env
LOG_LEVEL=DEBUG
ENABLE_EVALUATION_TRACING=true
SAVE_INTERMEDIATE_RESULTS=true

# For model debugging
ENABLE_MODEL_PROFILING=true
LOG_MODEL_RESPONSES=true
```

### Performance Monitoring

```bash
# Check service health
curl http://localhost:9088/health

# Monitor evaluation progress
curl http://localhost:9088/evaluations/active

# Check GPU utilization
curl http://localhost:9088/metrics/gpu
```

## 🤝 Contributing

Please see the main [Bud Stack Contributing Guide](../../CONTRIBUTING.md).

### Service-Specific Guidelines

1. Add comprehensive tests for new benchmarks
2. Validate benchmark implementations against reference results
3. Document benchmark configurations and expected results
4. Ensure reproducible evaluation results
5. Optimize for both accuracy and performance
6. Follow established benchmark formatting standards

## 📄 License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](../../LICENSE) file for details.

## 🔗 Related Documentation

- [Main Bud Stack README](../../README.md)
- [CLAUDE.md Development Guide](../../CLAUDE.md)
- [API Documentation](http://localhost:9088/docs) (when running)
- [Benchmark Guide](./docs/benchmarks.md)
- [Custom Evaluation Tutorial](./docs/custom-evaluations.md)
- [Performance Optimization](./docs/performance-optimization.md)
