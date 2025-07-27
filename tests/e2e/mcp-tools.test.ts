import { Server } from "@modelcontextprotocol/server";
import { mockCompanies } from '../fixtures';

// Mock the entire MCP server module
const mockServer = {
  registerTool: jest.fn(),
  start: jest.fn().mockResolvedValue(undefined),
  stop: jest.fn().mockResolvedValue(undefined)
};

jest.mock('@modelcontextprotocol/server', () => ({
  Server: jest.fn().mockImplementation(() => mockServer)
}));

describe('MCP Firms End-to-End Tests', () => {
  let server: any;
  let registeredTools: Map<string, any>;

  beforeEach(() => {
    jest.clearAllMocks();
    registeredTools = new Map();

    // Capture registered tools
    mockServer.registerTool.mockImplementation((tool) => {
      registeredTools.set(tool.name, tool);
    });

    // Set up environment
    process.env.INSEE_API_KEY = 'test-insee-key';
    process.env.BANQUE_FRANCE_API_KEY = 'test-bf-key';
    process.env.INPI_USERNAME = 'test-inpi-user';
    process.env.INPI_PASSWORD = 'test-inpi-pass';

    // Import server (this will trigger tool registration)
    jest.isolateModules(() => {
      const serverModule = require('../../src/index');
      server = serverModule.default;
    });
  });

  afterEach(() => {
    delete process.env.INSEE_API_KEY;
    delete process.env.BANQUE_FRANCE_API_KEY;
    delete process.env.INPI_USERNAME;
    delete process.env.INPI_PASSWORD;
  });

  describe('Tool Registration', () => {
    it('should register all required MCP tools', () => {
      expect(registeredTools.has('search_enterprises')).toBe(true);
      expect(registeredTools.has('get_enterprise_details')).toBe(true);
      expect(registeredTools.has('get_api_status')).toBe(true);
    });

    it('should register tools with correct metadata', () => {
      const searchTool = registeredTools.get('search_enterprises');
      expect(searchTool).toMatchObject({
        name: 'search_enterprises',
        description: expect.stringContaining('Search for French enterprises'),
        inputSchema: expect.any(Object),
        handler: expect.any(Function)
      });

      const detailsTool = registeredTools.get('get_enterprise_details');
      expect(detailsTool).toMatchObject({
        name: 'get_enterprise_details',
        description: expect.stringContaining('detailed information about a French enterprise'),
        inputSchema: expect.any(Object),
        handler: expect.any(Function)
      });

      const statusTool = registeredTools.get('get_api_status');
      expect(statusTool).toMatchObject({
        name: 'get_api_status',
        description: expect.stringContaining('Check the status'),
        inputSchema: expect.any(Object),
        handler: expect.any(Function)
      });
    });
  });

  describe('Tool Schemas', () => {
    it('should validate search_enterprises input correctly', () => {
      const searchTool = registeredTools.get('search_enterprises');
      const schema = searchTool.inputSchema;

      // Valid inputs
      expect(() => schema.parse({
        query: 'DANONE',
        source: 'all',
        includeHistory: false,
        maxResults: 10
      })).not.toThrow();

      expect(() => schema.parse({
        query: '552032534',
        source: 'insee'
      })).not.toThrow();

      // Invalid source
      expect(() => schema.parse({
        query: 'DANONE',
        source: 'invalid-source'
      })).toThrow();

      // Invalid maxResults
      expect(() => schema.parse({
        query: 'DANONE',
        maxResults: 150 // Over 100
      })).toThrow();
    });

    it('should validate get_enterprise_details input correctly', () => {
      const detailsTool = registeredTools.get('get_enterprise_details');
      const schema = detailsTool.inputSchema;

      // Valid SIREN
      expect(() => schema.parse({
        siren: mockCompanies.danone.siren,
        source: 'all',
        includeFinancials: true,
        includeIntellectualProperty: true
      })).not.toThrow();

      // Invalid SIREN - too short
      expect(() => schema.parse({
        siren: '12345'
      })).toThrow();

      // Invalid SIREN - contains letters
      expect(() => schema.parse({
        siren: '12345678A'
      })).toThrow();

      // Invalid SIREN - too long
      expect(() => schema.parse({
        siren: '1234567890'
      })).toThrow();
    });

    it('should validate get_api_status input correctly', () => {
      const statusTool = registeredTools.get('get_api_status');
      const schema = statusTool.inputSchema;

      // Should accept empty object
      expect(() => schema.parse({})).not.toThrow();
    });
  });

  describe('End-to-End Workflows', () => {
    // Mock adapter setup
    const mockAdapters = {
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

    beforeEach(() => {
      // Mock the setupAdapters function
      jest.doMock('../../src/adapters', () => ({
        setupAdapters: jest.fn(() => mockAdapters)
      }));
    });

    describe('Company Research Workflow', () => {
      it('should complete full company research workflow', async () => {
        // Step 1: Search for company
        mockAdapters.insee.search.mockResolvedValue([{
          siren: mockCompanies.danone.siren,
          name: mockCompanies.danone.name,
          legalForm: mockCompanies.danone.legalForm,
          status: 'active'
        }]);
        mockAdapters['banque-france'].search.mockResolvedValue([]);
        mockAdapters.inpi.search.mockResolvedValue([]);

        const searchTool = registeredTools.get('search_enterprises');
        const searchResult = await searchTool.handler({
          query: 'DANONE',
          source: 'all',
          includeHistory: false,
          maxResults: 10
        });

        expect(searchResult.success).toBe(true);
        expect(searchResult.results).toHaveLength(3);
        
        // Extract SIREN from search results
        const foundSiren = searchResult.results[0].data[0].siren;

        // Step 2: Get detailed information
        mockAdapters.insee.getDetails.mockResolvedValue({
          basicInfo: {
            siren: foundSiren,
            name: mockCompanies.danone.name,
            legalForm: mockCompanies.danone.legalForm,
            address: mockCompanies.danone.address,
            status: 'active'
          }
        });
        mockAdapters['banque-france'].getDetails.mockResolvedValue({
          financials: {
            revenue: 27661000000,
            employees: 95947
          }
        });
        mockAdapters.inpi.getDetails.mockResolvedValue({
          intellectualProperty: {
            trademarks: 245,
            patents: 89,
            designs: 34
          }
        });

        const detailsTool = registeredTools.get('get_enterprise_details');
        const detailsResult = await detailsTool.handler({
          siren: foundSiren,
          source: 'all',
          includeFinancials: true,
          includeIntellectualProperty: true
        });

        expect(detailsResult.success).toBe(true);
        expect(detailsResult.siren).toBe(foundSiren);
        expect(detailsResult.details.insee).toHaveProperty('basicInfo');
        expect(detailsResult.details['banque-france']).toHaveProperty('financials');
        expect(detailsResult.details.inpi).toHaveProperty('intellectualProperty');
      });
    });

    describe('API Monitoring Workflow', () => {
      it('should monitor API availability and rate limits', async () => {
        // Mock status responses
        mockAdapters.insee.getStatus.mockResolvedValue({
          available: true,
          rateLimit: { remaining: 4500, reset: new Date(Date.now() + 3600000) }
        });
        mockAdapters['banque-france'].getStatus.mockResolvedValue({
          available: true,
          rateLimit: { remaining: 900, reset: new Date(Date.now() + 3600000) }
        });
        mockAdapters.inpi.getStatus.mockResolvedValue({
          available: false
        });

        const statusTool = registeredTools.get('get_api_status');
        const statusResult = await statusTool.handler({});

        expect(statusResult.success).toBe(true);
        expect(statusResult.status.insee.available).toBe(true);
        expect(statusResult.status.insee.rateLimit.remaining).toBe(4500);
        expect(statusResult.status['banque-france'].available).toBe(true);
        expect(statusResult.status.inpi.available).toBe(false);
      });
    });

    describe('Error Recovery Workflow', () => {
      it('should handle partial API failures gracefully', async () => {
        // INSEE works
        mockAdapters.insee.search.mockResolvedValue([{
          siren: mockCompanies.danone.siren,
          name: mockCompanies.danone.name
        }]);
        
        // Banque de France fails
        mockAdapters['banque-france'].search.mockRejectedValue(
          new Error('Service temporarily unavailable')
        );
        
        // INPI works but returns empty
        mockAdapters.inpi.search.mockResolvedValue([]);

        const searchTool = registeredTools.get('search_enterprises');
        const result = await searchTool.handler({
          query: mockCompanies.danone.siren,
          source: 'all'
        });

        expect(result.success).toBe(true);
        expect(result.results).toHaveLength(3);
        
        // INSEE should have data
        expect(result.results[0].data).toBeDefined();
        expect(result.results[0].data).toHaveLength(1);
        
        // Banque de France should have error
        expect(result.results[1].error).toBe('Service temporarily unavailable');
        
        // INPI should have empty data
        expect(result.results[2].data).toEqual([]);
      });
    });

    describe('Batch Processing Workflow', () => {
      it('should handle batch company lookups efficiently', async () => {
        const companies = [
          mockCompanies.danone,
          mockCompanies.airbus,
          mockCompanies.carrefour
        ];

        // Mock search responses
        companies.forEach(company => {
          mockAdapters.insee.search.mockResolvedValueOnce([{
            siren: company.siren,
            name: company.name,
            status: 'active'
          }]);
          mockAdapters['banque-france'].search.mockResolvedValueOnce([]);
          mockAdapters.inpi.search.mockResolvedValueOnce([]);
        });

        const searchTool = registeredTools.get('search_enterprises');
        
        // Perform batch searches
        const searchPromises = companies.map(company =>
          searchTool.handler({
            query: company.siren,
            source: 'insee',
            maxResults: 1
          })
        );

        const searchResults = await Promise.all(searchPromises);

        // All searches should succeed
        searchResults.forEach((result, index) => {
          expect(result.success).toBe(true);
          expect(result.results[0].data[0].siren).toBe(companies[index].siren);
        });

        // Now get details for all found companies
        const detailsTool = registeredTools.get('get_enterprise_details');
        
        companies.forEach(company => {
          mockAdapters.insee.getDetails.mockResolvedValueOnce({
            basicInfo: {
              siren: company.siren,
              name: company.name
            }
          });
        });

        const detailsPromises = companies.map(company =>
          detailsTool.handler({
            siren: company.siren,
            source: 'insee'
          })
        );

        const detailsResults = await Promise.all(detailsPromises);

        // All detail fetches should succeed
        detailsResults.forEach((result, index) => {
          expect(result.success).toBe(true);
          expect(result.details.insee.basicInfo.siren).toBe(companies[index].siren);
        });
      });
    });

    describe('Real-world Use Cases', () => {
      it('should support competitor analysis workflow', async () => {
        // Search for companies in same industry
        const industryCode = '47.11F'; // Hypermarkets
        
        mockAdapters.insee.search.mockResolvedValue([
          { siren: mockCompanies.carrefour.siren, name: 'CARREFOUR', activity: industryCode },
          { siren: '542065479', name: 'E.LECLERC', activity: industryCode },
          { siren: '444608442', name: 'AUCHAN', activity: industryCode }
        ]);

        const searchTool = registeredTools.get('search_enterprises');
        const competitorSearch = await searchTool.handler({
          query: industryCode,
          source: 'insee',
          maxResults: 20
        });

        expect(competitorSearch.success).toBe(true);
        expect(competitorSearch.results[0].data).toHaveLength(3);

        // Get financial details for comparison
        const detailsTool = registeredTools.get('get_enterprise_details');
        const competitors = competitorSearch.results[0].data;

        // Mock financial data for each competitor
        const financialData = [
          { revenue: 90700000000, employees: 321000 }, // Carrefour
          { revenue: 58650000000, employees: 133000 }, // E.Leclerc
          { revenue: 51897000000, employees: 179000 }  // Auchan
        ];

        competitors.forEach((company, index) => {
          mockAdapters['banque-france'].getDetails.mockResolvedValueOnce({
            financials: financialData[index]
          });
        });

        const competitorDetails = await Promise.all(
          competitors.map(company =>
            detailsTool.handler({
              siren: company.siren,
              source: 'banque-france',
              includeFinancials: true
            })
          )
        );

        // Verify we can compare financial metrics
        competitorDetails.forEach((result, index) => {
          expect(result.success).toBe(true);
          expect(result.details['banque-france'].financials).toEqual(financialData[index]);
        });
      });

      it('should support due diligence workflow', async () => {
        const targetSiren = mockCompanies.startup.siren;

        // Step 1: Basic company search
        mockAdapters.insee.search.mockResolvedValue([{
          siren: targetSiren,
          name: mockCompanies.startup.name,
          creationDate: mockCompanies.startup.creationDate,
          status: 'active'
        }]);

        const searchTool = registeredTools.get('search_enterprises');
        const searchResult = await searchTool.handler({
          query: targetSiren,
          source: 'insee'
        });

        expect(searchResult.success).toBe(true);

        // Step 2: Comprehensive details from all sources
        mockAdapters.insee.getDetails.mockResolvedValue({
          basicInfo: {
            siren: targetSiren,
            name: mockCompanies.startup.name,
            legalForm: mockCompanies.startup.legalForm,
            creationDate: mockCompanies.startup.creationDate,
            employees: mockCompanies.startup.employees
          }
        });

        mockAdapters['banque-france'].getDetails.mockResolvedValue({
          financials: {
            revenue: 2500000,
            netIncome: -150000, // Loss (common for startups)
            equity: 850000,
            debt: 500000
          },
          creditRating: {
            score: '5+',
            trend: 'improving'
          }
        });

        mockAdapters.inpi.getDetails.mockResolvedValue({
          intellectualProperty: {
            trademarks: 3,
            patents: 2,
            designs: 0
          }
        });

        const detailsTool = registeredTools.get('get_enterprise_details');
        const dueDiligence = await detailsTool.handler({
          siren: targetSiren,
          source: 'all',
          includeFinancials: true,
          includeIntellectualProperty: true
        });

        expect(dueDiligence.success).toBe(true);
        
        // Check all aspects for due diligence
        const { insee, 'banque-france': bf, inpi } = dueDiligence.details;
        
        // Company is active
        expect(insee.basicInfo.status).toBe('active');
        
        // Financial health check
        expect(bf.financials.revenue).toBeGreaterThan(0);
        expect(bf.financials.equity).toBeGreaterThan(bf.financials.debt); // Positive net worth
        
        // Has intellectual property
        expect(inpi.intellectualProperty.trademarks + inpi.intellectualProperty.patents).toBeGreaterThan(0);
      });
    });
  });

  describe('Performance and Scalability', () => {
    it('should handle high-volume concurrent tool calls', async () => {
      const mockAdapters = {
        insee: { search: jest.fn(), getDetails: jest.fn(), getStatus: jest.fn() },
        'banque-france': { search: jest.fn(), getDetails: jest.fn(), getStatus: jest.fn() },
        inpi: { search: jest.fn(), getDetails: jest.fn(), getStatus: jest.fn() }
      };

      jest.doMock('../../src/adapters', () => ({
        setupAdapters: jest.fn(() => mockAdapters)
      }));

      // Mock fast responses
      mockAdapters.insee.search.mockResolvedValue([{ siren: '123456789', name: 'Test' }]);
      mockAdapters.insee.getStatus.mockResolvedValue({ available: true });

      const searchTool = registeredTools.get('search_enterprises');
      const statusTool = registeredTools.get('get_api_status');

      // Simulate 50 concurrent tool calls
      const concurrentCalls = 50;
      const startTime = Date.now();

      const promises = [];
      for (let i = 0; i < concurrentCalls; i++) {
        if (i % 2 === 0) {
          promises.push(searchTool.handler({
            query: `Company${i}`,
            source: 'insee'
          }));
        } else {
          promises.push(statusTool.handler({}));
        }
      }

      const results = await Promise.all(promises);
      const duration = Date.now() - startTime;

      // All calls should succeed
      results.forEach(result => {
        expect(result.success).toBe(true);
      });

      // Should complete in reasonable time (less than 5 seconds for 50 calls)
      expect(duration).toBeLessThan(5000);
    });
  });
});