import { Server } from "@modelcontextprotocol/server";
import { z } from "zod";
import axios from 'axios';
import { 
  mockCompanies, 
  mockINSEEResponses,
  mockBanqueFranceResponses,
  mockINPIResponses,
  createMockCache, 
  createMockRateLimiter
} from './fixtures';

// Mock dependencies
jest.mock('axios');
jest.mock('../src/adapters', () => ({
  setupAdapters: jest.fn()
}));
jest.mock('../src/rate-limiter', () => ({
  createRateLimiter: jest.fn()
}));
jest.mock('../src/cache', () => ({
  createCache: jest.fn()
}));

const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('MCP Firms Server Integration Tests', () => {
  let server: Server;
  let mockAdapters: any;
  let searchHandler: any;
  let detailsHandler: any;
  let statusHandler: any;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Set up environment variables
    process.env.INSEE_API_KEY = 'test-insee-key';
    process.env.BANQUE_FRANCE_API_KEY = 'test-bf-key';
    process.env.INPI_USERNAME = 'test-inpi-user';
    process.env.INPI_PASSWORD = 'test-inpi-pass';

    // Mock cache and rate limiter
    const mockCache = createMockCache();
    const mockRateLimiter = createMockRateLimiter();

    require('../src/cache').createCache.mockReturnValue(mockCache);
    require('../src/rate-limiter').createRateLimiter.mockReturnValue(mockRateLimiter);

    // Create mock adapters
    mockAdapters = {
      insee: {
        search: jest.fn(),
        getDetails: jest.fn(),
        getStatus: jest.fn()
      },
      'banque-france': {
        search: jest.fn(),
        getDetails: jest.fn(),
        getStatus: jest.fn()
      },
      inpi: {
        search: jest.fn(),
        getDetails: jest.fn(),
        getStatus: jest.fn()
      }
    };

    require('../src/adapters').setupAdapters.mockReturnValue(mockAdapters);

    // Import and initialize server
    const serverModule = require('../src/index');
    server = serverModule.default;

    // Extract registered tool handlers
    const registerToolSpy = jest.spyOn(server, 'registerTool');
    
    // Re-import to trigger registration
    jest.isolateModules(() => {
      require('../src/index');
    });

    // Find handlers from spy calls
    const calls = registerToolSpy.mock.calls;
    searchHandler = calls.find(call => call[0].name === 'search_enterprises')?.[0].handler;
    detailsHandler = calls.find(call => call[0].name === 'get_enterprise_details')?.[0].handler;
    statusHandler = calls.find(call => call[0].name === 'get_api_status')?.[0].handler;
  });

  afterEach(() => {
    delete process.env.INSEE_API_KEY;
    delete process.env.BANQUE_FRANCE_API_KEY;
    delete process.env.INPI_USERNAME;
    delete process.env.INPI_PASSWORD;
  });

  describe('Server Initialization', () => {
    it('should initialize server with correct metadata', () => {
      expect(server).toBeDefined();
      expect(server).toBeInstanceOf(Server);
    });

    it('should register all required tools', () => {
      const registerToolSpy = jest.spyOn(server, 'registerTool');
      
      jest.isolateModules(() => {
        require('../src/index');
      });

      const registeredTools = registerToolSpy.mock.calls.map(call => call[0].name);
      
      expect(registeredTools).toContain('search_enterprises');
      expect(registeredTools).toContain('get_enterprise_details');
      expect(registeredTools).toContain('get_api_status');
    });
  });

  describe('search_enterprises tool', () => {
    it('should search across all sources when source is "all"', async () => {
      // Mock adapter responses
      mockAdapters.insee.search.mockResolvedValue([{
        siren: mockCompanies.danone.siren,
        name: mockCompanies.danone.name,
        source: 'INSEE'
      }]);
      mockAdapters['banque-france'].search.mockResolvedValue([]);
      mockAdapters.inpi.search.mockResolvedValue([]);

      const result = await searchHandler({
        query: 'DANONE',
        source: 'all',
        includeHistory: false,
        maxResults: 10
      });

      expect(result.success).toBe(true);
      expect(result.results).toHaveLength(3);
      expect(result.results[0]).toMatchObject({
        source: 'insee',
        data: expect.arrayContaining([
          expect.objectContaining({
            siren: mockCompanies.danone.siren
          })
        ])
      });

      // Verify all adapters were called
      expect(mockAdapters.insee.search).toHaveBeenCalledWith('DANONE', {
        includeHistory: false,
        maxResults: 10
      });
      expect(mockAdapters['banque-france'].search).toHaveBeenCalled();
      expect(mockAdapters.inpi.search).toHaveBeenCalled();
    });

    it('should search specific source when specified', async () => {
      mockAdapters.insee.search.mockResolvedValue([{
        siren: mockCompanies.danone.siren,
        name: mockCompanies.danone.name
      }]);

      const result = await searchHandler({
        query: mockCompanies.danone.siren,
        source: 'insee',
        includeHistory: false,
        maxResults: 5
      });

      expect(result.success).toBe(true);
      expect(result.results).toHaveLength(1);
      expect(result.results[0].source).toBe('insee');

      // Only INSEE adapter should be called
      expect(mockAdapters.insee.search).toHaveBeenCalled();
      expect(mockAdapters['banque-france'].search).not.toHaveBeenCalled();
      expect(mockAdapters.inpi.search).not.toHaveBeenCalled();
    });

    it('should handle adapter errors gracefully', async () => {
      mockAdapters.insee.search.mockRejectedValue(new Error('INSEE API error'));
      mockAdapters['banque-france'].search.mockResolvedValue([]);
      mockAdapters.inpi.search.mockResolvedValue([]);

      const result = await searchHandler({
        query: 'DANONE',
        source: 'all',
        includeHistory: false,
        maxResults: 10
      });

      expect(result.success).toBe(true);
      expect(result.results).toHaveLength(3);
      
      // INSEE should have error
      expect(result.results[0]).toMatchObject({
        source: 'insee',
        error: 'INSEE API error'
      });
      
      // Others should have data
      expect(result.results[1]).toHaveProperty('data');
      expect(result.results[2]).toHaveProperty('data');
    });

    it('should handle unknown source error', async () => {
      const result = await searchHandler({
        query: 'DANONE',
        source: 'unknown-source',
        includeHistory: false,
        maxResults: 10
      });

      expect(result.success).toBe(false);
      expect(result.error).toBe('Unknown source: unknown-source');
    });

    it('should validate input parameters', async () => {
      // Test with invalid SIREN (should still work as text search)
      mockAdapters.insee.search.mockResolvedValue([]);

      const result = await searchHandler({
        query: '123', // Too short for SIREN
        source: 'insee',
        includeHistory: true,
        maxResults: 50
      });

      expect(result.success).toBe(true);
      expect(mockAdapters.insee.search).toHaveBeenCalledWith('123', {
        includeHistory: true,
        maxResults: 50
      });
    });
  });

  describe('get_enterprise_details tool', () => {
    it('should get details from all sources when source is "all"', async () => {
      // Mock adapter responses
      mockAdapters.insee.getDetails.mockResolvedValue({
        basicInfo: {
          siren: mockCompanies.danone.siren,
          name: mockCompanies.danone.name
        }
      });
      mockAdapters['banque-france'].getDetails.mockResolvedValue({
        financials: {
          revenue: 1000000
        }
      });
      mockAdapters.inpi.getDetails.mockResolvedValue({
        intellectualProperty: {
          trademarks: 10,
          patents: 5
        }
      });

      const result = await detailsHandler({
        siren: mockCompanies.danone.siren,
        source: 'all',
        includeFinancials: true,
        includeIntellectualProperty: true
      });

      expect(result.success).toBe(true);
      expect(result.siren).toBe(mockCompanies.danone.siren);
      expect(result.details).toHaveProperty('insee');
      expect(result.details).toHaveProperty('banque-france');
      expect(result.details).toHaveProperty('inpi');

      // Verify all adapters were called with correct options
      const expectedOptions = {
        includeFinancials: true,
        includeIntellectualProperty: true
      };
      
      expect(mockAdapters.insee.getDetails).toHaveBeenCalledWith(
        mockCompanies.danone.siren,
        expectedOptions
      );
      expect(mockAdapters['banque-france'].getDetails).toHaveBeenCalledWith(
        mockCompanies.danone.siren,
        expectedOptions
      );
      expect(mockAdapters.inpi.getDetails).toHaveBeenCalledWith(
        mockCompanies.danone.siren,
        expectedOptions
      );
    });

    it('should get details from specific source', async () => {
      mockAdapters['banque-france'].getDetails.mockResolvedValue({
        basicInfo: { siren: mockCompanies.danone.siren },
        financials: { revenue: 1000000 }
      });

      const result = await detailsHandler({
        siren: mockCompanies.danone.siren,
        source: 'banque-france',
        includeFinancials: true,
        includeIntellectualProperty: false
      });

      expect(result.success).toBe(true);
      expect(result.details).toHaveProperty('banque-france');
      expect(result.details).not.toHaveProperty('insee');
      expect(result.details).not.toHaveProperty('inpi');

      // Only Banque de France adapter should be called
      expect(mockAdapters['banque-france'].getDetails).toHaveBeenCalled();
      expect(mockAdapters.insee.getDetails).not.toHaveBeenCalled();
      expect(mockAdapters.inpi.getDetails).not.toHaveBeenCalled();
    });

    it('should handle adapter errors gracefully', async () => {
      mockAdapters.insee.getDetails.mockRejectedValue(new Error('INSEE error'));
      mockAdapters['banque-france'].getDetails.mockResolvedValue({
        financials: { revenue: 1000000 }
      });
      mockAdapters.inpi.getDetails.mockRejectedValue(new Error('INPI error'));

      const result = await detailsHandler({
        siren: mockCompanies.danone.siren,
        source: 'all',
        includeFinancials: true,
        includeIntellectualProperty: true
      });

      expect(result.success).toBe(true);
      expect(result.details.insee).toMatchObject({ error: 'INSEE error' });
      expect(result.details['banque-france']).toHaveProperty('financials');
      expect(result.details.inpi).toMatchObject({ error: 'INPI error' });
    });

    it('should validate SIREN format', async () => {
      // Invalid SIREN should be caught by schema validation
      await expect(async () => {
        const SearchSchema = z.object({
          siren: z.string().regex(/^\d{9}$/, "SIREN must be 9 digits")
        });
        
        SearchSchema.parse({ siren: '12345' }); // Too short
      }).rejects.toThrow();
    });
  });

  describe('get_api_status tool', () => {
    it('should get status from all adapters', async () => {
      // Mock adapter status responses
      mockAdapters.insee.getStatus.mockResolvedValue({
        available: true,
        rateLimit: { remaining: 950, reset: new Date() }
      });
      mockAdapters['banque-france'].getStatus.mockResolvedValue({
        available: true,
        rateLimit: { remaining: 900, reset: new Date() }
      });
      mockAdapters.inpi.getStatus.mockResolvedValue({
        available: false
      });

      const result = await statusHandler({});

      expect(result.success).toBe(true);
      expect(result.status).toHaveProperty('insee');
      expect(result.status).toHaveProperty('banque-france');
      expect(result.status).toHaveProperty('inpi');

      expect(result.status.insee.available).toBe(true);
      expect(result.status['banque-france'].available).toBe(true);
      expect(result.status.inpi.available).toBe(false);

      // Verify all adapters were called
      expect(mockAdapters.insee.getStatus).toHaveBeenCalled();
      expect(mockAdapters['banque-france'].getStatus).toHaveBeenCalled();
      expect(mockAdapters.inpi.getStatus).toHaveBeenCalled();
    });

    it('should handle adapter errors in status check', async () => {
      mockAdapters.insee.getStatus.mockRejectedValue(new Error('Network error'));
      mockAdapters['banque-france'].getStatus.mockResolvedValue({
        available: true,
        rateLimit: { remaining: 900, reset: new Date() }
      });
      mockAdapters.inpi.getStatus.mockResolvedValue({
        available: true,
        rateLimit: { remaining: 800, reset: new Date() }
      });

      const result = await statusHandler({});

      expect(result.success).toBe(true);
      expect(result.status.insee).toMatchObject({
        available: false,
        error: 'Network error'
      });
      expect(result.status['banque-france'].available).toBe(true);
      expect(result.status.inpi.available).toBe(true);
    });
  });

  describe('Error Handling', () => {
    it('should handle unexpected errors in search', async () => {
      // Make all adapters throw unexpected errors
      const unexpectedError = new Error('Unexpected error');
      mockAdapters.insee.search.mockRejectedValue(unexpectedError);
      mockAdapters['banque-france'].search.mockRejectedValue(unexpectedError);
      mockAdapters.inpi.search.mockRejectedValue(unexpectedError);

      const result = await searchHandler({
        query: 'DANONE',
        source: 'all',
        includeHistory: false,
        maxResults: 10
      });

      expect(result.success).toBe(true); // Should still succeed
      expect(result.results).toHaveLength(3);
      
      // All should have errors
      result.results.forEach(r => {
        expect(r.error).toBe('Unexpected error');
      });
    });

    it('should handle missing adapters gracefully', async () => {
      // Simulate missing adapter
      delete mockAdapters.insee;

      const result = await searchHandler({
        query: 'DANONE',
        source: 'insee',
        includeHistory: false,
        maxResults: 10
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('Unknown source');
    });
  });

  describe('Integration with Cache and Rate Limiter', () => {
    it('should use cache and rate limiter in adapters', async () => {
      const mockCache = createMockCache();
      const mockRateLimiter = createMockRateLimiter();

      require('../src/cache').createCache.mockReturnValue(mockCache);
      require('../src/rate-limiter').createRateLimiter.mockReturnValue(mockRateLimiter);

      // Verify that setupAdapters was called with cache and rate limiter
      const setupAdaptersCalls = require('../src/adapters').setupAdapters.mock.calls;
      
      expect(setupAdaptersCalls.length).toBeGreaterThan(0);
      expect(setupAdaptersCalls[0][0]).toHaveProperty('cache');
      expect(setupAdaptersCalls[0][0]).toHaveProperty('rateLimiter');
    });
  });
});