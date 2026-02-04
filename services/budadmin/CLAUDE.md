# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development
- `yarn dev` - Start development server on http://localhost:3000
- `yarn build` - Build production bundle
- `yarn start` - Start production server
- `yarn lint` - Run Next.js linting (note: no ESLint config file exists)

### Docker

**IMPORTANT: Dev Mode Configuration**

The `NEXT_PUBLIC_ENABLE_DEV_MODE` flag controls visibility of dev-only features (Prompts, Evaluations, Guard Rails menu items). This **MUST** be set at Docker **BUILD TIME**, not runtime, because Next.js performs tree-shaking during build that eliminates unreachable code.

Build commands:
- **Production**: `docker build -t budadmin:prod .` - Dev features hidden (default)
- **Development**: `docker build -t budadmin:dev --build-arg NEXT_PUBLIC_ENABLE_DEV_MODE=true .` - Dev features visible

Other commands:
- `docker run -p 3000:3000 --env-file .env budadmin:dev` - Run container with environment variables

**Why build-time?**: Other `NEXT_PUBLIC_*` variables (URLs, keys) use runtime replacement via `entrypoint.sh`, but boolean feature flags cause Next.js/Webpack to eliminate code at build time. Setting `NEXT_PUBLIC_ENABLE_DEV_MODE=true` at runtime won't restore code that was already tree-shaken.

## Architecture Overview

This is a Next.js 14 dashboard application for managing AI/ML model deployments and infrastructure.

### Key Technologies
- **Framework**: Next.js 14 with React 18 and TypeScript
- **State Management**: Zustand stores in `/src/stores/`
- **Styling**: Tailwind CSS + Ant Design + Radix UI components
- **API Client**: Custom axios wrapper in `/src/pages/api/requests.ts`

### Directory Structure
- `/src/components/` - Reusable UI components (auth, charts, popups, ui)
- `/src/flows/` - Complex multi-step workflows (AddModel, Benchmark, Cluster, DeployModel, Project)
- `/src/pages/` - Next.js pages and API routes
- `/src/stores/` - Zustand state management
- `/src/hooks/` - Custom React hooks
- `/src/utils/` - Utility functions

### API Architecture
The application uses a centralized API client (`AppRequest`) with:
- Automatic token refresh on 401 responses
- Network connectivity monitoring
- Bearer token authentication from localStorage
- Base URL configured via `NEXT_PUBLIC_BASE_URL` environment variable

Key API patterns:
```typescript
// GET request
await AppRequest.Get(`/endpoint`, { params: { key: value } })

// POST request
await AppRequest.Post(`/endpoint`, payload)
```

### Authentication Flow
1. Tokens stored in localStorage as `access_token` and `refresh_token`
2. Automatic token refresh with request queuing
3. Redirects to `/auth/login` on authentication failure
4. Role-based access control managed in `useUser` store

### State Management Patterns
Zustand stores follow this pattern:
- Async actions for API calls
- Loading states (`isLoading`, `loadingCount`)
- Error handling with toast notifications
- Complex workflows split into steps

Example store usage:
```typescript
const { user, getUser, isLoading } = useUser();
const { deploymentData, setStep, currentStep } = useDeployModel();
```

### Environment Variables
Critical environment variables that must be set:
- `NEXT_PUBLIC_BASE_URL` - Main API endpoint
- `NEXT_PUBLIC_VERCEL_ENV` - Environment setting
- `NEXT_PUBLIC_PASSWORD` - Authentication password
- `NEXT_PUBLIC_PRIVATE_KEY` - Encryption key
- `NEXT_PUBLIC_PLAYGROUND_URL` - Playground URL
- `NEXT_PUBLIC_ENABLE_DEV_MODE` - **Build-time only** flag to enable dev features (Prompts, Evaluations, Guard Rails)
- Various `NEXT_PUBLIC_NOVU_*` for notifications

**Note**: Most `NEXT_PUBLIC_*` variables are set at runtime via Helm/environment, but `NEXT_PUBLIC_ENABLE_DEV_MODE` must be set at Docker build time to prevent tree-shaking.

### TypeScript Path Aliases
The project uses these path aliases configured in tsconfig.json:
- `@/*` maps to `/src/*`

### Key Features
1. **Model Management** - Deploy, evaluate, and manage AI models
2. **Cluster Management** - Manage cloud and local compute clusters
3. **Benchmarking** - Performance testing and leaderboards
4. **Project Organization** - Resource organization by projects
5. **Real-time Updates** - Socket.io integration for live updates

### Development Notes
- No test suite exists - consider API response structures when making changes
- No ESLint configuration file - rely on Next.js default linting
- Complex workflows in `/src/flows/` have multiple interdependent steps
- API error responses show toast notifications via `handleErrorResponse`
- File uploads use FormData with automatic content-type switching

### Toast Notifications
Always use the custom toast functions from `@/components/toast` instead of Ant Design's `message` API to maintain consistent theming:

```typescript
import { successToast, errorToast } from "@/components/toast";

// Correct - uses themed toast
successToast("Pipeline updated successfully");
errorToast("Failed to update pipeline");

// Incorrect - do NOT use antd message
import { message } from "antd";
message.success("..."); // Don't use this
message.error("...");   // Don't use this
```
