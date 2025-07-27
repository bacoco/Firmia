import { MemoryCache, createCache } from '../../src/cache';
import NodeCache from 'node-cache';

// Mock NodeCache
jest.mock('node-cache');
const MockedNodeCache = NodeCache as jest.MockedClass<typeof NodeCache>;

describe('MemoryCache', () => {
  let cache: MemoryCache;
  let mockNodeCacheInstance: any;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Create a mock instance with all methods
    mockNodeCacheInstance = {
      get: jest.fn(),
      set: jest.fn(),
      del: jest.fn(),
      flushAll: jest.fn(),
      getStats: jest.fn(() => ({
        hits: 10,
        misses: 5,
        keys: 3,
        ksize: 100,
        vsize: 500
      }))
    };

    // Make NodeCache constructor return our mock instance
    MockedNodeCache.mockImplementation(() => mockNodeCacheInstance);
    
    cache = new MemoryCache();
  });

  describe('constructor', () => {
    it('should initialize with default options', () => {
      expect(MockedNodeCache).toHaveBeenCalledWith({
        stdTTL: 3600,
        checkperiod: 600,
        useClones: false
      });
    });

    it('should initialize with custom options', () => {
      const customOptions = {
        stdTTL: 7200,
        checkperiod: 300,
        maxKeys: 1000
      };

      new MemoryCache(customOptions);

      expect(MockedNodeCache).toHaveBeenCalledWith({
        stdTTL: 7200,
        checkperiod: 300,
        useClones: false,
        maxKeys: 1000
      });
    });
  });

  describe('get', () => {
    it('should retrieve value from cache', async () => {
      const testValue = { data: 'test data' };
      mockNodeCacheInstance.get.mockReturnValue(testValue);

      const result = await cache.get('test-key');

      expect(mockNodeCacheInstance.get).toHaveBeenCalledWith('test-key');
      expect(result).toEqual(testValue);
    });

    it('should return undefined for non-existent key', async () => {
      mockNodeCacheInstance.get.mockReturnValue(undefined);

      const result = await cache.get('non-existent');

      expect(result).toBeUndefined();
    });

    it('should handle different data types', async () => {
      const testCases = [
        { key: 'string', value: 'test string' },
        { key: 'number', value: 12345 },
        { key: 'boolean', value: true },
        { key: 'array', value: [1, 2, 3] },
        { key: 'object', value: { name: 'test', id: 1 } },
        { key: 'null', value: null }
      ];

      for (const testCase of testCases) {
        mockNodeCacheInstance.get.mockReturnValue(testCase.value);
        
        const result = await cache.get(testCase.key);
        
        expect(result).toEqual(testCase.value);
      }
    });
  });

  describe('set', () => {
    it('should store value in cache with default TTL', async () => {
      const testValue = { data: 'test data' };

      await cache.set('test-key', testValue);

      expect(mockNodeCacheInstance.set).toHaveBeenCalledWith('test-key', testValue, undefined);
    });

    it('should store value with custom TTL', async () => {
      const testValue = { data: 'test data' };
      const customTTL = 7200; // 2 hours

      await cache.set('test-key', testValue, customTTL);

      expect(mockNodeCacheInstance.set).toHaveBeenCalledWith('test-key', testValue, customTTL);
    });

    it('should handle different data types', async () => {
      const testCases = [
        { key: 'string', value: 'test string' },
        { key: 'number', value: 12345 },
        { key: 'boolean', value: true },
        { key: 'array', value: [1, 2, 3] },
        { key: 'object', value: { name: 'test', id: 1 } },
        { key: 'null', value: null },
        { key: 'undefined', value: undefined }
      ];

      for (const testCase of testCases) {
        await cache.set(testCase.key, testCase.value);
        
        expect(mockNodeCacheInstance.set).toHaveBeenCalledWith(
          testCase.key,
          testCase.value,
          undefined
        );
      }
    });

    it('should overwrite existing values', async () => {
      await cache.set('existing-key', 'original value');
      await cache.set('existing-key', 'new value');

      expect(mockNodeCacheInstance.set).toHaveBeenCalledTimes(2);
      expect(mockNodeCacheInstance.set).toHaveBeenLastCalledWith(
        'existing-key',
        'new value',
        undefined
      );
    });
  });

  describe('delete', () => {
    it('should delete key from cache', async () => {
      await cache.delete('test-key');

      expect(mockNodeCacheInstance.del).toHaveBeenCalledWith('test-key');
    });

    it('should handle deletion of non-existent key', async () => {
      mockNodeCacheInstance.del.mockReturnValue(0);

      await cache.delete('non-existent');

      expect(mockNodeCacheInstance.del).toHaveBeenCalledWith('non-existent');
    });

    it('should handle multiple deletions', async () => {
      const keys = ['key1', 'key2', 'key3'];

      for (const key of keys) {
        await cache.delete(key);
      }

      expect(mockNodeCacheInstance.del).toHaveBeenCalledTimes(3);
      keys.forEach(key => {
        expect(mockNodeCacheInstance.del).toHaveBeenCalledWith(key);
      });
    });
  });

  describe('flush', () => {
    it('should clear all cache entries', async () => {
      await cache.flush();

      expect(mockNodeCacheInstance.flushAll).toHaveBeenCalled();
    });

    it('should handle multiple flush calls', async () => {
      await cache.flush();
      await cache.flush();

      expect(mockNodeCacheInstance.flushAll).toHaveBeenCalledTimes(2);
    });
  });

  describe('getStats', () => {
    it('should return cache statistics', () => {
      const stats = cache.getStats();

      expect(mockNodeCacheInstance.getStats).toHaveBeenCalled();
      expect(stats).toEqual({
        hits: 10,
        misses: 5,
        keys: 3,
        ksize: 100,
        vsize: 500
      });
    });

    it('should return updated statistics', () => {
      // First call
      cache.getStats();

      // Update mock to return different stats
      mockNodeCacheInstance.getStats.mockReturnValue({
        hits: 20,
        misses: 8,
        keys: 5,
        ksize: 200,
        vsize: 800
      });

      // Second call
      const updatedStats = cache.getStats();

      expect(updatedStats).toEqual({
        hits: 20,
        misses: 8,
        keys: 5,
        ksize: 200,
        vsize: 800
      });
    });

    it('should handle zero statistics', () => {
      mockNodeCacheInstance.getStats.mockReturnValue({
        hits: 0,
        misses: 0,
        keys: 0,
        ksize: 0,
        vsize: 0
      });

      const stats = cache.getStats();

      expect(stats).toEqual({
        hits: 0,
        misses: 0,
        keys: 0,
        ksize: 0,
        vsize: 0
      });
    });
  });
});

