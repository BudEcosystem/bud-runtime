# BudNotify Service

[![License](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0)
[![Python 3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Dapr](https://img.shields.io/badge/Dapr-1.10+-blue.svg)](https://dapr.io/)

A comprehensive notification service that handles pub/sub messaging across the Bud Stack platform. BudNotify enables real-time communication between services, manages event-driven workflows, and provides multi-channel notification delivery to users.

## =� Features

- **Pub/Sub Messaging**: Event-driven communication between all platform services
- **Multi-Channel Notifications**: Email, SMS, webhook, and in-app notifications
- **Event Routing**: Intelligent message routing based on event types and user preferences
- **Template Management**: Customizable notification templates with internationalization support
- **Delivery Guarantees**: At-least-once delivery with retry mechanisms and dead letter queues
- **User Preferences**: Granular notification preferences and subscription management
- **Real-time Updates**: WebSocket support for instant notifications
- **Audit Trail**: Complete notification history and delivery tracking

## =� Table of Contents

- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Development](#-development)
- [API Documentation](#-api-documentation)
- [Deployment](#-deployment)
- [Testing](#-testing)
- [Troubleshooting](#-troubleshooting)

## <� Architecture

### Service Structure

```
budnotify/
   budnotify/
      notifications/      # Core notification management
         routes.py       # REST API endpoints
         services.py     # Business logic
         models.py       # SQLAlchemy models
         schemas.py      # Pydantic schemas
         templates.py    # Template management
      channels/           # Notification channels
         email.py        # Email provider integrations
         sms.py          # SMS provider integrations
         webhook.py      # Webhook delivery
         websocket.py    # Real-time notifications
      pubsub/             # Pub/sub messaging
         handlers.py     # Event handlers
         publishers.py   # Message publishers
         subscribers.py  # Message subscribers
      preferences/        # User preferences
         routes.py       # Preference endpoints
         services.py     # Preference management
      commons/            # Shared utilities
          config.py       # Configuration
          database.py     # Database setup
          exceptions.py   # Custom exceptions
   templates/              # Notification templates
      email/             # Email templates
      sms/               # SMS templates
      push/              # Push notification templates
   tests/                  # Test suite
   deploy/                 # Deployment scripts
```

### Core Components

- **Message Router**: Routes events to appropriate handlers and channels
- **Channel Manager**: Manages multiple notification delivery channels
- **Template Engine**: Processes notification templates with user data
- **Preference Manager**: Handles user notification preferences and subscriptions
- **Delivery Tracker**: Monitors notification delivery status and retries
- **Event Publisher**: Publishes platform events via Dapr pub/sub

### Event Flow

```
                                                 
   Service       �   Dapr          � BudNotify   
   Events            Pub/Sub           Router    
                                          ,      
                                               
                                              <                          
                                                                        
                   �                       �                        �        
                 Email                   SMS                   WebSocket     
               Delivery               Delivery                 Delivery      
                                                                             
```

## =� Prerequisites

### Required

- **Python 3.10+
- **Docker** and Docker Compose
- **Git**

### Service Dependencies

- **Redis** - Dapr pub/sub and state management
- **Dapr** - Service mesh and pub/sub
- **PostgreSQL** - Notification history and preferences (optional)

### Provider Dependencies

- **Email Provider** - SMTP, SendGrid, AWS SES, etc.
- **SMS Provider** - Twilio, AWS SNS, etc.
- **Push Provider** - Firebase, APNs, etc.

## =� Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/BudEcosystem/bud-stack.git
cd bud-stack/services/budnotify

# Setup environment
cp .env.sample .env
# Edit .env with your configuration
```

### 2. Configure Environment

Edit `.env` file with required configurations:

```bash
# Database (optional - for notification history)
DATABASE_URL=postgresql://budnotify:budnotify123@localhost:5432/budnotify

# Redis
REDIS_URL=redis://localhost:6379

# Dapr
DAPR_HTTP_PORT=3510
DAPR_GRPC_PORT=50005
DAPR_API_TOKEN=your-token

# Application
APP_NAME=bud-serve-notify
LOG_LEVEL=INFO

# Email Configuration
EMAIL_PROVIDER=smtp  # smtp, sendgrid, ses
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-password
FROM_EMAIL=notifications@yourdomain.com

# SMS Configuration (optional)
SMS_PROVIDER=twilio  # twilio, sns
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_FROM_NUMBER=+1234567890

# Webhook Configuration
WEBHOOK_SECRET=your-webhook-secret
WEBHOOK_TIMEOUT=30

# WebSocket Configuration
WEBSOCKET_ENABLED=true
WEBSOCKET_PORT=8080
```

### 3. Start Development Environment

```bash
# Start development environment
./deploy/start_dev.sh

# Service will be available at:
# API: http://localhost:9085
# API Docs: http://localhost:9085/docs
# WebSocket: ws://localhost:8080
```

### 4. Initialize Database (Optional)

```bash
# Run migrations for notification history
alembic upgrade head

# Optional: Seed template data
python scripts/seed_templates.py
```

## =� Development

### Code Quality

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
./scripts/install_hooks.sh

# Linting and formatting
ruff check budnotify/ --fix
ruff format budnotify/

# Type checking
mypy budnotify/

# Run all quality checks
./scripts/lint.sh
```

### Template Management

```bash
# Add new email template
python scripts/add_template.py --type email --name welcome --file templates/email/welcome.html

# Validate templates
python scripts/validate_templates.py

# Update template translations
python scripts/update_translations.py --locale es
```

### Event Testing

```bash
# Test event publishing
python scripts/test_event_publisher.py --event model_deployed --data '{"model_id": "test"}'

# Monitor event subscriptions
python scripts/monitor_subscriptions.py
```

## =� API Documentation

### Key Endpoints

#### Notification Management
- `POST /notifications/send` - Send single notification
- `POST /notifications/bulk` - Send bulk notifications
- `GET /notifications/{id}` - Get notification status
- `GET /notifications/{id}/history` - Get delivery history

#### User Preferences
- `GET /preferences/{user_id}` - Get user notification preferences
- `PUT /preferences/{user_id}` - Update user preferences
- `POST /preferences/{user_id}/subscribe` - Subscribe to event type
- `DELETE /preferences/{user_id}/unsubscribe` - Unsubscribe from event type

#### Template Management
- `GET /templates` - List notification templates
- `POST /templates` - Create new template
- `PUT /templates/{id}` - Update template
- `POST /templates/{id}/preview` - Preview template with data

#### Event Publishing
- `POST /events/publish` - Publish platform event
- `GET /events/subscriptions` - List active subscriptions
- `GET /events/types` - List supported event types

### Notification Examples

#### Send Email Notification
```json
POST /notifications/send
{
  "type": "email",
  "recipient": "user@example.com",
  "template": "model_deployment_complete",
  "data": {
    "user_name": "John Doe",
    "model_name": "llama-2-7b",
    "cluster_name": "production-cluster",
    "deployment_time": "2024-01-15T10:30:00Z"
  },
  "priority": "normal",
  "send_at": "2024-01-15T11:00:00Z"
}
```

#### Bulk Notification
```json
POST /notifications/bulk
{
  "notifications": [
    {
      "type": "email",
      "recipient": "admin@example.com",
      "template": "system_alert",
      "data": {"alert_type": "cluster_down", "cluster_id": "cluster-1"}
    },
    {
      "type": "sms",
      "recipient": "+1234567890",
      "template": "urgent_alert",
      "data": {"message": "Critical system failure"}
    }
  ]
}
```

#### Event Publishing
```json
POST /events/publish
{
  "event_type": "model.deployed",
  "source": "budcluster",
  "data": {
    "model_id": "model-123",
    "cluster_id": "cluster-456",
    "status": "success",
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "metadata": {
    "user_id": "user-789",
    "project_id": "project-101"
  }
}
```

### User Preferences

#### Set Notification Preferences
```json
PUT /preferences/user-123
{
  "channels": {
    "email": {
      "enabled": true,
      "address": "user@example.com"
    },
    "sms": {
      "enabled": false,
      "number": "+1234567890"
    },
    "push": {
      "enabled": true,
      "tokens": ["device-token-1", "device-token-2"]
    }
  },
  "subscriptions": {
    "model.deployed": ["email", "push"],
    "cluster.failed": ["email", "sms", "push"],
    "system.maintenance": ["email"]
  },
  "quiet_hours": {
    "enabled": true,
    "start": "22:00",
    "end": "08:00",
    "timezone": "America/New_York"
  }
}
```

## =� Deployment

### Docker Deployment

```bash
# Build image
docker build -t budnotify:latest .

# Run with docker-compose
docker-compose up -d
```

### Kubernetes Deployment

```bash
# Deploy with Helm
helm install budnotify ./charts/budnotify/

# Or as part of full stack
cd ../../infra/helm/bud
helm dependency update
helm install bud .
```

### Production Configuration

```yaml
# values.yaml for Helm
budnotify:
  replicas: 3
  resources:
    requests:
      memory: "256Mi"
      cpu: "250m"
    limits:
      memory: "1Gi"
      cpu: "1000m"
  env:
    - name: EMAIL_PROVIDER
      value: "sendgrid"
    - name: SMS_PROVIDER
      value: "twilio"
  secrets:
    - name: EMAIL_API_KEY
      key: sendgrid-api-key
    - name: SMS_AUTH_TOKEN
      key: twilio-auth-token
```

## >� Testing

### Unit Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=budnotify --cov-report=html

# Run specific test module
pytest tests/test_email_delivery.py
```

### Integration Tests

```bash
# With Dapr sidecar
pytest tests/integration/ --dapr-http-port 3510 --dapr-api-token $DAPR_API_TOKEN
```

### Channel Tests

```bash
# Test email delivery
pytest tests/channels/test_email.py

# Test SMS delivery
pytest tests/channels/test_sms.py

# Test webhook delivery
pytest tests/channels/test_webhook.py
```

### Event Tests

```bash
# Test pub/sub integration
pytest tests/pubsub/test_dapr_integration.py

# Test event handling
pytest tests/pubsub/test_event_handlers.py
```

## =' Troubleshooting

### Common Issues

#### Email Delivery Failed
```bash
# Error: SMTP authentication failed
# Solution: Check email provider credentials
# Verify SMTP settings in .env
export SMTP_USERNAME=correct-username
export SMTP_PASSWORD=correct-password
```

#### SMS Delivery Failed
```bash
# Error: Twilio authentication failed
# Solution: Verify Twilio credentials
curl -X GET "https://api.twilio.com/2010-04-01/Accounts.json" \
  -u $TWILIO_ACCOUNT_SID:$TWILIO_AUTH_TOKEN
```

#### Event Not Received
```bash
# Error: Published event not received by subscribers
# Solution: Check Dapr pub/sub configuration
curl http://localhost:3510/v1.0/publish/pubsub/test-topic \
  -H "Content-Type: application/json" \
  -d '{"test": "message"}'
```

#### Template Rendering Error
```bash
# Error: Template variable not found
# Solution: Validate template data
python scripts/validate_template.py --template welcome --data '{"name": "John"}'
```

### Debug Mode

Enable detailed logging:
```bash
# In .env
LOG_LEVEL=DEBUG
ENABLE_CHANNEL_LOGGING=true

# For event debugging
ENABLE_EVENT_TRACING=true
DAPR_LOG_LEVEL=debug
```

### Monitoring

```bash
# Check service health
curl http://localhost:9085/health

# Monitor delivery statistics
curl http://localhost:9085/metrics/delivery

# Check event subscriptions
curl http://localhost:9085/events/subscriptions/status
```

## > Contributing

Please see the main [Bud Stack Contributing Guide](../../CONTRIBUTING.md).

### Service-Specific Guidelines

1. Follow event naming conventions (service.action format)
2. Add tests for new notification channels
3. Update template documentation for new templates
4. Ensure proper error handling for delivery failures
5. Maintain backward compatibility for event schemas

## =� License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](../../LICENSE) file for details.

## = Related Documentation

- [Main Bud Stack README](../../README.md)
- [CLAUDE.md Development Guide](../../CLAUDE.md)
- [API Documentation](http://localhost:9085/docs) (when running)
- [Event Schema Documentation](./docs/event-schemas.md)
- [Template Guide](./docs/template-guide.md)
- [Channel Integration Guide](./docs/channel-integration.md)
