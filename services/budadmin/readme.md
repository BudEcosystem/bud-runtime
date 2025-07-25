# BudAdmin Dashboard

[![License](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0)
[![Next.js](https://img.shields.io/badge/Next.js-14+-black.svg)](https://nextjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue.svg)](https://www.typescriptlang.org/)
[![React](https://img.shields.io/badge/React-18+-blue.svg)](https://reactjs.org/)

A comprehensive Next.js 14 dashboard application for managing AI/ML model deployments and infrastructure with real-time updates via Socket.io. BudAdmin provides an intuitive web interface for all Bud Stack platform operations.

## 🚀 Features

- **Model Management**: Register, deploy, and monitor AI/ML models across clusters
- **Cluster Administration**: Manage multi-cloud clusters (AWS EKS, Azure AKS, on-premises)
- **Project Organization**: Organize models and deployments by projects with team collaboration
- **Real-time Monitoring**: Live updates of deployment status and performance metrics
- **Performance Analytics**: Interactive dashboards with charts and performance insights
- **User Management**: Role-based access control with Keycloak integration
- **Benchmarking**: Model performance evaluation and comparison tools
- **Deployment Orchestration**: Visual deployment workflows and status tracking
- **Resource Management**: Monitor cluster resources and optimize utilization

## 📋 Table of Contents

- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Development](#-development)
- [Configuration](#-configuration)
- [Deployment](#-deployment)
- [Testing](#-testing)
- [Troubleshooting](#-troubleshooting)

## 🏗️ Architecture

### Frontend Structure

```
budadmin/
├── src/
│   ├── pages/              # Next.js 14 pages
│   │   ├── api/           # API routes
│   │   │   └── requests.ts # Centralized API client
│   │   ├── auth/          # Authentication pages
│   │   ├── dashboard/     # Main dashboard
│   │   ├── models/        # Model management
│   │   ├── clusters/      # Cluster management
│   │   ├── projects/      # Project management
│   │   └── analytics/     # Performance analytics
│   ├── components/        # Reusable UI components
│   │   ├── common/        # Common components
│   │   ├── charts/        # Chart components
│   │   ├── forms/         # Form components
│   │   ├── layout/        # Layout components
│   │   └── modals/        # Modal components
│   ├── flows/             # Multi-step workflows
│   │   ├── model-deployment/
│   │   ├── cluster-setup/
│   │   └── benchmarking/
│   ├── stores/            # Zustand state management
│   │   ├── auth.ts        # Authentication state
│   │   ├── models.ts      # Model state
│   │   ├── clusters.ts    # Cluster state
│   │   └── projects.ts    # Project state
│   ├── hooks/             # Custom React hooks
│   │   ├── useAuth.ts     # Authentication hook
│   │   ├── useModels.ts   # Model management hook
│   │   └── useWebSocket.ts # WebSocket hook
│   ├── utils/             # Utility functions
│   │   ├── api.ts         # API utilities
│   │   ├── auth.ts        # Auth utilities
│   │   └── formatting.ts  # Data formatting
│   └── styles/            # Styling
│       ├── globals.css    # Global styles
│       └── components/    # Component styles
├── public/                # Static assets
├── types/                 # TypeScript type definitions
├── tests/                 # Test files
├── docs/                  # Documentation
└── deploy/                # Deployment configurations
```

### Core Technologies

- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe JavaScript
- **Tailwind CSS** - Utility-first CSS framework
- **Ant Design** - UI component library
- **Radix UI** - Headless UI components
- **Zustand** - Lightweight state management
- **Socket.io** - Real-time communication
- **React Query** - Server state management
- **Chart.js/Recharts** - Data visualization

### State Management

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    Auth     │     │   Models    │     │  Clusters   │
│    Store    │     │    Store    │     │    Store    │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                    │
       └───────────────────┴────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Global     │
                    │  State      │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   React     │
                    │ Components  │
                    └─────────────┘
```

## 📦 Prerequisites

### Required

- **Node.js** 18+ (LTS recommended)
- **npm** or **yarn**
- **Git**

### Service Dependencies

- **BudApp API** - Backend API service
- **WebSocket Server** - Real-time updates
- **Authentication Provider** - Keycloak or similar

### Development Tools

- **VS Code** (recommended)
- **Node.js extensions**
- **TypeScript support**

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/BudEcosystem/bud-stack.git
cd bud-stack/services/budadmin

# Install dependencies
npm install
# or
yarn install
```

### 2. Configure Environment

Create a `.env.local` file:

```bash
# API Configuration
NEXT_PUBLIC_BASE_URL=http://localhost:9081
NEXT_PUBLIC_API_VERSION=v1

# Authentication
NEXT_PUBLIC_AUTH_PROVIDER=keycloak
NEXT_PUBLIC_KEYCLOAK_URL=http://localhost:8080
NEXT_PUBLIC_KEYCLOAK_REALM=bud-serve
NEXT_PUBLIC_KEYCLOAK_CLIENT_ID=bud-admin

# WebSocket Configuration
NEXT_PUBLIC_WEBSOCKET_URL=ws://localhost:8080

# Notification Service
NEXT_PUBLIC_NOVU_SOCKET_URL=wss://ws.novu.co
NEXT_PUBLIC_NOVU_BASE_URL=https://api.novu.co
NEXT_PUBLIC_NOVU_APP_ID=your-novu-app-id

# Feature Flags
NEXT_PUBLIC_ENABLE_ANALYTICS=true
NEXT_PUBLIC_ENABLE_BENCHMARKING=true
NEXT_PUBLIC_ENABLE_PLAYGROUND=true

# External Services
NEXT_PUBLIC_PLAYGROUND_URL=http://localhost:3001
NEXT_PUBLIC_TEMP_API_BASE_URL=http://localhost:9087
NEXT_PUBLIC_COPY_CODE_API_BASE_URL=http://localhost:9088

# Development
NEXT_PUBLIC_ENVIRONMENT=development
NEXT_PUBLIC_LOG_LEVEL=debug
```

### 3. Start Development Server

```bash
# Development mode (with hot reload)
npm run dev
# or
yarn dev

# Application will be available at:
# http://localhost:8007 (configured port)
```

### 4. Build for Production

```bash
# Build production bundle
npm run build
# or
yarn build

# Start production server
npm run start
# or
yarn start
```

## 💻 Development

### Code Quality

```bash
# Linting
npm run lint
# or
yarn lint

# Type checking
npm run type-check
# or
yarn type-check

# Format code
npm run format
# or
yarn format
```

### Component Development

```bash
# Start Storybook (if configured)
npm run storybook

# Run component tests
npm run test:components
```

### State Management

The application uses Zustand for state management:

```typescript
// stores/auth.ts
import { create } from 'zustand'

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  login: (credentials: LoginCredentials) => Promise<void>
  logout: () => void
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  login: async (credentials) => {
    // Login logic
  },
  logout: () => {
    set({ user: null, token: null, isAuthenticated: false })
  }
}))
```

### API Integration

```typescript
// utils/api.ts
import axios from 'axios'

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_BASE_URL,
  timeout: 10000,
})

// Request interceptor for auth
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
    }
    return Promise.reject(error)
  }
)
```

## ⚙️ Configuration

### Environment Variables

```bash
# Required
NEXT_PUBLIC_BASE_URL=            # Backend API URL
NEXT_PUBLIC_WEBSOCKET_URL=       # WebSocket server URL

# Authentication
NEXT_PUBLIC_AUTH_PROVIDER=       # Auth provider (keycloak, oauth)
NEXT_PUBLIC_KEYCLOAK_URL=        # Keycloak server URL
NEXT_PUBLIC_KEYCLOAK_REALM=      # Keycloak realm
NEXT_PUBLIC_KEYCLOAK_CLIENT_ID=  # Keycloak client ID

# Optional Features
NEXT_PUBLIC_ENABLE_ANALYTICS=    # Enable analytics dashboard
NEXT_PUBLIC_ENABLE_BENCHMARKING= # Enable benchmarking features
NEXT_PUBLIC_ENABLE_PLAYGROUND=   # Enable model playground

# External Services
NEXT_PUBLIC_NOVU_APP_ID=         # Novu notification service
NEXT_PUBLIC_PLAYGROUND_URL=      # Model playground URL
```

### Next.js Configuration

```javascript
// next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  experimental: {
    appDir: true,
  },
  env: {
    CUSTOM_KEY: process.env.CUSTOM_KEY,
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_BASE_URL}/api/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
```

### Tailwind Configuration

```javascript
// tailwind.config.js
module.exports = {
  content: [
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          500: '#3b82f6',
          900: '#1e3a8a',
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}
```

## 🚀 Deployment

### Docker Deployment

```bash
# Build Docker image
docker build -t budadmin:latest .

# Run container
docker run -d -p 8007:3000 \
  -e NEXT_PUBLIC_BASE_URL=https://api.yourdomain.com \
  -e NEXT_PUBLIC_WEBSOCKET_URL=wss://ws.yourdomain.com \
  budadmin:latest
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  budadmin:
    build: .
    ports:
      - "8007:3000"
    environment:
      - NEXT_PUBLIC_BASE_URL=http://budapp:9081
      - NEXT_PUBLIC_WEBSOCKET_URL=ws://budapp:8080
    depends_on:
      - budapp
    networks:
      - bud-network
```

### Kubernetes Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: budadmin
spec:
  replicas: 3
  selector:
    matchLabels:
      app: budadmin
  template:
    metadata:
      labels:
        app: budadmin
    spec:
      containers:
      - name: budadmin
        image: budadmin:latest
        ports:
        - containerPort: 3000
        env:
        - name: NEXT_PUBLIC_BASE_URL
          value: "https://api.yourdomain.com"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
```

### Helm Deployment

```bash
# Deploy with Helm
helm install budadmin ./charts/budadmin/

# Or as part of full stack
cd ../../infra/helm/bud
helm dependency update
helm install bud .
```

## 🧪 Testing

### Unit Tests

```bash
# Run all tests
npm run test
# or
yarn test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage
```

### Integration Tests

```bash
# Run integration tests
npm run test:integration

# Run E2E tests with Playwright
npm run test:e2e
```

### Component Testing

```bash
# Test React components
npm run test:components

# Visual regression testing
npm run test:visual
```

### Example Test

```typescript
// __tests__/components/ModelCard.test.tsx
import { render, screen } from '@testing-library/react'
import { ModelCard } from '@/components/models/ModelCard'

describe('ModelCard', () => {
  const mockModel = {
    id: '1',
    name: 'llama-2-7b',
    status: 'deployed',
    cluster: 'production'
  }

  it('renders model information correctly', () => {
    render(<ModelCard model={mockModel} />)
    
    expect(screen.getByText('llama-2-7b')).toBeInTheDocument()
    expect(screen.getByText('deployed')).toBeInTheDocument()
    expect(screen.getByText('production')).toBeInTheDocument()
  })

  it('handles click events', () => {
    const onClickMock = jest.fn()
    render(<ModelCard model={mockModel} onClick={onClickMock} />)
    
    screen.getByRole('button').click()
    expect(onClickMock).toHaveBeenCalledWith(mockModel)
  })
})
```

## 🔧 Troubleshooting

### Common Issues

#### Build Errors
```bash
# Error: Module not found
# Solution: Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Error: TypeScript compilation errors
# Solution: Check types and update dependencies
npm run type-check
npm update
```

#### Authentication Issues
```bash
# Error: Invalid token or unauthorized
# Solution: Check Keycloak configuration
# Verify NEXT_PUBLIC_KEYCLOAK_* variables
# Clear browser localStorage/cookies
```

#### API Connection Issues
```bash
# Error: Network request failed
# Solution: Verify backend API is running
curl http://localhost:9081/health

# Check CORS configuration
# Verify NEXT_PUBLIC_BASE_URL is correct
```

#### WebSocket Connection Failed
```bash
# Error: WebSocket connection refused
# Solution: Check WebSocket server and URL
# Verify NEXT_PUBLIC_WEBSOCKET_URL
# Check network/firewall settings
```

### Debug Mode

Enable debug logging:
```bash
# In .env.local
NEXT_PUBLIC_LOG_LEVEL=debug
NEXT_PUBLIC_ENVIRONMENT=development

# Enable React DevTools
NODE_ENV=development npm run dev
```

### Performance Monitoring

```bash
# Analyze bundle size
npm run analyze

# Check performance metrics
# Use browser DevTools Performance tab
# Monitor Core Web Vitals
```

### Browser Compatibility

- **Chrome** 90+
- **Firefox** 88+
- **Safari** 14+
- **Edge** 90+

## 🤝 Contributing

Please see the main [Bud Stack Contributing Guide](../../CONTRIBUTING.md).

### Frontend-Specific Guidelines

1. Follow React and Next.js best practices
2. Use TypeScript for all new code
3. Write comprehensive tests for components
4. Follow the established folder structure
5. Use Tailwind CSS for styling
6. Ensure responsive design for all screen sizes
7. Optimize for performance and accessibility

## 📄 License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](../../LICENSE) file for details.

## 🔗 Related Documentation

- [Main Bud Stack README](../../README.md)
- [CLAUDE.md Development Guide](../../CLAUDE.md)
- [Component Storybook](http://localhost:6006) (when running)
- [UI/UX Guidelines](./docs/ui-guidelines.md)
- [State Management Guide](./docs/state-management.md)
- [Deployment Guide](./docs/deployment.md)