describe('createCache', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    MockedNodeCache.mockImplementation(() => ({
      get: jest.fn(),
      set: jest.fn(),
      del: jest.fn(),
      flushAll: jest.fn(),
      getStats: jest.fn(() => ({
        hits: 0,
        misses: 0,
        keys: 0,
        ksize: 0,
        vsize: 0
      }))
    }));
  });

  it('should create a cache instance with default options', () => {
    const cache = createCache();

    expect(cache).toBeDefined();
    expect(cache).toHaveProperty('get');
    expect(cache).toHaveProperty('set');
    expect(cache).toHaveProperty('delete');
    expect(cache).toHaveProperty('flush');
    expect(cache).toHaveProperty('getStats');
  });

  it('should create a cache instance with custom options', () => {
    const customOptions = {
      stdTTL: 1800,
      checkperiod: 120,
      errorOnMissing: true
    };

    const cache = createCache(customOptions);

    expect(MockedNodeCache).toHaveBeenCalledWith({
      stdTTL: 1800,
      checkperiod: 120,
      useClones: false,
      errorOnMissing: true
    });
    expect(cache).toBeDefined();
  });

  it('should create independent cache instances', () => {
    const cache1 = createCache();
    const cache2 = createCache();

    expect(cache1).not.toBe(cache2);
    expect(MockedNodeCache).toHaveBeenCalledTimes(2);
  });
});

describe('Cache Integration Tests', () => {
  let cache: MemoryCache;
  let mockNodeCacheInstance: any;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Create a more realistic mock that simulates actual caching behavior
    const storage = new Map<string, { value: any; ttl?: number; expires?: number }>();
    
    mockNodeCacheInstance = {
      get: jest.fn((key: string) => {
        const item = storage.get(key);
        if (!item) return undefined;
        if (item.expires && Date.now() > item.expires) {
          storage.delete(key);
          return undefined;
        }
        return item.value;
      }),
      set: jest.fn((key: string, value: any, ttl?: number) => {
        const item: any = { value };
        if (ttl) {
          item.ttl = ttl;
          item.expires = Date.now() + (ttl * 1000);
        }
        storage.set(key, item);
        return true;
      }),
      del: jest.fn((key: string) => {
        const deleted = storage.delete(key);
        return deleted ? 1 : 0;
      }),
      flushAll: jest.fn(() => {
        storage.clear();
      }),
      getStats: jest.fn(() => ({
        hits: 0,
        misses: 0,
        keys: storage.size,
        ksize: 0,
        vsize: 0
      }))
    };

    MockedNodeCache.mockImplementation(() => mockNodeCacheInstance);
    cache = new MemoryCache();
  });

  it('should handle cache workflow correctly', async () => {
    // Set a value
    await cache.set('workflow-key', { step: 1, data: 'initial' });

    // Get the value
    const value1 = await cache.get('workflow-key');
    expect(value1).toEqual({ step: 1, data: 'initial' });

    // Update the value
    await cache.set('workflow-key', { step: 2, data: 'updated' });

    // Get updated value
    const value2 = await cache.get('workflow-key');
    expect(value2).toEqual({ step: 2, data: 'updated' });

    // Check stats
    const stats = cache.getStats();
    expect(stats.keys).toBe(1);

    // Delete the value
    await cache.delete('workflow-key');

    // Verify deletion
    const value3 = await cache.get('workflow-key');
    expect(value3).toBeUndefined();

    // Check stats after deletion
    const statsAfterDelete = cache.getStats();
    expect(statsAfterDelete.keys).toBe(0);
  });

  it('should handle multiple keys independently', async () => {
    const testData = [
      { key: 'user:123', value: { name: 'John', role: 'admin' } },
      { key: 'user:456', value: { name: 'Jane', role: 'user' } },
      { key: 'config:app', value: { theme: 'dark', lang: 'en' } }
    ];

    // Set all values
    for (const item of testData) {
      await cache.set(item.key, item.value);
    }

    // Verify all values
    for (const item of testData) {
      const value = await cache.get(item.key);
      expect(value).toEqual(item.value);
    }

    // Delete one key
    await cache.delete('user:123');

    // Verify deletion doesn't affect other keys
    expect(await cache.get('user:123')).toBeUndefined();
    expect(await cache.get('user:456')).toEqual(testData[1].value);
    expect(await cache.get('config:app')).toEqual(testData[2].value);

    // Flush all
    await cache.flush();

    // Verify all keys are gone
    for (const item of testData) {
      expect(await cache.get(item.key)).toBeUndefined();
    }
  });
});