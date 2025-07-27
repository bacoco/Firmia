import { TokenBucketRateLimiter, createRateLimiter } from '../../src/rate-limiter';
import pLimit from 'p-limit';

// Mock p-limit
jest.mock('p-limit');
const mockedPLimit = pLimit as jest.MockedFunction<typeof pLimit>;

describe('TokenBucketRateLimiter', () => {
  let rateLimiter: TokenBucketRateLimiter;
  let mockLimiter: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    
    // Create a mock limiter function
    mockLimiter = jest.fn(async (fn: () => Promise<void>) => {
      await fn();
    });
    
    mockedPLimit.mockReturnValue(mockLimiter);
    
    rateLimiter = new TokenBucketRateLimiter();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('constructor', () => {
    it('should initialize with default configuration', () => {
      expect(mockedPLimit).toHaveBeenCalledTimes(3); // insee, banque-france, inpi
      
      // Default rate limit for each source should be 10 requests per second
      expect(mockedPLimit).toHaveBeenCalledWith(10);
    });

    it('should initialize with custom configuration', () => {
      const customConfig = {
        limits: {
          insee: {
            requestsPerSecond: 30,
            requestsPerMinute: 500,
            requestsPerHour: 5000
          },
          'custom-source': {
            requestsPerSecond: 5,
            requestsPerMinute: 50,
            requestsPerHour: 500
          }
        },
        defaultLimit: {
          requestsPerSecond: 15,
          requestsPerMinute: 150,
          requestsPerHour: 1500
        }
      };

      rateLimiter = new TokenBucketRateLimiter(customConfig);

      // Should initialize insee with 30 req/s (most restrictive between 30, 500/60=8.33, 5000/3600=1.39)
      // Should initialize custom-source with 5 req/s
      // Should initialize banque-france and inpi with default 15 req/s
      expect(mockedPLimit).toHaveBeenCalledWith(30); // insee
      expect(mockedPLimit).toHaveBeenCalledWith(5);  // custom-source
      expect(mockedPLimit).toHaveBeenCalledWith(15); // defaults
    });

    it('should calculate the most restrictive limit', () => {
      const config = {
        limits: {
          'test-source': {
            requestsPerSecond: 100,    // 100 req/s
            requestsPerMinute: 300,    // 5 req/s (more restrictive)
            requestsPerHour: 10800     // 3 req/s (most restrictive)
          }
        }
      };

      rateLimiter = new TokenBucketRateLimiter(config);

      // Should use 3 req/s as it's the most restrictive
      expect(mockedPLimit).toHaveBeenCalledWith(3);
    });
  });

  describe('acquire', () => {
    it('should acquire a rate limit slot for known source', async () => {
      await rateLimiter.acquire('insee');

      expect(mockLimiter).toHaveBeenCalled();
      
      // The function passed to limiter should include a delay
      const limiterFunction = mockLimiter.mock.calls[0][0];
      const setTimeoutSpy = jest.spyOn(global, 'setTimeout');
      
      await limiterFunction();
      
      expect(setTimeoutSpy).toHaveBeenCalledWith(expect.any(Function), 100);
    });

    it('should initialize limiter for unknown source', async () => {
      // Clear previous calls
      mockedPLimit.mockClear();
      
      await rateLimiter.acquire('new-source');

      // Should have initialized a new limiter
      expect(mockedPLimit).toHaveBeenCalledWith(10); // default limit
      expect(mockLimiter).toHaveBeenCalled();
    });

    it('should increment counter on acquire', async () => {
      const status1 = await rateLimiter.getStatus('insee');
      const remaining1 = status1.remaining;

      await rateLimiter.acquire('insee');
      
      // Execute the limiter function to increment counter
      await mockLimiter.mock.calls[0][0]();

      const status2 = await rateLimiter.getStatus('insee');
      expect(status2.remaining).toBe(remaining1 - 1);
    });

    it('should handle multiple consecutive acquires', async () => {
      const promises = [];
      
      for (let i = 0; i < 5; i++) {
        promises.push(rateLimiter.acquire('insee'));
      }

      await Promise.all(promises);

      expect(mockLimiter).toHaveBeenCalledTimes(5);
    });

    it('should reset counter after time window', async () => {
      // Acquire some slots
      await rateLimiter.acquire('insee');
      await mockLimiter.mock.calls[0][0]();

      // Check current status
      const statusBefore = await rateLimiter.getStatus('insee');
      expect(statusBefore.remaining).toBeLessThan(1000); // Default hour limit

      // Advance time by more than 1 hour
      jest.advanceTimersByTime(3600001);

      // Acquire another slot
      await rateLimiter.acquire('insee');
      await mockLimiter.mock.calls[1][0]();

      // Counter should have been reset
      const statusAfter = await rateLimiter.getStatus('insee');
      expect(statusAfter.remaining).toBe(999); // 1000 - 1
    });
  });

  describe('getStatus', () => {
    it('should return status for known source', async () => {
      const status = await rateLimiter.getStatus('insee');

      expect(status).toHaveProperty('remaining');
      expect(status).toHaveProperty('reset');
      expect(status.remaining).toBe(1000); // Default hour limit
      expect(status.reset).toBeInstanceOf(Date);
      expect(status.reset.getTime()).toBeGreaterThan(Date.now());
    });

    it('should return zero remaining for unknown source', async () => {
      const status = await rateLimiter.getStatus('unknown-source');

      expect(status.remaining).toBe(0);
      expect(status.reset).toBeInstanceOf(Date);
    });

    it('should calculate remaining correctly based on usage', async () => {
      // Make some requests
      for (let i = 0; i < 10; i++) {
        await rateLimiter.acquire('insee');
        await mockLimiter.mock.calls[i][0]();
      }

      const status = await rateLimiter.getStatus('insee');
      expect(status.remaining).toBe(990); // 1000 - 10
    });

    it('should use custom limits for calculation', async () => {
      const customConfig = {
        limits: {
          'test-source': {
            requestsPerSecond: 10,
            requestsPerHour: 500 // Custom hour limit
          }
        }
      };

      rateLimiter = new TokenBucketRateLimiter(customConfig);
      
      const status = await rateLimiter.getStatus('test-source');
      expect(status.remaining).toBe(500);
    });

    it('should never return negative remaining', async () => {
      // Make many requests
      for (let i = 0; i < 1100; i++) {
        await rateLimiter.acquire('insee');
        await mockLimiter.mock.calls[i][0]();
      }

      const status = await rateLimiter.getStatus('insee');
      expect(status.remaining).toBe(0);
    });
  });

  describe('reset', () => {
    it('should reset counter for source', async () => {
      // Make some requests
      for (let i = 0; i < 5; i++) {
        await rateLimiter.acquire('insee');
        await mockLimiter.mock.calls[i][0]();
      }

      // Check status before reset
      const statusBefore = await rateLimiter.getStatus('insee');
      expect(statusBefore.remaining).toBe(995);

      // Reset the counter
      rateLimiter.reset('insee');

      // Check status after reset
      const statusAfter = await rateLimiter.getStatus('insee');
      expect(statusAfter.remaining).toBe(1000);
    });

    it('should update reset time', async () => {
      const statusBefore = await rateLimiter.getStatus('insee');
      const resetTimeBefore = statusBefore.reset.getTime();

      // Advance time
      jest.advanceTimersByTime(60000); // 1 minute

      // Reset the counter
      rateLimiter.reset('insee');

      const statusAfter = await rateLimiter.getStatus('insee');
      const resetTimeAfter = statusAfter.reset.getTime();

      expect(resetTimeAfter).toBeGreaterThan(resetTimeBefore);
    });

    it('should handle reset for non-existent source gracefully', () => {
      // Should not throw
      expect(() => rateLimiter.reset('unknown-source')).not.toThrow();
    });
  });
});

