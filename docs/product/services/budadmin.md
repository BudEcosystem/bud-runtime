# budadmin - Low-Level Design
---

## 1. Document Overview

### 1.1 Purpose

This LLD provides build-ready technical specifications for budadmin, the main dashboard application of Bud AI Foundry. Built with Next.js 14, it serves as the primary user interface for platform management.

### 1.2 Scope

**In Scope:**
- Dashboard and navigation
- Cluster management UI
- Model deployment workflows
- Endpoint configuration
- User and project management
- Monitoring views
- State management with Zustand

**Out of Scope:**
- API implementation (backend services)
- Authentication logic (Keycloak)
- Model inference (budgateway)

### 1.3 Intended Audience

| Audience | What They Need |
|----------|----------------|
| Frontend Developers | Component structure, state patterns |
| UX Designers | UI capabilities, flow patterns |
| Operations | Configuration, deployment |

---

## 2. System Context & Assumptions

### 2.1 Business Assumptions

- Primary interface for platform users
- Supports desktop and tablet screen sizes
- Real-time updates for cluster status
- Multi-step workflows for complex operations

### 2.2 Technical Assumptions

- Next.js 14 with App Router
- Zustand for client-side state
- Ant Design 5.x component library
- Keycloak for authentication

### 2.3 External Dependencies

| Dependency | Type | Failure Impact | Fallback Strategy |
|------------|------|----------------|-------------------|
| budapp API | Required | No functionality | Show error state |
| Keycloak | Required | No authentication | Redirect to login |
| WebSocket | Optional | No real-time updates | Polling fallback |

---

## 3. Detailed Architecture

### 3.1 Application Structure

```
src/
├── pages/              # Next.js pages (routing)
│   ├── api/            # API routes (BFF pattern)
│   │   └── requests.ts # Centralized API client
│   ├── clusters/       # Cluster management
│   ├── endpoints/      # Model endpoints
│   ├── models/         # Model registry
│   ├── projects/       # Project management
│   └── settings/       # Platform settings
│
├── components/         # Reusable UI components
│   ├── common/         # Shared components
│   ├── clusters/       # Cluster-specific
│   ├── endpoints/      # Endpoint-specific
│   └── layouts/        # Page layouts
│
├── flows/              # Multi-step workflows
│   ├── DeploymentFlow/
│   └── ClusterSetupFlow/
│
├── stores/             # Zustand state stores
│   ├── useAuthStore.ts
│   ├── useClusterStore.ts
│   └── useEndpointStore.ts
│
├── hooks/              # Custom React hooks
│   ├── useApi.ts
│   ├── useWebSocket.ts
│   └── usePolling.ts
│
└── styles/             # Global and component styles
```

### 3.2 State Management

```typescript
// useClusterStore.ts
interface ClusterStore {
  clusters: Cluster[];
  selectedCluster: Cluster | null;
  loading: boolean;
  fetchClusters: () => Promise<void>;
  selectCluster: (id: string) => void;
  refreshCluster: (id: string) => Promise<void>;
}
```

---

## 4. Data Design

### 4.1 API Client Pattern

```typescript
// pages/api/requests.ts
export const apiClient = {
  clusters: {
    list: () => fetch('/api/clusters'),
    get: (id: string) => fetch(`/api/clusters/${id}`),
    create: (data: CreateClusterRequest) => fetch('/api/clusters', {
      method: 'POST',
      body: JSON.stringify(data)
    }),
  },
  endpoints: {
    list: (projectId: string) => fetch(`/api/projects/${projectId}/endpoints`),
    deploy: (data: DeployRequest) => fetch('/api/endpoints', {
      method: 'POST',
      body: JSON.stringify(data)
    }),
  },
};
```

---

## 5. API & Interface Design

### 5.1 BFF (Backend for Frontend) Routes

