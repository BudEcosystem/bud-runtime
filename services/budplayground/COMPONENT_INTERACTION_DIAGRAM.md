# Component Interaction Diagram & Architecture

## High-Level Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Next.js Application                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┼──────────────┐
                │             │              │
                ▼             ▼              ▼
        ┌────────────┐ ┌─────────────┐ ┌──────────────┐
        │ chat/page  │ │ AuthContext │ │ LoaderContext│
        └────────────┘ └─────────────┘ └──────────────┘
                │
                │ setPromptIds, setActiveChatList
                ▼
        ┌──────────────────┐
        │ Zustand Store    │
        │  (useChatStore)  │
        └──────────────────┘
                │
    ┌───────────┼────────────┐
    │           │            │
    ▼           ▼            ▼
┌─────────┐ ┌─────────┐ ┌──────────┐
│ Active  │ │Messages │ │promptIds │
│ Chats   │ │ Storage │ │          │
└─────────┘ └─────────┘ └──────────┘
    │
    │ getPromptIds, getMessages, createChat
    ▼
┌──────────────────────────────────────┐
│         ChatWindow Component         │
│  (Orchestrates entire chat UI)       │
└──────────────────────────────────────┘
    │
    ├─ promptIds: string[]
    ├─ promptData: any
    ├─ promptFormSubmitted: boolean
    ├─ input: string (from useChat)
    ├─ messages: Message[]
    └─ status: "submitted" | "streaming" | "pending"
    │
    ├─────────────────────────────────────────┐
    │                                         │
    ▼                                         ▼
┌──────────────────┐              ┌──────────────────┐
│  PromptForm      │              │  NormalEditor    │
│  (Form Intake)   │              │  (Message Input) │
└──────────────────┘              └──────────────────┘
    │                                    │
    ├─ Visibility:                       ├─ Disabled: !promptFormSubmitted
    │ showPromptForm && promptIds > 0    │           || !deployment
    │                                    │
    ├─ Fetches:                          └─ isPromptMode: promptIds > 0
    │ getPromptConfig(promptId)
    │
    ├─ Renders:
    │ Dynamic form fields based on
    │ input_schema
    │
    └─ onSubmit:
      handlePromptFormSubmit(data)
        ├─ setPromptData(data)
        ├─ setPromptFormSubmitted(true)
        ├─ append(userMessage)
        └─ setShowPromptForm(false)
```

---

## State Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    URL Parameters                                │
│  ?promptIds=id1,id2&model=gpt-4o-mini&agentId=agent_123        │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │  chat/page.tsx      │
            │  Parse URL Params   │
            └─────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
         ▼             ▼             ▼
    promptIds      model        agentId
         │             │             │
         └─────────────┼─────────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │  Zustand Store      │
            │  setPromptIds()     │
            │  setAgentContext()  │
            └─────────────────────┘
                       │
         ┌─────────────┼──────────────┐
         │             │              │
         ▼             ▼              ▼
    promptIds[]   agentContext[]  activeChatList[]
    (global)      (per chat)       (sessions)
         │             │              │
         └─────────────┼──────────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │  ChatWindow         │
            │  getPromptIds()     │
            │  getAgentContext()  │
            └─────────────────────┘
                       │
         ┌─────────────┼──────────────┐
         │             │              │
         ▼             ▼              ▼
    Check if      Get agent      Show/hide
    form needed   context        PromptForm
         │             │              │
         └─────────────┴──────────────┘
                       │
                       ▼
                 PromptForm
            (if promptIds.length > 0)
```

---

## Message Flow - Form to API

