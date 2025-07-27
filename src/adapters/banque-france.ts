import axios from "axios";
import type { 
  BaseAdapter, 
  AdapterConfig, 
  SearchOptions, 
  DetailsOptions, 
  SearchResult, 
  EnterpriseDetails, 
  AdapterStatus 
} from "./index.js";

// interface BanqueFranceFinancialStatement {
//   year: number;
//   revenue?: number;
//   netIncome?: number;
//   totalAssets?: number;
//   equity?: number;
//   debt?: number;
//   employees?: number;
// }

interface BanqueFranceCreditRating {
  rating: string;
  date: string;
  score?: number;
  riskLevel?: string;
}

interface BanqueFrancePaymentIncident {
  date: string;
  amount: number;
  type: string;
  status: string;
}

export class BanqueFranceAdapter implements BaseAdapter {
  private readonly baseUrl = "https://developer.webstat.banque-france.fr/api";
  private readonly apiKey: string;
  private readonly rateLimiter: AdapterConfig["rateLimiter"];
  private readonly cache: AdapterConfig["cache"];

  constructor(config: AdapterConfig) {
    this.rateLimiter = config.rateLimiter;
    this.cache = config.cache;
    this.apiKey = process.env['BANQUE_FRANCE_API_KEY'] || "";
    
    if (!this.apiKey) {
      console.warn("Banque de France API key not found in environment variables");
    }
  }

