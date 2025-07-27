import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import axios from 'axios';
import { INPIAdapter } from '../inpi.js';
import type { AdapterConfig } from '../index.js';

jest.mock('axios');

describe('INPIAdapter', () => {
  let adapter: INPIAdapter;
  let mockConfig: AdapterConfig;

  beforeEach(() => {
    jest.clearAllMocks();
    
    mockConfig = {
      rateLimiter: {
        acquire: jest.fn().mockResolvedValue(undefined),
        getStatus: jest.fn().mockResolvedValue({ remaining: 100, reset: new Date() })
      },
      cache: {
        get: jest.fn().mockResolvedValue(null),
        set: jest.fn().mockResolvedValue(undefined)
      }
    } as any;

    process.env.INPI_USERNAME = 'test@example.com';
    process.env.INPI_PASSWORD = 'testpassword';

    adapter = new INPIAdapter(mockConfig);
  });

  describe('authentication', () => {
    it('should authenticate and cache token', async () => {
      const mockAuthResponse = {
        data: {
          access_token: 'test-token',
          token_type: 'Bearer',
          expires_in: 3600
        }
      };

      jest.mocked(axios.post).mockResolvedValueOnce(mockAuthResponse);
      jest.mocked(axios.create).mockReturnValue({
        get: jest.fn().mockResolvedValue({ data: { companies: [] } })
      } as any);

      await adapter.search('test', {});

      expect(axios.post).toHaveBeenCalledWith(
        'https://registre-national-entreprises.inpi.fr/api/sso/login',
        {
          username: 'test@example.com',
          password: 'testpassword'
        }
      );

      expect(mockConfig.cache.set).toHaveBeenCalledWith(
        'inpi:auth:token',
        expect.objectContaining({
          token: 'test-token',
          expiry: expect.any(String)
        }),
        expect.any(Number)
      );
    });
  });

  describe('search', () => {
    beforeEach(() => {
      // Mock authentication
      jest.mocked(axios.post).mockResolvedValue({
        data: {
          access_token: 'test-token',
          token_type: 'Bearer',
          expires_in: 3600
        }
      });
    });

    it('should search by SIREN', async () => {
      const mockCompanies = [{
        siren: '123456789',
        denomination: 'Test Company',
        formeJuridique: 'SAS',
        adresse: '123 Test Street',
        codePostal: '75001',
        ville: 'Paris'
      }];

      jest.mocked(axios.create).mockReturnValue({
        get: jest.fn().mockResolvedValue({ data: { companies: mockCompanies } })
      } as any);

      const results = await adapter.search('123456789', {});

      expect(results).toHaveLength(1);
      expect(results[0]).toEqual({
        siren: '123456789',
        name: 'Test Company',
        legalForm: 'SAS',
        address: '123 Test Street 75001 Paris',
        activity: undefined,
        creationDate: undefined,
        status: 'actif'
      });
    });

    it('should search by company name', async () => {
      const mockCompanies = [{
        siren: '987654321',
        denomination: 'Another Company',
        formeJuridique: 'SARL'
      }];

      jest.mocked(axios.create).mockReturnValue({
        get: jest.fn().mockResolvedValue({ data: { companies: mockCompanies } })
      } as any);

      const results = await adapter.search('Another Company', { maxResults: 5 });

      expect(results).toHaveLength(1);
      expect(mockConfig.cache.set).toHaveBeenCalledWith(
        expect.stringContaining('inpi:search:'),
        results,
        3600
      );
    });
  });

  describe('getDetails', () => {
    beforeEach(() => {
      // Mock authentication
      jest.mocked(axios.post).mockResolvedValue({
        data: {
          access_token: 'test-token',
          token_type: 'Bearer',
          expires_in: 3600
        }
      });
    });

    it('should get company details with intellectual property', async () => {
      const mockCompany = {
        siren: '123456789',
        denomination: 'Test Company',
        capitalSocial: 100000,
        effectif: 50
      };

      const mockAttachments = {
        attachments: [
          { id: '1', type: 'BILAN', nomDocument: 'Marque déposée', confidentiel: false },
          { id: '2', type: 'ACTE', typeDocument: 'Brevet', confidentiel: false }
        ]
      };

      const mockAxios = {
        get: jest.fn()
          .mockResolvedValueOnce({ data: mockCompany })
          .mockResolvedValueOnce({ data: mockAttachments })
      };

      jest.mocked(axios.create).mockReturnValue(mockAxios as any);

      const details = await adapter.getDetails('123456789', { includeIntellectualProperty: true });

      expect(details.basicInfo.siren).toBe('123456789');
      expect(details.financials).toEqual({
        revenue: 100000,
        employees: 50,
        lastUpdate: expect.any(String)
      });
      expect(details.intellectualProperty).toEqual({
        trademarks: 1,
        patents: 1,
        designs: 0
      });
    });
  });

  describe('getBeneficialOwners', () => {
    beforeEach(() => {
      // Mock authentication
      jest.mocked(axios.post).mockResolvedValue({
        data: {
          access_token: 'test-token',
          token_type: 'Bearer',
          expires_in: 3600
        }
      });
    });

    it('should get beneficial owners', async () => {
      const mockCompany = {
        siren: '123456789',
        representants: [
          {
            nom: 'John Doe',
            role: 'Président',
            dateNaissance: '1980-01-01'
          },
          {
            nom: 'Company Holdings',
            role: 'Actionnaire',
            entreprise: {
              siren: '987654321',
              denomination: 'Holding Company'
            }
          }
        ]
      };

      jest.mocked(axios.create).mockReturnValue({
        get: jest.fn().mockResolvedValue({ data: mockCompany })
      } as any);

      const owners = await adapter.getBeneficialOwners('123456789');

      expect(owners).toHaveLength(2);
      expect(owners[0]).toEqual({
        name: 'John Doe',
        role: 'Président',
        birthDate: '1980-01-01',
        isCompany: false,
        companySiren: undefined
      });
      expect(owners[1]).toEqual({
        name: 'Company Holdings',
        role: 'Actionnaire',
        birthDate: undefined,
        isCompany: true,
        companySiren: '987654321'
      });
    });
  });

  describe('getCompanyPublications', () => {
    beforeEach(() => {
      // Mock authentication
      jest.mocked(axios.post).mockResolvedValue({
        data: {
          access_token: 'test-token',
          token_type: 'Bearer',
          expires_in: 3600
        }
      });
    });

    it('should get filtered company publications', async () => {
      const mockAttachments = {
        attachments: [
          {
            id: '1',
            type: 'BILAN',
            nomDocument: 'Bilan 2023',
            dateDepot: '2024-01-15',
            confidentiel: false,
            url: '/api/bilans/1/download'
          },
          {
            id: '2',
            type: 'ACTE',
            nomDocument: 'Statuts mis à jour',
            dateDepot: '2024-02-01',
            confidentiel: true,
            url: '/api/actes/2/download'
          },
          {
            id: '3',
            type: 'BILAN',
            nomDocument: 'Bilan 2022',
            dateDepot: '2023-01-15',
            confidentiel: false,
            url: '/api/bilans/3/download'
          }
        ]
      };

      jest.mocked(axios.create).mockReturnValue({
        get: jest.fn().mockResolvedValue({ data: mockAttachments })
      } as any);

      const publications = await adapter.getCompanyPublications('123456789', {
        type: 'BILAN',
        includeConfidential: false,
        from: new Date('2023-06-01')
      });

      expect(publications).toHaveLength(1);
      expect(publications[0]).toEqual({
        id: '1',
        type: 'BILAN',
        name: 'Bilan 2023',
        date: '2024-01-15',
        confidential: false,
        downloadUrl: 'https://registre-national-entreprises.inpi.fr/api/bilans/1/download'
      });
    });
  });

  describe('getStatus', () => {
    it('should return available status when API is accessible', async () => {
      jest.mocked(axios.post).mockResolvedValue({
        data: {
          access_token: 'test-token',
          token_type: 'Bearer',
          expires_in: 3600
        }
      });

      jest.mocked(axios.create).mockReturnValue({
        get: jest.fn().mockResolvedValue({ data: { companies: [] } })
      } as any);

      const status = await adapter.getStatus();

      expect(status.available).toBe(true);
      expect(status.rateLimit).toBeDefined();
      expect(status.lastCheck).toBeInstanceOf(Date);
    });

    it('should return unavailable status when API fails', async () => {
      jest.mocked(axios.post).mockRejectedValue(new Error('Network error'));

      const status = await adapter.getStatus();

      expect(status.available).toBe(false);
      expect(status.lastCheck).toBeInstanceOf(Date);
    });
  });
});