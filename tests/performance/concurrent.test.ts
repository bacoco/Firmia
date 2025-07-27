import { INSEEAdapter } from '../../src/adapters/insee';
import { BanqueFranceAdapter } from '../../src/adapters/banque-france';
import { INPIAdapter } from '../../src/adapters/inpi';
import { setupAdapters } from '../../src/adapters';
import { createCache } from '../../src/cache';
import { createRateLimiter } from '../../src/rate-limiter';
import axios from 'axios';
import { mockCompanies, mockINSEEResponses } from '../fixtures';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('Concurrent Request Performance Tests', () => {
  let adapters: ReturnType<typeof setupAdapters>;
  let cache: ReturnType<typeof createCache>;
  let rateLimiter: ReturnType<typeof createRateLimiter>;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Set up environment
    process.env.INSEE_API_KEY = 'test-key';
    process.env.BANQUE_FRANCE_API_KEY = 'test-key';
    process.env.INPI_USERNAME = 'test-user';
    process.env.INPI_PASSWORD = 'test-pass';

    // Create real cache and rate limiter for performance testing
    cache = createCache();
    rateLimiter = createRateLimiter({
      limits: {
        insee: { requestsPerSecond: 30, requestsPerMinute: 500 },
        'banque-france': { requestsPerSecond: 10, requestsPerMinute: 100 },
        inpi: { requestsPerSecond: 20, requestsPerMinute: 200 }
      }
    });

    adapters = setupAdapters({ cache, rateLimiter });

    // Mock axios.create for INPI
    (axios.create as jest.Mock) = jest.fn(() => ({
      get: jest.fn(),
      post: jest.fn(),
      defaults: { headers: {} }
    }));
  });

  afterEach(() => {
    delete process.env.INSEE_API_KEY;
    delete process.env.BANQUE_FRANCE_API_KEY;
    delete process.env.INPI_USERNAME;
    delete process.env.INPI_PASSWORD;
  });

  describe('Single Adapter Concurrent Requests', () => {
    it('should handle multiple concurrent searches efficiently', async () => {
      // Mock successful responses
      mockedAxios.get.mockResolvedValue({
        data: mockINSEEResponses.searchByName
      });

      const startTime = Date.now();
      const queries = ['DANONE', 'CARREFOUR', 'AIRBUS', 'TOTAL', 'RENAULT'];
      
      // Execute searches concurrently
      const promises = queries.map(query => 
        adapters.insee.search(query, { maxResults: 5 })
      );

      const results = await Promise.all(promises);
      const duration = Date.now() - startTime;

      // All searches should complete
      expect(results).toHaveLength(queries.length);
      results.forEach(result => {
        expect(result).toBeDefined();
        expect(Array.isArray(result)).toBe(true);
      });

      // Should complete reasonably quickly (under 2 seconds for 5 requests)
      expect(duration).toBeLessThan(2000);

      // Verify rate limiting was applied
      expect(mockedAxios.get).toHaveBeenCalledTimes(queries.length);
    });

    it('should benefit from caching on repeated requests', async () => {
      mockedAxios.get.mockResolvedValue({
        data: mockINSEEResponses.searchByName
      });

      const query = 'DANONE';
      
      // First request - should hit API
      const startTime1 = Date.now();
      const result1 = await adapters.insee.search(query, { maxResults: 5 });
      const duration1 = Date.now() - startTime1;

      // Second request - should hit cache
      const startTime2 = Date.now();
      const result2 = await adapters.insee.search(query, { maxResults: 5 });
      const duration2 = Date.now() - startTime2;

      expect(result1).toEqual(result2);
      expect(duration2).toBeLessThan(duration1); // Cache hit should be faster
      expect(mockedAxios.get).toHaveBeenCalledTimes(1); // Only one API call
    });

    it('should handle mixed cache hits and API calls', async () => {
      mockedAxios.get.mockResolvedValue({
        data: mockINSEEResponses.searchByName
      });

      // Pre-populate cache with some queries
      const cachedQueries = ['DANONE', 'CARREFOUR'];
      for (const query of cachedQueries) {
        await adapters.insee.search(query, { maxResults: 5 });
      }

      // Reset mock to count only new API calls
      mockedAxios.get.mockClear();

      // Mix of cached and new queries
      const allQueries = ['DANONE', 'AIRBUS', 'CARREFOUR', 'TOTAL', 'RENAULT'];
      const startTime = Date.now();

      const promises = allQueries.map(query =>
        adapters.insee.search(query, { maxResults: 5 })
      );

      const results = await Promise.all(promises);
      const duration = Date.now() - startTime;

      expect(results).toHaveLength(allQueries.length);
      // Should only make API calls for non-cached queries
      expect(mockedAxios.get).toHaveBeenCalledTimes(3); // AIRBUS, TOTAL, RENAULT
      expect(duration).toBeLessThan(1000); // Should be fast due to cache hits
    });
  });

  describe('Multi-Adapter Concurrent Requests', () => {
    beforeEach(() => {
      // Mock INPI authentication
      mockedAxios.post.mockResolvedValue({
        data: { access_token: 'test-token', expires_in: 3600 }
      });
    });

    it('should handle concurrent requests across multiple adapters', async () => {
      // Mock responses for each adapter
      mockedAxios.get.mockImplementation((url: string) => {
        if (url.includes('insee.fr')) {
          return Promise.resolve({ data: mockINSEEResponses.searchByName });
        } else if (url.includes('banque-france.fr')) {
          return Promise.resolve({ data: { bilans: [] } });
        } else {
          return Promise.resolve({ data: { companies: [] } });
        }
      });

      const siren = mockCompanies.danone.siren;
      const startTime = Date.now();

      // Search across all adapters concurrently
      const promises = [
        adapters.insee.search(siren, {}),
        adapters['banque-france'].search(siren, {}),
        adapters.inpi.search(siren, {})
      ];

      const [inseeResults, bfResults, inpiResults] = await Promise.all(promises);
      const duration = Date.now() - startTime;

      // All should complete
      expect(inseeResults).toBeDefined();
      expect(bfResults).toBeDefined();
      expect(inpiResults).toBeDefined();

      // Should complete within reasonable time despite different rate limits
      expect(duration).toBeLessThan(3000);
    });

    it('should respect individual adapter rate limits', async () => {
      // Mock slow responses to simulate rate limiting effect
      mockedAxios.get.mockImplementation(() => 
        new Promise(resolve => 
          setTimeout(() => resolve({ data: mockINSEEResponses.searchByName }), 50)
        )
      );

      const startTime = Date.now();
      
      // Make many concurrent requests to different adapters
      const promises = [];
      
      // 15 requests to INSEE (30 req/s limit)
      for (let i = 0; i < 15; i++) {
        promises.push(adapters.insee.search(`Company${i}`, {}));
      }
      
      // 5 requests to Banque de France (10 req/s limit)
      for (let i = 0; i < 5; i++) {
        promises.push(adapters['banque-france'].search(`${100000000 + i}`, {}));
      }

      await Promise.all(promises);
      const duration = Date.now() - startTime;

      // Should handle all requests without errors
      expect(promises).toHaveLength(20);
      
      // Duration should reflect rate limiting
      // With proper rate limiting, this should take at least 500ms
      expect(duration).toBeGreaterThan(500);
    });
  });

  describe('Error Handling Under Load', () => {
    it('should handle API errors gracefully under concurrent load', async () => {
      // Mock intermittent failures
      let callCount = 0;
      mockedAxios.get.mockImplementation(() => {
        callCount++;
        if (callCount % 3 === 0) {
          // Every third request fails
          return Promise.reject(new Error('API Error'));
        }
        return Promise.resolve({ data: mockINSEEResponses.searchByName });
      });

      const queries = Array.from({ length: 10 }, (_, i) => `Company${i}`);
      
      const promises = queries.map(async (query) => {
        try {
          return await adapters.insee.search(query, {});
        } catch (error) {
          return { error: error.message };
        }
      });

      const results = await Promise.all(promises);

      // Should handle mix of successes and failures
      const successes = results.filter(r => !r.error);
      const failures = results.filter(r => r.error);

      expect(successes.length).toBeGreaterThan(0);
      expect(failures.length).toBeGreaterThan(0);
      expect(results).toHaveLength(queries.length);
    });

    it('should handle rate limit errors without blocking other requests', async () => {
      // Mock rate limit error after certain number of requests
      let requestCount = 0;
      mockedAxios.get.mockImplementation(() => {
        requestCount++;
        if (requestCount > 5) {
          const error: any = new Error('Rate limit exceeded');
          error.response = { status: 429 };
          error.isAxiosError = true;
          return Promise.reject(error);
        }
        return Promise.resolve({ data: mockINSEEResponses.searchByName });
      });

      const queries = Array.from({ length: 10 }, (_, i) => `Company${i}`);
      
      const results = await Promise.allSettled(
        queries.map(query => adapters.insee.search(query, {}))
      );

      // Should have both fulfilled and rejected promises
      const fulfilled = results.filter(r => r.status === 'fulfilled');
      const rejected = results.filter(r => r.status === 'rejected');

      expect(fulfilled.length).toBe(5);
      expect(rejected.length).toBe(5);
    });
  });

  describe('Memory and Resource Usage', () => {
    it('should handle large result sets efficiently', async () => {
      // Mock large response
      const largeResponse = {
        unitesLegales: Array.from({ length: 100 }, (_, i) => ({
          siren: `${100000000 + i}`,
          denominationUniteLegale: `Company ${i}`,
          categorieJuridiqueUniteLegale: '5710',
          adresseSiegeUniteLegale: {
            numeroVoieEtablissement: `${i}`,
            typeVoieEtablissement: 'RUE',
            libelleVoieEtablissement: 'TEST',
            codePostalEtablissement: '75001',
            libelleCommuneEtablissement: 'PARIS'
          },
          activitePrincipaleUniteLegale: '62.01Z',
          dateCreationUniteLegale: '2020-01-01',
          etatAdministratifUniteLegale: 'A'
        }))
      };

      mockedAxios.get.mockResolvedValue({ data: largeResponse });

      const startMemory = process.memoryUsage().heapUsed;
      
      // Make multiple requests for large datasets
      const promises = Array.from({ length: 5 }, (_, i) =>
        adapters.insee.search(`LargeQuery${i}`, { maxResults: 100 })
      );

      const results = await Promise.all(promises);
      
      const endMemory = process.memoryUsage().heapUsed;
      const memoryIncrease = endMemory - startMemory;

      // Verify results
      results.forEach(result => {
        expect(result).toHaveLength(100);
      });

      // Memory increase should be reasonable (less than 50MB for 500 total results)
      expect(memoryIncrease).toBeLessThan(50 * 1024 * 1024);
    });

    it('should clean up resources properly after concurrent operations', async () => {
      mockedAxios.get.mockResolvedValue({
        data: mockINSEEResponses.searchByName
      });

      // Perform many operations
      const operations = Array.from({ length: 50 }, (_, i) => 
        adapters.insee.search(`Query${i}`, {})
      );

      await Promise.all(operations);

      // Force garbage collection if available
      if (global.gc) {
        global.gc();
      }

      // Cache should still be functional
      const cacheStats = cache.getStats();
      expect(cacheStats.keys).toBeGreaterThan(0);

      // Should be able to perform more operations
      const moreOperations = Array.from({ length: 10 }, (_, i) =>
        adapters.insee.search(`NewQuery${i}`, {})
      );

      const moreResults = await Promise.all(moreOperations);
      expect(moreResults).toHaveLength(10);
    });
  });

  describe('Performance Benchmarks', () => {
    it('should measure average response time for concurrent requests', async () => {
      mockedAxios.get.mockResolvedValue({
        data: mockINSEEResponses.searchByName
      });

      const iterations = 20;
      const responseTimes: number[] = [];

      for (let i = 0; i < iterations; i++) {
        const startTime = Date.now();
        await adapters.insee.search(`Benchmark${i}`, {});
        responseTimes.push(Date.now() - startTime);
      }

      const avgResponseTime = responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length;
      const minResponseTime = Math.min(...responseTimes);
      const maxResponseTime = Math.max(...responseTimes);

      console.log(`
        Performance Metrics:
        - Average response time: ${avgResponseTime.toFixed(2)}ms
        - Min response time: ${minResponseTime}ms
        - Max response time: ${maxResponseTime}ms
      `);

      // Average should be reasonable
      expect(avgResponseTime).toBeLessThan(200);
      
      // Should not have extreme outliers
      expect(maxResponseTime).toBeLessThan(avgResponseTime * 3);
    });

    it('should measure throughput under sustained load', async () => {
      mockedAxios.get.mockResolvedValue({
        data: mockINSEEResponses.searchByName
      });

      const duration = 5000; // Run for 5 seconds
      const startTime = Date.now();
      let requestCount = 0;
      const errors: Error[] = [];

      // Keep making requests for the duration
      while (Date.now() - startTime < duration) {
        try {
          await adapters.insee.search(`Load${requestCount}`, {});
          requestCount++;
        } catch (error) {
          errors.push(error);
        }
        
        // Small delay to prevent tight loop
        await new Promise(resolve => setTimeout(resolve, 10));
      }

      const actualDuration = Date.now() - startTime;
      const throughput = (requestCount / actualDuration) * 1000; // requests per second

      console.log(`
        Throughput Metrics:
        - Total requests: ${requestCount}
        - Duration: ${actualDuration}ms
        - Throughput: ${throughput.toFixed(2)} req/s
        - Errors: ${errors.length}
      `);

      // Should achieve reasonable throughput
      expect(throughput).toBeGreaterThan(5); // At least 5 req/s
      expect(errors.length).toBe(0); // No errors under normal load
    });
  });
});