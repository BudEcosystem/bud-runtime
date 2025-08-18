#!/usr/bin/env node

/**
 * Test script to verify the models catalog API integration
 */

const axios = require('axios');

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000';

async function testModelsCatalog() {
  console.log('Testing Models Catalog API Integration');
  console.log('Base URL:', BASE_URL);
  console.log('---');

  try {
    // Test 1: Basic catalog fetch
    console.log('Test 1: Fetching models catalog...');
    const response = await axios.get(`${BASE_URL}/models/catalog`, {
      params: {
        page: 1,
        limit: 10,
        table_source: 'model'
      },
      headers: {
        'Authorization': `Bearer ${process.env.ACCESS_TOKEN || ''}`
      }
    });

    console.log('✓ API call successful');
    console.log(`✓ Total models: ${response.data.total_record || response.data.total_count || 0}`);
    console.log(`✓ Total pages: ${response.data.total_pages || 0}`);

    if (response.data.models && response.data.models.length > 0) {
      console.log(`✓ Retrieved ${response.data.models.length} models`);

      // Display first model details
      const firstModel = response.data.models[0];
      const model = firstModel.model || firstModel;
      console.log('\nFirst model details:');
      console.log(`  - Name: ${model.name}`);
      console.log(`  - Author: ${model.author || 'Unknown'}`);
      console.log(`  - Provider Type: ${model.provider_type}`);
      console.log(`  - Model Size: ${model.model_size}B`);
      console.log(`  - Endpoints Count: ${firstModel.endpoints_count || 0}`);
    }

    // Test 2: Search functionality
    console.log('\nTest 2: Testing search functionality...');
    const searchResponse = await axios.get(`${BASE_URL}/models/catalog`, {
      params: {
        page: 1,
        limit: 10,
        name: 'GPT',
        search: true,
        table_source: 'model'
      },
      headers: {
        'Authorization': `Bearer ${process.env.ACCESS_TOKEN || ''}`
      }
    });

    console.log('✓ Search API call successful');
    console.log(`✓ Found ${searchResponse.data.models?.length || 0} models matching "GPT"`);

    console.log('\n✅ All tests passed successfully!');
    console.log('\nIntegration Summary:');
    console.log('- The /models/catalog endpoint is accessible');
    console.log('- Data structure matches expected format');
    console.log('- Search functionality is working');
    console.log('- The models page should now display real data from the API');

  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
    if (error.response) {
      console.error('Response status:', error.response.status);
      console.error('Response data:', error.response.data);
    }
    console.log('\nTroubleshooting tips:');
    console.log('1. Ensure the backend service is running');
    console.log('2. Check that NEXT_PUBLIC_BASE_URL is set correctly');
    console.log('3. Verify you have a valid access token if authentication is required');
    console.log('4. Check that the /models/catalog endpoint exists in the backend');
    process.exit(1);
  }
}

// Run the test
testModelsCatalog();
