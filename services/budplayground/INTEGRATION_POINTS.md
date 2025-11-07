# Integration Points for Agent Settings

## Quick Reference Guide

### 1. URL Parameter Detection
**File**: `app/chat/page.tsx` (lines 119-141)
```typescript
// Add agent-related URL parameters here
const agentId = params.get('agentId');
const agentSettings = params.get('agentSettings');
```

### 2. Store Enhancement
**File**: `app/store/chat.ts`
```typescript
// Add to ChatStore interface
agentContext?: {
  agentId: string;
  settings: AgentSettings;
  metadata: Record<string, any>;
};

// Methods to add
setAgentContext: (chatId: string, context: AgentContext) => void;
getAgentContext: (chatId: string) => AgentContext | undefined;
```

### 3. PromptForm Integration Points
**File**: `app/chat/components/PromptForm.tsx`

**Entry Point** (lines 16-24):
```typescript
interface PromptFormProps {
  promptIds?: string[];
  chatId?: string;
  onSubmit: (data: any) => void;
  onClose?: () => void;
  agentContext?: AgentContext;  // ADD THIS
}
```

**Data Fetch** (lines 27-96):
```typescript
// Merge agent settings with form data
useEffect(() => {
  // After getPromptConfig, merge agent defaults
  const mergedSchema = agentContext
    ? mergeAgentDefaults(schemaToUse, agentContext.settings)
    : schemaToUse;
}, [promptIds, agentContext, apiKey, accessKey]);
```

**Form Submission** (lines 106-161):
```typescript
const handleSubmit = (e: React.FormEvent) => {
  // Include agent context in payload
  const payload: any = { ... };
  if (agentContext) {
    payload.agentId = agentContext.agentId;
    payload.agentMetadata = agentContext.metadata;
  }
  onSubmit(payload);
};
```

### 4. ChatWindow Coordination
**File**: `app/chat/components/ChatWindow.tsx`

**State Setup** (after line 38):
```typescript
const agentContext = store.getAgentContext(chat.id);

// In useChat body construction (around line 41):
const body = useMemo(() => {
  const baseBody = { ... };
  if (promptData) {
    baseBody = { ...baseBody, ...promptData };
  }
  if (agentContext) {
    baseBody.agentId = agentContext.agentId;
    baseBody.agentMetadata = agentContext.metadata;
  }
  return baseBody;
}, [chat, currentSettingPreset, promptData, agentContext]);

// Pass to PromptForm (around line 372):
<PromptForm
  promptIds={getPromptIds()}
  chatId={chat.id}
  onSubmit={handlePromptFormSubmit}
  agentContext={agentContext}  // ADD THIS
/>
```

**Form Submission Handler** (around line 188):
```typescript
const handlePromptFormSubmit = (data: any) => {
  setPromptData(data);
  setPromptFormSubmitted(true);

  // If agent context, save it
  if (data.agentId) {
    store.setAgentContext(chat.id, {
      agentId: data.agentId,
      metadata: data.agentMetadata
    });
  }

  append({ role: 'user', content: userMessage });
  setShowPromptForm(false);
};
```

### 5. API Endpoint Enhancement
**File**: `app/api/prompt-chat/route.ts`

**Request Handling** (around line 67):
```typescript
const { messages, id, model, metadata, chat, prompt, agentId, agentMetadata } = await req.json();

// Add to gateway call headers (around line 130):
const headers: Record<string, string> = {
  'Content-Type': 'application/json',
  ...(authorization && { 'Authorization': authorization }),
  ...(agentId && { 'X-Agent-ID': agentId }),
  ...(agentMetadata && { 'X-Agent-Metadata': JSON.stringify(agentMetadata) }),
  // ... existing headers
};

// Add to request body (around line 99):
const requestBody: any = {
  temperature: body.settings?.temperature ?? 1,
  ...(agentId && { agent_id: agentId }),
  ...(agentMetadata && { agent_metadata: agentMetadata }),
  // ... existing body
};
```

### 6. NormalEditor (No Changes Required)
**File**: `app/components/bud/components/input/NormalEditor.tsx`
- Component is purely presentational
- Receives agent context indirectly through disabled/isPromptMode props
- No direct integration needed

### 7. Type Definitions to Add
**File**: `app/types/chat.ts` (or new `app/types/agent.ts`)
```typescript
export interface AgentSettings {
  temperature?: number;
  maxTokens?: number;
  system_prompt?: string;
  // ... other agent-specific settings
}

export interface AgentContext {
  agentId: string;
  settings: AgentSettings;
  metadata: {
    agentName?: string;
    agentVersion?: string;
    constraints?: Record<string, any>;
    [key: string]: any;
  };
}

export interface AgentIntegrationPayload {
  agentId: string;
  agentMetadata: AgentContext['metadata'];
  // ... other fields
}
```

---

