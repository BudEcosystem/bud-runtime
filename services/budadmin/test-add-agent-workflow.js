/**
 * Test script for Add Agent Workflow API Integration
 *
 * This script tests the workflow API endpoint for adding agents
 * Usage: node test-add-agent-workflow.js
 */

const https = require('https');

// Configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_BASE_URL || 'https://localhost:8000';
const PROJECT_ID = 'dda389c5-b98f-486b-92c2-593041a6865b'; // Example project ID from the user's request

// Parse base URL
const url = new URL(API_BASE_URL);
const hostname = url.hostname;
const port = url.port || 443;
const basePath = url.pathname.replace(/\/$/, '');

/**
 * Make HTTPS request to the API
 */
function makeRequest(path, method, data) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: hostname,
      port: port,
      path: basePath + path,
      method: method,
      headers: {
        'Content-Type': 'application/json',
        'x-resource-type': 'project',
        'x-entity-id': PROJECT_ID,
        // Add auth headers if needed
        // 'Authorization': 'Bearer YOUR_TOKEN'
      },
      rejectUnauthorized: false // For self-signed certificates in dev
    };

    const req = https.request(options, (res) => {
      let data = '';

      res.on('data', (chunk) => {
        data += chunk;
      });

      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(parsed);
          } else {
            reject(new Error(`API Error: ${res.statusCode} - ${JSON.stringify(parsed)}`));
          }
        } catch (e) {
          reject(new Error(`Failed to parse response: ${data}`));
        }
      });
    });

    req.on('error', (error) => {
      reject(error);
    });

    if (data) {
      req.write(JSON.stringify(data));
    }

    req.end();
  });
}

/**
 * Test the workflow creation endpoint
 */
async function testWorkflowCreation() {
  console.log('Testing Add Agent Workflow API Integration\n');
  console.log('===========================================\n');

  try {
    // Step 1: Create workflow with project selection
    console.log('Step 1: Creating workflow with project selection...');
    const payload = {
      workflow_total_steps: 6,
      step_number: 1,
      project_id: PROJECT_ID
    };

    console.log('Request payload:', JSON.stringify(payload, null, 2));

    const response = await makeRequest('/prompts/prompt-workflow', 'POST', payload);

    console.log('✅ Success! Workflow created.');
    console.log('Response:', JSON.stringify(response, null, 2));

    if (response.workflow_id) {
      console.log(`\nWorkflow ID: ${response.workflow_id}`);
      console.log('This ID can be used for subsequent workflow steps.');
    }

    return response;

  } catch (error) {
    console.error('❌ Error:', error.message);
    process.exit(1);
  }
}

/**
 * Test subsequent workflow steps
 */
async function testWorkflowSteps(workflowId) {
  console.log('\n===========================================\n');
  console.log('Testing subsequent workflow steps...\n');

  try {
    // Step 2: Update agent type (prompt_type)
    console.log('Step 2: Updating agent type...');
    const step2Payload = {
      workflow_id: workflowId,
      step_number: 2,
      prompt_type: 'simple_prompt' // Using the correct field name
    };

    console.log('Request payload:', JSON.stringify(step2Payload, null, 2));

    const step2Response = await makeRequest('/prompts/prompt-workflow', 'POST', step2Payload);
    console.log('✅ Step 2 completed successfully.');
    console.log('Response:', JSON.stringify(step2Response, null, 2));

    // Step 3: Update model
    console.log('\nStep 3: Updating model...');
    const step3Payload = {
      step_number: 3,
      workflow_id: workflowId,
      model_id: 'example-model-id' // Would need a real model ID
    };

    console.log('Request payload:', JSON.stringify(step3Payload, null, 2));

    // Note: This would fail without a valid model_id
    // const step3Response = await makeRequest('/prompts/prompt-workflow', 'POST', step3Payload);
    console.log('⚠️ Skipping Step 3 (requires valid model_id)');

    console.log('\n✅ Workflow steps test completed!');

  } catch (error) {
    console.error('❌ Error in workflow steps:', error.message);
  }
}

/**
 * Main test function
 */
async function runTests() {
  console.log(`\nAPI Base URL: ${API_BASE_URL}`);
  console.log(`Project ID: ${PROJECT_ID}\n`);

  // Test workflow creation
  const workflowResponse = await testWorkflowCreation();

  // If workflow was created successfully, test subsequent steps
  if (workflowResponse && workflowResponse.workflow_id) {
    await testWorkflowSteps(workflowResponse.workflow_id);
  }

  console.log('\n===========================================');
  console.log('Test completed!\n');
}

// Run tests
runTests().catch(console.error);
