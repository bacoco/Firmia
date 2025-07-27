#!/usr/bin/env node

/**
 * Test script to verify INSEE API authentication
 * Tests both the new API key method and OAuth2 method
 */

import dotenv from 'dotenv';
import axios from 'axios';

// Load environment variables
dotenv.config();

const NEW_BASE_URL = "https://api.insee.fr/api-sirene/3.11";
const TOKEN_URL = "https://api.insee.fr/token";
const API_KEY = process.env.INSEE_API_KEY_INTEGRATION;

console.log('🔍 Testing INSEE API Authentication Methods\n');

/**
 * Test 1: API Key Integration method
 */
async function testApiKeyMethod() {
  console.log('1️⃣ Testing API Key Integration method...');
  
  if (!API_KEY) {
    console.log('❌ INSEE_API_KEY_INTEGRATION not found in environment');
    return false;
  }

  try {
    const response = await axios.get(`${NEW_BASE_URL}/informations`, {
      headers: {
        "X-INSEE-Api-Key-Integration": API_KEY,
        "Accept": "application/json"
      },
      timeout: 10000
    });

    console.log('✅ API Key method successful!');
    console.log(`📊 Status: ${response.status}`);
    console.log(`📝 Response: ${JSON.stringify(response.data, null, 2)}\n`);
    return true;
  } catch (error) {
    console.log('❌ API Key method failed:');
    if (error.response) {
      console.log(`📊 Status: ${error.response.status}`);
      console.log(`📝 Error: ${JSON.stringify(error.response.data, null, 2)}`);
    } else {
      console.log(`📝 Error: ${error.message}`);
    }
    console.log('');
    return false;
  }
}

/**
 * Test 2: OAuth2 Token method
 */
async function testOAuth2Method() {
  console.log('2️⃣ Testing OAuth2 Client Credentials method...');
  
  // Decode the Basic auth credentials from the curl example
  const basicAuth = "SmI5dUpkbnRtNWVGa0Rwd0EyY1d4VGJMRXRVYTpwd1RxeTV3a2ZBbEhsd2djaGdSU3FmSUdOMllh";
  
  try {
    // Step 1: Get access token
    console.log('🔄 Requesting OAuth2 token...');
    
    const tokenResponse = await axios.post(TOKEN_URL, 
      "grant_type=client_credentials",
      {
        headers: {
          "Authorization": `Basic ${basicAuth}`,
          "Content-Type": "application/x-www-form-urlencoded"
        },
        timeout: 10000
      }
    );

    console.log('✅ OAuth2 token obtained!');
    console.log(`📊 Token type: ${tokenResponse.data.token_type}`);
    console.log(`⏰ Expires in: ${tokenResponse.data.expires_in} seconds`);
    console.log(`🔑 Token: ${tokenResponse.data.access_token.substring(0, 20)}...\n`);

    // Step 2: Use the token to make an API call
    console.log('🔄 Testing API call with OAuth2 token...');
    
    const apiResponse = await axios.get(`${NEW_BASE_URL}/informations`, {
      headers: {
        "Authorization": `Bearer ${tokenResponse.data.access_token}`,
        "Accept": "application/json"
      },
      timeout: 10000
    });

    console.log('✅ OAuth2 API call successful!');
    console.log(`📊 Status: ${apiResponse.status}`);
    console.log(`📝 Response: ${JSON.stringify(apiResponse.data, null, 2)}\n`);
    return true;

  } catch (error) {
    console.log('❌ OAuth2 method failed:');
    if (error.response) {
      console.log(`📊 Status: ${error.response.status}`);
      console.log(`📝 Error: ${JSON.stringify(error.response.data, null, 2)}`);
    } else {
      console.log(`📝 Error: ${error.message}`);
    }
    console.log('');
    return false;
  }
}

/**
 * Test 3: Search functionality with new API
 */
async function testSearchFunctionality() {
  console.log('3️⃣ Testing search functionality...');

  if (!API_KEY) {
    console.log('⏭️ Skipping search test (no API key)\n');
    return false;
  }

  try {
    // Test search for "Airbus"
    const response = await axios.get(`${NEW_BASE_URL}/siren`, {
      headers: {
        "X-INSEE-Api-Key-Integration": API_KEY,
        "Accept": "application/json"
      },
      params: {
        q: 'denominationUniteLegale:Airbus',
        nombre: 3
      },
      timeout: 10000
    });

    console.log('✅ Search functionality working!');
    console.log(`📊 Status: ${response.status}`);
    console.log(`📝 Found ${response.data.header?.total || 0} results`);
    
    if (response.data.unitesLegales && response.data.unitesLegales.length > 0) {
      const first = response.data.unitesLegales[0];
      console.log(`🏢 First result: ${first.denominationUniteLegale} (SIREN: ${first.siren})`);
    }
    console.log('');
    return true;

  } catch (error) {
    console.log('❌ Search test failed:');
    if (error.response) {
      console.log(`📊 Status: ${error.response.status}`);
      console.log(`📝 Error: ${JSON.stringify(error.response.data, null, 2)}`);
    } else {
      console.log(`📝 Error: ${error.message}`);
    }
    console.log('');
    return false;
  }
}

/**
 * Main test runner
 */
async function runTests() {
  console.log('🚀 INSEE API Authentication Test Suite');
  console.log('=====================================\n');

  const results = {
    apiKey: await testApiKeyMethod(),
    oauth2: await testOAuth2Method(),
    search: await testSearchFunctionality()
  };

  console.log('📋 Test Results Summary:');
  console.log('========================');
  console.log(`✅ API Key Integration: ${results.apiKey ? 'PASS' : 'FAIL'}`);
  console.log(`✅ OAuth2 Client Creds: ${results.oauth2 ? 'PASS' : 'FAIL'}`);
  console.log(`✅ Search Functionality: ${results.search ? 'PASS' : 'FAIL'}`);
  
  const totalPassed = Object.values(results).filter(Boolean).length;
  console.log(`\n🎯 Overall: ${totalPassed}/3 tests passed`);
  
  if (totalPassed >= 1) {
    console.log('\n🎉 INSEE API authentication is working! Ready for September 2024 transition.');
  } else {
    console.log('\n⚠️ All tests failed. Check your API credentials and network connection.');
  }

  process.exit(totalPassed >= 1 ? 0 : 1);
}

// Run the tests
runTests().catch(error => {
  console.error('💥 Test runner failed:', error);
  process.exit(1);
});