import { describe, it, expect, beforeEach, jest } from "@jest/globals";
import axios from "axios";
import { BanqueFranceAdapter } from "../banque-france.js";
import type { AdapterConfig } from "../index.js";

jest.mock("axios");
const mockedAxios = jest.mocked(axios);

describe("BanqueFranceAdapter", () => {
  let adapter: BanqueFranceAdapter;
  let mockConfig: AdapterConfig;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env.BANQUE_FRANCE_API_KEY = "test-api-key";

    mockConfig = {
      rateLimiter: {
        acquire: jest.fn().mockResolvedValue(undefined),
        getStatus: jest.fn().mockResolvedValue({
          remaining: 100,
          reset: new Date()
        })
      },
      cache: {
        get: jest.fn().mockResolvedValue(null),
        set: jest.fn().mockResolvedValue(undefined)
      }
    } as any;

    adapter = new BanqueFranceAdapter(mockConfig);
  });

  describe("search", () => {
    it("should return empty array for non-SIREN queries", async () => {
      const result = await adapter.search("Test Company", {});
      
      expect(result).toEqual([]);
      expect(mockedAxios.get).not.toHaveBeenCalled();
    });

    it("should search by SIREN and return results", async () => {
      const mockResponse = {
        data: {
          bilans: [{
            raisonSociale: "TEST COMPANY SAS",
            formeJuridique: "SAS",
            adresse: {
              numero: "123",
              voie: "RUE DE LA PAIX",
              codePostal: "75001",
              ville: "PARIS"
            },
            activitePrincipale: "62.01Z",
            dateCreation: "2020-01-15",
            situation: "active"
          }]
        }
      };

      mockedAxios.get.mockResolvedValue(mockResponse);

      const result = await adapter.search("123456789", { maxResults: 5 });

      expect(mockConfig.rateLimiter.acquire).toHaveBeenCalledWith("banque-france");
      expect(mockedAxios.get).toHaveBeenCalledWith(
        "https://developer.webstat.banque-france.fr/api/entreprises/bilans/123456789",
        {
          headers: {
            "Authorization": "Bearer test-api-key",
            "Accept": "application/json"
          },
          params: {
            limit: 5
          }
        }
      );

      expect(result).toHaveLength(1);
      expect(result[0]).toEqual({
        siren: "123456789",
        name: "TEST COMPANY SAS",
        legalForm: "SAS",
        address: "123 RUE DE LA PAIX 75001 PARIS",
        activity: "62.01Z",
        creationDate: "2020-01-15",
        status: "active"
      });
    });

    it("should handle 404 errors gracefully", async () => {
      mockedAxios.get.mockRejectedValue({
        isAxiosError: true,
        response: { status: 404 }
      });

      const result = await adapter.search("999999999", {});
      
      expect(result).toEqual([]);
    });

    it("should use cached results when available", async () => {
      const cachedResults = [{
        siren: "123456789",
        name: "CACHED COMPANY"
      }];

      mockConfig.cache.get = jest.fn().mockResolvedValue(cachedResults);

      const result = await adapter.search("123456789", {});

      expect(result).toEqual(cachedResults);
      expect(mockedAxios.get).not.toHaveBeenCalled();
    });
  });

  describe("getDetails", () => {
    it("should get company details with financial information", async () => {
      const mockFinancialStatements = [{
        companyName: "TEST COMPANY SAS",
        year: 2023,
        revenue: 1000000,
        employees: 50
      }];

      const mockCreditRating = {
        cotation: "4+",
        dateCotation: "2024-01-15",
        score: 75
      };

      const mockPaymentIncidents = [{
        date: "2023-06-01",
        amount: 5000,
        type: "late_payment",
        status: "resolved"
      }];

      mockedAxios.get.mockImplementation((url) => {
        if (url.includes("/bilans/")) {
          return Promise.resolve({ data: { bilans: mockFinancialStatements } });
        } else if (url.includes("/cotation/")) {
          return Promise.resolve({ data: mockCreditRating });
        } else if (url.includes("/incidents-paiement/")) {
          return Promise.resolve({ data: { incidents: mockPaymentIncidents } });
        }
        return Promise.reject(new Error("Unknown endpoint"));
      });

      const result = await adapter.getDetails("123456789", { includeFinancials: true });

      expect(result.basicInfo.siren).toBe("123456789");
      expect(result.basicInfo.name).toBe("TEST COMPANY SAS");
      expect(result.financials).toEqual({
        revenue: 1000000,
        employees: 50,
        lastUpdate: "2023"
      });

      const extendedFinancials = (result as any).extendedFinancials;
      expect(extendedFinancials.statements).toEqual(mockFinancialStatements);
      expect(extendedFinancials.creditRating).toEqual({
        rating: "4+",
        date: "2024-01-15",
        score: 75,
        riskLevel: "Satisfactory"
      });
      expect(extendedFinancials.paymentIncidents).toEqual(mockPaymentIncidents);
    });

    it("should handle missing financial data", async () => {
      mockedAxios.get.mockImplementation((url) => {
        if (url.includes("/bilans/")) {
          return Promise.reject({ isAxiosError: true, response: { status: 404 } });
        } else if (url.includes("/cotation/")) {
          return Promise.reject({ isAxiosError: true, response: { status: 404 } });
        } else if (url.includes("/incidents-paiement/")) {
          return Promise.reject({ isAxiosError: true, response: { status: 404 } });
        }
        return Promise.reject(new Error("Unknown endpoint"));
      });

      const result = await adapter.getDetails("999999999", { includeFinancials: true });

      expect(result.basicInfo.siren).toBe("999999999");
      expect(result.basicInfo.name).toBe("");
      expect(result.financials).toBeUndefined();
    });
  });

  describe("getStatus", () => {
    it("should return available status when API is reachable", async () => {
      mockedAxios.get.mockResolvedValue({ data: { status: "ok" } });

      const status = await adapter.getStatus();

      expect(mockedAxios.get).toHaveBeenCalledWith(
        "https://developer.webstat.banque-france.fr/api/health",
        {
          headers: {
            "Authorization": "Bearer test-api-key",
            "Accept": "application/json"
          }
        }
      );

      expect(status.available).toBe(true);
      expect(status.rateLimit).toBeDefined();
      expect(status.lastCheck).toBeInstanceOf(Date);
    });

    it("should return unavailable status when API is unreachable", async () => {
      mockedAxios.get.mockRejectedValue(new Error("Network error"));

      const status = await adapter.getStatus();

      expect(status.available).toBe(false);
      expect(status.lastCheck).toBeInstanceOf(Date);
    });
  });

  describe("rating mapping", () => {
    it("should correctly map credit ratings to risk levels", async () => {
      const ratings = [
        { cotation: "3++", expected: "Excellent" },
        { cotation: "3+", expected: "Very Good" },
        { cotation: "3", expected: "Good" },
        { cotation: "4+", expected: "Satisfactory" },
        { cotation: "4", expected: "Fair" },
        { cotation: "5+", expected: "Weak" },
        { cotation: "5", expected: "Poor" },
        { cotation: "6", expected: "Very Poor" },
        { cotation: "7", expected: "Major Risk" },
        { cotation: "8", expected: "Threatened" },
        { cotation: "9", expected: "Payment Incidents" },
        { cotation: "X", expected: "Unknown" }
      ];

      for (const { cotation, expected } of ratings) {
        mockedAxios.get.mockImplementation((url) => {
          if (url.includes("/bilans/")) {
            return Promise.resolve({ data: { bilans: [{ companyName: "TEST" }] } });
          } else if (url.includes("/cotation/")) {
            return Promise.resolve({ data: { cotation, dateCotation: "2024-01-01" } });
          } else {
            return Promise.resolve({ data: { incidents: [] } });
          }
        });

        const result = await adapter.getDetails("123456789", { includeFinancials: true });
        const creditRating = (result as any).extendedFinancials.creditRating;
        
        expect(creditRating.riskLevel).toBe(expected);
      }
    });
  });
});