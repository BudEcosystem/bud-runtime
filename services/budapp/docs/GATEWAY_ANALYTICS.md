# BudApp Gateway Analytics Operations

## Overview

The Gateway Analytics Operations module in BudApp provides secure, authenticated access to gateway analytics data and manages blocking rules for API protection. It serves as the middleware layer between the frontend (BudAdmin) and backend services (BudMetrics, BudGateway), adding authentication, authorization, data enrichment, and real-time synchronization.

## Architecture

```
BudAdmin (Frontend)
        ↓ [JWT Auth]
    BudApp (This Module)
        ├─→ BudMetrics (Analytics Data)
        ├─→ PostgreSQL (Blocking Rules)
        └─→ Redis (Real-time Sync)
            ↓
        BudGateway (Enforcement)
```

## Module Structure

```
budapp/gateway_analytics_ops/
├── __init__.py
├── models.py              # SQLAlchemy models for blocking rules
├── schemas.py             # Pydantic schemas for API contracts
├── crud.py               # Database operations for blocking rules
├── services.py           # Business logic and proxy services
├── gateway_analytics_routes.py  # FastAPI route definitions
└── README.md             # Module documentation
```

## Features

### 1. Analytics Data Proxy

The module proxies analytics requests to BudMetrics while:
- Enforcing authentication via JWT tokens
- Filtering data based on user's project access
- Enriching responses with entity names (projects, models, endpoints)
- Caching frequently accessed data

### 2. Blocking Rules Management

Complete CRUD operations for managing API blocking rules:
- IP address and CIDR range blocking
- Geographic (country-based) blocking
- User agent pattern blocking
- Rate-based blocking with configurable thresholds

### 3. Real-time Synchronization

Blocking rules are synchronized to the gateway in real-time:
- PostgreSQL as source of truth
- Redis for real-time distribution
- Automatic sync on rule changes
- Bulk sync capabilities

## API Endpoints

### Analytics Endpoints

#### POST `/api/v1/gateway/analytics`
Query comprehensive gateway analytics with filtering.

**Request:**
```json
{
  "project_ids": ["uuid1", "uuid2"],
  "model_ids": ["uuid3"],
  "endpoint_ids": ["uuid4"],
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-01-31T23:59:59Z",
  "time_bucket": "1h",
  "metrics": ["total_requests", "error_rate", "avg_response_time"],
  "group_by": ["project_id", "model_id"]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "time_series": [...],
    "summary": {...},
    "enriched_entities": {
      "projects": {...},
      "models": {...},
      "endpoints": {...}
    }
  }
}
```

#### GET `/api/v1/gateway/geographical-stats`
Get geographical distribution of API requests.

**Query Parameters:**
- `start_time`: ISO timestamp (default: 7 days ago)
- `end_time`: ISO timestamp (default: now)
- `project_ids`: Comma-separated UUIDs

#### GET `/api/v1/gateway/blocking-stats`
Get statistics on blocked requests.

#### GET `/api/v1/gateway/top-routes`
Get most accessed API routes with performance metrics.

#### GET `/api/v1/gateway/client-analytics`
Get analytics grouped by client/user.

### Blocking Rules Endpoints

#### POST `/api/v1/gateway/blocking-rules`
Create a new blocking rule.

**Request:**
```json
{
  "name": "Block suspicious IPs",
  "description": "Block IPs showing suspicious behavior",
  "rule_type": "ip_blocking",
  "rule_config": {
    "ip_addresses": ["192.168.1.1", "10.0.0.0/8"],
    "action": "block"
  },
  "reason": "Suspicious activity detected",
  "priority": 100,
  "endpoint_id": "uuid"  // Optional: specific endpoint
}
```

#### GET `/api/v1/gateway/blocking-rules`
List blocking rules with filtering.

**Query Parameters:**
- `project_id`: Filter by project
- `rule_type`: Filter by type
- `status`: Filter by status (active/inactive)
- `page`: Page number
- `page_size`: Items per page

#### PUT `/api/v1/gateway/blocking-rules/{rule_id}`
Update an existing blocking rule.

#### DELETE `/api/v1/gateway/blocking-rules/{rule_id}`
Delete a blocking rule.

#### POST `/api/v1/gateway/blocking-rules/sync`
Manually trigger sync of blocking rules to Redis.

## Database Models

### GatewayBlockingRule

