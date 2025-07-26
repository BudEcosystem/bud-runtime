# Ask Bud Service

[![License](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Dapr](https://img.shields.io/badge/Dapr-1.10+-blue.svg)](https://dapr.io/)

An intelligent AI assistant service that provides cluster and performance analysis capabilities through natural language queries. Ask Bud simplifies interaction with your inference stack by translating user requests into actionable insights about clusters, deployments, models, and system performance.

## 🚀 Features

- **Natural Language Interface**: Query your infrastructure using intuitive natural language
- **Cluster Analysis**: Comprehensive cluster health, performance, and resource utilization insights
- **Performance Monitoring**: Real-time analysis of model deployment performance and bottlenecks
- **Intelligent Recommendations**: AI-powered suggestions for optimization and troubleshooting
- **Multi-Service Integration**: Seamless access to data from all Bud Stack services
- **Contextual Responses**: Context-aware responses based on user roles and project access
- **Conversation History**: Maintains conversation context for follow-up questions
- **Interactive Visualizations**: Generates charts and graphs for complex data analysis

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
ask-bud/
├── ask_bud/
│   ├── assistant/          # Core AI assistant functionality
│   │   ├── routes.py       # REST API endpoints
│   │   ├── services.py     # Business logic
│   │   ├── models.py       # SQLAlchemy models
│   │   ├── schemas.py      # Pydantic schemas
│   │   └── conversation.py # Conversation management
│   ├── analysis/           # Data analysis capabilities
│   │   ├── cluster.py      # Cluster analysis
│   │   ├── performance.py  # Performance analysis
│   │   ├── models.py       # Model analysis
│   │   └── recommendations.py # AI recommendations
│   ├── integrations/       # Service integrations
│   │   ├── budapp.py       # BudApp integration
│   │   ├── budcluster.py   # BudCluster integration
│   │   ├── budsim.py       # BudSim integration
│   │   ├── budmetrics.py   # BudMetrics integration
│   │   └── budmodel.py     # BudModel integration
│   ├── nlp/                # Natural language processing
│   │   ├── intent.py       # Intent recognition
│   │   ├── entities.py     # Entity extraction
│   │   ├── context.py      # Context management
│   │   └── responses.py    # Response generation
│   └── commons/            # Shared utilities
│       ├── config.py       # Configuration
│       ├── database.py     # Database setup
│       └── exceptions.py   # Custom exceptions
├── models/                 # AI models and weights
│   ├── intent_classifier/  # Intent classification model
│   ├── entity_extractor/   # Named entity recognition
│   └── response_generator/ # Response generation model
├── tests/                  # Test suite
└── deploy/                 # Deployment scripts
```

### Core Components

- **NLP Engine**: Processes natural language queries and extracts intent/entities
- **Analysis Engine**: Performs data analysis across all Bud Stack services
- **Recommendation Engine**: Generates AI-powered insights and suggestions
- **Integration Layer**: Communicates with other Bud Stack services via Dapr
- **Conversation Manager**: Maintains context and conversation history
- **Visualization Generator**: Creates charts and graphs for complex data

### Query Processing Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Natural   │────▶│     NLP     │────▶│   Intent    │
│   Language  │     │  Processing │     │Recognition  │
│    Query    │     └─────────────┘     └──────┬──────┘
└─────────────┘                                │
                                               │
    ┌──────────────────────────────────────────┼──────────────────────────────────────────┐
    │                                          │                                          │
┌───▼───────┐        ┌─────────────┐        ┌─────▼─────┐        ┌─────────────┐
│  Cluster  │        │Performance  │        │   Model   │        │    Data     │
│ Analysis  │        │  Analysis   │        │ Analysis  │        │Aggregation  │
└───────────┘        └─────────────┘        └───────────┘        └──────┬──────┘
                                                                         │
                                                                         ▼
                                                               ┌─────────────┐
                                                               │  Response   │
                                                               │ Generation  │
                                                               └─────────────┘
```

## 📦 Prerequisites

### Required

- **Python** 3.8+
- **Docker** and Docker Compose
- **Git**

### Service Dependencies

- **PostgreSQL** - Conversation history and user context
- **Redis** - Dapr state store and caching
- **Dapr** - Service mesh and inter-service communication

### AI/ML Dependencies

- **Transformers** - Pre-trained language models
- **spaCy** - Natural language processing
- **scikit-learn** - Machine learning utilities
- **Matplotlib/Plotly** - Data visualization

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/BudEcosystem/bud-stack.git
cd bud-stack/services/ask-bud

# Setup environment
cp .env.sample .env
# Edit .env with your configuration
```

### 2. Configure Environment

Edit `.env` file with required configurations:

```bash
# Database
DATABASE_URL=postgresql://askbud:askbud123@localhost:5432/askbud

# Redis
REDIS_URL=redis://localhost:6379

# Dapr
DAPR_HTTP_PORT=3510
DAPR_GRPC_PORT=50006
DAPR_API_TOKEN=your-token

# Application
APP_NAME=bud-serve-assistant
LOG_LEVEL=INFO

# AI Configuration
AI_MODEL_PROVIDER=openai  # openai, anthropic, local
OPENAI_API_KEY=your-openai-key
MODEL_NAME=gpt-4-turbo-preview

# Local AI Models (if using local provider)
LOCAL_MODEL_PATH=./models/
INTENT_MODEL=intent_classifier_v1
ENTITY_MODEL=entity_extractor_v1

# Service URLs
BUDAPP_SERVICE_URL=http://budapp:9081
BUDCLUSTER_SERVICE_URL=http://budcluster:9082
BUDSIM_SERVICE_URL=http://budsim:9083
BUDMETRICS_SERVICE_URL=http://budmetrics:9085
BUDMODEL_SERVICE_URL=http://budmodel:9084

# Features
ENABLE_VISUALIZATIONS=true
ENABLE_RECOMMENDATIONS=true
MAX_CONVERSATION_HISTORY=50
```

### 3. Start Development Environment

```bash
# Start development environment
./deploy/start_dev.sh

# Service will be available at:
# API: http://localhost:9086
# API Docs: http://localhost:9086/docs
```

### 4. Initialize Database and Models

```bash
# Run migrations
alembic upgrade head

# Download and setup AI models
python scripts/setup_models.py

# Optional: Seed conversation examples
python scripts/seed_conversations.py
```

## 💻 Development

### Code Quality

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
./scripts/install_hooks.sh

# Linting and formatting
ruff check ask_bud/ --fix
ruff format ask_bud/

# Type checking
mypy ask_bud/

# Run all quality checks
./scripts/lint.sh
```

### Model Management

```bash
# Train custom intent classifier
python scripts/train_intent_model.py --data training_data.json

# Evaluate model performance
python scripts/evaluate_models.py

# Update pre-trained models
python scripts/update_models.py
```

### Integration Testing

```bash
# Test service integrations
python scripts/test_integrations.py

# Validate query processing
python scripts/test_query_processing.py --query "What's the status of my clusters?"
```

## 📚 API Documentation

### Key Endpoints

#### Assistant Interaction
- `POST /assistant/ask` - Ask a question to the AI assistant
- `GET /assistant/conversations/{user_id}` - Get conversation history
- `DELETE /assistant/conversations/{user_id}` - Clear conversation history
- `POST /assistant/feedback` - Provide feedback on responses

#### Analysis Endpoints
- `GET /analysis/clusters` - Get cluster analysis summary
- `GET /analysis/performance` - Get performance analysis
- `GET /analysis/models` - Get model performance insights
- `GET /analysis/recommendations` - Get AI recommendations

#### Context Management
- `GET /context/{user_id}` - Get user context
- `PUT /context/{user_id}` - Update user context
- `POST /context/{user_id}/reset` - Reset user context

### Query Examples

#### Basic Questions
```json
POST /assistant/ask
{
  "user_id": "user-123",
  "query": "What's the current status of my clusters?",
  "context": {
    "project_id": "project-456",
    "user_role": "admin"
  }
}
```

#### Performance Analysis
```json
POST /assistant/ask
{
  "user_id": "user-123",
  "query": "Show me the performance metrics for the llama-2-7b model deployed on the production cluster in the last 24 hours",
  "include_visualizations": true
}
```

#### Troubleshooting
```json
POST /assistant/ask
{
  "user_id": "user-123",
  "query": "Why is my model deployment failing on the AWS cluster?",
  "context": {
    "deployment_id": "deploy-789",
    "cluster_id": "cluster-101"
  }
}
```

### Response Format

```json
{
  "response_id": "resp-123",
  "user_id": "user-123",
  "query": "What's the status of my clusters?",
  "response": {
    "text": "You have 3 active clusters: 2 are healthy and 1 requires attention...",
    "structured_data": {
      "clusters": [
        {
          "id": "cluster-1",
          "name": "production",
          "status": "healthy",
          "utilization": 0.75
        }
      ]
    },
    "visualizations": [
      {
        "type": "bar_chart",
        "title": "Cluster Resource Utilization",
        "data_url": "/visualizations/cluster-util-123.png"
      }
    ],
    "recommendations": [
      "Consider scaling down cluster-2 during off-peak hours",
      "Update cluster-3 to the latest Kubernetes version"
    ]
  },
  "confidence": 0.92,
  "processing_time_ms": 850,
  "sources": ["budcluster", "budmetrics"],
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## 🚀 Deployment

### Docker Deployment

```bash
# Build image
docker build -t ask-bud:latest .

# Run with docker-compose
docker-compose up -d
```

### Kubernetes Deployment

```bash
# Deploy with Helm
helm install ask-bud ./charts/ask-bud/

# Or as part of full stack
cd ../../infra/helm/bud
helm dependency update
helm install bud .
```

### Production Configuration

```yaml
# values.yaml for Helm
ask_bud:
  replicas: 2
  resources:
    requests:
      memory: "1Gi"
      cpu: "500m"
    limits:
      memory: "4Gi"
      cpu: "2000m"
  env:
    - name: AI_MODEL_PROVIDER
      value: "openai"
    - name: ENABLE_VISUALIZATIONS
      value: "true"
  secrets:
    - name: OPENAI_API_KEY
      key: openai-api-key
  persistence:
    enabled: true
    size: 5Gi
```

## 🧪 Testing

### Unit Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=ask_bud --cov-report=html

# Run specific test module
pytest tests/test_nlp_processing.py
```

### Integration Tests

```bash
# With Dapr sidecar
pytest tests/integration/ --dapr-http-port 3510 --dapr-api-token $DAPR_API_TOKEN
```

### NLP Tests

```bash
# Test intent recognition
pytest tests/nlp/test_intent_recognition.py

# Test entity extraction
pytest tests/nlp/test_entity_extraction.py

# Test response generation
pytest tests/nlp/test_response_generation.py
```

### End-to-End Tests

```bash
# Test complete query processing flow
python tests/e2e/test_query_flow.py

# Test service integrations
python tests/e2e/test_service_integrations.py
```

## 🔧 Troubleshooting

### Common Issues

#### AI Model Not Loading
```bash
# Error: Failed to load AI model
# Solution: Download required models
python scripts/setup_models.py --force-download

# Check model files
ls -la models/
```

#### Service Integration Failed
```bash
# Error: Cannot connect to BudCluster service
# Solution: Verify service URLs and Dapr configuration
curl http://budcluster:9082/health

# Check Dapr service discovery
dapr list
```

#### Poor Response Quality
```bash
# Error: AI responses are not accurate
# Solution: Update training data and retrain models
python scripts/retrain_models.py --data updated_training_data.json

# Adjust model parameters
export MODEL_TEMPERATURE=0.3
export MAX_TOKENS=500
```

#### Conversation Context Lost
```bash
# Error: Assistant doesn't remember previous context
# Solution: Check Redis connection and conversation storage
redis-cli ping
python scripts/validate_conversation_storage.py
```

### Debug Mode

Enable detailed logging:
```bash
# In .env
LOG_LEVEL=DEBUG
ENABLE_NLP_LOGGING=true
ENABLE_INTEGRATION_LOGGING=true

# For AI debugging
AI_DEBUG_MODE=true
SAVE_DEBUG_RESPONSES=true
```

### Performance Monitoring

```bash
# Check service health
curl http://localhost:9086/health

# Monitor AI model performance
curl http://localhost:9086/metrics/models

# Check conversation statistics
curl http://localhost:9086/metrics/conversations
```

## 🤝 Contributing

Please see the main [Bud Stack Contributing Guide](../../CONTRIBUTING.md).

### Service-Specific Guidelines

1. Add training examples for new query types
2. Test AI responses for accuracy and relevance
3. Update intent classification for new capabilities
4. Ensure proper error handling for service integrations
5. Maintain conversation context consistency

## 📄 License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](../../LICENSE) file for details.

## 🔗 Related Documentation

- [Main Bud Stack README](../../README.md)
- [CLAUDE.md Development Guide](../../CLAUDE.md)
- [API Documentation](http://localhost:9086/docs) (when running)
- [NLP Model Documentation](./docs/nlp-models.md)
- [Query Examples](./docs/query-examples.md)
- [Integration Guide](./docs/integration-guide.md)