| Route | Backend API | Purpose |
|-------|-------------|---------|
| /api/clusters | budapp | Cluster operations |
| /api/endpoints | budapp | Endpoint operations |
| /api/models | budmodel | Model registry |
| /api/metrics | budmetrics | Performance data |

---

## 6. Logic & Algorithm Details

### 6.1 Deployment Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Select    │────▶│   Select    │────▶│  Configure  │
│    Model    │     │   Cluster   │     │  Parameters │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌──────────────────────────┘
                    │
                    ▼
              ┌─────────────┐     ┌─────────────┐
              │   Review    │────▶│   Deploy    │
              │   Summary   │     │             │
              └─────────────┘     └─────────────┘
```

### 6.2 Real-Time Updates

```typescript
// useWebSocket hook
function useClusterStatus(clusterId: string) {
  const [status, setStatus] = useState<ClusterStatus | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}/clusters/${clusterId}/status`);
    ws.onmessage = (event) => {
      setStatus(JSON.parse(event.data));
    };
    return () => ws.close();
  }, [clusterId]);

  return status;
}
```

---

## 7. GenAI/ML-Specific Design

### 7.1 Model Deployment UI

| Step | Component | Data Collected |
|------|-----------|----------------|
| Model Selection | ModelSelector | model_id, version |
| Cluster Selection | ClusterSelector | cluster_id |
| Parameters | ParameterForm | replicas, resources |
| Optimization | OptimizationPanel | optimization_level |
| Review | ReviewSummary | All above |

---

## 8. Configuration & Environment

### 8.1 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| NEXT_PUBLIC_API_URL | Yes | - | budapp API URL |
| NEXT_PUBLIC_WS_URL | Yes | - | WebSocket URL |
| NEXT_PUBLIC_KEYCLOAK_URL | Yes | - | Keycloak URL |
| NEXT_PUBLIC_KEYCLOAK_REALM | Yes | - | Keycloak realm |
| NEXT_PUBLIC_KEYCLOAK_CLIENT_ID | Yes | - | OAuth client ID |

---

## 9. Security Design

### 9.1 Authentication Flow

1. User accesses protected route
2. Redirect to Keycloak login
3. Receive OAuth tokens
4. Store in secure cookie
5. Attach to API requests

### 9.2 Authorization

- Role-based access control via Keycloak
- UI elements hidden based on permissions
- API routes validate tokens

---

## 10. Performance & Scalability

### 10.1 Optimization Strategies

- Server-side rendering for initial load
- Code splitting by route
- Image optimization via Next.js
- Caching API responses

### 10.2 Bundle Size

- Tree-shaking Ant Design imports
- Dynamic imports for large components
- Compression enabled

---

## 11. Error Handling & Logging

### 11.1 Error Boundaries

```typescript
// ErrorBoundary component wraps major sections
// Displays friendly error UI on React errors
// Reports errors to monitoring service
```

### 11.2 API Error Handling

- Toast notifications for user errors
- Retry logic for transient failures
- Redirect to login on 401

---

## 12. Deployment & Infrastructure

### 12.1 Build and Deploy

```bash
npm run build    # Build production bundle
npm run start    # Start production server
```

### 12.2 Container

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build
EXPOSE 8007
CMD ["npm", "start"]
```

---

## 13. Testing Strategy

- Unit tests: Jest + React Testing Library
- E2E tests: Playwright
- Visual regression: Chromatic (optional)

---

## 14. Limitations & Future Enhancements

### 14.1 Current Limitations

- Desktop-focused responsive design
- No offline support
- Limited keyboard navigation

### 14.2 Planned Improvements

1. Mobile-responsive redesign
2. Dark mode support
3. Keyboard shortcuts
4. Accessibility (a11y) audit

---

## 15. Appendix

### 15.1 Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| next | 14.x | React framework |
| antd | 5.x | UI components |
| zustand | 4.x | State management |
| @ant-design/icons | 5.x | Icons |
| axios | 1.x | HTTP client |