## Data Flow Modifications

### Current Flow
```
URL → chat/page.tsx → ChatWindow → (PromptForm OR NormalEditor) → /api/prompt-chat → gateway
```

### Enhanced Flow with Agent Settings
```
URL (with agentId) → chat/page.tsx → ChatWindow
                                        ├→ Get agent context from store
                                        ├→ Pass to PromptForm
                                        └→ Merge into API body
                                             └→ /api/prompt-chat → gateway
```

---

## Implementation Checklist

### Phase 1: Store Enhancement
- [ ] Add agentContext to ChatStore interface
- [ ] Implement setAgentContext/getAgentContext methods
- [ ] Update localStorage persistence for agent context

### Phase 2: Type Definitions
- [ ] Create AgentSettings type
- [ ] Create AgentContext type
- [ ] Create AgentIntegrationPayload type
- [ ] Update PromptFormProps interface

### Phase 3: PromptForm Enhancement
- [ ] Accept agentContext prop
- [ ] Merge agent defaults with schema
- [ ] Include agent context in submission payload
- [ ] Handle agent constraints validation

### Phase 4: ChatWindow Integration
- [ ] Retrieve agent context from store
- [ ] Pass to PromptForm component
- [ ] Merge agent context into API body
- [ ] Save agent context on form submission

### Phase 5: API Endpoint Updates
- [ ] Extract agent fields from request body
- [ ] Add agent headers to gateway call
- [ ] Handle agent-specific error responses
- [ ] Log agent context for observability

### Phase 6: Testing
- [ ] Unit tests for agent context storage
- [ ] Integration tests for prompt form with agent
- [ ] E2E tests for complete agent flow
- [ ] Mock agent API responses

---

## Testing Strategy

### Unit Tests
```typescript
// Test agent context merging
describe('AgentContext Integration', () => {
  it('should merge agent settings with form defaults', () => {
    const schema = { topic: { type: 'string' } };
    const agentContext = { settings: { topic: 'Science' } };
    const merged = mergeAgentDefaults(schema, agentContext.settings);
    expect(merged.topic.default).toBe('Science');
  });

  it('should include agent metadata in submission', () => {
    const formData = { topic: 'Science' };
    const agentContext = { agentId: 'agent_123', metadata: { ... } };
    const payload = buildPayload(formData, agentContext);
    expect(payload.agentId).toBe('agent_123');
  });
});
```

### Integration Tests
```typescript
// Test full flow with agent
describe('Chat with Agent', () => {
  it('should initialize form with agent context', () => {
    render(<ChatWindow chat={chat} agentContext={agentContext} />);
    // Assert form shows agent defaults
  });

  it('should send agent context to API', async () => {
    // Mock API call
    // Assert agentId header is present
  });
});
```

---

## File Dependencies Map

```
chat/page.tsx
├── Reads: URL params (agentId, agentSettings)
├── Writes: setPromptIds, setAgentContext
└── Depends: store/chat.ts

chat/components/ChatWindow.tsx
├── Reads: agentContext from store
├── Writes: setAgentContext on form submit
├── Passes: agentContext to PromptForm
└── Depends: store/chat.ts, PromptForm.tsx, types/agent.ts

chat/components/PromptForm.tsx
├── Reads: agentContext prop
├── Merges: Agent defaults with schema
├── Submits: agentId + agentMetadata in payload
└── Depends: types/agent.ts, lib/api.ts

api/prompt-chat/route.ts
├── Reads: agentId, agentMetadata from body
├── Passes: As headers to gateway
└── Depends: types/agent.ts

store/chat.ts
├── Stores: agentContext per chat
├── Persists: To localStorage
└── Depends: types/agent.ts
```

---

## Migration Path

### For Existing Prompts (without agents)
- agentContext is optional (undefined by default)
- Existing flows continue unchanged
- Payload without agent fields is valid

### For New Agent-Based Workflows
- Include agentId in URL parameters
- Store will load agent context
- Form merges agent defaults
- API includes agent metadata

### Backward Compatibility
- All agent fields are optional
- Existing API contracts remain valid
- No breaking changes to gateway endpoint

---

## Key Considerations

1. **State Persistence**
   - Agent context should persist across page reloads
   - Clear when switching agents
   - Account for multi-user scenarios

2. **Form Validation**
   - Agent constraints must be respected
   - Pre-population should not override user input
   - Clear visual indication of agent-provided defaults

3. **API Contract**
   - Header format: 'X-Agent-ID', 'X-Agent-Metadata'
   - Body format: agent_id, agent_metadata
   - Gateway must accept and route based on agent

4. **Error Handling**
   - Agent not found scenarios
   - Invalid agent settings
   - Agent quota exceeded
   - Graceful fallback to non-agent mode

5. **Performance**
   - Lazy load agent configs
   - Cache agent settings
   - Minimize re-renders on agent context change
