import { INSEEAdapter } from '../../src/adapters/insee';
import axios from 'axios';
import { 
  mockCompanies, 
  mockINSEEResponses, 
  createMockCache, 
  createMockRateLimiter,
  mockApiErrors 
} from '../fixtures';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('INSEEAdapter', () => {
  let adapter: INSEEAdapter;
  let mockCache: ReturnType<typeof createMockCache>;
  let mockRateLimiter: ReturnType<typeof createMockRateLimiter>;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env.INSEE_API_KEY = 'test-api-key';
    
    mockCache = createMockCache();
    mockRateLimiter = createMockRateLimiter();
    
    adapter = new INSEEAdapter({
      cache: mockCache,
      rateLimiter: mockRateLimiter
    });
  });

  afterEach(() => {
    delete process.env.INSEE_API_KEY;
  });

  describe('constructor', () => {
    it('should initialize with API key from environment', () => {
      expect(adapter).toBeDefined();
    });

    it('should warn when API key is missing', () => {
      const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();
      delete process.env.INSEE_API_KEY;
      
      new INSEEAdapter({
        cache: mockCache,
        rateLimiter: mockRateLimiter
      });
      
      expect(consoleWarnSpy).toHaveBeenCalledWith('INSEE API key not found in environment variables');
      consoleWarnSpy.mockRestore();
    });
  });

  describe('search', () => {
    const searchOptions = { maxResults: 10 };

    it('should search by company name', async () => {
      mockedAxios.get.mockResolvedValueOnce({
        data: mockINSEEResponses.searchByName
      });

      const results = await adapter.search('DANONE', searchOptions);

      expect(mockCache.get).toHaveBeenCalledWith('insee:search:DANONE:{"maxResults":10}');
      expect(mockRateLimiter.acquire).toHaveBeenCalledWith('insee');
      expect(mockedAxios.get).toHaveBeenCalledWith(
        'https://api.insee.fr/entreprises/sirene/V3/siren',
        expect.objectContaining({
          headers: {
            Authorization: 'Bearer test-api-key',
            Accept: 'application/json'
          },
          params: {
            nombre: 10,
            q: 'denominationUniteLegale:"DANONE"'
          }
        })
      );
      
      expect(results).toHaveLength(1);
      expect(results[0]).toMatchObject({
        siren: mockCompanies.danone.siren,
        name: mockCompanies.danone.name,
        legalForm: mockCompanies.danone.legalForm
      });
      
      expect(mockCache.set).toHaveBeenCalledWith(
        'insee:search:DANONE:{"maxResults":10}',
        results,
        3600
      );
    });

    it('should search by SIREN number', async () => {
      mockedAxios.get.mockResolvedValueOnce({
        data: mockINSEEResponses.searchBySiren
      });

      const results = await adapter.search(mockCompanies.danone.siren, searchOptions);

      expect(mockedAxios.get).toHaveBeenCalledWith(
        `https://api.insee.fr/entreprises/sirene/V3/siren/${mockCompanies.danone.siren}`,
        expect.objectContaining({
          headers: {
            Authorization: 'Bearer test-api-key',
            Accept: 'application/json'
          },
          params: {
            nombre: 10
          }
        })
      );
    });

    it('should search by SIRET number', async () => {
      mockedAxios.get.mockResolvedValueOnce({
        data: mockINSEEResponses.searchBySiren
      });

      const results = await adapter.search(mockCompanies.danone.siret, searchOptions);

      expect(mockedAxios.get).toHaveBeenCalledWith(
        `https://api.insee.fr/entreprises/sirene/V3/siret/${mockCompanies.danone.siret}`,
        expect.any(Object)
      );
    });

    it('should return cached results when available', async () => {
      const cachedResults = [{ siren: '123456789', name: 'Cached Company' }];
      mockCache.get.mockResolvedValueOnce(cachedResults);

      const results = await adapter.search('DANONE', searchOptions);

      expect(results).toEqual(cachedResults);
      expect(mockedAxios.get).not.toHaveBeenCalled();
      expect(mockRateLimiter.acquire).not.toHaveBeenCalled();
    });

    it('should handle API errors gracefully', async () => {
      mockedAxios.get.mockRejectedValueOnce({
        isAxiosError: true,
        response: {
          data: mockINSEEResponses.unauthorized
        }
      });

      await expect(adapter.search('DANONE', searchOptions))
        .rejects.toThrow('INSEE API error: Jeton invalide');
    });

    it('should handle network errors', async () => {
      mockedAxios.get.mockRejectedValueOnce(mockApiErrors.networkError);

      await expect(adapter.search('DANONE', searchOptions))
        .rejects.toThrow(mockApiErrors.networkError);
    });

    it('should handle empty results', async () => {
      mockedAxios.get.mockResolvedValueOnce({
        data: { unitesLegales: [] }
      });

      const results = await adapter.search('NONEXISTENT', searchOptions);

      expect(results).toEqual([]);
    });

    it('should respect rate limits', async () => {
      mockRateLimiter.acquire.mockRejectedValueOnce(new Error('Rate limit exceeded'));

      await expect(adapter.search('DANONE', searchOptions))
        .rejects.toThrow('Rate limit exceeded');
      
      expect(mockedAxios.get).not.toHaveBeenCalled();
    });
  });

  describe('getDetails', () => {
    const detailsOptions = { includeFinancials: true };

    it('should get enterprise details by SIREN', async () => {
      mockedAxios.get.mockResolvedValueOnce({
        data: mockINSEEResponses.searchBySiren
      });

      const details = await adapter.getDetails(mockCompanies.danone.siren, detailsOptions);

      expect(mockCache.get).toHaveBeenCalledWith(
        `insee:details:${mockCompanies.danone.siren}:{"includeFinancials":true}`
      );
      expect(mockRateLimiter.acquire).toHaveBeenCalledWith('insee');
      expect(mockedAxios.get).toHaveBeenCalledWith(
        `https://api.insee.fr/entreprises/sirene/V3/siren/${mockCompanies.danone.siren}`,
        expect.objectContaining({
          headers: {
            Authorization: 'Bearer test-api-key',
            Accept: 'application/json'
          }
        })
      );

      expect(details).toMatchObject({
        basicInfo: {
          siren: mockCompanies.danone.siren,
          name: mockCompanies.danone.name,
          legalForm: mockCompanies.danone.legalForm
        },
        financials: {
          employees: mockCompanies.danone.employees
        }
      });

      expect(mockCache.set).toHaveBeenCalledWith(
        `insee:details:${mockCompanies.danone.siren}:{"includeFinancials":true}`,
        details,
        3600
      );
    });

    it('should return cached details when available', async () => {
      const cachedDetails = {
        basicInfo: { siren: '123456789', name: 'Cached Company' },
        financials: {}
      };
      mockCache.get.mockResolvedValueOnce(cachedDetails);

      const details = await adapter.getDetails(mockCompanies.danone.siren, detailsOptions);

      expect(details).toEqual(cachedDetails);
      expect(mockedAxios.get).not.toHaveBeenCalled();
    });

    it('should handle not found errors', async () => {
      mockedAxios.get.mockRejectedValueOnce({
        isAxiosError: true,
        response: {
          data: mockINSEEResponses.notFound
        }
      });

      await expect(adapter.getDetails('999999999', detailsOptions))
        .rejects.toThrow('INSEE API error: Aucune unité légale ne correspond aux critères de recherche');
    });
  });

  describe('getStatus', () => {
    it('should return available status when API is accessible', async () => {
      mockedAxios.get.mockResolvedValueOnce({ data: {} });
      mockRateLimiter.getStatus.mockResolvedValueOnce({
        remaining: 950,
        reset: new Date(Date.now() + 3600000)
      });

      const status = await adapter.getStatus();

      expect(mockedAxios.get).toHaveBeenCalledWith(
        'https://api.insee.fr/entreprises/sirene/V3/informations',
        expect.objectContaining({
          headers: {
            Authorization: 'Bearer test-api-key',
            Accept: 'application/json'
          }
        })
      );

      expect(status).toMatchObject({
        available: true,
        rateLimit: {
          remaining: 950
        }
      });
      expect(status.lastCheck).toBeInstanceOf(Date);
    });

    it('should return unavailable status when API is not accessible', async () => {
      mockedAxios.get.mockRejectedValueOnce(mockApiErrors.networkError);

      const status = await adapter.getStatus();

      expect(status).toMatchObject({
        available: false
      });
      expect(status.lastCheck).toBeInstanceOf(Date);
    });
  });

  describe('formatAddress', () => {
    it('should format complete address correctly', async () => {
      mockedAxios.get.mockResolvedValueOnce({
        data: mockINSEEResponses.searchBySiren
      });

      const results = await adapter.search(mockCompanies.danone.siren, {});
      
      // Check if address was formatted correctly
      expect(results[0]?.address).toBe('17 BOULEVARD HAUSSMANN 75009 PARIS');
    });

    it('should handle missing address parts', async () => {
      const responseWithPartialAddress = {
        uniteLegale: {
          ...mockINSEEResponses.searchBySiren.uniteLegale,
          adresseSiegeUniteLegale: {
            libelleVoieEtablissement: 'HAUSSMANN',
            libelleCommuneEtablissement: 'PARIS'
          }
        }
      };

      mockedAxios.get.mockResolvedValueOnce({
        data: responseWithPartialAddress
      });

      const details = await adapter.getDetails(mockCompanies.danone.siren, {});
      
      expect(details.basicInfo.address).toBe('HAUSSMANN PARIS');
    });

    it('should handle null address', async () => {
      const responseWithNullAddress = {
        uniteLegale: {
          ...mockINSEEResponses.searchBySiren.uniteLegale,
          adresseSiegeUniteLegale: null
        }
      };

      mockedAxios.get.mockResolvedValueOnce({
        data: responseWithNullAddress
      });

      const details = await adapter.getDetails(mockCompanies.danone.siren, {});
      
      expect(details.basicInfo.address).toBe('');
    });
  });
});