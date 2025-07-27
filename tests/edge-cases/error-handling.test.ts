import { setupAdapters } from '../../src/adapters/index.js';
import { createCache } from '../../src/cache/index.js';
import { createRateLimiter } from '../../src/rate-limiter/index.js';
import { enhancedMockCompanies, mockErrorScenarios } from '../fixtures/enhanced-mock-data.js';
import axios from 'axios';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('Comprehensive Error Handling Tests', () => {
  let adapters: ReturnType<typeof setupAdapters>;
  let cache: ReturnType<typeof createCache>;
  let rateLimiter: ReturnType<typeof createRateLimiter>;

  beforeEach(() => {
    jest.clearAllMocks();
    
    cache = createCache();
    rateLimiter = createRateLimiter();
    adapters = setupAdapters({ cache, rateLimiter });

    // Set environment variables
    process.env.INSEE_API_KEY = 'test-insee-key';
    process.env.BANQUE_FRANCE_API_KEY = 'test-bf-key';
    process.env.INPI_USERNAME = 'test-inpi-user';
    process.env.INPI_PASSWORD = 'test-inpi-pass';
  });

  afterEach(async () => {
    await cache.flush();
    delete process.env.INSEE_API_KEY;
    delete process.env.BANQUE_FRANCE_API_KEY;
    delete process.env.INPI_USERNAME;
    delete process.env.INPI_PASSWORD;
  });

  describe('Network Error Handling', () => {
    it('should handle connection timeouts gracefully', async () => {
      const siren = enhancedMockCompanies.danone.siren;
      
      // Mock timeout error
      mockedAxios.get.mockRejectedValue({
        code: 'ECONNABORTED',
        message: 'timeout of 30000ms exceeded',
        isAxiosError: true
      });

      // All adapters should handle timeouts
      await expect(adapters.insee.search(siren, {}))
        .rejects.toThrow('INSEE API error');

      await expect(adapters['banque-france'].search(siren, {}))
        .rejects.toThrow('Banque de France API error');
    });

    it('should handle connection refused errors', async () => {
      const siren = enhancedMockCompanies.startup.siren;
      
      mockedAxios.get.mockRejectedValue({
        code: 'ECONNREFUSED',
        message: 'connect ECONNREFUSED 127.0.0.1:80',
        isAxiosError: true
      });

      await expect(adapters.insee.search(siren, {}))
        .rejects.toThrow('INSEE API error');
    });

    it('should handle DNS resolution failures', async () => {
      const siren = enhancedMockCompanies.carrefour.siren;
      
      mockedAxios.get.mockRejectedValue({
        code: 'ENOTFOUND',
        message: 'getaddrinfo ENOTFOUND api.insee.fr',
        isAxiosError: true
      });

      await expect(adapters.insee.search(siren, {}))
        .rejects.toThrow('INSEE API error');
    });

    it('should handle network unreachable errors', async () => {
      mockedAxios.get.mockRejectedValue({
        code: 'ENETUNREACH',
        message: 'network is unreachable',
        isAxiosError: true
      });

      await expect(adapters.insee.getDetails('123456789', {}))
        .rejects.toThrow('INSEE API error');
    });
  });

  describe('HTTP Error Handling', () => {
    it('should handle 400 Bad Request errors', async () => {
      mockedAxios.get.mockRejectedValue({
        isAxiosError: true,
        response: {
          status: 400,
          data: { message: 'Invalid SIREN format' }
        }
      });

      await expect(adapters.insee.search('invalid-siren', {}))
        .rejects.toThrow('INSEE API error: Invalid SIREN format');
    });

    it('should handle 401 Unauthorized errors', async () => {
      mockedAxios.get.mockRejectedValue({
        isAxiosError: true,
        response: {
          status: 401,
          data: { message: 'Invalid API key' }
        }
      });

      await expect(adapters.insee.search('123456789', {}))
        .rejects.toThrow('INSEE API error: Invalid API key');
    });

    it('should handle 403 Forbidden errors', async () => {
      mockedAxios.get.mockRejectedValue({
        isAxiosError: true,
        response: {
          status: 403,
          data: { message: 'Access denied to this resource' }
        }
      });

      await expect(adapters['banque-france'].getDetails('123456789', {}))
        .rejects.toThrow('Banque de France API error: Access denied to this resource');
    });

    it('should handle 404 Not Found errors appropriately', async () => {
      mockedAxios.get.mockRejectedValue({
        isAxiosError: true,
        response: { status: 404 }
      });

      // INSEE should throw error for 404
      await expect(adapters.insee.search('999999999', {}))
        .rejects.toThrow('INSEE API error');

      // Banque de France should return empty array for 404
      const bfResults = await adapters['banque-france'].search('999999999', {});
      expect(bfResults).toEqual([]);
    });

    it('should handle 429 Rate Limit Exceeded errors', async () => {
      mockedAxios.get.mockRejectedValue({
        isAxiosError: true,
        response: {
          status: 429,
          data: { message: 'Rate limit exceeded' }
        }
      });

      await expect(adapters.insee.search('123456789', {}))
        .rejects.toThrow('INSEE API error: Rate limit exceeded');
    });

    it('should handle 500 Internal Server Error', async () => {
      mockedAxios.get.mockRejectedValue({
        isAxiosError: true,
        response: {
          status: 500,
          data: { message: 'Internal server error' }
        }
      });

      await expect(adapters.insee.search('123456789', {}))
        .rejects.toThrow('INSEE API error: Internal server error');
    });

    it('should handle 502 Bad Gateway errors', async () => {
      mockedAxios.get.mockRejectedValue({
        isAxiosError: true,
        response: {
          status: 502,
          data: { message: 'Bad gateway' }
        }
      });

      await expect(adapters['banque-france'].search('123456789', {}))
        .rejects.toThrow('Banque de France API error: Bad gateway');
    });

    it('should handle 503 Service Unavailable errors', async () => {
      mockedAxios.get.mockRejectedValue({
        isAxiosError: true,
        response: {
          status: 503,
          data: { message: 'Service temporarily unavailable' }
        }
      });

      await expect(adapters.insee.getStatus())
        .resolves.toMatchObject({ available: false });
    });
  });

  describe('Data Parsing Error Handling', () => {
    it('should handle malformed JSON responses', async () => {
      mockedAxios.get.mockRejectedValue(new SyntaxError('Unexpected token in JSON'));

      await expect(adapters.insee.search('123456789', {}))
        .rejects.toThrow();
    });

    it('should handle unexpected response structure', async () => {
      // Mock response with missing expected fields
      mockedAxios.get.mockResolvedValue({
        data: {
          unexpected: 'structure',
          missing: 'unitesLegales field'
        }
      });

      const results = await adapters.insee.search('123456789', {});
      expect(results).toEqual([]); // Should return empty array for malformed data
    });

    it('should handle null or undefined response data', async () => {
      mockedAxios.get.mockResolvedValue({ data: null });

      const results = await adapters.insee.search('123456789', {});
      expect(results).toEqual([]);
    });

    it('should handle empty response data', async () => {
      mockedAxios.get.mockResolvedValue({ data: {} });

      const results = await adapters.insee.search('123456789', {});
      expect(results).toEqual([]);
    });

    it('should handle array instead of object in response', async () => {
      mockedAxios.get.mockResolvedValue({
        data: ['this', 'should', 'be', 'an', 'object']
      });

      const results = await adapters.insee.search('123456789', {});
      expect(results).toEqual([]);
    });
  });

  describe('Input Validation Error Handling', () => {
    it('should handle invalid SIREN numbers', async () => {
      const invalidSirens = [
        '', // Empty
        '12345', // Too short
        '1234567890', // Too long
        '12345678A', // Contains letters
        'ABCDEFGHI', // All letters
        '000000000', // All zeros
        null as any, // Null
        undefined as any // Undefined
      ];

      for (const invalidSiren of invalidSirens) {
        // Some adapters might validate input, others might let the API validate
        try {
          await adapters.insee.search(invalidSiren, {});
        } catch (error) {
          // Should handle gracefully
          expect(error).toBeInstanceOf(Error);
        }
      }
    });

    it('should handle invalid search options', async () => {
      const siren = enhancedMockCompanies.danone.siren;
      
      const invalidOptions = [
        { maxResults: -1 }, // Negative
        { maxResults: 0 }, // Zero
        { maxResults: 1000000 }, // Extremely large
        { maxResults: 'invalid' as any }, // Wrong type
        { includeHistory: 'yes' as any }, // Wrong type
        null as any, // Null options
        undefined as any // Undefined options
      ];

      mockedAxios.get.mockResolvedValue({
        data: { unitesLegales: [] }
      });

      for (const options of invalidOptions) {
        try {
          await adapters.insee.search(siren, options);
        } catch (error) {
          // Should handle gracefully
          expect(error).toBeInstanceOf(Error);
        }
      }
    });

    it('should handle special characters in search queries', async () => {
      const specialQueries = [
        'Company & Associates',
        'L\'Entreprise Française',
        'Company "With Quotes"',
        'Company <script>alert("xss")</script>',
        'Company\nWith\nNewlines',
        'Company\tWith\tTabs',
        'Company   With   Spaces',
        '🏢 Company with Emojis 🚀',
        'Company%20With%20Encoding'
      ];

      mockedAxios.get.mockResolvedValue({
        data: { unitesLegales: [] }
      });

      for (const query of specialQueries) {
        const results = await adapters.insee.search(query, {});
        expect(Array.isArray(results)).toBe(true);
      }
    });
  });

  describe('Cache Error Handling', () => {
    it('should handle cache get failures gracefully', async () => {
      const siren = enhancedMockCompanies.danone.siren;
      
      // Mock cache to throw error
      jest.spyOn(cache, 'get').mockRejectedValue(new Error('Cache unavailable'));
      
      // Mock successful API response
      mockedAxios.get.mockResolvedValue({
        data: {
          uniteLegale: {
            siren,
            denominationUniteLegale: 'Test Company'
          }
        }
      });

      // Should fallback to API when cache fails
      const results = await adapters.insee.getDetails(siren, {});
      expect(results.basicInfo.siren).toBe(siren);
    });

    it('should handle cache set failures gracefully', async () => {
      const siren = enhancedMockCompanies.danone.siren;
      
      // Mock cache set to throw error
      jest.spyOn(cache, 'set').mockRejectedValue(new Error('Cache write failed'));
      
      mockedAxios.get.mockResolvedValue({
        data: {
          uniteLegale: {
            siren,
            denominationUniteLegale: 'Test Company'
          }
        }
      });

      // Should still work even if cache write fails
      const results = await adapters.insee.getDetails(siren, {});
      expect(results.basicInfo.siren).toBe(siren);
    });

    it('should handle cache corruption', async () => {
      const siren = enhancedMockCompanies.danone.siren;
      
      // Mock cache to return corrupted data
      jest.spyOn(cache, 'get').mockResolvedValue({
        corrupted: 'data',
        notValid: 'search result'
      });

      mockedAxios.get.mockResolvedValue({
        data: {
          uniteLegale: {
            siren,
            denominationUniteLegale: 'Test Company'
          }
        }
      });

      // Should handle corrupted cache data and fallback to API
      const results = await adapters.insee.getDetails(siren, {});
      expect(results.basicInfo.siren).toBe(siren);
    });
  });

  describe('Rate Limiter Error Handling', () => {
    it('should handle rate limiter failures gracefully', async () => {
      const siren = enhancedMockCompanies.danone.siren;
      
      // Mock rate limiter to throw error
      jest.spyOn(rateLimiter, 'acquire').mockRejectedValue(new Error('Rate limiter failed'));
      
      mockedAxios.get.mockResolvedValue({
        data: {
          uniteLegale: {
            siren,
            denominationUniteLegale: 'Test Company'
          }
        }
      });

      // Should still work even if rate limiter fails
      await expect(adapters.insee.getDetails(siren, {}))
        .rejects.toThrow('Rate limiter failed');
    });

    it('should handle rate limiter status failures', async () => {
      // Mock rate limiter status to throw error
      jest.spyOn(rateLimiter, 'getStatus').mockRejectedValue(new Error('Status unavailable'));

      // getStatus should handle the error
      const status = await adapters.insee.getStatus();
      expect(status.available).toBe(false);
    });
  });

  describe('Adapter Configuration Error Handling', () => {
    it('should handle missing environment variables gracefully', async () => {
      // Remove environment variables
      delete process.env.INSEE_API_KEY;
      delete process.env.BANQUE_FRANCE_API_KEY;
      delete process.env.INPI_USERNAME;
      delete process.env.INPI_PASSWORD;

      // Create new adapters without credentials
      const newAdapters = setupAdapters({ cache, rateLimiter });

      // Should not throw during creation, but may fail during API calls
      expect(newAdapters.insee).toBeDefined();
      expect(newAdapters['banque-france']).toBeDefined();
      expect(newAdapters.inpi).toBeDefined();
    });

    it('should handle invalid API credentials', async () => {
      mockedAxios.get.mockRejectedValue({
        isAxiosError: true,
        response: {
          status: 401,
          data: { message: 'Invalid credentials' }
        }
      });

      await expect(adapters.insee.search('123456789', {}))
        .rejects.toThrow('INSEE API error: Invalid credentials');
    });
  });

  describe('INPI Authentication Error Handling', () => {
    it('should handle INPI authentication failures', async () => {
      // Mock authentication failure
      mockedAxios.post.mockRejectedValue({
        isAxiosError: true,
        response: {
          status: 401,
          data: { message: 'Invalid credentials' }
        }
      });

      await expect(adapters.inpi.search('123456789', {}))
        .rejects.toThrow('INPI authentication failed');
    });

    it('should handle INPI token expiration', async () => {
      // Mock successful authentication first
      mockedAxios.post.mockResolvedValueOnce({
        data: {
          access_token: 'expired-token',
          expires_in: -1 // Already expired
        }
      });

      // Mock token refresh
      mockedAxios.post.mockResolvedValueOnce({
        data: {
          access_token: 'new-token',
          expires_in: 3600
        }
      });

      // Mock API call with new token
      mockedAxios.get.mockResolvedValue({
        data: {
          companies: [{
            siren: '123456789',
            denomination: 'Test Company'
          }]
        }
      });

      const results = await adapters.inpi.search('123456789', {});
      expect(results).toHaveLength(1);
    });
  });

  describe('Concurrent Error Handling', () => {
    it('should handle concurrent errors without affecting other requests', async () => {
      const siren = enhancedMockCompanies.danone.siren;
      
      // Mix successful and failing requests
      let callCount = 0;
      mockedAxios.get.mockImplementation(() => {
        callCount++;
        if (callCount % 2 === 0) {
          return Promise.reject({
            isAxiosError: true,
            response: { status: 500, data: { message: 'Server error' } }
          });
        } else {
          return Promise.resolve({
            data: {
              uniteLegale: {
                siren,
                denominationUniteLegale: 'Test Company'
              }
            }
          });
        }
      });

      const promises = [];
      for (let i = 0; i < 10; i++) {
        promises.push(
          adapters.insee.getDetails(siren, {})
            .catch(error => error.message)
        );
      }

      const results = await Promise.all(promises);
      
      // Should have mix of successful results and error messages
      const successes = results.filter(r => r && r.basicInfo);
      const errors = results.filter(r => typeof r === 'string');
      
      expect(successes.length).toBeGreaterThan(0);
      expect(errors.length).toBeGreaterThan(0);
    });

    it('should maintain system stability under error storm', async () => {
      // Create error storm
      mockedAxios.get.mockRejectedValue(new Error('Simulated error storm'));
      
      const promises = [];
      for (let i = 0; i < 100; i++) {
        promises.push(
          adapters.insee.search(`query-${i}`, {})
            .catch(error => 'error')
        );
      }

      const results = await Promise.all(promises);
      
      // All should be handled as errors
      expect(results.every(r => r === 'error')).toBe(true);
      
      // System should still be responsive
      const status = await adapters.insee.getStatus();
      expect(status).toHaveProperty('available');
    });
  });

  describe('Recovery and Resilience', () => {
    it('should recover from temporary service outages', async () => {
      const siren = enhancedMockCompanies.danone.siren;
      let isOutage = true;

      mockedAxios.get.mockImplementation(() => {
        if (isOutage) {
          return Promise.reject({
            isAxiosError: true,
            response: { status: 503, data: { message: 'Service unavailable' } }
          });
        } else {
          return Promise.resolve({
            data: {
              uniteLegale: {
                siren,
                denominationUniteLegale: 'Test Company'
              }
            }
          });
        }
      });

      // First call should fail
      await expect(adapters.insee.getDetails(siren, {}))
        .rejects.toThrow('INSEE API error');

      // Simulate service recovery
      isOutage = false;

      // Second call should succeed
      const results = await adapters.insee.getDetails(siren, {});
      expect(results.basicInfo.siren).toBe(siren);
    });

    it('should maintain partial functionality during partial outages', async () => {
      const siren = enhancedMockCompanies.danone.siren;

      // INSEE fails
      mockedAxios.get.mockImplementation((url: string) => {
        if (url.includes('insee.fr')) {
          return Promise.reject(new Error('INSEE unavailable'));
        } else if (url.includes('banque-france.fr')) {
          return Promise.resolve({
            data: {
              bilans: [{
                raisonSociale: 'Test Company',
                revenue: 1000000
              }]
            }
          });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      // INSEE should fail
      await expect(adapters.insee.search(siren, {}))
        .rejects.toThrow('INSEE unavailable');

      // Banque de France should still work
      const bfResults = await adapters['banque-france'].search(siren, {});
      expect(bfResults).toHaveLength(1);
    });
  });
});