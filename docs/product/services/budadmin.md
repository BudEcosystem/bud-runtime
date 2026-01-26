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

---

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

## 6. Configuration & Environment

### 6.1 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| NEXT_PUBLIC_API_URL | Yes | - | budapp API URL |
| NEXT_PUBLIC_WS_URL | Yes | - | WebSocket URL |
| NEXT_PUBLIC_KEYCLOAK_URL | Yes | - | Keycloak URL |
| NEXT_PUBLIC_KEYCLOAK_REALM | Yes | - | Keycloak realm |
| NEXT_PUBLIC_KEYCLOAK_CLIENT_ID | Yes | - | OAuth client ID |

---

## 7. Security Design

### 7.1 Authentication Flow

1. User accesses protected route
2. Redirect to Keycloak login
3. Receive OAuth tokens
4. Store in secure cookie
5. Attach to API requests

### 7.2 Authorization

- Role-based access control via Keycloak
- UI elements hidden based on permissions
- API routes validate tokens

---

## 8. Performance & Scalability

### 8.1 Optimization Strategies

- Server-side rendering for initial load
- Code splitting by route
- Image optimization via Next.js
- Caching API responses

### 8.2 Bundle Size

- Tree-shaking Ant Design imports
- Dynamic imports for large components
- Compression enabled

---

## 9. Deployment & Infrastructure

### 10.2 Container
