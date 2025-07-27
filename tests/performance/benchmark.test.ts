import { createCache } from '../../src/cache/index.js';
import { createRateLimiter } from '../../src/rate-limiter/index.js';
import { setupAdapters } from '../../src/adapters/index.js';
import { mockCompanies } from '../fixtures/index.js';

describe('Performance Benchmarks', () => {
  let cache: ReturnType<typeof createCache>;
  let rateLimiter: ReturnType<typeof createRateLimiter>;
  let adapters: ReturnType<typeof setupAdapters>;

  beforeEach(() => {
    cache = createCache();
    rateLimiter = createRateLimiter();
    adapters = setupAdapters({ cache, rateLimiter });
  });

  afterEach(async () => {
    await cache.flush();
  });

  describe('Cache Benchmarks', () => {
    it('should benchmark cache write performance', async () => {
      const iterations = [100, 500, 1000, 2000];
      const results = [];

      for (const count of iterations) {
        const startTime = process.hrtime.bigint();
        
        for (let i = 0; i < count; i++) {
          await cache.set(`benchmark-write-${i}`, {
            id: i,
            data: `test-data-${i}`,
            timestamp: Date.now()
          });
        }
        
        const endTime = process.hrtime.bigint();
        const duration = Number(endTime - startTime) / 1_000_000; // Convert to milliseconds
        const throughput = count / (duration / 1000); // Operations per second
        
        results.push({
          operations: count,
          duration,
          throughput: Math.round(throughput)
        });
      }

      // Verify performance scales reasonably
      expect(results[0].throughput).toBeGreaterThan(1000); // At least 1000 ops/sec for small sets
      
      console.log('Cache Write Performance:');
      results.forEach(result => {
        console.log(`  ${result.operations} ops: ${result.duration.toFixed(2)}ms (${result.throughput} ops/sec)`);
      });

      // Performance should not degrade drastically with scale
      const firstThroughput = results[0].throughput;
      const lastThroughput = results[results.length - 1].throughput;
      expect(lastThroughput).toBeGreaterThan(firstThroughput * 0.5); // Should retain at least 50% performance
    });

    it('should benchmark cache read performance', async () => {
      const cacheSize = 1000;
      const readCounts = [100, 500, 1000, 2000];

      // Pre-populate cache
      for (let i = 0; i < cacheSize; i++) {
        await cache.set(`benchmark-read-${i}`, {
          id: i,
          data: `test-data-${i}`,
          metadata: { created: Date.now() }
        });
      }

      const results = [];

      for (const count of readCounts) {
        const startTime = process.hrtime.bigint();
        
        // Random reads to simulate real usage
        for (let i = 0; i < count; i++) {
          const randomKey = `benchmark-read-${Math.floor(Math.random() * cacheSize)}`;
          await cache.get(randomKey);
        }
        
        const endTime = process.hrtime.bigint();
        const duration = Number(endTime - startTime) / 1_000_000;
        const throughput = count / (duration / 1000);
        
        results.push({
          operations: count,
          duration,
          throughput: Math.round(throughput)
        });
      }

      // Read performance should be very high
      expect(results[0].throughput).toBeGreaterThan(5000); // At least 5000 reads/sec
      
      console.log('Cache Read Performance:');
      results.forEach(result => {
        console.log(`  ${result.operations} ops: ${result.duration.toFixed(2)}ms (${result.throughput} ops/sec)`);
      });
    });

    it('should benchmark cache hit ratio under load', async () => {
      const totalRequests = 1000;
      const cacheSize = 100; // Smaller cache than requests to force some misses
      const hitRatioThreshold = 0.7; // Expect at least 70% hit ratio

      // Simulate realistic access pattern (some keys accessed more frequently)
      const keyWeights = Array.from({ length: cacheSize }, (_, i) => ({
        key: `weighted-${i}`,
        weight: Math.random() * 0.8 + 0.2 // Weight between 0.2 and 1.0
      }));

      let hits = 0;
      let misses = 0;

      const startTime = process.hrtime.bigint();

      for (let i = 0; i < totalRequests; i++) {
        // Select key based on weighted probability
        const randomValue = Math.random();
        const selectedKey = keyWeights.find(kw => randomValue < kw.weight)?.key || keyWeights[0].key;
        
        const cached = await cache.get(selectedKey);
        if (cached) {
          hits++;
        } else {
          misses++;
          // Cache miss - store data
          await cache.set(selectedKey, {
            id: selectedKey,
            data: `data-for-${selectedKey}`,
            accessTime: Date.now()
          });
        }
      }

      const endTime = process.hrtime.bigint();
      const duration = Number(endTime - startTime) / 1_000_000;
      const hitRatio = hits / (hits + misses);

      console.log(`Cache Hit Ratio Benchmark:`);
      console.log(`  Total requests: ${totalRequests}`);
      console.log(`  Hits: ${hits}, Misses: ${misses}`);
      console.log(`  Hit ratio: ${(hitRatio * 100).toFixed(1)}%`);
      console.log(`  Duration: ${duration.toFixed(2)}ms`);

      expect(hitRatio).toBeGreaterThan(hitRatioThreshold);
    });
  });

  describe('Rate Limiter Benchmarks', () => {
    it('should benchmark rate limiter acquire performance', async () => {
      const sources = ['benchmark-source-1', 'benchmark-source-2', 'benchmark-source-3'];
      const requestCounts = [50, 100, 200, 400];

      for (const source of sources) {
        console.log(`\nRate Limiter Performance for ${source}:`);
        
        for (const count of requestCounts) {
          const startTime = process.hrtime.bigint();
          
          const promises = [];
          for (let i = 0; i < count; i++) {
            promises.push(rateLimiter.acquire(source));
          }
          
          await Promise.all(promises);
          
          const endTime = process.hrtime.bigint();
          const duration = Number(endTime - startTime) / 1_000_000;
          const throughput = count / (duration / 1000);
          
          console.log(`  ${count} acquires: ${duration.toFixed(2)}ms (${Math.round(throughput)} ops/sec)`);
          
          // Reset rate limiter for next test
          rateLimiter.reset(source);
        }
      }
    });

    it('should benchmark concurrent rate limiting', async () => {
      const concurrentSources = [5, 10, 20, 50];
      const requestsPerSource = 20;

      for (const sourceCount of concurrentSources) {
        const startTime = process.hrtime.bigint();
        
        const sourcePromises = [];
        for (let i = 0; i < sourceCount; i++) {
          const source = `concurrent-bench-${i}`;
          const sourceOps = [];
          
          for (let j = 0; j < requestsPerSource; j++) {
            sourceOps.push(rateLimiter.acquire(source));
          }
          
          sourcePromises.push(Promise.all(sourceOps));
        }
        
        await Promise.all(sourcePromises);
        
        const endTime = process.hrtime.bigint();
        const duration = Number(endTime - startTime) / 1_000_000;
        const totalOps = sourceCount * requestsPerSource;
        const throughput = totalOps / (duration / 1000);
        
        console.log(`Concurrent Rate Limiting - ${sourceCount} sources:`)
        console.log(`  ${totalOps} total ops: ${duration.toFixed(2)}ms (${Math.round(throughput)} ops/sec)`);
      }
    });

    it('should benchmark rate limiter status queries', async () => {
      const sources = 100;
      const statusQueries = 1000;

      // Initialize sources
      for (let i = 0; i < sources; i++) {
        await rateLimiter.acquire(`status-bench-${i}`);
      }

      const startTime = process.hrtime.bigint();
      
      const promises = [];
      for (let i = 0; i < statusQueries; i++) {
        const sourceIndex = i % sources;
        promises.push(rateLimiter.getStatus(`status-bench-${sourceIndex}`));
      }
      
      const results = await Promise.all(promises);
      
      const endTime = process.hrtime.bigint();
      const duration = Number(endTime - startTime) / 1_000_000;
      const throughput = statusQueries / (duration / 1000);

      console.log(`Rate Limiter Status Performance:`);
      console.log(`  ${statusQueries} status queries: ${duration.toFixed(2)}ms (${Math.round(throughput)} ops/sec)`);
      
      // All status queries should succeed
      expect(results).toHaveLength(statusQueries);
      expect(results.every(status => status.remaining >= 0)).toBe(true);
    });
  });

  describe('System Integration Benchmarks', () => {
    it('should benchmark cache + rate limiter coordination', async () => {
      const operations = 500;
      const sources = ['integrated-source-1', 'integrated-source-2'];
      
      const startTime = process.hrtime.bigint();
      
      const promises = [];
      for (let i = 0; i < operations; i++) {
        const source = sources[i % sources.length];
        
        promises.push(
          rateLimiter.acquire(source)
            .then(() => cache.set(`integrated-${source}-${i}`, {
              source,
              operation: i,
              timestamp: Date.now()
            }))
            .then(() => cache.get(`integrated-${source}-${i}`))
        );
      }
      
      const results = await Promise.all(promises);
      
      const endTime = process.hrtime.bigint();
      const duration = Number(endTime - startTime) / 1_000_000;
      const throughput = operations / (duration / 1000);

      console.log(`Integrated Cache + Rate Limiter Performance:`);
      console.log(`  ${operations} ops: ${duration.toFixed(2)}ms (${Math.round(throughput)} ops/sec)`);
      
      // All operations should complete successfully
      expect(results).toHaveLength(operations);
      expect(results.every(result => result !== undefined)).toBe(true);
    });

    it('should benchmark memory usage under load', async () => {
      const initialMemory = process.memoryUsage();
      
      // Create significant load
      const cacheEntries = 5000;
      const largeDataSize = 1000; // 1KB per entry
      
      for (let i = 0; i < cacheEntries; i++) {
        await cache.set(`memory-test-${i}`, {
          id: i,
          data: 'x'.repeat(largeDataSize),
          metadata: {
            created: Date.now(),
            index: i,
            size: largeDataSize
          }
        });
      }
      
      const peakMemory = process.memoryUsage();
      
      // Clear cache
      await cache.flush();
      
      // Force garbage collection if available
      if (global.gc) {
        global.gc();
      }
      
      const finalMemory = process.memoryUsage();
      
      const memoryIncrease = peakMemory.heapUsed - initialMemory.heapUsed;
      const memoryRecovery = peakMemory.heapUsed - finalMemory.heapUsed;
      
      console.log(`Memory Usage Benchmark:`);
      console.log(`  Initial heap: ${(initialMemory.heapUsed / 1024 / 1024).toFixed(2)} MB`);
      console.log(`  Peak heap: ${(peakMemory.heapUsed / 1024 / 1024).toFixed(2)} MB`);
      console.log(`  Final heap: ${(finalMemory.heapUsed / 1024 / 1024).toFixed(2)} MB`);
      console.log(`  Memory increase: ${(memoryIncrease / 1024 / 1024).toFixed(2)} MB`);
      console.log(`  Memory recovery: ${(memoryRecovery / 1024 / 1024).toFixed(2)} MB`);
      
      // Memory usage should be reasonable (less than 50MB for 5MB of data)
      expect(memoryIncrease).toBeLessThan(50 * 1024 * 1024);
      
      // Should recover most memory after flush
      expect(memoryRecovery).toBeGreaterThan(memoryIncrease * 0.5);
    });

    it('should generate performance summary report', async () => {
      const testSuites = [
        {
          name: 'Cache Write',
          operations: 1000,
          expectedThroughput: 1000
        },
        {
          name: 'Cache Read',
          operations: 2000,
          expectedThroughput: 5000
        },
        {
          name: 'Rate Limiter',
          operations: 500,
          expectedThroughput: 100
        }
      ];

      const summary = {
        testRun: new Date().toISOString(),
        environment: {
          nodeVersion: process.version,
          platform: process.platform,
          arch: process.arch
        },
        results: []
      };

      for (const suite of testSuites) {
        const startTime = process.hrtime.bigint();
        
        // Run simplified benchmark
        if (suite.name === 'Cache Write') {
          for (let i = 0; i < suite.operations; i++) {
            await cache.set(`perf-${i}`, { id: i });
          }
        } else if (suite.name === 'Cache Read') {
          // Pre-populate
          for (let i = 0; i < 100; i++) {
            await cache.set(`read-${i}`, { id: i });
          }
          // Read operations
          for (let i = 0; i < suite.operations; i++) {
            await cache.get(`read-${i % 100}`);
          }
        } else if (suite.name === 'Rate Limiter') {
          const promises = [];
          for (let i = 0; i < suite.operations; i++) {
            promises.push(rateLimiter.acquire('perf-test'));
          }
          await Promise.all(promises);
        }
        
        const endTime = process.hrtime.bigint();
        const duration = Number(endTime - startTime) / 1_000_000;
        const actualThroughput = Math.round(suite.operations / (duration / 1000));
        
        const result = {
          suite: suite.name,
          operations: suite.operations,
          duration: Math.round(duration),
          throughput: actualThroughput,
          expected: suite.expectedThroughput,
          performance: actualThroughput >= suite.expectedThroughput ? 'PASS' : 'WARN'
        };
        
        summary.results.push(result);
      }

      console.log('\n=== PERFORMANCE SUMMARY REPORT ===');
      console.log(`Test Run: ${summary.testRun}`);
      console.log(`Environment: Node ${summary.environment.nodeVersion} on ${summary.environment.platform} ${summary.environment.arch}`);
      console.log('\nResults:');
      summary.results.forEach(result => {
        console.log(`  ${result.suite}: ${result.throughput} ops/sec (${result.performance})`);
        console.log(`    Operations: ${result.operations}, Duration: ${result.duration}ms`);
      });

      // At least some tests should meet performance expectations
      const passingTests = summary.results.filter(r => r.performance === 'PASS');
      expect(passingTests.length).toBeGreaterThan(0);
    });
  });
});