```
USER INTERACTION:

1. User fills PromptForm
   └─ Enters: "topic: Science Fiction"
   └─ Selects: "Advanced" level

   ┌─────────────────────────────────┐
   │  Form Data                      │
   ├─────────────────────────────────┤
   │ {                               │
   │   topic: "Science Fiction",     │
   │   level: "Advanced"             │
   │ }                               │
   └─────────────────────────────────┘

2. User clicks "Next"
   └─ handlePromptFormSubmit triggered

   ┌──────────────────────────────────────────┐
   │ Prompt Form Submission Payload           │
   ├──────────────────────────────────────────┤
   │ {                                        │
   │   prompt: {                              │
   │     id: "prompt_123",                    │
   │     version: "1",                        │
   │     variables: {                         │
   │       topic: "Science Fiction",          │
   │       level: "Advanced"                  │
   │     }                                    │
   │   },                                     │
   │   model: "gpt-4o-mini",                  │
   │   agentId: "agent_123",        [IF AGENT]│
   │   agentMetadata: {...}         [IF AGENT]│
   │ }                                        │
   └──────────────────────────────────────────┘

3. ChatWindow.handlePromptFormSubmit
   ├─ setPromptData(payload)
   ├─ setPromptFormSubmitted(true)
   ├─ append(userMessage)
   └─ setShowPromptForm(false)

4. useChat merges data

   ┌──────────────────────────────────────────┐
   │ useChat Body (for useChat hook)          │
   ├──────────────────────────────────────────┤
   │ {                                        │
   │   model: "gpt-4o-mini",                  │
   │   metadata: {                            │
   │     project_id: "proj_123"               │
   │   },                                     │
   │   settings: {                            │
   │     temperature: 0.8,                    │
   │     ...                                  │
   │   },                                     │
   │   prompt: {                              │
   │     id: "prompt_123",                    │
   │     version: "1",                        │
   │     variables: {                         │
   │       topic: "Science Fiction",          │
   │       level: "Advanced"                  │
   │     }                                    │
   │   },                                     │
   │   agentId: "agent_123"        [IF AGENT]  │
   │ }                                        │
   └──────────────────────────────────────────┘

5. POST /api/prompt-chat

   ┌──────────────────────────────────────────┐
   │ Request Headers                          │
   ├──────────────────────────────────────────┤
   │ Authorization: Bearer <token>            │
   │ X-Agent-ID: agent_123          [IF AGENT]│
   │ X-Agent-Metadata: {...}        [IF AGENT]│
   │ Content-Type: application/json           │
   └──────────────────────────────────────────┘

   ┌──────────────────────────────────────────┐
   │ Request Body                             │
   ├──────────────────────────────────────────┤
   │ {                                        │
   │   messages: [...],                       │
   │   model: "gpt-4o-mini",                  │
   │   prompt: {...},                         │
   │   temperature: 1,                        │
   │   agentId: "agent_123"        [IF AGENT]  │
   │ }                                        │
   └──────────────────────────────────────────┘

6. /api/prompt-chat processing
   ├─ buildPromptInput() - construct input
   ├─ transformVariables() - spaces to underscores
   ├─ POST to gateway /v1/responses
   └─ Parse response (SSE or JSON)

   ┌──────────────────────────────────────────┐
   │ Gateway Call                             │
   ├──────────────────────────────────────────┤
   │ POST {baseURL}/v1/responses              │
   │                                          │
   │ Headers:                                 │
   │   Authorization: Bearer <token>          │
   │   X-Agent-ID: agent_123                  │
   │   project-id: proj_123                   │
   │                                          │
   │ Body:                                    │
   │   {                                      │
   │     prompt: {                            │
   │       id: "prompt_123",                  │
   │       variables: {                       │
   │         topic: "Science_Fiction",        │
   │         level: "Advanced"                │
   │       }                                  │
   │     },                                   │
   │     temperature: 1,                      │
   │     agent_id: "agent_123"                │
   │   }                                      │
   └──────────────────────────────────────────┘

7. Response Stream
   ├─ Parse SSE or JSON response
   ├─ Extract: text, usage, finishReason
   └─ Return to useChat as stream

8. ChatWindow.handleFinish
   ├─ Add to messages array
   ├─ Save to store via addMessage()
   ├─ Update chat total_tokens
   └─ Display in UI
```

---

## State Hierarchy

```
LocalStorage (Browser)
    │
    ├─ chat-storage-{userIdentifier}
    │  └─ activeChatList: Session[]
    │  └─ messages: Record<string, SavedMessage[]>
    │  └─ settingPresets: Settings[]
    │  └─ currentSettingPreset: Settings
    │  └─ notes: Note[]
    │  [Agent Context would be stored here]
    │
    └─ Other keys...
         │
         ▼
    Zustand Store (useChatStore)
         │
         ├─ promptIds: string[] (global)
         ├─ activeChatList: Session[]
         ├─ messages: Record<string, SavedMessage[]>
         ├─ settingPresets: Settings[]
         ├─ currentSettingPreset: Settings
         ├─ notes: Note[]
         └─ agentContext?: AgentContext (per chat) [IF ADDED]
              │
              ▼
         ChatWindow Component State
              │
              ├─ showPromptForm: boolean
              ├─ promptFormSubmitted: boolean
              ├─ promptData: any
              ├─ input: string (from useChat)
              ├─ messages: Message[] (from useChat)
              ├─ status: "submitted" | "streaming" (from useChat)
              └─ toggleLeft, toggleRight: boolean
```

---

## Component Dependency Graph

