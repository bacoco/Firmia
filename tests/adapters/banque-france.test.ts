import { BanqueFranceAdapter } from '../../src/adapters/banque-france';
import axios from 'axios';
import { 
  mockCompanies, 
  mockBanqueFranceResponses, 
  createMockCache, 
  createMockRateLimiter,
  mockApiErrors 
} from '../fixtures';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('BanqueFranceAdapter', () => {
  let adapter: BanqueFranceAdapter;
  let mockCache: ReturnType<typeof createMockCache>;
  let mockRateLimiter: ReturnType<typeof createMockRateLimiter>;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env.BANQUE_FRANCE_API_KEY = 'test-api-key';
    
    mockCache = createMockCache();
    mockRateLimiter = createMockRateLimiter();
    
    adapter = new BanqueFranceAdapter({
      cache: mockCache,
      rateLimiter: mockRateLimiter
    });
  });

  afterEach(() => {
    delete process.env.BANQUE_FRANCE_API_KEY;
  });

  describe('constructor', () => {
    it('should initialize with API key from environment', () => {
      expect(adapter).toBeDefined();
    });

    it('should warn when API key is missing', () => {
      const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();
      delete process.env.BANQUE_FRANCE_API_KEY;
      
      new BanqueFranceAdapter({
        cache: mockCache,
        rateLimiter: mockRateLimiter
      });
      
      expect(consoleWarnSpy).toHaveBeenCalledWith('Banque de France API key not found in environment variables');
      consoleWarnSpy.mockRestore();
    });
  });

  describe('search', () => {
    const searchOptions = { maxResults: 10 };

    it('should search by SIREN number and return financial data', async () => {
      mockedAxios.get.mockResolvedValueOnce({
        data: {
          bilans: [{
            raisonSociale: mockCompanies.danone.name,
            formeJuridique: mockCompanies.danone.legalForm,
            adresse: mockCompanies.danone.address,
            activitePrincipale: mockCompanies.danone.activity,
            dateCreation: mockCompanies.danone.creationDate,
            situation: 'active'
          }]
        }
      });

      const results = await adapter.search(mockCompanies.danone.siren, searchOptions);

      expect(mockCache.get).toHaveBeenCalledWith(
        `banque-france:search:${mockCompanies.danone.siren}:{"maxResults":10}`
      );
      expect(mockRateLimiter.acquire).toHaveBeenCalledWith('banque-france');
      expect(mockedAxios.get).toHaveBeenCalledWith(
        `https://developer.webstat.banque-france.fr/api/entreprises/bilans/${mockCompanies.danone.siren}`,
        expect.objectContaining({
          headers: {
            Authorization: 'Bearer test-api-key',
            Accept: 'application/json'
          },
          params: {
            limit: 10
          }
        })
      );
      
      expect(results).toHaveLength(1);
      expect(results[0]).toMatchObject({
        siren: mockCompanies.danone.siren,
        name: mockCompanies.danone.name,
        status: 'active'
      });
      
      expect(mockCache.set).toHaveBeenCalledWith(
        `banque-france:search:${mockCompanies.danone.siren}:{"maxResults":10}`,
        results,
        3600
      );
    });

    it('should return empty array for text search (non-SIREN)', async () => {
      const results = await adapter.search('DANONE', searchOptions);

      expect(results).toEqual([]);
      expect(mockedAxios.get).not.toHaveBeenCalled();
      expect(mockRateLimiter.acquire).not.toHaveBeenCalled();
    });

    it('should return empty array when company not found (404)', async () => {
      mockedAxios.get.mockRejectedValueOnce({
        isAxiosError: true,
        response: { status: 404 }
      });

      const results = await adapter.search('999999999', searchOptions);

      expect(results).toEqual([]);
    });

    it('should handle API errors gracefully', async () => {
      mockedAxios.get.mockRejectedValueOnce({
        isAxiosError: true,
        response: {
          data: { message: 'Invalid authentication' }
        }
      });

      await expect(adapter.search(mockCompanies.danone.siren, searchOptions))
        .rejects.toThrow('Banque de France API error: Invalid authentication');
    });

    it('should return cached results when available', async () => {
      const cachedResults = [{ siren: '123456789', name: 'Cached Company' }];
      mockCache.get.mockResolvedValueOnce(cachedResults);

      const results = await adapter.search(mockCompanies.danone.siren, searchOptions);

      expect(results).toEqual(cachedResults);
      expect(mockedAxios.get).not.toHaveBeenCalled();
    });

    it('should handle empty response data', async () => {
      mockedAxios.get.mockResolvedValueOnce({
        data: { bilans: [] }
      });

      const results = await adapter.search(mockCompanies.danone.siren, searchOptions);

      expect(results).toEqual([]);
    });
  });

  describe('getDetails', () => {
    const detailsOptions = { includeFinancials: true };

    it('should get detailed financial information', async () => {
      // Mock financial statements call
      mockedAxios.get.mockImplementation((url) => {
        if (url.includes('/bilans/')) {
          return Promise.resolve({
            data: {
              bilans: [{
                companyName: mockCompanies.danone.name,
                revenue: mockBanqueFranceResponses.detailsResult.financials.current.turnover,
                employees: mockBanqueFranceResponses.detailsResult.financials.current.employees,
                year: 2023
              }]
            }
          });
        } else if (url.includes('/cotation/')) {
          return Promise.resolve({
            data: {
              cotation: '3++',
              dateCotation: '2024-01-15',
              score: 95
            }
          });
        } else if (url.includes('/incidents-paiement/')) {
          return Promise.resolve({
            data: { incidents: [] }
          });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      const details = await adapter.getDetails(mockCompanies.danone.siren, detailsOptions);

      expect(mockCache.get).toHaveBeenCalled();
      expect(mockRateLimiter.acquire).toHaveBeenCalledWith('banque-france');
      
      expect(details.basicInfo).toMatchObject({
        siren: mockCompanies.danone.siren,
        name: mockCompanies.danone.name,
        status: 'active'
      });

      expect(details.financials).toMatchObject({
        revenue: mockBanqueFranceResponses.detailsResult.financials.current.turnover,
        employees: mockBanqueFranceResponses.detailsResult.financials.current.employees,
        lastUpdate: '2023'
      });

      // Check extended financials
      const extendedFinancials = (details as any).extendedFinancials;
      expect(extendedFinancials.creditRating).toMatchObject({
        rating: '3++',
        riskLevel: 'Excellent'
      });
      expect(extendedFinancials.paymentIncidents).toEqual([]);
    });

    it('should handle details request without financials', async () => {
      const details = await adapter.getDetails(mockCompanies.danone.siren, {
        includeFinancials: false
      });

      expect(details.basicInfo.siren).toBe(mockCompanies.danone.siren);
      expect(details.financials).toBeUndefined();
      expect(mockedAxios.get).not.toHaveBeenCalled();
    });

    it('should handle missing financial data gracefully', async () => {
      mockedAxios.get.mockImplementation((url) => {
        if (url.includes('/bilans/')) {
          return Promise.reject({
            isAxiosError: true,
            response: { status: 404 }
          });
        } else if (url.includes('/cotation/') || url.includes('/incidents-paiement/')) {
          return Promise.reject({
            isAxiosError: true,
            response: { status: 404 }
          });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      const details = await adapter.getDetails(mockCompanies.danone.siren, detailsOptions);

      expect(details.basicInfo.siren).toBe(mockCompanies.danone.siren);
      expect(details.financials).toBeUndefined();
    });

    it('should return cached details when available', async () => {
      const cachedDetails = {
        basicInfo: { siren: '123456789', name: 'Cached Company' },
        financials: { revenue: 1000000 }
      };
      mockCache.get.mockResolvedValueOnce(cachedDetails);

      const details = await adapter.getDetails(mockCompanies.danone.siren, detailsOptions);

      expect(details).toEqual(cachedDetails);
      expect(mockedAxios.get).not.toHaveBeenCalled();
    });
  });

  describe('getStatus', () => {
    it('should return available status when API is accessible', async () => {
      mockedAxios.get.mockResolvedValueOnce({ data: { status: 'ok' } });
      mockRateLimiter.getStatus.mockResolvedValueOnce({
        remaining: 900,
        reset: new Date(Date.now() + 3600000)
      });

      const status = await adapter.getStatus();

      expect(mockedAxios.get).toHaveBeenCalledWith(
        'https://developer.webstat.banque-france.fr/api/health',
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
          remaining: 900
        }
      });
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

  describe('rating mapping', () => {
    it('should correctly map credit ratings to risk levels', async () => {
      const ratings = [
        { rating: '3++', expected: 'Excellent' },
        { rating: '3+', expected: 'Very Good' },
        { rating: '3', expected: 'Good' },
        { rating: '4+', expected: 'Satisfactory' },
        { rating: '4', expected: 'Fair' },
        { rating: '5+', expected: 'Weak' },
        { rating: '5', expected: 'Poor' },
        { rating: '6', expected: 'Very Poor' },
        { rating: '7', expected: 'Major Risk' },
        { rating: '8', expected: 'Threatened' },
        { rating: '9', expected: 'Payment Incidents' },
        { rating: 'X', expected: 'Unknown' }
      ];

      for (const testCase of ratings) {
        mockedAxios.get.mockImplementation((url) => {
          if (url.includes('/bilans/')) {
            return Promise.resolve({
              data: {
                bilans: [{
                  companyName: 'Test Company',
                  year: 2023
                }]
              }
            });
          } else if (url.includes('/cotation/')) {
            return Promise.resolve({
              data: {
                cotation: testCase.rating,
                dateCotation: '2024-01-15'
              }
            });
          } else if (url.includes('/incidents-paiement/')) {
            return Promise.resolve({ data: { incidents: [] } });
          }
          return Promise.reject(new Error('Unknown endpoint'));
        });

        const details = await adapter.getDetails('123456789', { includeFinancials: true });
        const extendedFinancials = (details as any).extendedFinancials;
        
        expect(extendedFinancials.creditRating.riskLevel).toBe(testCase.expected);
      }
    });
  });

  describe('address formatting', () => {
    it('should format structured address correctly', async () => {
      mockedAxios.get.mockResolvedValueOnce({
        data: {
          bilans: [{
            raisonSociale: 'Test Company',
            adresse: {
              numero: '17',
              voie: 'Boulevard Haussmann',
              codePostal: '75009',
              ville: 'Paris'
            }
          }]
        }
      });

      const results = await adapter.search('123456789', {});
      expect(results[0].address).toBe('17 Boulevard Haussmann 75009 Paris');
    });

    it('should handle string address', async () => {
      mockedAxios.get.mockResolvedValueOnce({
        data: {
          bilans: [{
            raisonSociale: 'Test Company',
            adresse: '17 Boulevard Haussmann 75009 Paris'
          }]
        }
      });

      const results = await adapter.search('123456789', {});
      expect(results[0].address).toBe('17 Boulevard Haussmann 75009 Paris');
    });

    it('should handle missing address', async () => {
      mockedAxios.get.mockResolvedValueOnce({
        data: {
          bilans: [{
            raisonSociale: 'Test Company',
            adresse: null
          }]
        }
      });

      const results = await adapter.search('123456789', {});
      expect(results[0].address).toBe('');
    });
  });
});