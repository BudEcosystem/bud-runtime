# Add Agent Workflow API Integration

## Overview
The Add Agent workflow has been integrated with the backend API using the `/prompts/prompt-workflow` endpoint. The workflow consists of 6 steps with API calls at each step.

## Workflow Steps

### Step 1: Select Project (`SelectProject.tsx`)
- **Component**: `/src/flows/AddAgent/SelectProject.tsx`
- **API Payload**:
  ```json
  {
    "workflow_total_steps": 6,
    "step_number": 1,
    "project_id": "dda389c5-b98f-486b-92c2-593041a6865b"
  }
  ```
- **Response**: Creates workflow and returns `workflow_id`
- **Next Step**: Navigate to SelectAgentType

### Step 2: Select Agent Type (`SelectAgentType.tsx`)
- **Component**: `/src/flows/AddAgent/SelectAgentType.tsx`
- **API Payload**:
  ```json
  {
    "workflow_id": "e1cf0e7e-fa52-41fd-b09d-9146d7985fba",
    "step_number": 2,
    "prompt_type": "simple_prompt"  // Options: simple_prompt, prompt_workflow, agent, chatflow
  }
  ```
- **Next Step**: Navigate to SelectModel

### Step 3: Select Model (To be implemented)
- **API Payload**:
  ```json
  {
    "workflow_id": "workflow_id",
    "step_number": 3,
    "model_id": "selected_model_id"
  }
  ```

### Step 4: Configuration (To be implemented)
- **API Payload**:
  ```json
  {
    "workflow_id": "workflow_id",
    "step_number": 4,
    "agent_configuration": { /* configuration object */ }
  }
  ```

### Step 5: Review (To be implemented)
- **API Payload**:
  ```json
  {
    "workflow_id": "workflow_id",
    "step_number": 5,
    "prompt_messages": [ /* array of messages */ ]
  }
  ```

### Step 6: Success/Deploy (To be implemented)
- **API Payload**:
  ```json
  {
    "workflow_id": "workflow_id",
    "step_number": 6,
    "trigger_workflow": true
  }
  ```

## State Management

### Store: `useAddAgent.tsx`
Located at `/src/stores/useAddAgent.tsx`

Key methods:
- `createWorkflow(projectId)` - Creates initial workflow
- `updateAgentType()` - Updates agent type (step 2)
- `updateModel()` - Updates model selection (step 3)
- `updateConfiguration()` - Updates agent configuration (step 4)
- `updatePrompts()` - Updates prompt messages (step 5)
- `deployAgent()` - Triggers deployment (step 6)

## Testing

### Test Script
A test script is available at `test-add-agent-workflow.js` to verify the API integration.

Run with:
```bash
node test-add-agent-workflow.js
```

## Headers
All API calls include the following headers:
```javascript
{
  "x-resource-type": "project",
  "x-entity-id": projectId
}
```

## Error Handling
- Each step includes error handling with toast notifications
- Workflow state is maintained in the store
- Navigation is prevented if workflow is not initialized

## Flow Order (Updated)
1. SelectProject (Step 1) - First step
2. SelectAgentType (Step 2) - Second step
3. SelectModel (Step 3)
4. Configuration (Step 4)
5. Review/DeploymentWarning (Step 5)
6. Success (Step 6)