```
┌────────────────────────────────────────────────────────────────┐
│                      chat/page.tsx                              │
│  Entry point, URL param parsing, session creation              │
└────────────────────────────────────────────────────────────────┘
        │
        │ imports
        ▼
┌────────────────────────────────────────────────────────────────┐
│                   ChatWindow.tsx                                │
│  Orchestrator, form/editor display, message handling           │
│                                                                 │
│  Reads: promptIds, messages, settings from store              │
│  Writes: messages, agentContext to store                      │
│  Uses: useChat hook for API integration                       │
└────────────────────────────────────────────────────────────────┘
        │
        ├─────────────────────────────────────┬──────────────────┐
        │                                     │                  │
        ▼                                     ▼                  ▼
┌─────────────────────────┐     ┌─────────────────────┐   ┌────────────────┐
│    PromptForm.tsx       │     │  NormalEditor.tsx   │   │  Messages.tsx  │
│                         │     │                     │   │                │
│ Props:                  │     │ Props:              │   │ Props:         │
│  - promptIds            │     │  - input            │   │  - messages    │
│  - onSubmit             │     │  - handleSubmit     │   │  - reload      │
│  - agentContext         │     │  - isLoading        │   │  - onEdit      │
│                         │     │  - disabled         │   │                │
│ Effects:                │     │  - isPromptMode     │   │ Renders:       │
│  - fetchPromptConfig    │     │  - stop             │   │  - message list│
│  - mergeAgentDefaults   │     │                     │   │  - edit UI     │
│                         │     │ Handlers:           │   │  - feedback    │
│ Renders:                │     │  - handleSubmit     │   │                │
│  - Dynamic form fields  │     │  - handleInputChange│   │                │
│  - Based on schema      │     │  - onKeyDown        │   │                │
│                         │     │                     │   │                │
│ Emits:                  │     │ UI:                 │   │                │
│  - onSubmit(payload)    │     │  - textarea         │   │                │
│                         │     │  - send button      │   │                │
│                         │     │  - stop button      │   │                │
└─────────────────────────┘     └─────────────────────┘   └────────────────┘
        │                               │
        │                               │
        └───────────────┬───────────────┘
                        │
                    (handlers)
                        │
                        ▼
            ┌──────────────────────┐
            │  Zustand Store       │
            │  (useChatStore)      │
            │                      │
            │ Methods:             │
            │ - addMessage         │
            │ - updateChat         │
            │ - setPromptIds       │
            │ - setAgentContext    │
            │                      │
            │ Subscriptions:       │
            │ - useChatStore()     │
            └──────────────────────┘
```

---

## API Endpoint Request/Response Flow

```
NORMAL CHAT FLOW:
┌─────────────────────────────────┐
│  Client (useChat hook)          │
│  POST /api/chat                 │
└──────────────┬──────────────────┘
               │
               │ {messages, model, settings, ...}
               ▼
        ┌────────────────────┐
        │  api/chat/route.ts │
        │                    │
        │ 1. Parse request   │
        │ 2. Create OpenAI   │
        │    proxy client    │
        │ 3. streamText()    │
        │ 4. Collect metrics │
        │ 5. Return stream   │
        └────────┬───────────┘
                 │
                 │ {model, messages, settings, ...}
                 ▼
        ┌────────────────────┐
        │  BudGateway        │
        │  /openai/v1/chat   │
        │  /completions      │
        └────────┬───────────┘
                 │
                 │ Streaming response
                 ▼
        ┌────────────────────┐
        │  Client receives   │
        │  streaming chunks  │
        │  in Vercel format  │
        └────────┬───────────┘
                 │
                 │ handleFinish() callback
                 ▼
        ┌────────────────────┐
        │  addMessage()      │
        │  updateChat()      │
        │  updateMetrics()   │
        └────────────────────┘


PROMPT CHAT FLOW:
┌─────────────────────────────────┐
│  Client (useChat hook)          │
│  POST /api/prompt-chat          │
└──────────────┬──────────────────┘
               │
        {messages, prompt, input/variables, ...}
               │
               ▼
        ┌─────────────────────────┐
        │ api/prompt-chat/route.ts│
        │                         │
        │ 1. Extract prompt data  │
        │ 2. buildPromptInput()   │
        │ 3. transformVariables() │
        │ 4. Build gateway body   │
        │ 5. fetch /v1/responses  │
        │ 6. Parse SSE or JSON    │
        │ 7. Convert to stream    │
        └──────────┬──────────────┘
                   │
         {prompt: {id, variables}, input}
                   │
                   ▼
        ┌──────────────────────┐
        │  BudGateway          │
        │  /v1/responses       │
        │  [prompt endpoint]   │
        └──────────┬───────────┘
                   │
                   │ SSE or JSON response
                   │ {output, usage, status}
                   ▼
        ┌──────────────────────┐
        │  Client receives     │
        │  streaming response  │
        │  (converted format)  │
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  handleFinish()      │
        │  addMessage()        │
        │  updateChat()        │
        └──────────────────────┘
```

---

## Form Submission Flow - Detailed