```python
class GatewayBlockingRule(Base):
    __tablename__ = "gateway_blocking_rules"

    id = Column(UUID, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    rule_type = Column(Enum(BlockingRuleType), nullable=False)
    rule_config = Column(JSON, nullable=False)
    status = Column(Enum(BlockingRuleStatus), default="active")
    reason = Column(String)
    priority = Column(Integer, default=0)

    # Relationships
    project_id = Column(UUID, ForeignKey("projects.id"))
    endpoint_id = Column(UUID, ForeignKey("endpoints.id"), nullable=True)
    created_by = Column(UUID, ForeignKey("users.id"))

    # Metrics
    match_count = Column(Integer, default=0)
    last_matched_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
```

## Service Implementation

### Analytics Service

```python
class GatewayAnalyticsService:
    """Service for proxying analytics requests to BudMetrics."""

    def __init__(self, session: Session, user: User):
        self.session = session
        self.user = user
        self.dapr_client = DaprClient()

    async def query_analytics(
        self,
        request: GatewayAnalyticsRequest
    ) -> GatewayAnalyticsResponse:
        # 1. Get user's accessible projects
        accessible_projects = await self.get_user_projects()

        # 2. Filter request by accessible projects
        filtered_request = self.filter_by_access(request, accessible_projects)

        # 3. Proxy to BudMetrics via Dapr
        response = await self.dapr_client.invoke_method(
            app_id="budmetrics",
            method_name="gateway/analytics",
            data=filtered_request
        )

        # 4. Enrich response with entity names
        enriched_response = await self.enrich_response(response)

        return enriched_response
```

### Blocking Rules Service

```python
class BlockingRulesService:
    """Service for managing blocking rules."""

    def __init__(self, session: Session, user: User):
        self.session = session
        self.user = user
        self.redis_client = RedisClient()
        self.crud = BlockingRuleDataManager(session)

    async def create_blocking_rule(
        self,
        project_id: UUID,
        rule_data: BlockingRuleCreate
    ) -> BlockingRule:
        # 1. Validate user has access to project
        await self.validate_project_access(project_id)

        # 2. Create rule in database
        rule = await self.crud.create_blocking_rule(
            project_id=project_id,
            user_id=self.user.id,
            rule_data=rule_data
        )

        # 3. Sync to Redis for gateway
        await self.sync_rule_to_redis(rule)

        return rule

    async def sync_rule_to_redis(self, rule: GatewayBlockingRule):
        """Sync a single rule to Redis."""
        key = f"gateway:blocking:rules:{rule.id}"
        value = {
            "id": str(rule.id),
            "type": rule.rule_type,
            "config": rule.rule_config,
            "status": rule.status,
            "project_id": str(rule.project_id),
            "endpoint_id": str(rule.endpoint_id) if rule.endpoint_id else None
        }
        await self.redis_client.set(key, json.dumps(value))

        # Add to appropriate index
        if rule.rule_type == "ip_blocking":
            for ip in rule.rule_config.get("ip_addresses", []):
                await self.redis_client.sadd(f"gateway:blocking:ips", ip)
```

## Redis Synchronization

### Data Structure

```
# Individual rules
gateway:blocking:rules:{rule_id} -> JSON rule data

# Indexes for fast lookup
gateway:blocking:ips -> Set of blocked IPs
gateway:blocking:countries -> Set of blocked country codes
gateway:blocking:user_agents -> Set of blocked patterns

# Rate limiting counters
gateway:rate_limit:{client_id} -> Request count (with TTL)

# Rule effectiveness metrics
gateway:blocking:stats:{rule_id} -> Match count
```

### Sync Process

1. **On Rule Create/Update/Delete**:
   - Update PostgreSQL (source of truth)
   - Sync to Redis immediately
   - Publish event for gateway notification

2. **Periodic Full Sync**:
   ```python
   @scheduled_task(interval=300)  # Every 5 minutes
   async def sync_all_rules():
       rules = await get_all_active_rules()
       await redis.delete("gateway:blocking:*")
       for rule in rules:
           await sync_rule_to_redis(rule)
   ```

3. **Gateway Consumption**:
   - Gateway subscribes to Redis changes
   - Maintains local cache with TTL
   - Falls back to Redis on cache miss

## Security Considerations

### Authentication & Authorization

1. **JWT Token Validation**:
   - All endpoints require valid JWT token
   - Token must contain user ID and roles
   - Token expiry is enforced

2. **Project-based Access Control**:
   ```python
   async def validate_project_access(
       self,
       project_id: UUID,
       required_permission: str = "read"
   ):
       # Check if user has access to project
       access = await self.session.query(ProjectUser).filter(
           ProjectUser.project_id == project_id,
           ProjectUser.user_id == self.user.id,
           ProjectUser.role.in_(["owner", "admin", "member"])
       ).first()

       if not access:
           raise HTTPException(403, "Access denied to project")
   ```