  async search(query: string, options: SearchOptions): Promise<SearchResult[]> {
    const cacheKey = `banque-france:search:${query}:${JSON.stringify(options)}`;
    
    // Check cache first
    const cached = await this.cache.get(cacheKey);
    if (cached) {
      return cached as SearchResult[];
    }

    // Apply rate limiting
    await this.rateLimiter.acquire("banque-france");

    try {
      // Check if query is a SIREN number
      const isSiren = /^\d{9}$/.test(query);
      
      if (!isSiren) {
        // Banque de France primarily works with SIREN numbers
        // For text search, we return empty array as this API focuses on financial data by SIREN
        return [];
      }

      // Get financial statements for the company
      const response = await axios.get(`${this.baseUrl}/entreprises/bilans/${query}`, {
        headers: {
          "Authorization": `Bearer ${this.apiKey}`,
          "Accept": "application/json"
        },
        params: {
          limit: options.maxResults || 10
        }
      });

      const results = this.transformSearchResults(response.data, query);
      
      // Cache the results for 1 hour
      await this.cache.set(cacheKey, results, 3600);
      
      return results;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        if (error.response?.status === 404) {
          // Company not found in Banque de France database
          return [];
        }
        throw new Error(`Banque de France API error: ${error.response?.data?.message || error.message}`);
      }
      throw error;
    }
  }

  async getDetails(siren: string, options: DetailsOptions): Promise<EnterpriseDetails> {
    const cacheKey = `banque-france:details:${siren}:${JSON.stringify(options)}`;
    
    // Check cache first
    const cached = await this.cache.get(cacheKey);
    if (cached) {
      return cached as EnterpriseDetails;
    }

    // Apply rate limiting
    await this.rateLimiter.acquire("banque-france");

    try {
      const details: EnterpriseDetails = {
        basicInfo: {
          siren,
          name: "",
          status: "active"
        }
      };

      // Fetch financial statements if requested
      if (options.includeFinancials) {
        const [financialStatements, creditRating, paymentIncidents] = await Promise.all([
          this.getFinancialStatements(siren),
          this.getCreditRating(siren),
          this.getPaymentIncidents(siren)
        ]);

        if (financialStatements.length > 0) {
          const latestStatement = financialStatements[0];
          details.basicInfo.name = latestStatement.companyName || `Company ${siren}`;
          
          details.financials = {
            revenue: latestStatement.revenue,
            employees: latestStatement.employees,
            lastUpdate: latestStatement.year.toString()
          };

          // Add extended financial data to details
          (details as any).extendedFinancials = {
            statements: financialStatements,
            creditRating,
            paymentIncidents
          };
        }
      }
      
      // Cache the results for 1 hour
      await this.cache.set(cacheKey, details, 3600);
      
      return details;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(`Banque de France API error: ${error.response?.data?.message || error.message}`);
      }
      throw error;
    }
  }

  async getStatus(): Promise<AdapterStatus> {
    try {
      // Make a simple request to check API availability
      await axios.get(`${this.baseUrl}/health`, {
        headers: {
          "Authorization": `Bearer ${this.apiKey}`,
          "Accept": "application/json"
        }
      });

      return {
        available: true,
        rateLimit: await this.rateLimiter.getStatus("banque-france"),
        lastCheck: new Date()
      };
    } catch (error) {
      return {
        available: false,
        lastCheck: new Date()
      };
    }
  }

  private async getFinancialStatements(siren: string): Promise<any[]> {
    try {
      const response = await axios.get(`${this.baseUrl}/entreprises/bilans/${siren}/derniers`, {
        headers: {
          "Authorization": `Bearer ${this.apiKey}`,
          "Accept": "application/json"
        },
        params: {
          limit: 3 // Get last 3 annual statements
        }
      });

      return response.data.bilans || [];
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        return [];
      }
      throw error;
    }
  }

  private async getCreditRating(siren: string): Promise<BanqueFranceCreditRating | null> {
    try {
      const response = await axios.get(`${this.baseUrl}/entreprises/cotation/${siren}`, {
        headers: {
          "Authorization": `Bearer ${this.apiKey}`,
          "Accept": "application/json"
        }
      });

      const data = response.data;
      if (!data || !data.cotation) {
        return null;
      }

      return {
        rating: data.cotation,
        date: data.dateCotation,
        score: data.score,
        riskLevel: this.mapRatingToRiskLevel(data.cotation)
      };
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        return null;
      }
      throw error;
    }
  }

  private async getPaymentIncidents(siren: string): Promise<BanqueFrancePaymentIncident[]> {
    try {
      const response = await axios.get(`${this.baseUrl}/entreprises/incidents-paiement/${siren}`, {
        headers: {
          "Authorization": `Bearer ${this.apiKey}`,
          "Accept": "application/json"
        }
      });

      return response.data.incidents || [];
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        return [];
      }
      throw error;
    }
  }

  private transformSearchResults(data: any, siren: string): SearchResult[] {
    if (!data || !data.bilans || data.bilans.length === 0) {
      return [];
    }

    // Return a single search result based on the latest financial statement
    const latestBilan = data.bilans[0];
    
    return [{
      siren: siren,
      name: latestBilan.raisonSociale || `Company ${siren}`,
      legalForm: latestBilan.formeJuridique,
      address: this.formatAddress(latestBilan.adresse),
      activity: latestBilan.activitePrincipale,
      creationDate: latestBilan.dateCreation,
      status: latestBilan.situation || "active"
    }];
  }

  private formatAddress(address: any): string {
    if (!address) return "";
    
    if (typeof address === 'string') {
      return address;
    }
    
    const parts = [
      address.numero,
      address.voie,
      address.codePostal,
      address.ville
    ].filter(Boolean);
    
    return parts.join(" ");
  }

  private mapRatingToRiskLevel(rating: string): string {
    // Map Banque de France ratings to risk levels
    // Ratings typically go from 3++ (excellent) to 9 (payment incidents)
    const ratingMap: Record<string, string> = {
      "3++": "Excellent",
      "3+": "Very Good",
      "3": "Good",
      "4+": "Satisfactory",
      "4": "Fair",
      "5+": "Weak",
      "5": "Poor",
      "6": "Very Poor",
      "7": "Major Risk",
      "8": "Threatened",
      "9": "Payment Incidents"
    };
    
    return ratingMap[rating] || "Unknown";
  }
}