```
┌──────────────────────────────────────────────────────────────┐
│ USER ACTION: Click "Next" button in PromptForm               │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────┐
        │ PromptForm.handleSubmit()       │
        │ (lines 106-161)                 │
        └──────────────┬──────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
    ┌─────────────┐         ┌──────────────────┐
    │ Check if    │         │ Build Payload    │
    │ schema      │         │ (structured vs   │
    │ is          │         │  unstructured)   │
    │ structured  │         │                  │
    └──────┬──────┘         └────────┬─────────┘
           │                         │
           │                    YES (schema)
           │                    │
           │                    ▼
           │            ┌─────────────────┐
           │            │ Extract fields  │
           │            │ from formData   │
           │            │ into variables  │
           │            └────────┬────────┘
           │                     │
           │                     ▼
           │            ┌─────────────────────────┐
           │            │ variables = {           │
           │            │   place: "kerala",      │
           │            │   author: "John"        │
           │            │ }                       │
           │            └────────┬────────────────┘
           │                     │
           │      NO (no schema)  │
           │      │               │
           │      ▼               │
           │   ┌──────────────┐   │
           │   │ Extract      │   │
           │   │ unstructured │   │
           │   │ text from    │   │
           │   │ input field  │   │
           │   └────┬─────────┘   │
           │        │             │
           │        ▼             │
           │   ┌──────────────┐   │
           │   │ input =      │   │
           │   │ "text..."    │   │
           │   └────┬─────────┘   │
           │        │             │
           └────────┼─────────────┘
                    │
                    ▼
        ┌───────────────────────────────────┐
        │ Build Complete Payload            │
        │                                   │
        │ payload = {                       │
        │   prompt: {                       │
        │     id: promptId,                 │
        │     version: promptVersion,       │
        │     variables: variables          │
        │   },                              │
        │   input: input (if no schema),    │
        │   model: promptDeployment,        │
        │   promptId: promptId,             │
        │   variables: variables (copy)     │
        │ }                                 │
        └──────────┬──────────────────────┘
                   │
                   │ onSubmit(payload)
                   │ (passed callback)
                   ▼
        ┌──────────────────────────────────┐
        │ ChatWindow.handlePromptFormSubmit │
        │ (lines 188-214)                  │
        └──────────┬───────────────────────┘
                   │
        ┌──────────┴──────────────────────┐
        │                                 │
        ▼                                 ▼
    ┌─────────────────┐         ┌──────────────────────┐
    │ setPromptData() │         │ setPromptFormSubmitted│
    │ Store in local  │         │ (true)               │
    │ state for body  │         │ Enable NormalEditor  │
    │ merging         │         └──────────────────────┘
    └────────┬────────┘
             │
             ▼
    ┌──────────────────────────────────┐
    │ Build userMessage from formData  │
    │                                  │
    │ IF structured:                   │
    │   "place: kerala\nauthor: John"  │
    │                                  │
    │ IF unstructured:                 │
    │   formData['unstructuredSchema']  │
    └────────┬─────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────┐
    │ append({                          │
    │   role: 'user',                   │
    │   content: userMessage            │
    │ })                                │
    │                                  │
    │ [Triggers useChat hook]           │
    └────────┬─────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────┐
    │ useChat constructs body:          │
    │                                  │
    │ {                                 │
    │   model: ...,                     │
    │   metadata: {...},                │
    │   settings: {...},                │
    │   ...promptData  ← merged here     │
    │ }                                 │
    └────────┬─────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────┐
    │ POST /api/prompt-chat             │
    │ with merged body                  │
    └────────┬─────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────┐
    │ setShowPromptForm(false)          │
    │ Hide form from UI                 │
    └──────────────────────────────────┘
```

---

## Error Handling Flow

```
PromptForm.useEffect (lines 84-89)
    │
    ├─ Error fetching prompt config
    │
    ├─ Fallback: inputSchema = null
    ├─ Display: unstructuredSchema input
    ├─ Set: promptVersion = undefined
    └─ Set: promptDeployment = undefined
         │
         ▼
    Form still works but without schema
    (user can enter free text)


ChatWindow.body construction
    │
    ├─ If promptData missing: use baseBody only
    ├─ If currentSettingPreset invalid: use defaults
    └─ If selectedDeployment missing: disable editor
         │
         ▼
    API receives partial data and handles gracefully


API endpoint /api/prompt-chat
    │
    ├─ Error 401: No auth (return error)
    ├─ Error 400: No prompt input (return error)
    ├─ Error gateway call: Catch and return error message
    │
    └─ Success: Parse response (SSE or JSON)
         ├─ If SSE parse fails: Try JSON
         ├─ If both fail: Throw error
         └─ If no text extracted: Empty but valid response
```
