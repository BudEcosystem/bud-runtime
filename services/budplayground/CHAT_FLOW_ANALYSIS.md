# BudPlayground Chat Flow Analysis

## Overview
The budplayground service implements a dual-mode chat system:
1. **Normal Chat Mode** - Standard conversation with a selected deployment
2. **Prompt Mode** - Chat flow initiated by prompt IDs with structured/unstructured input forms

This analysis details how PromptForm and NormalEditor interact, state management, and API integration.

---

## 1. PromptForm Component (`PromptForm.tsx`)

### Purpose
Displays a form when prompt IDs are present in the URL. Allows users to input structured data or unstructured text based on the prompt's input schema.

### Key Features

#### Props
```typescript
interface PromptFormProps {
  promptIds?: string[];      // Prompt identifiers from URL
  chatId?: string;           // Current chat session ID
  onSubmit: (data: any) => void;  // Callback when form submitted
  onClose?: () => void;      // Callback to close form
}
```

#### Data Flow
1. **Initialization (useEffect lines 27-96)**
   - Triggered when `promptIds` or auth credentials change
   - Calls `getPromptConfig(promptIds[0])` to fetch prompt configuration
   - Extracts input schema, version, and deployment name from response

2. **Schema Extraction (lines 50-64)**
   ```typescript
   // Handles two schema formats:
   // 1. Direct properties: { fieldName: { type, title, ... } }
   // 2. Nested $defs: { $defs: { InputSchema: { properties: {...} } } }

   let schemaToUse = config.data.input_schema ?? null;
   if (schemaToUse && schemaToUse.$defs?.InputSchema) {
     schemaToUse = schemaToUse.$defs.InputSchema.properties;
   }
   ```

3. **Form Initialization (lines 68-78)**
   - Initializes form data with default values from schema
   - Falls back to `unstructuredSchema` field if no schema properties

#### Input Rendering (lines 163-216)
Dynamically renders fields based on schema type:
- **string**: Text input (Ant Design Input)
- **number/integer**: Number input with min/max (InputNumber)
- **boolean**: Checkbox
- **default**: Text input fallback

#### Submission (lines 106-161)

**Payload Structure for Structured Input:**
```typescript
{
  prompt: {
    id: "prompt-id",
    version: "9",
    variables: {           // Structured variables
      place: "kerala",
      author: "John Doe"
    }
  },
  input: undefined,        // Not included for structured
  model: "gpt-4o-mini",   // From deployment_name
  promptId: "prompt-id",
  variables: {...}         // Copy of variables
}
```

**Payload Structure for Unstructured Input:**
```typescript
{
  prompt: {
    id: "prompt-id",
    version: "1"
    // No variables field
  },
  input: "User entered text here",  // Unstructured text
  model: "gpt-4o-mini",
  promptId: "prompt-id"
}
```

### Key Implementation Details
- **Loading State (lines 21, 218-226)**: Shows loading spinner while fetching config
- **Form Visibility**: Only rendered if `showPromptForm` is true and `promptIds.length > 0` (ChatWindow line 371)
- **Form Hiding**: Automatically closes after submission via `setShowPromptForm(false)` in ChatWindow (line 213)
- **Error Handling**: Gracefully falls back to unstructured input on fetch failure (lines 84-89)

---

## 2. NormalEditor Component (`NormalEditor.tsx`)

### Purpose
Textarea-based message input component for both normal and prompt modes.

### Key Features

#### Props
```typescript
interface EditorProps {
  input: string;                    // Current input value
  handleSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;               // Disable during API call
  error?: Error;
  disabled?: boolean;               // Disable if no deployment selected
  stop?: () => void;                // Stop streaming
  handleInputChange: (e: any) => void;
  isPromptMode?: boolean;           // Flag for prompt-based chat
}
```

#### UI Components
1. **Textarea (lines 51-71)**
   - `disabled={isLoading || disabled}`
   - Placeholder changes based on mode (line 58-62):
     - Normal: "Select a deployment to chat"
     - Prompt: "Type a message and press Enter to send"
   - Keyboard handler: Enter sends, Shift+Enter adds newline

2. **Send Button (lines 93-122)**
   - Shows "Send" text when idle
   - Shows "Stop" icon when loading
   - Clicking during loading calls `stop()` to cancel streaming

#### Disabled State Logic
From ChatWindow (lines 345-350):
```typescript
disabled={
  promptIds.length > 0
    ? !promptFormSubmitted  // Disabled until form submitted
    : !chat?.selectedDeployment?.name  // Disabled if no deployment
}
isPromptMode={promptIds.length > 0}
```

