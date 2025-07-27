import { INPIAdapter } from '../../src/adapters/inpi';
import axios from 'axios';
import { 
  mockCompanies, 
  mockINPIResponses, 
  createMockCache, 
  createMockRateLimiter,
  mockApiErrors 
} from '../fixtures';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('INPIAdapter', () => {
  let adapter: INPIAdapter;
  let mockCache: ReturnType<typeof createMockCache>;
  let mockRateLimiter: ReturnType<typeof createMockRateLimiter>;
  let mockAxiosInstance: any;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env.INPI_USERNAME = 'test-user';
    process.env.INPI_PASSWORD = 'test-pass';
    
    mockCache = createMockCache();
    mockRateLimiter = createMockRateLimiter();
    
    // Mock axios.create to return a mock instance
    mockAxiosInstance = {
      get: jest.fn(),
      post: jest.fn(),
      defaults: { headers: {} }
    };
    
    (axios.create as jest.Mock) = jest.fn(() => mockAxiosInstance);
    
    adapter = new INPIAdapter({
      cache: mockCache,
      rateLimiter: mockRateLimiter
    });
  });

  afterEach(() => {
    delete process.env.INPI_USERNAME;
    delete process.env.INPI_PASSWORD;
  });

  describe('constructor', () => {
    it('should initialize with credentials from environment', () => {
      expect(adapter).toBeDefined();
      expect(axios.create).toHaveBeenCalledWith({
        baseURL: 'https://registre-national-entreprises.inpi.fr',
        timeout: 30000,
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json'
        }
      });
    });

    it('should warn when credentials are missing', () => {
      const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();
      delete process.env.INPI_USERNAME;
      delete process.env.INPI_PASSWORD;
      
      new INPIAdapter({
        cache: mockCache,
        rateLimiter: mockRateLimiter
      });
      
      expect(consoleWarnSpy).toHaveBeenCalledWith('INPI credentials not found in environment variables');
      consoleWarnSpy.mockRestore();
    });
  });

  describe('authentication', () => {
    it('should authenticate and cache token', async () => {
      const mockAuthResponse = {
        data: {
          access_token: 'test-token-12345',
          token_type: 'Bearer',
          expires_in: 3600
        }
      };

      mockedAxios.post.mockResolvedValueOnce(mockAuthResponse);
      mockAxiosInstance.get.mockResolvedValueOnce({
        data: { companies: [] }
      });

      await adapter.search('DANONE', {});

      expect(mockedAxios.post).toHaveBeenCalledWith(
        'https://registre-national-entreprises.inpi.fr/api/sso/login',
        {
          username: 'test-user',
          password: 'test-pass'
        }
      );

      expect(mockCache.set).toHaveBeenCalledWith(
        'inpi:auth:token',
        expect.objectContaining({
          token: 'test-token-12345',
          expiry: expect.any(String)
        }),
        expect.any(Number)
      );
    });

    it('should use cached authentication token', async () => {
      const futureDate = new Date(Date.now() + 3600000);
      mockCache.get.mockImplementation((key) => {
        if (key === 'inpi:auth:token') {
          return Promise.resolve({
            token: 'cached-token',
            expiry: futureDate.toISOString()
          });
        }
        return Promise.resolve(undefined);
      });

      mockAxiosInstance.get.mockResolvedValueOnce({
        data: { companies: [] }
      });

      await adapter.search('DANONE', {});

      expect(mockedAxios.post).not.toHaveBeenCalled();
      expect(mockAxiosInstance.get).toHaveBeenCalledWith(
        '/api/companies',
        expect.objectContaining({
          headers: {
            Authorization: 'Bearer cached-token'
          }
        })
      );
    });

    it('should re-authenticate when token is expired', async () => {
      const pastDate = new Date(Date.now() - 3600000);
      mockCache.get.mockImplementation((key) => {
        if (key === 'inpi:auth:token') {
          return Promise.resolve({
            token: 'expired-token',
            expiry: pastDate.toISOString()
          });
        }
        return Promise.resolve(undefined);
      });

      mockedAxios.post.mockResolvedValueOnce({
        data: {
          access_token: 'new-token',
          token_type: 'Bearer',
          expires_in: 3600
        }
      });

      mockAxiosInstance.get.mockResolvedValueOnce({
        data: { companies: [] }
      });

      await adapter.search('DANONE', {});

      expect(mockedAxios.post).toHaveBeenCalled();
    });

    it('should handle authentication errors', async () => {
      mockedAxios.post.mockRejectedValueOnce({
        isAxiosError: true,
        response: {
          data: { message: 'Invalid credentials' }
        }
      });

      await expect(adapter.search('DANONE', {}))
        .rejects.toThrow('INPI authentication failed: Invalid credentials');
    });
  });

  describe('search', () => {
    const searchOptions = { maxResults: 10 };

    beforeEach(() => {
      // Mock successful authentication
      mockedAxios.post.mockResolvedValueOnce({
        data: {
          access_token: 'test-token',
          token_type: 'Bearer',
          expires_in: 3600
        }
      });
    });

    it('should search by company name', async () => {
      mockAxiosInstance.get.mockResolvedValueOnce({
        data: {
          companies: [{
            siren: mockCompanies.danone.siren,
            denomination: mockCompanies.danone.name,
            formeJuridique: mockCompanies.danone.legalForm,
            adresse: '17 BOULEVARD HAUSSMANN',
            codePostal: '75009',
            ville: 'PARIS',
            codeCategory: mockCompanies.danone.activity,
            dateCreation: mockCompanies.danone.creationDate,
            statut: 'ACTIF'
          }]
        }
      });

      const results = await adapter.search('DANONE', searchOptions);

      expect(mockRateLimiter.acquire).toHaveBeenCalledWith('inpi');
      expect(mockAxiosInstance.get).toHaveBeenCalledWith(
        '/api/companies',
        expect.objectContaining({
          params: {
            companyName: 'DANONE',
            pageSize: 10
          }
        })
      );

      expect(results).toHaveLength(1);
      expect(results[0]).toMatchObject({
        siren: mockCompanies.danone.siren,
        name: mockCompanies.danone.name,
        legalForm: mockCompanies.danone.legalForm,
        status: 'actif'
      });
    });

    it('should search by SIREN number', async () => {
      mockAxiosInstance.get.mockResolvedValueOnce({
        data: {
          companies: [{
            siren: mockCompanies.danone.siren,
            denomination: mockCompanies.danone.name
          }]
        }
      });

      await adapter.search(mockCompanies.danone.siren, searchOptions);

      expect(mockAxiosInstance.get).toHaveBeenCalledWith(
        '/api/companies',
        expect.objectContaining({
          params: {
            'siren[]': mockCompanies.danone.siren,
            pageSize: 10
          }
        })
      );
    });

    it('should return cached results when available', async () => {
      const cachedResults = [{ siren: '123456789', name: 'Cached Company' }];
      mockCache.get.mockResolvedValueOnce(cachedResults);

      const results = await adapter.search('DANONE', searchOptions);

      expect(results).toEqual(cachedResults);
      expect(mockAxiosInstance.get).not.toHaveBeenCalled();
    });

    it('should handle rate limit errors', async () => {
      mockAxiosInstance.get.mockRejectedValueOnce({
        isAxiosError: true,
        response: { status: 429 }
      });

      await expect(adapter.search('DANONE', searchOptions))
        .rejects.toThrow('INPI API rate limit exceeded. Please try again later.');
    });

    it('should handle empty results', async () => {
      mockAxiosInstance.get.mockResolvedValueOnce({
        data: { companies: [] }
      });

      const results = await adapter.search('NONEXISTENT', searchOptions);

      expect(results).toEqual([]);
    });
  });

  describe('getDetails', () => {
    const detailsOptions = { includeIntellectualProperty: true };

    beforeEach(() => {
      // Mock successful authentication
      mockedAxios.post.mockResolvedValueOnce({
        data: {
          access_token: 'test-token',
          token_type: 'Bearer',
          expires_in: 3600
        }
      });
    });

    it('should get company details with intellectual property', async () => {
      mockAxiosInstance.get
        .mockResolvedValueOnce({
          data: {
            siren: mockCompanies.danone.siren,
            denomination: mockCompanies.danone.name,
            formeJuridique: mockCompanies.danone.legalForm,
            capitalSocial: mockCompanies.danone.capital,
            effectif: 95947
          }
        })
        .mockResolvedValueOnce({
          data: {
            attachments: [
              { nomDocument: 'Dépôt de marque DANONE', type: 'ACTE' },
              { typeDocument: 'MARQUE', type: 'ACTE' },
              { nomDocument: 'Brevet fermentation', type: 'ACTE' },
              { nomDocument: 'Dessin bouteille', type: 'ACTE' }
            ]
          }
        });

      const details = await adapter.getDetails(mockCompanies.danone.siren, detailsOptions);

      expect(mockRateLimiter.acquire).toHaveBeenCalledWith('inpi');
      
      expect(details.basicInfo).toMatchObject({
        siren: mockCompanies.danone.siren,
        name: mockCompanies.danone.name
      });

      expect(details.financials).toMatchObject({
        revenue: mockCompanies.danone.capital,
        employees: 95947
      });

      expect(details.intellectualProperty).toEqual({
        trademarks: 2,
        patents: 1,
        designs: 1
      });
    });

    it('should get details without intellectual property', async () => {
      mockAxiosInstance.get.mockResolvedValueOnce({
        data: {
          siren: mockCompanies.danone.siren,
          denomination: mockCompanies.danone.name
        }
      });

      const details = await adapter.getDetails(mockCompanies.danone.siren, {
        includeIntellectualProperty: false
      });

      expect(details.intellectualProperty).toBeUndefined();
      // Should only make one API call (company details)
      expect(mockAxiosInstance.get).toHaveBeenCalledTimes(1);
    });

    it('should handle missing attachments gracefully', async () => {
      const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();
      
      mockAxiosInstance.get
        .mockResolvedValueOnce({
          data: {
            siren: mockCompanies.danone.siren,
            denomination: mockCompanies.danone.name
          }
        })
        .mockRejectedValueOnce(new Error('Attachments not available'));

      const details = await adapter.getDetails(mockCompanies.danone.siren, detailsOptions);

      expect(details.intellectualProperty).toBeUndefined();
      expect(consoleWarnSpy).toHaveBeenCalled();
      consoleWarnSpy.mockRestore();
    });
  });

  describe('getStatus', () => {
    it('should return available status when API is accessible', async () => {
      mockedAxios.post.mockResolvedValueOnce({
        data: {
          access_token: 'test-token',
          token_type: 'Bearer',
          expires_in: 3600
        }
      });

      mockAxiosInstance.get.mockResolvedValueOnce({
        data: { companies: [] }
      });

      mockRateLimiter.getStatus.mockResolvedValueOnce({
        remaining: 800,
        reset: new Date(Date.now() + 3600000)
      });

      const status = await adapter.getStatus();

      expect(status).toMatchObject({
        available: true,
        rateLimit: {
          remaining: 800
        }
      });
    });

    it('should return unavailable status when API is not accessible', async () => {
      mockedAxios.post.mockRejectedValueOnce(mockApiErrors.networkError);

      const status = await adapter.getStatus();

      expect(status).toMatchObject({
        available: false
      });
      expect(status.lastCheck).toBeInstanceOf(Date);
    });
  });

  describe('getBeneficialOwners', () => {
    beforeEach(() => {
      mockedAxios.post.mockResolvedValueOnce({
        data: {
          access_token: 'test-token',
          token_type: 'Bearer',
          expires_in: 3600
        }
      });
    });

    it('should get beneficial owners information', async () => {
      mockAxiosInstance.get.mockResolvedValueOnce({
        data: {
          representants: [
            {
              nom: 'Jean Dupont',
              role: 'Président',
              dateNaissance: '1965-05-15'
            },
            {
              nom: 'Société Holding',
              role: 'Actionnaire principal',
              entreprise: {
                siren: '123456789',
                denomination: 'Holding SA'
              }
            }
          ]
        }
      });

      const owners = await adapter.getBeneficialOwners(mockCompanies.danone.siren);

      expect(owners).toHaveLength(2);
      expect(owners[0]).toMatchObject({
        name: 'Jean Dupont',
        role: 'Président',
        isCompany: false
      });
      expect(owners[1]).toMatchObject({
        name: 'Société Holding',
        isCompany: true,
        companySiren: '123456789'
      });
    });
  });

  describe('getCompanyPublications', () => {
    beforeEach(() => {
      mockedAxios.post.mockResolvedValueOnce({
        data: {
          access_token: 'test-token',
          token_type: 'Bearer',
          expires_in: 3600
        }
      });
    });

    it('should get company publications with filtering', async () => {
      mockAxiosInstance.get.mockResolvedValueOnce({
        data: {
          attachments: [
            {
              id: '1',
              type: 'BILAN',
              dateDepot: '2023-06-15',
              confidentiel: false,
              nomDocument: 'Bilan 2022',
              url: '/download/1'
            },
            {
              id: '2',
              type: 'ACTE',
              dateDepot: '2023-03-10',
              confidentiel: true,
              nomDocument: 'Procès verbal AGO'
            },
            {
              id: '3',
              type: 'BILAN',
              dateDepot: '2022-06-15',
              confidentiel: false,
              nomDocument: 'Bilan 2021',
              url: '/download/3'
            }
          ]
        }
      });

      const publications = await adapter.getCompanyPublications(
        mockCompanies.danone.siren,
        {
          type: 'BILAN',
          includeConfidential: false
        }
      );

      expect(publications).toHaveLength(2);
      expect(publications[0].type).toBe('BILAN');
      expect(publications[0].confidential).toBe(false);
      expect(publications[0].downloadUrl).toBeDefined();
      // Should be sorted by date descending
      expect(new Date(publications[0].date).getTime())
        .toBeGreaterThan(new Date(publications[1].date).getTime());
    });

    it('should filter by date range', async () => {
      mockAxiosInstance.get.mockResolvedValueOnce({
        data: {
          attachments: [
            {
              id: '1',
              type: 'BILAN',
              dateDepot: '2023-06-15',
              confidentiel: false
            },
            {
              id: '2',
              type: 'BILAN',
              dateDepot: '2022-06-15',
              confidentiel: false
            }
          ]
        }
      });

      const publications = await adapter.getCompanyPublications(
        mockCompanies.danone.siren,
        {
          from: new Date('2023-01-01'),
          to: new Date('2023-12-31')
        }
      );

      expect(publications).toHaveLength(1);
      expect(publications[0].id).toBe('1');
    });
  });

  describe('getDifferentialUpdates', () => {
    beforeEach(() => {
      mockedAxios.post.mockResolvedValueOnce({
        data: {
          access_token: 'test-token',
          token_type: 'Bearer',
          expires_in: 3600
        }
      });
    });

    it('should get differential updates with pagination', async () => {
      mockAxiosInstance.get.mockResolvedValueOnce({
        data: {
          companies: [
            {
              siren: '123456789',
              denomination: 'New Company',
              dateImmatriculation: new Date().toISOString()
            },
            {
              siren: '987654321',
              denomination: 'Updated Company'
            },
            {
              siren: '555555555',
              denomination: 'Closed Company',
              dateRadiation: '2024-01-01'
            }
          ],
          searchAfter: 'next-cursor-123'
        }
      });

      const result = await adapter.getDifferentialUpdates({
        from: new Date('2024-01-01'),
        to: new Date('2024-01-31'),
        pageSize: 50
      });

      expect(mockAxiosInstance.get).toHaveBeenCalledWith(
        '/api/companies/diff',
        expect.objectContaining({
          params: {
            from: '2024-01-01',
            to: '2024-01-31',
            pageSize: 50
          }
        })
      );

      expect(result.companies).toHaveLength(3);
      expect(result.companies[0].updateType).toBe('CREATION');
      expect(result.companies[1].updateType).toBe('MODIFICATION');
      expect(result.companies[2].updateType).toBe('RADIATION');
      expect(result.nextCursor).toBe('next-cursor-123');
    });
  });

  describe('status determination', () => {
    beforeEach(() => {
      mockedAxios.post.mockResolvedValueOnce({
        data: {
          access_token: 'test-token',
          token_type: 'Bearer',
          expires_in: 3600
        }
      });
    });

    it('should correctly determine company status', async () => {
      const testCases = [
        { dateRadiation: '2024-01-01', statut: null, expected: 'radié' },
        { dateRadiation: null, statut: 'ACTIF', expected: 'actif' },
        { dateRadiation: null, statut: 'EN LIQUIDATION', expected: 'en liquidation' },
        { dateRadiation: null, statut: null, expected: 'actif' }
      ];

      for (const testCase of testCases) {
        mockAxiosInstance.get.mockResolvedValueOnce({
          data: {
            companies: [{
              siren: '123456789',
              denomination: 'Test Company',
              dateRadiation: testCase.dateRadiation,
              statut: testCase.statut
            }]
          }
        });

        const results = await adapter.search('123456789', {});
        expect(results[0].status).toBe(testCase.expected);
      }
    });
  });
});