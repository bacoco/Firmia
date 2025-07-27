import { createCache } from '../../src/cache/index.js';
import { createRateLimiter } from '../../src/rate-limiter/index.js';
import { setupAdapters } from '../../src/adapters/index.js';
import { mockCompanies } from '../fixtures/index.js';
import axios from 'axios';

// Mock axios for performance testing
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('Performance Load Tests', () => {
  let cache: ReturnType<typeof createCache>;
  let rateLimiter: ReturnType<typeof createRateLimiter>;
  let adapters: ReturnType<typeof setupAdapters>;

  beforeEach(() => {
    jest.clearAllMocks();
    cache = createCache();
    rateLimiter = createRateLimiter();
    adapters = setupAdapters({ cache, rateLimiter });

    // Set environment variables
    process.env.INSEE_API_KEY = 'test-key';
    process.env.BANQUE_FRANCE_API_KEY = 'test-key';
    process.env.INPI_USERNAME = 'test-user';
    process.env.INPI_PASSWORD = 'test-pass';
  });

  afterEach(async () => {
    await cache.flush();
    delete process.env.INSEE_API_KEY;
    delete process.env.BANQUE_FRANCE_API_KEY;
    delete process.env.INPI_USERNAME;
    delete process.env.INPI_PASSWORD;
  });

  describe('Cache Performance Under Load', () => {
    it('should handle high-frequency cache operations', async () => {
      const operations = 1000;
      const startTime = Date.now();

      // Perform many cache operations
      const promises = [];
      for (let i = 0; i < operations; i++) {
        const key = `load-test-${i}`;
        const value = { id: i, data: `test-data-${i}`, timestamp: Date.now() };
        
        promises.push(
          cache.set(key, value).then(() => cache.get(key))
        );
      }

      const results = await Promise.all(promises);
      const duration = Date.now() - startTime;

      // All operations should complete
      expect(results).toHaveLength(operations);
      
      // Should complete within reasonable time (< 1 second for 1000 ops)
      expect(duration).toBeLessThan(1000);

      // Cache should have all entries
      const stats = cache.getStats();
      expect(stats.keys).toBe(operations);
    });

    it('should maintain performance with large cache size', async () => {
      const cacheSize = 5000;
      const testOps = 100;

      // Fill cache with large dataset
      for (let i = 0; i < cacheSize; i++) {
        await cache.set(`bulk-${i}`, {
          id: i,
          data: 'x'.repeat(100), // 100 bytes per entry
          metadata: { created: Date.now(), type: 'bulk' }
        });
      }

      // Measure performance of operations on large cache
      const startTime = Date.now();
      const promises = [];

      for (let i = 0; i < testOps; i++) {
        const randomKey = `bulk-${Math.floor(Math.random() * cacheSize)}`;
        promises.push(cache.get(randomKey));
      }

      const results = await Promise.all(promises);
      const duration = Date.now() - startTime;

      // All operations should complete
      expect(results).toHaveLength(testOps);
      
      // Performance should not degrade significantly with cache size
      expect(duration).toBeLessThan(500); // < 5ms per operation on average

      const stats = cache.getStats();
      expect(stats.keys).toBe(cacheSize);
    });

    it('should handle concurrent cache access efficiently', async () => {
      const concurrentUsers = 50;
      const operationsPerUser = 10;
      const startTime = Date.now();

      // Simulate concurrent users accessing cache
      const userPromises = [];
      for (let user = 0; user < concurrentUsers; user++) {
        const userOps = [];
        for (let op = 0; op < operationsPerUser; op++) {
          const key = `user-${user}-op-${op}`;
          const value = { user, operation: op, timestamp: Date.now() };
          
          userOps.push(
            cache.set(key, value)
              .then(() => cache.get(key))
              .then(() => cache.delete(key))
          );
        }
        userPromises.push(Promise.all(userOps));
      }

      await Promise.all(userPromises);
      const duration = Date.now() - startTime;

      // Should complete all operations within reasonable time
      expect(duration).toBeLessThan(2000); // 2 seconds for 2500 total operations

      // Cache should be empty after all deletions
      const stats = cache.getStats();
      expect(stats.keys).toBe(0);
    });

    it('should handle memory pressure gracefully', async () => {
      const largeCacheSize = 10000;
      const largeValueSize = 1000; // 1KB per entry = 10MB total

      // Create large values to test memory usage
      const largeValue = {
        id: 'memory-test',
        data: 'x'.repeat(largeValueSize),
        metadata: {
          created: Date.now(),
          size: largeValueSize,
          purpose: 'memory-pressure-test'
        }
      };

      const startTime = Date.now();

      // Fill cache with large data
      for (let i = 0; i < largeCacheSize; i++) {
        await cache.set(`memory-test-${i}`, {
          ...largeValue,
          id: i
        });

        // Check memory usage every 1000 entries
        if (i % 1000 === 0) {
          const stats = cache.getStats();
          expect(stats.keys).toBe(i + 1);
        }
      }

      const fillDuration = Date.now() - startTime;

      // Test retrieval performance with large cache
      const retrievalStartTime = Date.now();
      const randomKeys = [];
      for (let i = 0; i < 100; i++) {
        const randomIndex = Math.floor(Math.random() * largeCacheSize);
        randomKeys.push(`memory-test-${randomIndex}`);
      }

      const retrievalPromises = randomKeys.map(key => cache.get(key));
      const results = await Promise.all(retrievalPromises);
      const retrievalDuration = Date.now() - retrievalStartTime;

      // All retrievals should succeed
      expect(results.every(result => result !== undefined)).toBe(true);

      // Performance should remain acceptable even with large cache
      expect(retrievalDuration).toBeLessThan(1000); // < 10ms per retrieval on average

      console.log(`Cache performance: Fill ${largeCacheSize} entries in ${fillDuration}ms, retrieve 100 in ${retrievalDuration}ms`);
    });
  });

  describe('Rate Limiter Performance Under Load', () => {
    it('should handle burst requests efficiently', async () => {
      const burstSize = 100;
      const startTime = Date.now();

      // Create burst of requests
      const promises = [];
      for (let i = 0; i < burstSize; i++) {
        promises.push(rateLimiter.acquire('insee'));
      }

      await Promise.all(promises);
      const duration = Date.now() - startTime;

      // Should handle burst within reasonable time
      expect(duration).toBeLessThan(5000); // 5 seconds for 100 requests

      // Rate limiter should track all requests
      const status = await rateLimiter.getStatus('insee');
      expect(status.remaining).toBeLessThan(5000); // Should have consumed requests
    });

    it('should maintain performance across multiple sources', async () => {
      const sources = ['insee', 'banque-france', 'inpi', 'custom-1', 'custom-2'];
      const requestsPerSource = 50;
      const startTime = Date.now();

      // Create requests across multiple sources
      const promises = [];
      for (const source of sources) {
        for (let i = 0; i < requestsPerSource; i++) {
          promises.push(rateLimiter.acquire(source));
        }
      }

      await Promise.all(promises);
      const duration = Date.now() - startTime;

      // Should handle multi-source load efficiently
      expect(duration).toBeLessThan(10000); // 10 seconds for 250 total requests

      // Each source should have independent status
      for (const source of sources) {
        const status = await rateLimiter.getStatus(source);
        expect(status.remaining).toBeLessThan(1000);
        expect(status.reset).toBeInstanceOf(Date);
      }
    });

    it('should scale with concurrent rate limiting', async () => {
      const concurrentSources = 20;
      const requestsPerSource = 25;
      const startTime = Date.now();

      // Create many concurrent sources
      const sourcePromises = [];
      for (let i = 0; i < concurrentSources; i++) {
        const source = `concurrent-source-${i}`;
        const sourceOps = [];
        
        for (let j = 0; j < requestsPerSource; j++) {
          sourceOps.push(rateLimiter.acquire(source));
        }
        
        sourcePromises.push(Promise.all(sourceOps));
      }

      await Promise.all(sourcePromises);
      const duration = Date.now() - startTime;

      // Should scale to many concurrent sources
      expect(duration).toBeLessThan(15000); // 15 seconds for 500 total requests across 20 sources

      console.log(`Rate limiter performance: ${concurrentSources * requestsPerSource} requests across ${concurrentSources} sources in ${duration}ms`);
    });
  });

  describe('Adapter Performance Under Load', () => {
    it('should handle high-volume searches efficiently', async () => {
      const searchQueries = 200;
      
      // Mock fast API responses
      mockedAxios.get.mockResolvedValue({
        data: {
          unitesLegales: [{
            siren: '123456789',
            denominationUniteLegale: 'Test Company',
            etatAdministratifUniteLegale: 'A'
          }]
        }
      });

      const startTime = Date.now();

      // Create high volume of search requests
      const promises = [];
      for (let i = 0; i < searchQueries; i++) {
        promises.push(adapters.insee.search(`query-${i}`, { maxResults: 5 }));
      }

      const results = await Promise.all(promises);
      const duration = Date.now() - startTime;

      // All searches should complete
      expect(results).toHaveLength(searchQueries);
      
      // Should complete within reasonable time
      expect(duration).toBeLessThan(10000); // 10 seconds for 200 searches

      console.log(`Adapter performance: ${searchQueries} searches in ${duration}ms`);
    });

    it('should optimize with cache hits under load', async () => {
      const siren = mockCompanies.danone.siren;
      const requests = 100;

      // Mock API response (should only be called once due to caching)
      mockedAxios.get.mockResolvedValue({
        data: {
          uniteLegale: {
            siren: siren,
            denominationUniteLegale: mockCompanies.danone.name
          }
        }
      });

      const startTime = Date.now();

      // Make many identical requests
      const promises = [];
      for (let i = 0; i < requests; i++) {
        promises.push(adapters.insee.getDetails(siren, {}));
      }

      const results = await Promise.all(promises);
      const duration = Date.now() - startTime;

      // All requests should complete
      expect(results).toHaveLength(requests);
      
      // Should be very fast due to caching (most requests hit cache)
      expect(duration).toBeLessThan(1000); // < 1 second for 100 cached requests

      // Should have made minimal API calls due to caching
      expect(mockedAxios.get).toHaveBeenCalledTimes(1);

      const cacheStats = cache.getStats();
      expect(cacheStats.hits).toBeGreaterThan(0);
    });

    it('should handle mixed workload efficiently', async () => {
      const companies = Object.values(mockCompanies);
      const operationsPerCompany = 10;
      
      // Mock responses for different operations
      mockedAxios.get.mockImplementation((url: string) => {
        if (url.includes('siren/')) {
          return Promise.resolve({
            data: {
              uniteLegale: {
                siren: '123456789',
                denominationUniteLegale: 'Test Company'
              }
            }
          });
        } else {
          return Promise.resolve({
            data: {
              unitesLegales: [{
                siren: '123456789',
                denominationUniteLegale: 'Test Company'
              }]
            }
          });
        }
      });

      const startTime = Date.now();

      // Create mixed workload (search + details for each company)
      const promises = [];
      for (const company of companies) {
        for (let i = 0; i < operationsPerCompany; i++) {
          // Mix search and details requests
          if (i % 2 === 0) {
            promises.push(adapters.insee.search(company.siren, {}));
          } else {
            promises.push(adapters.insee.getDetails(company.siren, {}));
          }
        }
      }

      const results = await Promise.all(promises);
      const duration = Date.now() - startTime;

      // All operations should complete
      expect(results).toHaveLength(companies.length * operationsPerCompany);
      
      // Should handle mixed workload efficiently
      expect(duration).toBeLessThan(5000); // 5 seconds for mixed operations

      console.log(`Mixed workload performance: ${results.length} operations in ${duration}ms`);
    });
  });

  describe('System-wide Performance', () => {
    it('should maintain performance under full system load', async () => {
      const totalOperations = 500;
      const operationTypes = ['search', 'details', 'status'];
      const adapters_list = ['insee', 'banque-france'];
      
      // Mock all adapter responses
      mockedAxios.get.mockResolvedValue({
        data: { unitesLegales: [{ siren: '123456789', denominationUniteLegale: 'Test' }] }
      });

      mockedAxios.post.mockResolvedValue({
        data: { access_token: 'token', expires_in: 3600 }
      });

      const startTime = Date.now();

      // Create comprehensive system load
      const promises = [];
      for (let i = 0; i < totalOperations; i++) {
        const adapterName = adapters_list[i % adapters_list.length];
        const operationType = operationTypes[i % operationTypes.length];
        const adapter = adapters[adapterName];
        
        switch (operationType) {
          case 'search':
            promises.push(adapter.search(`query-${i}`, {}));
            break;
          case 'details':
            promises.push(adapter.getDetails('123456789', {}));
            break;
          case 'status':
            promises.push(adapter.getStatus());
            break;
        }
      }

      const results = await Promise.all(promises);
      const duration = Date.now() - startTime;

      // All operations should complete
      expect(results).toHaveLength(totalOperations);
      
      // System should handle full load within reasonable time
      expect(duration).toBeLessThan(15000); // 15 seconds for 500 mixed operations

      // System components should remain healthy
      const cacheStats = cache.getStats();
      expect(cacheStats.keys).toBeGreaterThan(0);

      const rateLimitStatus = await rateLimiter.getStatus('insee');
      expect(rateLimitStatus.remaining).toBeGreaterThanOrEqual(0);

      console.log(`System performance: ${totalOperations} mixed operations in ${duration}ms`);
      console.log(`Cache stats: ${cacheStats.keys} keys, ${cacheStats.hits} hits`);
      console.log(`Rate limit remaining: ${rateLimitStatus.remaining}`);
    });

    it('should recover from performance bottlenecks', async () => {
      // Simulate slow API responses
      mockedAxios.get.mockImplementation(() => 
        new Promise(resolve => 
          setTimeout(() => resolve({
            data: { unitesLegales: [{ siren: '123456789' }] }
          }), 100) // 100ms delay per request
        )
      );

      const slowRequests = 20;
      const startTime = Date.now();

      // Make requests with artificial delay
      const slowPromises = [];
      for (let i = 0; i < slowRequests; i++) {
        slowPromises.push(adapters.insee.search(`slow-${i}`, {}));
      }

      await Promise.all(slowPromises);
      const slowDuration = Date.now() - startTime;

      // Now test fast cached requests
      mockedAxios.get.mockResolvedValue({
        data: { unitesLegales: [{ siren: '123456789' }] }
      });

      const fastStartTime = Date.now();
      const fastPromises = [];
      for (let i = 0; i < slowRequests; i++) {
        // Same queries should hit cache now
        fastPromises.push(adapters.insee.search(`slow-${i}`, {}));
      }

      await Promise.all(fastPromises);
      const fastDuration = Date.now() - fastStartTime;

      // Cached requests should be much faster
      expect(fastDuration).toBeLessThan(slowDuration / 5); // At least 5x faster with cache

      console.log(`Recovery performance: Slow ${slowDuration}ms vs Fast ${fastDuration}ms`);
    });
  });
});