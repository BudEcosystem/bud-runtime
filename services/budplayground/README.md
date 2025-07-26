# BudPlayground Service

[![License](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0)
[![Next.js](https://img.shields.io/badge/Next.js-14+-black.svg)](https://nextjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue.svg)](https://www.typescriptlang.org/)
[![React](https://img.shields.io/badge/React-18+-blue.svg)](https://reactjs.org/)

An interactive playground interface for experimenting with GenAI models, enabling users to test inference, compare models, and adjust various settings. BudPlayground provides a user-friendly environment for model exploration and experimentation.

## 🚀 Features

- **Interactive Model Testing**: Real-time inference testing with various AI/ML models
- **Model Comparison**: Side-by-side comparison of different models and configurations
- **Parameter Tuning**: Adjust temperature, top-k, top-p, and other generation parameters
- **Prompt Templates**: Pre-built templates for common use cases and prompt engineering
- **Chat Interface**: Conversational interface for chat-based models
- **Code Generation**: Specialized interface for code generation and completion
- **Response Analysis**: Detailed analysis of model responses and performance metrics
- **Export Functionality**: Export conversations and results for further analysis
- **Real-time Streaming**: Support for streaming responses and real-time generation

## 📋 Table of Contents

- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Development](#-development)
- [Features](#-features)
- [Configuration](#-configuration)
- [Deployment](#-deployment)
- [Testing](#-testing)
- [Troubleshooting](#-troubleshooting)

## 🏗️ Architecture

### Frontend Structure

```
budplayground/
├── src/
│   ├── app/                # Next.js 14 App Router
│   │   ├── playground/     # Main playground interface
│   │   ├── compare/        # Model comparison
│   │   ├── templates/      # Prompt templates
│   │   └── api/           # API routes
│   ├── components/         # React components
│   │   ├── playground/     # Playground-specific components
│   │   │   ├── ChatInterface.tsx
│   │   │   ├── ModelSelector.tsx
│   │   │   ├── ParameterPanel.tsx
│   │   │   └── ResponseViewer.tsx
│   │   ├── templates/      # Template components
│   │   │   ├── TemplateLibrary.tsx
│   │   │   ├── TemplateEditor.tsx
│   │   │   └── TemplatePreview.tsx
│   │   ├── comparison/     # Comparison components
│   │   │   ├── ModelCompare.tsx
│   │   │   ├── ResponseDiff.tsx
│   │   │   └── MetricsPanel.tsx
│   │   └── ui/            # Reusable UI components
│   ├── hooks/             # Custom React hooks
│   │   ├── useModelAPI.ts
│   │   ├── useStreaming.ts
│   │   └── useTemplates.ts
│   ├── lib/               # Utilities and helpers
│   │   ├── api.ts         # API client
│   │   ├── models.ts      # Model definitions
│   │   └── streaming.ts   # Streaming utilities
│   ├── types/             # TypeScript definitions
│   └── styles/            # Styling
├── public/                # Static assets
├── templates/             # Prompt template files
├── docs/                  # Documentation
└── deploy/                # Deployment configurations
```

### Core Technologies

- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe JavaScript
- **Tailwind CSS** - Utility-first CSS framework
- **React** - UI library
- **Server-Sent Events** - Real-time streaming
- **Zustand** - State management
- **Monaco Editor** - Code editor component

### Component Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Model     │────▶│  Parameter  │────▶│   Prompt    │
│  Selector   │     │    Panel    │     │   Editor    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Response   │◄────│    API      │◄────│  Request    │
│   Viewer    │     │   Client    │     │  Handler    │
└─────────────┘     └─────────────┘     └─────────────┘
```

## 📦 Prerequisites

### Required

- **Node.js** 18+ (LTS recommended)
- **npm**, **yarn**, **pnpm**, or **bun**
- **Git**

### Service Dependencies

- **BudApp API** - Backend model serving
- **BudGateway** - Model inference routing
- **Model Providers** - Available AI/ML models

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/BudEcosystem/bud-stack.git
cd bud-stack/services/budplayground

# Install dependencies
npm install
# or
yarn install
# or
pnpm install
# or
bun install
```

### 2. Configure Environment

Create a `.env.local` file:

```bash
# API Configuration
NEXT_PUBLIC_API_BASE_URL=http://localhost:9081
NEXT_PUBLIC_GATEWAY_URL=http://localhost:8080

# Model Providers
NEXT_PUBLIC_ENABLE_OPENAI=true
NEXT_PUBLIC_ENABLE_ANTHROPIC=true
NEXT_PUBLIC_ENABLE_HUGGINGFACE=true
NEXT_PUBLIC_ENABLE_LOCAL_MODELS=true

# Features
NEXT_PUBLIC_ENABLE_STREAMING=true
NEXT_PUBLIC_ENABLE_COMPARISON=true
NEXT_PUBLIC_ENABLE_TEMPLATES=true
NEXT_PUBLIC_ENABLE_EXPORT=true

# UI Configuration
NEXT_PUBLIC_MAX_RESPONSE_LENGTH=4000
NEXT_PUBLIC_DEFAULT_MODEL=llama-2-7b
NEXT_PUBLIC_THEME=light

# Development
NEXT_PUBLIC_ENVIRONMENT=development
NEXT_PUBLIC_DEBUG=false
```

### 3. Start Development Server

```bash
# Development mode
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev

# Application will be available at:
# http://localhost:3000
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

# Format code
npm run format
```

### Component Development

The playground uses a modular component architecture:

```typescript
// components/playground/ChatInterface.tsx
import { useState, useEffect } from 'react'
import { useModelAPI } from '@/hooks/useModelAPI'
import { useStreaming } from '@/hooks/useStreaming'

interface ChatInterfaceProps {
  model: string
  parameters: ModelParameters
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  model,
  parameters
}) => {
  const { sendMessage, loading } = useModelAPI(model)
  const { stream, isStreaming } = useStreaming()

  const handleSubmit = async (message: string) => {
    if (parameters.streaming) {
      await stream(message, parameters)
    } else {
      await sendMessage(message, parameters)
    }
  }

  return (
    <div className="chat-interface">
      {/* Chat implementation */}
    </div>
  )
}
```

### API Integration

```typescript
// lib/api.ts
import axios from 'axios'

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL,
  timeout: 30000,
})

export interface ModelRequest {
  model: string
  prompt: string
  parameters: {
    temperature: number
    max_tokens: number
    top_p: number
    top_k: number
  }
  stream?: boolean
}

export const sendModelRequest = async (request: ModelRequest) => {
  const response = await api.post('/v1/chat/completions', {
    model: request.model,
    messages: [{ role: 'user', content: request.prompt }],
    ...request.parameters,
    stream: request.stream,
  })

  return response.data
}
```

## 🎮 Features

### Interactive Playground

- **Model Selection**: Choose from available models across different providers
- **Parameter Controls**: Adjust generation parameters with real-time preview
- **Prompt Engineering**: Advanced prompt editing with syntax highlighting
- **Response Streaming**: Real-time response generation with streaming support

### Model Comparison

```typescript
// Example comparison configuration
const comparisonConfig = {
  models: ['llama-2-7b', 'gpt-3.5-turbo', 'claude-3-haiku'],
  prompt: 'Explain quantum computing in simple terms',
  parameters: {
    temperature: 0.7,
    max_tokens: 200,
  },
  metrics: ['response_time', 'token_count', 'quality_score']
}
```

### Prompt Templates

Built-in templates for common use cases:

- **Conversational AI**: Chat and dialogue templates
- **Code Generation**: Programming and code completion
- **Creative Writing**: Story and content generation
- **Analysis**: Data analysis and reasoning
- **Translation**: Language translation templates
- **Summarization**: Text summarization templates

### Advanced Features

```typescript
// Streaming implementation
const useStreamingResponse = (model: string) => {
  const [response, setResponse] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)

  const streamResponse = async (prompt: string, parameters: any) => {
    setIsStreaming(true)
    setResponse('')

    const eventSource = new EventSource(
      `/api/stream?model=${model}&prompt=${encodeURIComponent(prompt)}`
    )

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'token') {
        setResponse(prev => prev + data.content)
      } else if (data.type === 'done') {
        setIsStreaming(false)
        eventSource.close()
      }
    }

    eventSource.onerror = () => {
      setIsStreaming(false)
      eventSource.close()
    }
  }

  return { response, isStreaming, streamResponse }
}
```

## ⚙️ Configuration

### Environment Variables

```bash
# Required
NEXT_PUBLIC_API_BASE_URL=         # Backend API URL
NEXT_PUBLIC_GATEWAY_URL=          # Gateway service URL

# Model Providers
NEXT_PUBLIC_ENABLE_OPENAI=        # Enable OpenAI models
NEXT_PUBLIC_ENABLE_ANTHROPIC=     # Enable Anthropic models
NEXT_PUBLIC_ENABLE_HUGGINGFACE=   # Enable Hugging Face models
NEXT_PUBLIC_ENABLE_LOCAL_MODELS=  # Enable local model support

# Features
NEXT_PUBLIC_ENABLE_STREAMING=     # Enable streaming responses
NEXT_PUBLIC_ENABLE_COMPARISON=    # Enable model comparison
NEXT_PUBLIC_ENABLE_TEMPLATES=     # Enable prompt templates
NEXT_PUBLIC_ENABLE_EXPORT=        # Enable export functionality

# UI Settings
NEXT_PUBLIC_MAX_RESPONSE_LENGTH=  # Maximum response display length
NEXT_PUBLIC_DEFAULT_MODEL=        # Default selected model
NEXT_PUBLIC_THEME=               # UI theme (light/dark)
```

### Model Configuration

```typescript
// lib/models.ts
export const modelConfig = {
  'openai': {
    'gpt-4': {
      name: 'GPT-4',
      provider: 'OpenAI',
      type: 'chat',
      maxTokens: 8192,
      supportsStreaming: true,
      parameters: {
        temperature: { min: 0, max: 2, default: 0.7 },
        top_p: { min: 0, max: 1, default: 1 },
        max_tokens: { min: 1, max: 4096, default: 1000 }
      }
    }
  },
  'anthropic': {
    'claude-3-sonnet': {
      name: 'Claude 3 Sonnet',
      provider: 'Anthropic',
      type: 'chat',
      maxTokens: 4096,
      supportsStreaming: true
    }
  },
  'huggingface': {
    'meta-llama/Llama-2-7b-hf': {
      name: 'Llama 2 7B',
      provider: 'Hugging Face',
      type: 'completion',
      maxTokens: 2048,
      supportsStreaming: false
    }
  }
}
```

## 🚀 Deployment

### Docker Deployment

```bash
# Build Docker image
docker build -t budplayground:latest .

# Run container
docker run -d -p 3000:3000 \
  -e NEXT_PUBLIC_API_BASE_URL=https://api.yourdomain.com \
  -e NEXT_PUBLIC_GATEWAY_URL=https://gateway.yourdomain.com \
  budplayground:latest
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  budplayground:
    build: .
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_BASE_URL=http://budapp:9081
      - NEXT_PUBLIC_GATEWAY_URL=http://budgateway:8080
    depends_on:
      - budapp
      - budgateway
    networks:
      - bud-network
```

### Kubernetes Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: budplayground
spec:
  replicas: 2
  selector:
    matchLabels:
      app: budplayground
  template:
    metadata:
      labels:
        app: budplayground
    spec:
      containers:
      - name: budplayground
        image: budplayground:latest
        ports:
        - containerPort: 3000
        env:
        - name: NEXT_PUBLIC_API_BASE_URL
          value: "https://api.yourdomain.com"
        - name: NEXT_PUBLIC_GATEWAY_URL
          value: "https://gateway.yourdomain.com"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
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

# Run E2E tests
npm run test:e2e
```

### Component Testing

```typescript
// __tests__/components/ChatInterface.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ChatInterface } from '@/components/playground/ChatInterface'

describe('ChatInterface', () => {
  const mockProps = {
    model: 'gpt-3.5-turbo',
    parameters: {
      temperature: 0.7,
      max_tokens: 1000,
      top_p: 1,
      top_k: 50
    }
  }

  it('renders chat interface correctly', () => {
    render(<ChatInterface {...mockProps} />)

    expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument()
    expect(screen.getByText('Send')).toBeInTheDocument()
  })

  it('sends message when form is submitted', async () => {
    const mockSendMessage = jest.fn()
    render(<ChatInterface {...mockProps} onSendMessage={mockSendMessage} />)

    const input = screen.getByPlaceholderText('Type your message...')
    const sendButton = screen.getByText('Send')

    fireEvent.change(input, { target: { value: 'Hello, world!' } })
    fireEvent.click(sendButton)

    await waitFor(() => {
      expect(mockSendMessage).toHaveBeenCalledWith('Hello, world!')
    })
  })
})
```

## 🔧 Troubleshooting

### Common Issues

#### API Connection Failed
```bash
# Error: Failed to connect to backend API
# Solution: Verify API endpoint and network connectivity
curl http://localhost:9081/health

# Check environment variables
echo $NEXT_PUBLIC_API_BASE_URL
```

#### Model Loading Issues
```bash
# Error: Model not available
# Solution: Check model availability and provider status
# Verify model configuration in backend services

# Check available models
curl http://localhost:9081/v1/models
```

#### Streaming Not Working
```bash
# Error: Streaming responses not received
# Solution: Verify Server-Sent Events support
# Check browser network tab for event stream

# Test streaming endpoint
curl -N http://localhost:9081/v1/stream
```

#### Performance Issues
```bash
# Error: Slow response times
# Solution: Check backend performance and optimize requests
# Monitor network requests and response times

# Enable performance monitoring
export NEXT_PUBLIC_DEBUG=true
```

### Debug Mode

Enable debug logging:
```bash
# In .env.local
NEXT_PUBLIC_DEBUG=true
NEXT_PUBLIC_LOG_LEVEL=debug

# Enable detailed API logging
NEXT_PUBLIC_LOG_API_REQUESTS=true
NEXT_PUBLIC_LOG_RESPONSES=true
```

### Performance Monitoring

```bash
# Analyze bundle size
npm run analyze

# Monitor performance
# Use browser DevTools Performance tab
# Check Core Web Vitals

# Profile component rendering
npm run profile
```

## 🤝 Contributing

Please see the main [Bud Stack Contributing Guide](../../CONTRIBUTING.md).

### Service-Specific Guidelines

1. Follow React and Next.js best practices
2. Use TypeScript for all new components
3. Write comprehensive tests for UI components
4. Ensure responsive design for all screen sizes
5. Optimize for performance and accessibility
6. Test with multiple model providers
7. Maintain consistent UI/UX patterns

## 📄 License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](../../LICENSE) file for details.

## 🔗 Related Documentation

- [Main Bud Stack README](../../README.md)
- [CLAUDE.md Development Guide](../../CLAUDE.md)
- [Component Documentation](./docs/components.md)
- [Model Integration Guide](./docs/model-integration.md)
- [Template Creation Guide](./docs/template-guide.md)
- [Deployment Guide](./docs/deployment.md)
