import { createRateLimiter, TokenBucketRateLimiter } from '../../src/rate-limiter/index.js';
import pLimit from 'p-limit';

// Mock p-limit
jest.mock('p-limit');
const mockedPLimit = pLimit as jest.MockedFunction<typeof pLimit>;

describe('Rate Limiter Edge Cases and Concurrent Behavior', () => {
  let rateLimiter: TokenBucketRateLimiter;

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    
    // Create a mock limiter that simulates real rate limiting behavior
    const mockLimiter = jest.fn(async (fn: () => Promise<void>) => {
      await fn();
    }) as any;
    
    // Add required properties to match LimitFunction interface
    mockLimiter.activeCount = 0;
    mockLimiter.pendingCount = 0;
    mockLimiter.clearQueue = jest.fn();
    
    mockedPLimit.mockReturnValue(mockLimiter);
    
    rateLimiter = new TokenBucketRateLimiter({
      limits: {
        'test-source': {
          requestsPerSecond: 5,
          requestsPerMinute: 100,
          requestsPerHour: 1000
        },
        'burst-source': {
          requestsPerSecond: 1,
          requestsPerMinute: 10,
          requestsPerHour: 100
        }
      }
    });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Concurrent Access Edge Cases', () => {
    it('should handle rapid concurrent acquisitions without race conditions', async () => {
      const concurrentRequests = 100;
      const promises = [];
      const results: any[] = [];

      // Create many simultaneous requests
      for (let i = 0; i < concurrentRequests; i++) {
        promises.push(
          rateLimiter.acquire('test-source')
            .then(() => results.push(i))
            .catch(error => results.push(`error-${i}: ${error.message}`))
        );
      }

      await Promise.all(promises);

      // All requests should complete
      expect(results).toHaveLength(concurrentRequests);
      
      // No error results should be present
      const errors = results.filter(r => typeof r === 'string' && r.startsWith('error-'));
      expect(errors).toHaveLength(0);

      // Rate limiter should track the requests correctly
      const status = await rateLimiter.getStatus('test-source');
      expect(status.remaining).toBeLessThan(1000);
    });

    it('should handle concurrent status queries safely', async () => {
      const statusQueries = 50;
      const promises = [];

      // Make concurrent status queries
      for (let i = 0; i < statusQueries; i++) {
        promises.push(rateLimiter.getStatus('test-source'));
      }

      const results = await Promise.all(promises);

      // All queries should succeed
      expect(results).toHaveLength(statusQueries);
      
      // All results should have consistent structure
      results.forEach(status => {
        expect(status).toHaveProperty('remaining');
        expect(status).toHaveProperty('reset');
        expect(typeof status.remaining).toBe('number');
        expect(status.reset).toBeInstanceOf(Date);
      });

      // All results should be identical (no race conditions)
      const firstResult = results[0];
      results.forEach(result => {
        expect(result.remaining).toBe(firstResult.remaining);
        expect(result.reset.getTime()).toBe(firstResult.reset.getTime());
      });
    });

    it('should handle mixed concurrent acquire and status operations', async () => {
      const operations = 100;
      const promises = [];
      const acquireResults: any[] = [];
      const statusResults: any[] = [];

      for (let i = 0; i < operations; i++) {
        if (i % 2 === 0) {
          // Acquire operation
          promises.push(
            rateLimiter.acquire('test-source')
              .then(() => acquireResults.push(i))
          );
        } else {
          // Status operation
          promises.push(
            rateLimiter.getStatus('test-source')
              .then(status => statusResults.push(status))
          );
        }
      }

      await Promise.all(promises);

      expect(acquireResults).toHaveLength(50);
      expect(statusResults).toHaveLength(50);

      // Status queries should show decreasing remaining count
      // (though exact values depend on timing)
      statusResults.forEach(status => {
        expect(status.remaining).toBeGreaterThanOrEqual(0);
        expect(status.remaining).toBeLessThanOrEqual(1000);
      });
    });
  });

  describe('Resource Exhaustion Edge Cases', () => {
    it('should handle rate limit exhaustion gracefully', async () => {
      const maxRequests = 1000; // Equal to hourly limit
      const promises = [];

      // Exhaust the rate limit
      for (let i = 0; i < maxRequests + 10; i++) {
        promises.push(
          rateLimiter.acquire('test-source')
            .catch(error => `error: ${error.message}`)
        );
      }

      const results = await Promise.all(promises);

      // Should handle all requests
      expect(results).toHaveLength(maxRequests + 10);

      // Check final status
      const finalStatus = await rateLimiter.getStatus('test-source');
      expect(finalStatus.remaining).toBe(0);
    });

    it('should maintain separate limits for different sources under stress', async () => {
      const sources = ['source-1', 'source-2', 'source-3'];
      const requestsPerSource = 200;
      const allPromises = [];

      for (const source of sources) {
        const sourcePromises = [];
        for (let i = 0; i < requestsPerSource; i++) {
          sourcePromises.push(rateLimiter.acquire(source));
        }
        allPromises.push(Promise.all(sourcePromises));
      }

      await Promise.all(allPromises);

      // Each source should have independent status
      for (const source of sources) {
        const status = await rateLimiter.getStatus(source);
        expect(status.remaining).toBeLessThan(1000);
        expect(status.remaining).toBeGreaterThanOrEqual(0);
      }
    });

    it('should handle burst requests correctly', async () => {
      // Configure for very low burst limit
      const burstLimiter = new TokenBucketRateLimiter({
        limits: {
          'burst-test': {
            requestsPerSecond: 2, // Very low limit
            requestsPerMinute: 10,
            requestsPerHour: 50
          }
        }
      });

      const burstSize = 20;
      const startTime = Date.now();
      
      const promises = [];
      for (let i = 0; i < burstSize; i++) {
        promises.push(burstLimiter.acquire('burst-test'));
      }

      await Promise.all(promises);
      const duration = Date.now() - startTime;

      // With such low limits, requests should be throttled
      const status = await burstLimiter.getStatus('burst-test');
      expect(status.remaining).toBeLessThan(50);
    });
  });

  describe('Time-based Edge Cases', () => {
    it('should handle counter reset at boundary conditions', async () => {
      // Make some requests
      for (let i = 0; i < 10; i++) {
        await rateLimiter.acquire('test-source');
      }

      const statusBefore = await rateLimiter.getStatus('test-source');
      expect(statusBefore.remaining).toBe(990);

      // Advance time to just before reset
      jest.advanceTimersByTime(3599999); // 1ms before 1 hour

      const statusAlmostReset = await rateLimiter.getStatus('test-source');
      expect(statusAlmostReset.remaining).toBe(990); // Should still be the same

      // Advance time past reset boundary
      jest.advanceTimersByTime(2); // 1ms past 1 hour

      // Make a request to trigger reset check
      await rateLimiter.acquire('test-source');

      const statusAfterReset = await rateLimiter.getStatus('test-source');
      expect(statusAfterReset.remaining).toBe(999); // Should be reset minus 1
    });

    it('should handle multiple resets correctly', async () => {
      // Initial requests
      for (let i = 0; i < 5; i++) {
        await rateLimiter.acquire('test-source');
      }

      expect((await rateLimiter.getStatus('test-source')).remaining).toBe(995);

      // First reset
      jest.advanceTimersByTime(3600001);
      await rateLimiter.acquire('test-source');
      expect((await rateLimiter.getStatus('test-source')).remaining).toBe(999);

      // More requests
      for (let i = 0; i < 3; i++) {
        await rateLimiter.acquire('test-source');
      }
      expect((await rateLimiter.getStatus('test-source')).remaining).toBe(996);

      // Second reset
      jest.advanceTimersByTime(3600001);
      await rateLimiter.acquire('test-source');
      expect((await rateLimiter.getStatus('test-source')).remaining).toBe(999);
    });

    it('should handle rapid consecutive resets', async () => {
      for (let resetCycle = 0; resetCycle < 5; resetCycle++) {
        // Make some requests
        for (let i = 0; i < 2; i++) {
          await rateLimiter.acquire('test-source');
        }

        // Advance time past reset
        jest.advanceTimersByTime(3600001);

        // Verify reset occurred
        const status = await rateLimiter.getStatus('test-source');
        expect(status.remaining).toBe(1000);
      }
    });
  });

  describe('Configuration Edge Cases', () => {
    it('should handle zero and negative limits gracefully', async () => {
      const edgeLimiter = new TokenBucketRateLimiter({
        limits: {
          'zero-limit': {
            requestsPerSecond: 0,
            requestsPerMinute: 0,
            requestsPerHour: 0
          },
          'negative-limit': {
            requestsPerSecond: -1,
            requestsPerMinute: -10,
            requestsPerHour: -100
          }
        }
      });

      // Should still work (implementation should handle edge cases)
      await edgeLimiter.acquire('zero-limit');
      await edgeLimiter.acquire('negative-limit');

      const zeroStatus = await edgeLimiter.getStatus('zero-limit');
      const negativeStatus = await edgeLimiter.getStatus('negative-limit');

      expect(zeroStatus.remaining).toBeGreaterThanOrEqual(0);
      expect(negativeStatus.remaining).toBeGreaterThanOrEqual(0);
    });

    it('should handle extremely large limits', async () => {
      const largeLimiter = new TokenBucketRateLimiter({
        limits: {
          'huge-limit': {
            requestsPerSecond: Number.MAX_SAFE_INTEGER,
            requestsPerMinute: Number.MAX_SAFE_INTEGER,
            requestsPerHour: Number.MAX_SAFE_INTEGER
          }
        }
      });

      // Should handle large numbers without overflow
      await largeLimiter.acquire('huge-limit');
      const status = await largeLimiter.getStatus('huge-limit');

      expect(status.remaining).toBeGreaterThan(0);
      expect(isFinite(status.remaining)).toBe(true);
    });

    it('should handle inconsistent time-based limits', async () => {
      // Configuration where smaller time units have higher limits (unrealistic but possible)
      const inconsistentLimiter = new TokenBucketRateLimiter({
        limits: {
          'inconsistent': {
            requestsPerSecond: 100,   // 100/sec = 6000/min = 360000/hour
            requestsPerMinute: 50,    // 50/min = 0.83/sec = 3000/hour
            requestsPerHour: 10       // 10/hour = 0.17/min = 0.003/sec
          }
        }
      });

      // Should use the most restrictive limit (10/hour = 0.003/sec)
      await inconsistentLimiter.acquire('inconsistent');
      const status = await inconsistentLimiter.getStatus('inconsistent');

      expect(status.remaining).toBeLessThan(100); // Should use hour limit, not second limit
    });
  });

  describe('Memory and Resource Management', () => {
    it('should handle creation of many dynamic sources', async () => {
      const sourceCount = 1000;
      const promises = [];

      // Create many unique sources dynamically
      for (let i = 0; i < sourceCount; i++) {
        promises.push(rateLimiter.acquire(`dynamic-source-${i}`));
      }

      await Promise.all(promises);

      // Verify all sources were created and tracked
      for (let i = 0; i < sourceCount; i++) {
        const status = await rateLimiter.getStatus(`dynamic-source-${i}`);
        expect(status.remaining).toBeLessThan(1000);
      }
    });

    it('should handle cleanup of unused sources', async () => {
      // Create temporary sources
      const tempSources = ['temp-1', 'temp-2', 'temp-3'];
      
      for (const source of tempSources) {
        await rateLimiter.acquire(source);
      }

      // Verify sources exist
      for (const source of tempSources) {
        const status = await rateLimiter.getStatus(source);
        expect(status.remaining).toBeLessThan(1000);
      }

      // Reset sources
      for (const source of tempSources) {
        rateLimiter.reset(source);
      }

      // Verify sources are reset
      for (const source of tempSources) {
        const status = await rateLimiter.getStatus(source);
        expect(status.remaining).toBe(1000);
      }
    });

    it('should handle stress test with rapid source creation and destruction', async () => {
      const cycles = 100;
      const sourcesPerCycle = 10;

      for (let cycle = 0; cycle < cycles; cycle++) {
        const sources = [];
        
        // Create sources
        for (let i = 0; i < sourcesPerCycle; i++) {
          const source = `stress-${cycle}-${i}`;
          sources.push(source);
          await rateLimiter.acquire(source);
        }

        // Use sources
        for (const source of sources) {
          await rateLimiter.acquire(source);
          const status = await rateLimiter.getStatus(source);
          expect(status.remaining).toBeLessThan(1000);
        }

        // Reset sources
        for (const source of sources) {
          rateLimiter.reset(source);
        }
      }

      // System should still be responsive
      await rateLimiter.acquire('final-test');
      const finalStatus = await rateLimiter.getStatus('final-test');
      expect(finalStatus.remaining).toBe(999);
    });
  });

  describe('Error Handling Edge Cases', () => {
    it('should handle reset of non-existent sources gracefully', () => {
      // Should not throw errors
      expect(() => rateLimiter.reset('non-existent-source')).not.toThrow();
      expect(() => rateLimiter.reset('')).not.toThrow();
      expect(() => rateLimiter.reset(null as any)).not.toThrow();
      expect(() => rateLimiter.reset(undefined as any)).not.toThrow();
    });

    it('should handle status queries for non-existent sources', async () => {
      const status = await rateLimiter.getStatus('non-existent-source');
      
      expect(status).toHaveProperty('remaining');
      expect(status).toHaveProperty('reset');
      expect(status.remaining).toBe(0); // Should indicate no capacity
      expect(status.reset).toBeInstanceOf(Date);
    });

    it('should handle malformed source names', async () => {
      const malformedSources = [
        '',
        ' ',
        '\n',
        '\t',
        'source with spaces',
        'source-with-émojis-🚀',
        'very-long-source-name-that-exceeds-normal-expectations-and-contains-many-characters',
        '123-numeric-start',
        'special!@#$%^&*()chars'
      ];

      for (const source of malformedSources) {
        // Should handle without throwing
        await rateLimiter.acquire(source);
        const status = await rateLimiter.getStatus(source);
        
        expect(status.remaining).toBeGreaterThanOrEqual(0);
        expect(status.reset).toBeInstanceOf(Date);
      }
    });
  });

  describe('Performance Under Edge Conditions', () => {
    it('should maintain performance with extreme concurrency', async () => {
      const extremeConcurrency = 500;
      const startTime = Date.now();

      const promises = [];
      for (let i = 0; i < extremeConcurrency; i++) {
        promises.push(rateLimiter.acquire('extreme-test'));
      }

      await Promise.all(promises);
      const duration = Date.now() - startTime;

      // Should complete within reasonable time even with extreme concurrency
      expect(duration).toBeLessThan(5000); // 5 seconds max

      const finalStatus = await rateLimiter.getStatus('extreme-test');
      expect(finalStatus.remaining).toBe(1000 - extremeConcurrency);
    });

    it('should handle repeated acquire/reset cycles efficiently', async () => {
      const cycles = 100;
      const startTime = Date.now();

      for (let i = 0; i < cycles; i++) {
        await rateLimiter.acquire('cycle-test');
        rateLimiter.reset('cycle-test');
      }

      const duration = Date.now() - startTime;

      // Should be efficient even with many cycles
      expect(duration).toBeLessThan(1000); // 1 second max

      const finalStatus = await rateLimiter.getStatus('cycle-test');
      expect(finalStatus.remaining).toBe(1000); // Should be reset
    });
  });
});