3. **Data Filtering**:
   - Analytics data automatically filtered by user's projects
   - Blocking rules scoped to accessible projects
   - No cross-project data leakage

### Input Validation

1. **SQL Injection Prevention**:
   - Use SQLAlchemy ORM for database queries
   - Parameterized queries for raw SQL
   - Input sanitization for all user inputs

2. **Schema Validation**:
   - Pydantic schemas for all API inputs
   - Type checking and range validation
   - Custom validators for complex rules

3. **Rate Limiting**:
   ```python
   @rate_limit(calls=100, period=60)  # 100 calls per minute
   async def query_analytics(...):
       # Implementation
   ```

## Performance Optimization

### Caching Strategy

1. **Response Caching**:
   ```python
   @cache(ttl=300, key_builder=analytics_cache_key)
   async def get_geographical_stats(...):
       # Expensive query cached for 5 minutes
   ```

2. **Entity Name Caching**:
   - Cache project, model, endpoint names
   - Refresh cache on entity updates
   - Use Redis for distributed caching

### Database Optimization

1. **Indexes**:
   ```sql
   CREATE INDEX idx_blocking_rules_project ON gateway_blocking_rules(project_id);
   CREATE INDEX idx_blocking_rules_type ON gateway_blocking_rules(rule_type);
   CREATE INDEX idx_blocking_rules_status ON gateway_blocking_rules(status);
   ```

2. **Query Optimization**:
   - Use eager loading for relationships
   - Batch queries where possible
   - Implement pagination for large results

## Monitoring & Logging

### Metrics

```python
# Prometheus metrics
gateway_analytics_requests = Counter(
    'gateway_analytics_requests_total',
    'Total analytics requests',
    ['endpoint', 'status']
)

blocking_rules_sync_duration = Histogram(
    'blocking_rules_sync_duration_seconds',
    'Time to sync rules to Redis'
)

blocking_rules_total = Gauge(
    'blocking_rules_total',
    'Total active blocking rules',
    ['type', 'project']
)
```

### Logging

```python
import structlog

logger = structlog.get_logger(__name__)

# Log important operations
logger.info(
    "blocking_rule_created",
    rule_id=rule.id,
    rule_type=rule.rule_type,
    project_id=rule.project_id,
    user_id=self.user.id
)

# Log errors with context
logger.error(
    "redis_sync_failed",
    rule_id=rule.id,
    error=str(e),
    retry_count=retry_count
)
```

## Testing

### Unit Tests

```python
# tests/test_blocking_rules.py
@pytest.mark.asyncio
async def test_create_blocking_rule():
    """Test creating a blocking rule."""
    service = BlockingRulesService(mock_session, mock_user)
    rule_data = BlockingRuleCreate(
        name="Test Rule",
        rule_type="ip_blocking",
        rule_config={"ip_addresses": ["192.168.1.1"]}
    )

    rule = await service.create_blocking_rule(project_id, rule_data)

    assert rule.name == "Test Rule"
    assert rule.rule_type == "ip_blocking"
    mock_redis.set.assert_called_once()
```

### Integration Tests

```python
@pytest.mark.integration
async def test_analytics_proxy_with_auth():
    """Test analytics proxy with authentication."""
    async with AsyncClient(app=app) as client:
        response = await client.post(
            "/api/v1/gateway/analytics",
            json={"start_time": "2024-01-01T00:00:00Z"},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code == 200
        assert "data" in response.json()
```

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**:
   - Check Redis URL in environment variables
   - Verify Redis is running
   - Check network connectivity

2. **Analytics Data Not Enriched**:
   - Verify entity IDs exist in database
   - Check for deleted entities
   - Review enrichment cache

3. **Blocking Rules Not Syncing**:
   - Check Redis connectivity
   - Verify sync job is running
   - Review sync logs for errors

4. **Access Denied Errors**:
   - Verify JWT token is valid
   - Check user's project access
   - Review permission requirements

## Migration Guide

### Database Migration

```bash
# Create blocking rules table
alembic upgrade head

# Verify migration
psql -d budapp -c "\\d gateway_blocking_rules"
```

### Redis Setup

```bash
# Set Redis URL
export REDIS_URL=redis://localhost:6379

# Test connection
redis-cli ping
```

### Initial Data Load

```python
# Script to migrate existing blocking rules
async def migrate_blocking_rules():
    # Load from old system
    old_rules = await load_old_rules()

    # Transform to new format
    for old_rule in old_rules:
        new_rule = transform_rule(old_rule)
        await crud.create_blocking_rule(new_rule)

    # Sync all to Redis
    await sync_all_rules_to_redis()
```