describe('createRateLimiter', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedPLimit.mockReturnValue(jest.fn());
  });

  it('should create rate limiter with default configuration', () => {
    const limiter = createRateLimiter();

    expect(limiter).toBeDefined();
    expect(limiter).toHaveProperty('acquire');
    expect(limiter).toHaveProperty('getStatus');
    expect(limiter).toHaveProperty('reset');

    // Should have initialized with predefined limits
    expect(mockedPLimit).toHaveBeenCalledWith(30); // insee
    expect(mockedPLimit).toHaveBeenCalledWith(10); // banque-france
    expect(mockedPLimit).toHaveBeenCalledWith(20); // inpi
  });

  it('should create rate limiter with custom configuration', () => {
    const customConfig = {
      limits: {
        'custom-api': {
          requestsPerSecond: 50,
          requestsPerMinute: 1000,
          requestsPerHour: 10000
        }
      },
      defaultLimit: {
        requestsPerSecond: 25,
        requestsPerMinute: 500,
        requestsPerHour: 5000
      }
    };

    const limiter = createRateLimiter(customConfig);

    expect(limiter).toBeDefined();
    // Custom config should override defaults
    expect(mockedPLimit).toHaveBeenCalledWith(50); // custom-api
  });
});

describe('Rate Limiter Integration Tests', () => {
  let rateLimiter: TokenBucketRateLimiter;
  let actualDelay: number = 0;

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useRealTimers(); // Use real timers for integration tests
    
    // Track actual delays
    actualDelay = 0;
    
    // Create a more realistic mock that simulates actual rate limiting
    mockedPLimit.mockImplementation((limit: number) => {
      let activeCount = 0;
      const queue: Array<() => void> = [];

      return async (fn: () => Promise<void>) => {
        if (activeCount >= limit) {
          // Wait for a slot to become available
          await new Promise<void>(resolve => {
            queue.push(resolve);
          });
        }

        activeCount++;
        
        try {
          await fn();
        } finally {
          activeCount--;
          
          // Release next item in queue if any
          if (queue.length > 0) {
            const next = queue.shift();
            if (next) next();
          }
        }
      };
    });

    rateLimiter = new TokenBucketRateLimiter({
      limits: {
        'test-api': {
          requestsPerSecond: 2 // Low limit for testing
        }
      }
    });
  });

  it('should enforce rate limits under load', async () => {
    const startTime = Date.now();
    const requests = 5; // 5 requests at 2 req/s should take ~2.5s
    const promises = [];

    for (let i = 0; i < requests; i++) {
      promises.push(
        rateLimiter.acquire('test-api').then(async () => {
          // Simulate API call
          await new Promise(resolve => setTimeout(resolve, 10));
        })
      );
    }

    await Promise.all(promises);

    const duration = Date.now() - startTime;
    
    // With rate limiting, this should take more time than without
    expect(duration).toBeGreaterThan(10 * requests); // At least the sum of simulated delays
  });

  it('should handle concurrent requests from multiple sources', async () => {
    const sources = ['insee', 'banque-france', 'inpi'];
    const requestsPerSource = 3;
    const promises = [];

    for (const source of sources) {
      for (let i = 0; i < requestsPerSource; i++) {
        promises.push(
          rateLimiter.acquire(source).then(async () => {
            // Track which source is making the request
            return source;
          })
        );
      }
    }

    const results = await Promise.all(promises);

    // All requests should complete
    expect(results).toHaveLength(sources.length * requestsPerSource);
    
    // Each source should have made the correct number of requests
    for (const source of sources) {
      const sourceRequests = results.filter(s => s === source);
      expect(sourceRequests).toHaveLength(requestsPerSource);
    }
  });

  it('should maintain independent limits for each source', async () => {
    // Configure different limits
    rateLimiter = new TokenBucketRateLimiter({
      limits: {
        'fast-api': {
          requestsPerSecond: 10
        },
        'slow-api': {
          requestsPerSecond: 1
        }
      }
    });

    const startTime = Date.now();
    
    // Make requests to both APIs
    await Promise.all([
      rateLimiter.acquire('fast-api'),
      rateLimiter.acquire('fast-api'),
      rateLimiter.acquire('slow-api'),
      rateLimiter.acquire('slow-api')
    ]);

    const duration = Date.now() - startTime;

    // The slow API should constrain the overall time
    // But fast API requests shouldn't be slowed down by slow API
    expect(duration).toBeLessThan(2000); // Should complete reasonably quickly
  });
});