---

## 3. State Management (Zustand Store)

### Chat Store (`app/store/chat.ts`)

#### Prompt-Specific State (lines 196-202)
```typescript
promptIds: string[];
setPromptIds: (ids: string[]) => void;
getPromptIds: () => string[];
```

**Flow:**
1. `chat/page.tsx` (lines 119-141) extracts promptIds from URL
2. Calls `setPromptIds(idsArray)` to store in global state
3. ChatWindow retrieves via `getPromptIds()` (line 38)
4. Compared against activeChatList to show/hide form

#### Session Management
- **activeChatList**: All active chat sessions
- **messages**: Keyed by chatId, stores all messages for that chat
- **Persistence**: Automatically saves to localStorage on state changes (line 155)

---

## 4. URL Parameters & Initialization

### URL Parameters (`chat/page.tsx` lines 119-141)

| Parameter | Type | Purpose |
|-----------|------|---------|
| `promptIds` | string | Comma-separated prompt IDs |
| `is_single_chat` | boolean | Single chat display mode |
| `model` | string | Pre-selected deployment model |
| `base_url` | string | Custom gateway base URL |
| `show_form` | boolean | Force show prompt form |

### Initialization Flow
1. **URL Parsing (lines 119-141)**
   ```typescript
   const promptIds = params.get('promptIds');
   if(promptIds) {
     const idsArray = promptIds.split(',').map(id => id.trim());
     setPromptIds(idsArray);
   }
   ```

2. **Chat Session Creation (lines 62-116)**
   - If promptIds exist: Create chats with IDs matching promptIds
   - If no promptIds: Create default single chat
   - Reuses existing chats if IDs match to prevent duplicates

3. **Form Display Detection (ChatWindow lines 94-103)**
   ```typescript
   const params = new URLSearchParams(window.location.search);
   const showForm = params.get('show_form');
   const promptIdsParam = params.get('promptIds');

   if (showForm === 'true' || (promptIdsParam && promptIdsParam.trim().length > 0)) {
     setShowPromptForm(true);
   }
   ```

---

## 5. API Integration

### Prompt Chat Endpoint (`app/api/prompt-chat/route.ts`)

**Route**: `POST /api/prompt-chat`

**Request Body Structure** (from line 99):
```typescript
{
  temperature: 1,                          // settings.temperature
  prompt?: {                               // Optional
    id: "prompt-id",
    version: "1",
    variables: {
      place: "kerala"                      // Space to underscore conversion
    }
  },
  input?: string                           // For unstructured prompts
}
```

**Key Processing (lines 52-64)**
```typescript
const buildPromptInput = (body: PromptBody) => {
  // Priority 1: Direct input field
  if (body.input && body.input.trim().length > 0) {
    return body.input;
  }
  // Priority 2: Construct from variables
  if (body.prompt?.variables) {
    return Object.entries(body.prompt.variables)
      .map(([key, value]) => `${key}: ${value}`)
      .join('\n');
  }
  return '';
};
```

**Variable Transformation (lines 111-118)**
```typescript
// Replace spaces with underscores for gateway compatibility
const transformedVariables: Record<string, string> = {};
Object.entries(body.prompt.variables).forEach(([key, value]) => {
  const transformedKey = key.replace(/\s+/g, '_');  // "first name" -> "first_name"
  transformedVariables[transformedKey] = value;
});
```

**Gateway Call (lines 139-143)**
```typescript
const response = await fetch(`${baseURL}/responses`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': authorization,
    'api-key': apiKey,
    'project-id': metadata.project_id
  },
  body: JSON.stringify(requestBody)
});
```

**Response Handling (lines 172-243)**
- Detects SSE format (lines 172-214) or JSON format (lines 217-243)
- Extracts text from `content_delta`, `output`, or `content.text` fields
- Returns usage metadata and finish reason
- Converts to streaming response for useChat hook

### Normal Chat Endpoint (`app/api/chat/route.ts`)

**Route**: `POST /api/chat`

**Client IP Propagation (lines 18-67)**
```typescript
const xForwardedFor = req.headers.get('x-forwarded-for');
const clientIp = xForwardedFor || cfConnectingIp || trueClientIp || xRealIp;
// Passed to gateway for accurate geolocation tracking
```

