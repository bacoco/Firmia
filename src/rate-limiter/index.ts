import pLimit from "p-limit";

export interface RateLimiter {
  acquire(source: string): Promise<void>;
  getStatus(source: string): Promise<RateLimitStatus>;
  reset(source: string): void;
}

export interface RateLimitStatus {
  remaining: number;
  reset: Date;
}

export interface RateLimiterConfig {
  limits?: Record<string, RateLimitConfig>;
  defaultLimit?: RateLimitConfig;
}

export interface RateLimitConfig {
  requestsPerSecond: number;
  requestsPerMinute?: number;
  requestsPerHour?: number;
}

export class TokenBucketRateLimiter implements RateLimiter {
  private limiters: Map<string, ReturnType<typeof pLimit>>;
  private counters: Map<string, { count: number; resetTime: Date }>;
  private config: RateLimiterConfig;

  constructor(config?: RateLimiterConfig) {
    this.config = config || {};
    this.limiters = new Map();
    this.counters = new Map();
    
    // Initialize limiters for known sources
    const sources = ["insee", "banque-france", "inpi"];
    sources.forEach(source => this.initializeLimiter(source));
  }

  private initializeLimiter(source: string): void {
    const config = this.config.limits?.[source] || this.config.defaultLimit || {
      requestsPerSecond: 10,
      requestsPerMinute: 100,
      requestsPerHour: 1000
    };
    
    // Use the most restrictive limit
    const limit = Math.min(
      config.requestsPerSecond,
      (config.requestsPerMinute || Infinity) / 60,
      (config.requestsPerHour || Infinity) / 3600
    );
    
    this.limiters.set(source, pLimit(Math.max(1, Math.floor(limit))));
    this.counters.set(source, {
      count: 0,
      resetTime: new Date(Date.now() + 3600000) // Reset in 1 hour
    });
  }

  async acquire(source: string): Promise<void> {
    if (!this.limiters.has(source)) {
      this.initializeLimiter(source);
    }
    
    const limiter = this.limiters.get(source)!;
    const counter = this.counters.get(source)!;
    
    // Check if we need to reset the counter
    if (new Date() > counter.resetTime) {
      counter.count = 0;
      counter.resetTime = new Date(Date.now() + 3600000);
    }
    
    // Acquire a slot
    await limiter(async () => {
      counter.count++;
      // Small delay to respect rate limits
      await new Promise(resolve => setTimeout(resolve, 100));
    });
  }

  async getStatus(source: string): Promise<RateLimitStatus> {
    const counter = this.counters.get(source);
    if (!counter) {
      return {
        remaining: 0,
        reset: new Date()
      };
    }
    
    const config = this.config.limits?.[source] || this.config.defaultLimit || {
      requestsPerHour: 1000
    };
    
    const limit = config.requestsPerHour || 1000;
    const remaining = Math.max(0, limit - counter.count);
    
    return {
      remaining,
      reset: counter.resetTime
    };
  }

  reset(source: string): void {
    const counter = this.counters.get(source);
    if (counter) {
      counter.count = 0;
      counter.resetTime = new Date(Date.now() + 3600000);
    }
  }
}

export function createRateLimiter(config?: RateLimiterConfig): RateLimiter {
  return new TokenBucketRateLimiter(config || {
    limits: {
      insee: {
        requestsPerSecond: 30,
        requestsPerMinute: 500,
        requestsPerHour: 5000
      },
      "banque-france": {
        requestsPerSecond: 10,
        requestsPerMinute: 100,
        requestsPerHour: 1000
      },
      inpi: {
        requestsPerSecond: 20,
        requestsPerMinute: 200,
        requestsPerHour: 2000
      }
    },
    defaultLimit: {
      requestsPerSecond: 10,
      requestsPerMinute: 100,
      requestsPerHour: 1000
    }
  });
}