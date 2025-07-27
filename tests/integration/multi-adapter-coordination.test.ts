import { setupAdapters } from '../../src/adapters/index.js';
import { createCache } from '../../src/cache/index.js';
import { createRateLimiter } from '../../src/rate-limiter/index.js';
import { mockCompanies, mockINSEEResponses, mockBanqueFranceResponses, mockINPIResponses } from '../fixtures/index.js';
import axios from 'axios';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('Multi-Adapter Coordination Integration Tests', () => {
  let adapters: ReturnType<typeof setupAdapters>;
  let cache: ReturnType<typeof createCache>;
  let rateLimiter: ReturnType<typeof createRateLimiter>;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Create real instances for integration testing
    cache = createCache();
    rateLimiter = createRateLimiter();
    adapters = setupAdapters({ cache, rateLimiter });

    // Set environment variables
    process.env.INSEE_API_KEY = 'test-insee-key';
    process.env.BANQUE_FRANCE_API_KEY = 'test-bf-key';
    process.env.INPI_USERNAME = 'test-inpi-user';
    process.env.INPI_PASSWORD = 'test-inpi-pass';
  });

  afterEach(async () => {
    // Cleanup
    await cache.flush();
    delete process.env.INSEE_API_KEY;
    delete process.env.BANQUE_FRANCE_API_KEY;
    delete process.env.INPI_USERNAME;
    delete process.env.INPI_PASSWORD;
  });

  describe('Coordinated Data Enrichment', () => {
    it('should enrich company data by combining all three adapters', async () => {
      const siren = mockCompanies.danone.siren;

      // Mock INSEE API response
      mockedAxios.get.mockImplementation((url: string) => {
        if (url.includes('insee.fr') && url.includes(siren)) {
          return Promise.resolve({
            data: mockINSEEResponses.searchBySiren
          });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      // Mock Banque de France API responses
      mockedAxios.get.mockImplementation((url: string) => {
        if (url.includes('banque-france.fr')) {
          if (url.includes('bilans')) {
            return Promise.resolve({
              data: {
                bilans: [{
                  companyName: mockCompanies.danone.name,
                  revenue: 27661000000,
                  employees: 95947,
                  year: 2023
                }]
              }
            });
          } else if (url.includes('cotation')) {
            return Promise.resolve({
              data: {
                cotation: '3++',
                dateCotation: '2024-01-15',
                score: 95
              }
            });
          } else if (url.includes('incidents-paiement')) {
            return Promise.resolve({
              data: { incidents: [] }
            });
          }
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      // Mock INPI API responses (authentication and company data)
      mockedAxios.post.mockImplementation((url: string) => {
        if (url.includes('inpi.fr') && url.includes('login')) {
          return Promise.resolve({
            data: {
              access_token: 'test-token',
              token_type: 'Bearer',
              expires_in: 3600
            }
          });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      // Step 1: Get basic info from INSEE
      const inseeResults = await adapters.insee.search(siren, { maxResults: 1 });
      expect(inseeResults).toHaveLength(1);
      expect(inseeResults[0].siren).toBe(siren);

      // Step 2: Get detailed financials from Banque de France
      const bfDetails = await adapters['banque-france'].getDetails(siren, { 
        includeFinancials: true 
      });
      expect(bfDetails.basicInfo.siren).toBe(siren);
      expect(bfDetails.financials).toBeDefined();

      // Step 3: Get intellectual property from INPI
      const inpiDetails = await adapters.inpi.getDetails(siren, {
        includeIntellectualProperty: true
      });
      expect(inpiDetails.basicInfo.siren).toBe(siren);

      // Verify data enrichment worked
      expect(inseeResults[0]).toHaveProperty('name');
      expect(bfDetails).toHaveProperty('financials');
      expect(inpiDetails).toHaveProperty('intellectualProperty');
    });

    it('should handle partial data availability gracefully', async () => {
      const siren = mockCompanies.startup.siren;

      // Mock responses: INSEE works, Banque de France has no data, INPI works
      mockedAxios.get.mockImplementation((url: string) => {
        if (url.includes('insee.fr')) {
          return Promise.resolve({
            data: {
              uniteLegale: {
                siren: siren,
                denominationUniteLegale: mockCompanies.startup.name,
                etatAdministratifUniteLegale: 'A'
              }
            }
          });
        } else if (url.includes('banque-france.fr')) {
          return Promise.reject({
            isAxiosError: true,
            response: { status: 404 }
          });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      mockedAxios.post.mockImplementation((url: string) => {
        if (url.includes('inpi.fr') && url.includes('login')) {
          return Promise.resolve({
            data: {
              access_token: 'test-token',
              token_type: 'Bearer',
              expires_in: 3600
            }
          });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      // Test each adapter's response to missing data
      const inseeResults = await adapters.insee.search(siren, {});
      expect(inseeResults).toHaveLength(1);

      const bfResults = await adapters['banque-france'].search(siren, {});
      expect(bfResults).toHaveLength(0); // Should return empty for non-found companies

      // All adapters should handle missing data gracefully
      expect(inseeResults).toBeDefined();
      expect(bfResults).toBeDefined();
    });
  });

  describe('Cache Coordination', () => {
    it('should coordinate cache usage across adapters', async () => {
      const siren = mockCompanies.carrefour.siren;
      const cacheKeys = [
        `insee:search:${siren}:{}`,
        `banque-france:search:${siren}:{}`,
        `inpi:search:${siren}:{}`
      ];

      // Mock API responses
      mockedAxios.get.mockResolvedValue({
        data: mockINSEEResponses.searchBySiren
      });

      // First calls should hit APIs and cache results
      await adapters.insee.search(siren, {});
      
      // Check cache statistics
      const initialStats = cache.getStats();
      expect(initialStats.keys).toBeGreaterThan(0);

      // Second calls should hit cache
      await adapters.insee.search(siren, {});
      
      const finalStats = cache.getStats();
      expect(finalStats.hits).toBeGreaterThan(initialStats.hits);
    });

    it('should handle cache invalidation appropriately', async () => {
      const siren = mockCompanies.airbus.siren;
      const testData = { siren, name: 'Test Company' };

      // Set initial data
      await cache.set('test-key', testData);
      
      const retrieved = await cache.get('test-key');
      expect(retrieved).toEqual(testData);

      // Flush cache
      await cache.flush();
      
      const afterFlush = await cache.get('test-key');
      expect(afterFlush).toBeUndefined();

      // Verify cache stats reflect the change
      const stats = cache.getStats();
      expect(stats.keys).toBe(0);
    });

    it('should prevent cache conflicts between adapters', async () => {
      const siren = mockCompanies.danone.siren;
      
      // Different cache keys for different adapters
      const inseeKey = `insee:search:${siren}:{}`;
      const bfKey = `banque-france:search:${siren}:{}`;
      const inpiKey = `inpi:search:${siren}:{}`;

      const inseeData = [{ siren, name: 'INSEE Data', source: 'insee' }];
      const bfData = [{ siren, name: 'BF Data', source: 'banque-france' }];
      const inpiData = [{ siren, name: 'INPI Data', source: 'inpi' }];

      // Set different data for each adapter
      await cache.set(inseeKey, inseeData);
      await cache.set(bfKey, bfData);
      await cache.set(inpiKey, inpiData);

      // Verify each adapter's data is isolated
      const retrievedInsee = await cache.get(inseeKey);
      const retrievedBf = await cache.get(bfKey);
      const retrievedInpi = await cache.get(inpiKey);

      expect(retrievedInsee).toEqual(inseeData);
      expect(retrievedBf).toEqual(bfData);
      expect(retrievedInpi).toEqual(inpiData);

      // Verify they're different
      expect(retrievedInsee).not.toEqual(retrievedBf);
      expect(retrievedBf).not.toEqual(retrievedInpi);
    });
  });

  describe('Rate Limiter Coordination', () => {
    it('should apply independent rate limits to each adapter', async () => {
      const sources = ['insee', 'banque-france', 'inpi'];
      const requestCounts = { insee: 0, 'banque-france': 0, inpi: 0 };

      // Make multiple requests to each source
      for (let i = 0; i < 5; i++) {
        for (const source of sources) {
          await rateLimiter.acquire(source);
          requestCounts[source]++;
        }
      }

      // Check that each source was rate limited independently
      for (const source of sources) {
        const status = await rateLimiter.getStatus(source);
        expect(status.remaining).toBeLessThan(1000); // Should have consumed some limits
        expect(requestCounts[source]).toBe(5);
      }
    });

    it('should handle rate limit resets per adapter', async () => {
      // Use up some rate limit
      await rateLimiter.acquire('insee');
      
      const statusBefore = await rateLimiter.getStatus('insee');
      const remainingBefore = statusBefore.remaining;

      // Reset rate limiter for INSEE
      rateLimiter.reset('insee');

      const statusAfter = await rateLimiter.getStatus('insee');
      const remainingAfter = statusAfter.remaining;

      expect(remainingAfter).toBeGreaterThan(remainingBefore);
    });

    it('should prevent rate limit interference between adapters', async () => {
      // Exhaust rate limit for one adapter
      for (let i = 0; i < 10; i++) {
        await rateLimiter.acquire('banque-france');
      }

      const bfStatus = await rateLimiter.getStatus('banque-france');
      const inseeStatus = await rateLimiter.getStatus('insee');

      // INSEE should not be affected by Banque de France rate limiting
      expect(bfStatus.remaining).toBeLessThan(inseeStatus.remaining);
    });
  });

  describe('Error Resilience', () => {
    it('should continue operation when one adapter fails', async () => {
      const siren = mockCompanies.danone.siren;

      // Mock INSEE to succeed
      mockedAxios.get.mockImplementation((url: string) => {
        if (url.includes('insee.fr')) {
          return Promise.resolve({
            data: mockINSEEResponses.searchBySiren
          });
        } else if (url.includes('banque-france.fr')) {
          // Banque de France fails
          return Promise.reject(new Error('Service unavailable'));
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      // INSEE should work
      const inseeResults = await adapters.insee.search(siren, {});
      expect(inseeResults).toHaveLength(1);

      // Banque de France should handle errors gracefully
      const bfResults = await adapters['banque-france'].search(siren, {});
      expect(bfResults).toEqual([]); // Should return empty array for failures
    });

    it('should recover from temporary failures', async () => {
      const siren = mockCompanies.danone.siren;
      let callCount = 0;

      // Mock to fail first call, succeed second call
      mockedAxios.get.mockImplementation((url: string) => {
        if (url.includes('insee.fr')) {
          callCount++;
          if (callCount === 1) {
            return Promise.reject(new Error('Temporary failure'));
          } else {
            return Promise.resolve({
              data: mockINSEEResponses.searchBySiren
            });
          }
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      // First call should fail
      try {
        await adapters.insee.search(siren, {});
        fail('Should have thrown an error');
      } catch (error) {
        expect(error.message).toContain('INSEE API error');
      }

      // Second call should succeed
      const results = await adapters.insee.search(siren, {});
      expect(results).toHaveLength(1);
    });

    it('should handle network timeouts gracefully', async () => {
      const siren = mockCompanies.danone.siren;

      // Mock network timeout
      mockedAxios.get.mockRejectedValue({
        code: 'ECONNABORTED',
        message: 'timeout of 30000ms exceeded'
      });

      try {
        await adapters.insee.search(siren, {});
        fail('Should have thrown a timeout error');
      } catch (error) {
        expect(error.message).toContain('INSEE API error');
      }
    });
  });

  describe('Data Consistency', () => {
    it('should maintain data format consistency across adapters', async () => {
      const siren = mockCompanies.danone.siren;

      // Mock consistent responses
      mockedAxios.get.mockImplementation((url: string) => {
        if (url.includes('insee.fr')) {
          return Promise.resolve({
            data: mockINSEEResponses.searchBySiren
          });
        } else if (url.includes('banque-france.fr')) {
          return Promise.resolve({
            data: {
              bilans: [{
                raisonSociale: mockCompanies.danone.name,
                adresse: mockCompanies.danone.address
              }]
            }
          });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      mockedAxios.post.mockImplementation((url: string) => {
        if (url.includes('inpi.fr') && url.includes('login')) {
          return Promise.resolve({
            data: {
              access_token: 'test-token',
              expires_in: 3600
            }
          });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      // All adapters should return SearchResult[] format
      const inseeResults = await adapters.insee.search(siren, {});
      const bfResults = await adapters['banque-france'].search(siren, {});

      // Verify consistent structure
      expect(inseeResults[0]).toHaveProperty('siren');
      expect(inseeResults[0]).toHaveProperty('name');
      expect(bfResults[0]).toHaveProperty('siren');
      expect(bfResults[0]).toHaveProperty('name');

      // Both should have the same SIREN
      expect(inseeResults[0].siren).toBe(siren);
      expect(bfResults[0].siren).toBe(siren);
    });

    it('should handle data transformation consistently', async () => {
      const testCases = [
        mockCompanies.danone,
        mockCompanies.airbus,
        mockCompanies.carrefour
      ];

      for (const company of testCases) {
        // Mock response for each company
        mockedAxios.get.mockResolvedValueOnce({
          data: {
            uniteLegale: {
              siren: company.siren,
              denominationUniteLegale: company.name,
              etatAdministratifUniteLegale: company.status
            }
          }
        });

        const results = await adapters.insee.search(company.siren, {});
        
        // Verify consistent transformation
        expect(results[0]).toMatchObject({
          siren: company.siren,
          name: company.name,
          status: company.status
        });
      }
    });
  });

  describe('Performance Coordination', () => {
    it('should handle concurrent requests across adapters efficiently', async () => {
      const companies = Object.values(mockCompanies);
      const startTime = Date.now();

      // Mock fast responses
      mockedAxios.get.mockResolvedValue({
        data: mockINSEEResponses.searchBySiren
      });

      mockedAxios.post.mockResolvedValue({
        data: {
          access_token: 'test-token',
          expires_in: 3600
        }
      });

      // Create concurrent requests across all adapters
      const promises = [];
      for (const company of companies) {
        promises.push(adapters.insee.search(company.siren, {}));
        promises.push(adapters['banque-france'].search(company.siren, {}));
      }

      const results = await Promise.all(promises);
      const duration = Date.now() - startTime;

      // Should complete all requests
      expect(results).toHaveLength(companies.length * 2);
      
      // Should be reasonably fast (less than 2 seconds for all requests)
      expect(duration).toBeLessThan(2000);
    });

    it('should optimize cache usage under load', async () => {
      const siren = mockCompanies.danone.siren;
      const requestCount = 20;

      // Mock API response
      mockedAxios.get.mockResolvedValue({
        data: mockINSEEResponses.searchBySiren
      });

      // Make many identical requests
      const promises = [];
      for (let i = 0; i < requestCount; i++) {
        promises.push(adapters.insee.search(siren, {}));
      }

      await Promise.all(promises);

      // Should have made only one API call due to caching
      expect(mockedAxios.get).toHaveBeenCalledTimes(1);

      // Cache should show high hit rate
      const stats = cache.getStats();
      expect(stats.hits).toBeGreaterThan(0);
    });
  });
});