**Request Body (lines 69-89)**
```typescript
{
  id,
  messages,
  model,
  session_id: id,
  stream_options: { include_usage: true },
  stream: true,
  max_completion_tokens: ...,
  frequency_penalty: ...,
  stop: ...,
  temperature: ...,
  extra_body: {
    guided_json: ...,
    guided_decoding_backend: "outlines"
  }
}
```

**Metrics Collection (lines 106-127)**
```typescript
onChunk({ chunk }) {
  if (ttft === 0) {
    ttft = Date.now() - startTime;  // Time to first token
  } else {
    itls.push(Date.now() - most_recent_time);  // Inter-token latencies
  }
}

// On finish:
dataStream.writeMessageAnnotation({
  type: 'metrics',
  e2e_latency: duration,
  ttft,
  throughput: completionTokens / duration,
  itl: average inter-token latency
});
```

---

## 6. Chat Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                   URL with promptIds                             │
└─────────────┬───────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│ chat/page.tsx: Extract & Parse URL Parameters                   │
│ - Parse promptIds from URL                                      │
│ - setPromptIds(idsArray) → Chat Store                           │
│ - Create chat sessions with ID = promptId                       │
└─────────────┬───────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│ ChatWindow: Check for Prompt Form Display                        │
│ - getPromptIds() from store (line 38)                           │
│ - If promptIds exist, setShowPromptForm(true) (line 101)        │
└─────────────┬───────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│ PromptForm: Render Dynamic Form                                  │
│ - fetch getPromptConfig(promptId)                               │
│ - render fields based on input_schema                           │
│ - collect user inputs                                            │
└─────────────┬───────────────────────────────────────────────────┘
              │
              ▼ User submits form
┌─────────────────────────────────────────────────────────────────┐
│ handlePromptFormSubmit (ChatWindow.tsx line 188)                 │
│ - setPromptData(formData) → stored in ChatWindow state          │
│ - setPromptFormSubmitted(true) → enables NormalEditor           │
│ - append({role: 'user', content: userMessage})                  │
│ - setShowPromptForm(false) → hides PromptForm                   │
└─────────────┬───────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│ useChat Hook Configuration                                       │
│ - api: '/api/prompt-chat' (if promptIds.length > 0)             │
│ - body includes promptData merged with chat settings            │
└─────────────┬───────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│ NormalEditor: Now Enabled                                        │
│ - disabled = false (because promptFormSubmitted = true)         │
│ - isPromptMode = true (shows prompt message)                    │
│ - Ready for follow-up messages                                  │
└─────────────┬───────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│ User Types Message & Hits Enter/Send                             │
│ - handleSubmit triggers useChat.append()                         │
│ - Includes promptData + new message                              │
└─────────────┬───────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│ /api/prompt-chat Endpoint                                        │
│ - Receives { prompt, input, model, metadata, settings }        │
│ - Calls gateway /v1/responses endpoint                          │
│ - Returns streaming response                                    │
└─────────────┬───────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Response Handling & Display                                      │
│ - Messages rendered in ChatWindow                                │
│ - Saved to store via addMessage()                                │
│ - Metrics collected (ttft, latency, throughput)                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Integration Points & Coordination

### 1. **Store Coordination**
| Component | Reads From Store | Writes To Store |
|-----------|------------------|-----------------|
| chat/page.tsx | - | setPromptIds, setActiveChatList |
| ChatWindow | promptIds, messages, currentSettingPreset | addMessage, updateChat |
| PromptForm | promptIds | - (reads only) |
| useChat hook | (via messages param) | - (handled by ChatWindow) |

### 2. **Data Flow Through useChat Hook**

**Body Construction (ChatWindow lines 41-66)**:
```typescript
const body = useMemo(() => {
  const baseBody = {
    model: chat?.selectedDeployment?.name,
    metadata: { project_id: ... },
    settings: currentSettingPreset,
  };

  // Merge prompt data on first message
  if (promptData) {
    return { ...baseBody, ...promptData };
  }
  return baseBody;
}, [chat, currentSettingPreset, promptData]);

const { messages, input, handleInputChange, handleSubmit } = useChat({
  api: promptIds.length > 0 ? '/api/prompt-chat' : '/api/chat',
  body: body,
  ...
});
```

### 3. **First Message vs Follow-up Messages**

**First Message (with prompt form)**:
- Body includes `prompt`, `input`/`variables`, and `model`
- `/api/prompt-chat` endpoint used
- Prompt context applied to gateway call

**Follow-up Messages**:
- promptData already stored, merged into body
- Regular textarea messages appended
- Same `/api/prompt-chat` endpoint (because promptData persists)

---

