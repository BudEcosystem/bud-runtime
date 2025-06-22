/**
 * K6 Load Test for Inference API
 * 
 * Usage:
 *   k6 run inference_load_test.js
 *   k6 run --vus 50 --duration 5m inference_load_test.js
 *   k6 run -e MODEL=llama2-7b -e ENDPOINT=http://localhost:8000 inference_load_test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.2/index.js';

// Custom metrics
const errorRate = new Rate('errors');
const inferenceLatency = new Trend('inference_latency');
const tokenLatency = new Trend('token_latency');

// Configuration from environment variables
const BASE_URL = __ENV.ENDPOINT || 'http://localhost:8000';
const MODEL = __ENV.MODEL || 'test-model';
const MAX_TOKENS = parseInt(__ENV.MAX_TOKENS) || 100;

// Test scenarios
export const options = {
  scenarios: {
    // Smoke test
    smoke: {
      executor: 'constant-vus',
      vus: 1,
      duration: '1m',
      tags: { scenario: 'smoke' },
    },
    
    // Load test - gradual ramp up
    load: {
      executor: 'ramping-vus',
      stages: [
        { duration: '2m', target: 10 },  // Ramp up to 10 users
        { duration: '5m', target: 10 },  // Stay at 10 users
        { duration: '2m', target: 20 },  // Ramp up to 20 users
        { duration: '5m', target: 20 },  // Stay at 20 users
        { duration: '2m', target: 0 },   // Ramp down
      ],
      startTime: '2m',  // Start after smoke test
      tags: { scenario: 'load' },
    },
    
    // Stress test - find breaking point
    stress: {
      executor: 'ramping-vus',
      stages: [
        { duration: '2m', target: 20 },
        { duration: '2m', target: 40 },
        { duration: '2m', target: 60 },
        { duration: '2m', target: 80 },
        { duration: '2m', target: 100 },
        { duration: '5m', target: 100 }, // Stay at peak
        { duration: '2m', target: 0 },
      ],
      startTime: '18m',  // Start after load test
      tags: { scenario: 'stress' },
    },
    
    // Spike test - sudden load increase
    spike: {
      executor: 'ramping-vus',
      stages: [
        { duration: '10s', target: 50 },  // Sudden spike
        { duration: '1m', target: 50 },   // Hold the spike
        { duration: '10s', target: 0 },   // Quick ramp down
      ],
      startTime: '35m',  // Start after stress test
      tags: { scenario: 'spike' },
    },
  },
  
  thresholds: {
    http_req_duration: ['p(95)<5000'],  // 95% of requests under 5s
    http_req_failed: ['rate<0.1'],      // Error rate under 10%
    errors: ['rate<0.1'],               // Custom error rate under 10%
  },
};

// Test data
const prompts = [
  "What is machine learning?",
  "Explain quantum computing in simple terms.",
  "How does photosynthesis work?",
  "What are the benefits of renewable energy?",
  "Describe the water cycle.",
  "What is artificial intelligence?",
  "How do vaccines work?",
  "Explain the theory of evolution.",
  "What causes climate change?",
  "How does the internet work?",
];

const complexPrompts = [
  "Write a detailed explanation of how neural networks learn, including backpropagation.",
  "Analyze the economic and social impacts of automation on the workforce.",
  "Compare and contrast different renewable energy sources and their efficiency.",
  "Explain the relationship between quantum mechanics and classical physics.",
  "Discuss the ethical implications of artificial intelligence in healthcare.",
];

// Helper function to get random prompt
function getRandomPrompt() {
  const useComplex = Math.random() < 0.2;  // 20% chance of complex prompt
  const promptArray = useComplex ? complexPrompts : prompts;
  return promptArray[Math.floor(Math.random() * promptArray.length)];
}

// Main test function
export default function() {
  const prompt = getRandomPrompt();
  const temperature = 0.7 + (Math.random() * 0.3);  // Random between 0.7-1.0
  
  const payload = JSON.stringify({
    model: MODEL,
    prompt: prompt,
    max_tokens: MAX_TOKENS,
    temperature: temperature,
    stream: false,
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'k6-load-test',
    },
    timeout: '30s',
  };

  // Record start time
  const startTime = new Date();

  // Make inference request
  const response = http.post(`${BASE_URL}/v1/completions`, payload, params);

  // Calculate latencies
  const totalLatency = new Date() - startTime;
  inferenceLatency.add(totalLatency);

  // Check response
  const success = check(response, {
    'status is 200': (r) => r.status === 200,
    'response has choices': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.choices && body.choices.length > 0;
      } catch (e) {
        return false;
      }
    },
    'response has text': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.choices[0].text && body.choices[0].text.length > 0;
      } catch (e) {
        return false;
      }
    },
    'response time < 10s': (r) => r.timings.duration < 10000,
  });

  errorRate.add(!success);

  // Parse response for additional metrics
  if (success && response.body) {
    try {
      const body = JSON.parse(response.body);
      
      // Calculate per-token latency if usage stats available
      if (body.usage && body.usage.completion_tokens > 0) {
        const tokensGenerated = body.usage.completion_tokens;
        const perTokenLatency = totalLatency / tokensGenerated;
        tokenLatency.add(perTokenLatency);
      }
      
      // Log sample responses occasionally
      if (Math.random() < 0.01) {  // 1% of responses
        console.log(`Sample response for prompt "${prompt.substring(0, 50)}..."`);
        console.log(`Response: "${body.choices[0].text.substring(0, 100)}..."`);
        console.log(`Latency: ${totalLatency}ms`);
      }
    } catch (e) {
      console.error('Failed to parse response:', e);
    }
  }

  // Sleep between requests (simulate user think time)
  sleep(Math.random() * 2 + 1);  // 1-3 seconds
}

// Custom summary
export function handleSummary(data) {
  const customData = {
    'Total Requests': data.metrics.http_reqs.values.count,
    'Success Rate': (100 - data.metrics.errors.values.rate * 100).toFixed(2) + '%',
    'Avg Latency': Math.round(data.metrics.http_req_duration.values.avg) + 'ms',
    'P95 Latency': Math.round(data.metrics.http_req_duration.values['p(95)']) + 'ms',
    'P99 Latency': Math.round(data.metrics.http_req_duration.values['p(99)']) + 'ms',
  };

  return {
    'stdout': textSummary(data, { indent: ' ', enableColors: true }) + 
              '\nCustom Summary:\n' + 
              JSON.stringify(customData, null, 2),
    'summary.json': JSON.stringify(data),
  };
}

// Lifecycle hooks
export function setup() {
  console.log(`Starting load test for model: ${MODEL}`);
  console.log(`Endpoint: ${BASE_URL}`);
  console.log(`Max tokens: ${MAX_TOKENS}`);
  
  // Test connectivity
  const testResponse = http.get(`${BASE_URL}/health`);
  if (testResponse.status !== 200) {
    throw new Error(`Health check failed: ${testResponse.status}`);
  }
}

export function teardown(data) {
  console.log('Load test completed');
}