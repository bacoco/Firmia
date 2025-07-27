import NodeCache from "node-cache";

export interface Cache {
  get(key: string): Promise<unknown>;
  set(key: string, value: unknown, ttl?: number): Promise<void>;
  delete(key: string): Promise<void>;
  flush(): Promise<void>;
  getStats(): CacheStats;
}

export interface CacheStats {
  hits: number;
  misses: number;
  keys: number;
  ksize: number;
  vsize: number;
}

export class MemoryCache implements Cache {
  private cache: NodeCache;

  constructor(options?: NodeCache.Options) {
    this.cache = new NodeCache({
      stdTTL: 3600, // Default TTL: 1 hour
      checkperiod: 600, // Check for expired keys every 10 minutes
      useClones: false, // Don't clone objects for better performance
      ...options
    });
  }

  async get(key: string): Promise<unknown> {
    return this.cache.get(key);
  }

  async set(key: string, value: unknown, ttl?: number): Promise<void> {
    if (ttl !== undefined) {
      this.cache.set(key, value, ttl);
    } else {
      this.cache.set(key, value);
    }
  }

  async delete(key: string): Promise<void> {
    this.cache.del(key);
  }

  async flush(): Promise<void> {
    this.cache.flushAll();
  }

  getStats(): CacheStats {
    const stats = this.cache.getStats();
    return {
      hits: stats.hits,
      misses: stats.misses,
      keys: stats.keys,
      ksize: stats.ksize,
      vsize: stats.vsize
    };
  }
}

export function createCache(options?: NodeCache.Options): Cache {
  return new MemoryCache(options);
}