## 8. Key Files & Responsibilities

| File | Responsibility |
|------|-----------------|
| `chat/page.tsx` | URL parameter parsing, chat session creation, prompt ID initialization |
| `chat/components/ChatWindow.tsx` | Orchestrates form/editor display, state coordination, message handling |
| `chat/components/PromptForm.tsx` | Dynamic form rendering, prompt config fetching, form submission |
| `components/bud/components/input/NormalEditor.tsx` | Message input UI, keyboard handling |
| `store/chat.ts` | Global state for chats, messages, prompt IDs, settings |
| `api/prompt-chat/route.ts` | Prompt-specific chat endpoint, gateway integration |
| `api/chat/route.ts` | Normal chat endpoint, metrics collection |
| `lib/api.ts` | Prompt config fetching, authentication handling |
| `lib/gateway.ts` | Gateway base URL resolution |

---

## 9. Integration Readiness Assessment

### Current Architecture Strengths
1. **Separation of Concerns**: Form logic isolated from chat logic
2. **State Persistence**: Messages and chats saved to localStorage
3. **Flexible Routing**: Chooses endpoint based on `promptIds` presence
4. **Schema Handling**: Supports both structured and unstructured inputs
5. **Error Recovery**: Graceful fallbacks for missing schemas

### Integration Points Needed (for agent settings)

1. **PromptForm → Settings Bridge**
   - Pass settings from agent to form
   - Pre-populate with agent defaults
   - Validate against agent constraints

2. **ChatWindow → Settings Sync**
   - Merge agent settings with user inputs
   - Update chat body with agent context
   - Handle settings changes mid-conversation

3. **Store Enhancement**
   - Track active agent context
   - Store agent-specific metadata
   - Support agent switching per chat

4. **API Endpoint Updates**
   - `/api/prompt-chat` enhancement for agent metadata
   - Gateway integration for agent routing
   - Agent context propagation

---

## 10. Example: Complete Prompt Flow

```
URL: /chat?promptIds=prompt_123&model=gpt-4o-mini

1. chat/page.tsx:
   - Extracts: promptIds = ['prompt_123'], model = 'gpt-4o-mini'
   - Creates: Chat { id: 'prompt_123', name: 'Prompt 1' }
   - Calls: setPromptIds(['prompt_123'])

2. ChatWindow mounts:
   - getPromptIds() returns ['prompt_123']
   - setShowPromptForm(true) triggered by useEffect

3. PromptForm renders:
   - Calls: getPromptConfig('prompt_123')
   - Response: { input_schema: {topic: {type: 'string'}}, deployment_name: 'gpt-4o-mini' }
   - Renders: Text input for 'topic'

4. User enters "Science Fiction" and clicks "Next":
   - onSubmit called with:
     {
       prompt: { id: 'prompt_123', version: '1', variables: {topic: 'Science Fiction'} },
       model: 'gpt-4o-mini',
       promptId: 'prompt_123'
     }

5. ChatWindow.handlePromptFormSubmit:
   - setPromptData({...payload})
   - setPromptFormSubmitted(true)
   - append({role: 'user', content: 'topic: Science Fiction'})
   - setShowPromptForm(false)

6. useChat processes append:
   - Sends POST to /api/prompt-chat with:
     {
       messages: [...],
       model: 'gpt-4o-mini',
       metadata: {...},
       settings: {...},
       prompt: {...},
       variables: {topic: 'Science Fiction'}
     }

7. /api/prompt-chat:
   - Calls gateway /v1/responses with prompt context
   - Returns streaming response

8. ChatWindow.handleFinish:
   - Saves messages to store
   - Updates chat total_tokens
   - Shows response in chat

9. User types follow-up "Make it about space exploration":
   - NormalEditor sends via useChat.handleSubmit
   - Same /api/prompt-chat endpoint used
   - Prompt context still included from promptData
   - Response continues conversation in prompt context
```

---

## Summary

The budplayground service implements a sophisticated dual-mode chat system where:

1. **PromptForm** acts as a pre-chat intake form, collecting structured/unstructured input
2. **NormalEditor** serves both as the initial prompt input and subsequent message sender
3. **Zustand Store** coordinates state across components and persists to localStorage
4. **API Routing** dynamically chooses endpoints based on prompt presence
5. **Gateway Integration** sends prompts with their full context to the backend

The system is ready for agent-based integration at multiple points:
- Form field customization via agent schema
- Settings propagation through ChatWindow
- Agent routing in API endpoints
- Context preservation across message streams
