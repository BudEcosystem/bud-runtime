# budadmin Service Documentation

---

## Overview

budadmin is the main dashboard application built with Next.js 14, providing the primary user interface for platform management, deployments, and monitoring.

---

## Service Identity

| Property | Value |
|----------|-------|
| **App ID** | budadmin |
| **Port** | 8007 |
| **Language** | TypeScript 5.x |
| **Framework** | Next.js 14 |
| **State** | Zustand |
| **UI Library** | Ant Design 5.x |

---

## Responsibilities

- Platform administration dashboard
- Cluster and deployment management
- Model endpoint configuration
- User and project management
- Monitoring and observability views
- Real-time status updates

---

## Application Structure

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

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Dashboard** | Overview of platform health and activity |
| **Cluster Management** | Create, configure, monitor clusters |
| **Model Deployment** | Deploy models with optimization |
| **Endpoint Management** | Configure and scale endpoints |
| **User Management** | Users, roles, permissions |
| **Project Management** | Organize resources by project |
| **Monitoring** | Real-time metrics and logs |
| **Audit Log** | View audit trail |

---

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | budapp API URL | Required |
| `NEXT_PUBLIC_WS_URL` | WebSocket URL | Required |
| `NEXT_PUBLIC_KEYCLOAK_URL` | Keycloak URL | Required |

---

## Development

```bash
cd services/budadmin

# Install dependencies
npm install

# Development server
npm run dev

# Type checking
npm run typecheck

# Linting
npm run lint

# Production build
npm run build
```

---

## Related Documents

- [End User Training](../training/end-user.md)
- [Dashboard Catalog](../operations/dashboard-catalog.md)
